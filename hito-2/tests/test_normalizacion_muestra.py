"""Pruebas de normalización con fuentes sintéticas, sin acceso remoto."""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

HITO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HITO / "scripts"))

import normalizar_muestra as n
from validar_muestra import validar_tablas


def _tsv(filas):
    encabezado = "client_id\tpath\tsentence\tlocale\n"
    contenido = "".join(
        f"{cliente}\t{archivo}\t{texto}\tes-Rioplatense\n"
        for cliente, archivo, texto in filas
    )
    return (encabezado + contenido).encode("utf-8")


def _crear_cv(ruta, extras=(), repetido=False):
    entradas = {
        "es-Rioplatense/train.tsv": _tsv([
            ("persona1", "uno.mp3", "hola"),
        ]),
        "es-Rioplatense/test.tsv": _tsv([
            ("persona1", "uno.mp3" if repetido else "dos.mp3", "chau"),
        ]),
        "es-Rioplatense/clips/uno.mp3": b"mp3-1",
        "es-Rioplatense/clips/dos.mp3": b"mp3-2",
    }
    for archivo in extras:
        entradas[f"es-Rioplatense/clips/{archivo}"] = b"extra"

    with tarfile.open(ruta, "w:gz") as tar:
        for nombre, contenido in entradas.items():
            info = tarfile.TarInfo(nombre)
            info.size = len(contenido)
            tar.addfile(info, io.BytesIO(contenido))


class NormalizacionTest(unittest.TestCase):
    def test_cli_armar_muestra_modo_aislado(self):
        resultado = subprocess.run(
            [
                sys.executable,
                "-I",
                str(HITO / "scripts" / "armar_muestra.py"),
                "accion-invalida",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(resultado.returncode, 1, resultado.stderr)
        self.assertIn("Uso: armar_muestra.py [normalizado|", resultado.stderr)
        self.assertNotIn("Traceback", resultado.stderr)

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)
        self.muestra = self.raiz / "muestra"
        self.cache = self.raiz / ".cache"
        self.muestra.mkdir()
        self.cache.mkdir()
        (self.raiz / "fuentes.toml").write_text(
            '[common_voice]\narchivo="cv.tar.gz"\n',
            encoding="utf-8",
        )

    def test_common_voice_correspondencia_y_grupo_por_colaborador(self):
        ruta = self.raiz / "cv.tar.gz"
        _crear_cv(ruta)
        tablas, resumen = n.common_voice(ruta)

        self.assertEqual(resumen["clips"], 2)
        self.assertEqual(resumen["mp3"], 2)
        self.assertEqual(len(tablas["asr_hablantes"]), 1)
        self.assertEqual(
            {r["source_split"] for r in tablas["asr_instancias"]},
            {"train", "test"},
        )
        self.assertEqual(
            len({r["group_id"] for r in tablas["asr_instancias"]}), 1
        )
        self.assertEqual(
            {r["audio_status"] for r in tablas["asr_instancias"]},
            {"no_verificado"},
        )

    def test_common_voice_rechaza_clip_sobrante(self):
        ruta = self.raiz / "cv.tar.gz"
        _crear_cv(ruta, extras=["tres.mp3"])
        with self.assertRaisesRegex(ValueError, "biyectivos"):
            n.common_voice(ruta)

    def test_common_voice_rechaza_clip_repetido_entre_splits(self):
        ruta = self.raiz / "cv.tar.gz"
        _crear_cv(ruta, repetido=True)
        with self.assertRaisesRegex(ValueError, "repetido"):
            n.common_voice(ruta)

    def test_openslr_y_cordeba_conservan_referencias_y_anomalias(self):
        for directorio in ("slr61", "cordeba"):
            (self.muestra / directorio).mkdir()

        pd.DataFrame([{
            "archivo": "a", "genero": "female", "hablante": "s1",
            "texto": "Hola", "en_muestra_de_audio": False,
        }]).to_csv(self.muestra / "slr61/transcripciones.csv", index=False)
        pd.DataFrame([{
            "archivo": "a", "bytes": 123, "legible": True, "duracion_s": 2.0,
        }]).to_csv(self.muestra / "slr61/manifiesto_audio.csv", index=False)
        pd.DataFrame([{
            "archivo": "c.wma", "legible": False, "duracion_s": "",
        }]).to_csv(self.muestra / "cordeba/grabaciones.csv", index=False)

        turnos = pd.DataFrame([{
            "archivo": "c.wma", "orden": 0, "hablante": "1", "texto": "qué tal",
        }])
        with patch.object(n.pd, "read_parquet", return_value=turnos):
            cordeba, _ = n.cordeba(self.muestra)
        slr61, _ = n.slr61(self.muestra)

        self.assertEqual(slr61["asr_instancias"][0]["audio_status"], "valido")
        self.assertEqual(cordeba["asr_instancias"][0]["audio_status"], "ilegible")
        self.assertEqual(cordeba["asr_instancias"][0]["reference_raw"], "qué tal")
        self.assertIsNone(cordeba["asr_instancias"][0]["duration_s"])

    def test_figshare_silencio_y_hablantes_por_sesion(self):
        raiz = self.muestra / "uba_games_figshare"
        raiz.mkdir()
        pd.DataFrame([{
            "recording_id": "r1", "session_id": "S21",
            "group_id": "S21", "duracion_s": 3.0,
        }]).to_csv(raiz / "grabaciones.csv", index=False)
        pd.DataFrame([
            {"session_id": "S21", "speaker_id": "sp1", "canal": 1},
            {"session_id": "S21", "speaker_id": "sp2", "canal": 2},
        ]).to_csv(raiz / "hablantes.csv", index=False)
        intervalos = pd.DataFrame([
            {
                "recording_id": "r1", "speaker_id": "sp1", "inicio_s": 0,
                "fin_s": 1, "texto_original": "#", "silencio_marcado": True,
                "origen_anotacion": "a",
            },
            {
                "recording_id": "r1", "speaker_id": "sp1", "inicio_s": 1,
                "fin_s": 2, "texto_original": "hola", "silencio_marcado": False,
                "origen_anotacion": "a",
            },
            {
                "recording_id": "r1", "speaker_id": "sp2", "inicio_s": 1.5,
                "fin_s": 2.5, "texto_original": "chau", "silencio_marcado": False,
                "origen_anotacion": "b",
            },
        ])
        with patch.object(n.pd, "read_parquet", return_value=intervalos):
            tablas, resumen = n.figshare(self.muestra)

        self.assertEqual(resumen["intervalos"], 3)
        self.assertIsNone(tablas["diarizacion_segmentos"][0]["speaker_id"])
        self.assertIsNone(tablas["diarizacion_segmentos"][1]["scored_as_speech"])
        self.assertEqual(len(tablas["diarizacion_hablantes"]), 2)
        self.assertEqual(
            validar_tablas(
                {nombre: n._tabla(nombre, filas) for nombre, filas in tablas.items()},
                "diarizacion",
            ),
            [],
        )

    def test_callhome_no_inventa_sesion_ni_fusiona_A_A1(self):
        carpeta = self.cache / "callhome"
        carpeta.mkdir()
        (carpeta / "data-00000-of-00005.parquet").write_bytes(b"synthetic")

        class Lote:
            def to_pylist(self):
                return [{
                    "audio": {"bytes": b"audio", "path": None},
                    "timestamps_start": [0.0, 0.5],
                    "timestamps_end": [0.6, 1.0],
                    "speakers": ["A", "A1"],
                }]

        class Parquet:
            schema_arrow = types.SimpleNamespace(names=[
                "audio", "timestamps_start", "timestamps_end", "speakers",
            ])

            def __init__(self, _ruta):
                pass

            def iter_batches(self, batch_size=1):
                yield Lote()

        paquete = types.ModuleType("pyarrow")
        paquete.__path__ = []
        modulo = types.ModuleType("pyarrow.parquet")
        modulo.ParquetFile = Parquet
        paquete.parquet = modulo

        with patch.dict(sys.modules, {
            "pyarrow": paquete,
            "pyarrow.parquet": modulo,
        }):
            tablas, resumen = n.callhome(self.cache)

        self.assertEqual(resumen["registros"], 1)
        hablantes = tablas["diarizacion_hablantes"]
        self.assertEqual(len(hablantes), 2)
        self.assertNotEqual(hablantes[0]["speaker_id"], hablantes[1]["speaker_id"])
        self.assertIsNone(tablas["diarizacion_grabaciones"][0]["session_id"])
        self.assertIsNone(tablas["diarizacion_grabaciones"][0]["duration_s"])

    def test_callhome_conserva_anomalias_sin_inventar_tiempos(self):
        carpeta = self.cache / "callhome"
        carpeta.mkdir()
        (carpeta / "data-00000-of-00005.parquet").write_bytes(b"synthetic")

        class Lote:
            def to_pylist(self):
                return [{
                    "audio": {"bytes": b"audio", "path": None},
                    "timestamps_start": [0.0, 342.684, 0.4, 348.964],
                    "timestamps_end": [0.5, -56.71, 0.7, -48.89],
                    "speakers": ["A", "B2", "A1", "A"],
                }]

        class Parquet:
            schema_arrow = types.SimpleNamespace(names=[
                "audio", "timestamps_start", "timestamps_end", "speakers",
            ])

            def __init__(self, _ruta):
                pass

            def iter_batches(self, batch_size=1):
                yield Lote()

        paquete = types.ModuleType("pyarrow")
        paquete.__path__ = []
        modulo = types.ModuleType("pyarrow.parquet")
        modulo.ParquetFile = Parquet
        paquete.parquet = modulo
        with patch.dict(sys.modules, {
            "pyarrow": paquete, "pyarrow.parquet": modulo,
        }):
            tablas, resumen = n.callhome(self.cache)

        self.assertEqual(resumen["registros"], 1)
        self.assertEqual(resumen["intervalos_originales"], 4)
        self.assertEqual(resumen["intervalos"], 2)
        self.assertEqual(resumen["intervalos_invalidos"], 2)
        self.assertEqual(
            [(a["fila"], a["indice_intervalo"], a["etiqueta_hablante"])
             for a in resumen["_anomalias"]],
            [(0, 1, "B2"), (0, 3, "A")],
        )
        self.assertEqual(resumen["_anomalias"][0]["fin_s"], -56.71)
        self.assertEqual(len(tablas["diarizacion_grabaciones"]), 1)
        self.assertEqual(len(tablas["diarizacion_segmentos"]), 2)
        self.assertEqual(len(tablas["diarizacion_hablantes"]), 2)
        self.assertIsNone(tablas["diarizacion_grabaciones"][0]["duration_s"])
        self.assertEqual(
            validar_tablas({nombre: n._tabla(nombre, filas)
                            for nombre, filas in tablas.items()}, "diarizacion"),
            [],
        )

    def test_callhome_rechaza_corrupcion_estructural(self):
        carpeta = self.cache / "callhome"
        carpeta.mkdir()
        (carpeta / "data-00000-of-00005.parquet").write_bytes(b"synthetic")

        class Lote:
            def to_pylist(self):
                return [{
                    "audio": {"bytes": b"audio", "path": None},
                    "timestamps_start": [0.0],
                    "timestamps_end": [],
                    "speakers": ["A"],
                }]

        class Parquet:
            schema_arrow = types.SimpleNamespace(names=[
                "audio", "timestamps_start", "timestamps_end", "speakers",
            ])

            def __init__(self, _ruta):
                pass

            def iter_batches(self, batch_size=1):
                yield Lote()

        paquete = types.ModuleType("pyarrow")
        paquete.__path__ = []
        modulo = types.ModuleType("pyarrow.parquet")
        modulo.ParquetFile = Parquet
        paquete.parquet = modulo
        with patch.dict(sys.modules, {
            "pyarrow": paquete, "pyarrow.parquet": modulo,
        }):
            with self.assertRaisesRegex(ValueError, "listas desalineadas"):
                n.callhome(self.cache)

    def test_publicacion_cinco_fuentes_con_anomalias_y_hash(self):
        fuentes = {}
        for source in ("common_voice", "slr61", "cordeba"):
            tablas = n._filas_asr()
            tablas["asr_instancias"].append(dict(
                source=source, recording_id=f"{source}-r",
                source_recording_id=f"{source}-r", session_id=None,
                group_id=None, speaker_id=None, duration_s=None,
                audio_ref=f"{source}:r", audio_status="no_verificado",
                reference_raw="hola", reference_norm=None,
                reference_origin="original", reference_scope="recording",
                language="es-AR", source_split=None, project_split=None,
            ))
            fuentes[source] = (tablas, {"registros": 1})

        fig = n._filas_dia()
        fig["diarizacion_grabaciones"].append(dict(
            source="uba_games_figshare", recording_id="f1",
            source_recording_id="f1", session_id="s1", group_id="s1",
            duration_s=1.0, audio_ref="figshare:f1",
            audio_status="no_verificado", reference_origin="phrases.rar",
            source_split=None, project_split=None,
        ))
        fig["diarizacion_hablantes"].append(dict(
            source="uba_games_figshare", speaker_id="f-sp",
            source_speaker_id="channel1", speaker_scope="session",
            session_id="s1", recording_id=None,
        ))
        fig["diarizacion_segmentos"].append(dict(
            source="uba_games_figshare", recording_id="f1", speaker_id="f-sp",
            start_s=0.0, end_s=1.009, annotation_raw="hola",
            is_silence_marker=False, scored_as_speech=None,
            reference_origin="phrases.rar",
        ))
        fuentes["uba_games_figshare"] = (fig, {"grabaciones": 1})

        ch = n._filas_dia()
        ch["diarizacion_grabaciones"].append(dict(
            source="callhome", recording_id="c1",
            source_recording_id="c1", session_id=None, group_id=None,
            duration_s=None, audio_ref="callhome:c1",
            audio_status="no_verificado", reference_origin="c1",
            source_split=None, project_split=None,
        ))
        ch["diarizacion_hablantes"].append(dict(
            source="callhome", speaker_id="c1:A",
            source_speaker_id="A", speaker_scope="recording",
            session_id=None, recording_id="c1",
        ))
        ch["diarizacion_segmentos"].append(dict(
            source="callhome", recording_id="c1", speaker_id="c1:A",
            start_s=0.0, end_s=1.0, annotation_raw=None,
            is_silence_marker=None, scored_as_speech=None,
            reference_origin="c1",
        ))
        fuentes["callhome"] = (ch, {
            "registros": 1, "intervalos": 1,
            "intervalos_originales": 2, "intervalos_invalidos": 1,
            "_anomalias": [{
                "archivo": "data-00000-of-00005.parquet", "fila": 0,
                "indice_intervalo": 1, "recording_id": "c1",
                "inicio_s": 342.684, "fin_s": -56.71,
                "etiqueta_hablante": "B2",
                "motivo": "intervalo_temporal_invalido",
            }],
        })
        adaptadores = {"uba_games_figshare": "figshare"}
        patches = [patch.object(
            n, adaptadores.get(key, key), return_value=value
        ) for key, value in fuentes.items()]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        destino = self.muestra / "normalizado"
        with patch.object(
            pd.DataFrame, "to_parquet",
            lambda df, ruta, **kw: df.to_pickle(ruta),
        ), patch.object(n.pd, "read_parquet", side_effect=pd.read_pickle):
            resultado = n.materializar(self.muestra, self.cache, destino)

        self.assertEqual(len(resultado["tablas"]), 5)
        self.assertEqual(resultado["fuentes"]["callhome"]["intervalos_invalidos"], 1)
        report = resultado["reportes_anomalias"]["callhome"]
        ruta = destino / report["archivo"]
        self.assertTrue(ruta.is_file())
        self.assertEqual(report["sha256"], hashlib.sha256(ruta.read_bytes()).hexdigest())
        self.assertEqual(report["cantidad"], 1)
        self.assertEqual(json.loads(ruta.read_text())["anomalias"][0]["etiqueta_hablante"], "B2")
        self.assertNotIn("B2", json.dumps(resultado))
        self.assertEqual(len(list(destino.glob("*.parquet"))), 2)
        self.assertEqual(len(list(destino.glob("*.csv"))), 3)

    def test_normalizacion_valida_publica_tablas_y_manifiesto(self):
        salida = self.muestra / "normalizado"
        salida.mkdir()
        (salida / "antiguo.txt").write_text("obsolete", encoding="utf-8")
        tablas = n._filas_asr()
        tablas["asr_instancias"].append({
            "source": "common_voice", "recording_id": "a.mp3",
            "source_recording_id": "a.mp3", "session_id": None,
            "group_id": "c1", "speaker_id": "c1", "duration_s": None,
            "audio_ref": "common_voice:TAR#a.mp3",
            "audio_status": "no_verificado", "reference_raw": "hola",
            "reference_norm": None, "reference_origin": "train.tsv",
            "reference_scope": "recording", "language": "es-Rioplatense",
            "source_split": "train", "project_split": None,
        })
        tablas["asr_hablantes"].append({
            "source": "common_voice", "speaker_id": "c1",
            "source_speaker_id": "c1", "speaker_scope": "source",
            "session_id": None, "recording_id": None,
        })

        # El contrato de CSV/Parquet real se prueba por separado.
        # Aquí se comprueba la publicación del directorio y su manifiesto.
        with patch.object(
            n, "common_voice", return_value=(tablas, {"clips": 1})
        ), patch.object(
            pd.DataFrame, "to_parquet",
            lambda df, ruta, **kw: df.to_pickle(ruta),
        ), patch.object(
            n.pd, "read_parquet", side_effect=pd.read_pickle,
        ):
            manifiesto = n.materializar(
                self.muestra, self.cache, salida, ("common_voice",)
            )

        self.assertEqual(manifiesto["tablas"]["asr_instancias"]["filas"], 1)
        self.assertTrue((salida / "MANIFIESTO_NORMALIZADO.json").is_file())
        self.assertFalse((salida / "antiguo.txt").exists())

    def test_normalizacion_invalida_no_sobrescribe_resultado_anterior(self):
        destino = self.muestra / "normalizado"
        destino.mkdir()
        (destino / "conservado.txt").write_text("original", encoding="utf-8")

        def cv(_ruta):
            tablas = n._filas_asr()
            tablas["asr_instancias"].append({
                "source": "cv", "recording_id": "r", "source_recording_id": "r",
                "audio_status": "valido", "reference_scope": "recording",
            })
            return tablas, {"n": 1}

        with patch.object(n, "common_voice", side_effect=cv):
            with self.assertRaisesRegex(ValueError, "inválida"):
                n.materializar(
                    self.muestra, self.cache, destino, ("common_voice",)
                )

        self.assertEqual(
            (destino / "conservado.txt").read_text(encoding="utf-8"),
            "original",
        )


if __name__ == "__main__":
    unittest.main()