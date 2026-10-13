"""Pruebas de la fase B: audio real pequeño y contrato integrado sintético."""
from __future__ import annotations

import io
import json
import sys
import tarfile
import tempfile
import types
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import pandas as pd

HITO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HITO / "scripts"))

import auditar_aptitud as b


def wav_bytes() -> bytes:
    salida = io.BytesIO()
    with wave.open(salida, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 16000)
    return salida.getvalue()


class AptitudAcusticaTest(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.hito = Path(temporal.name)
        self.cache = self.hito / ".cache"
        self.muestra = self.hito / "muestra"
        (self.muestra / "normalizado").mkdir(parents=True)

    def test_cli_modo_aislado_sin_acceso_a_originales(self):
        import subprocess

        r = subprocess.run(
            [
                sys.executable,
                "-I",
                str(HITO / "scripts" / "auditar_aptitud.py"),
                "--help",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("auditar_aptitud.py", r.stdout)

    def test_seleccion_determinista_y_sin_reemplazo(self):
        ids = [f"grab-{i:02d}" for i in range(20)]
        a = b.seleccionar(ids, 6, "grupo1")

        self.assertEqual(
            a,
            b.seleccionar(list(reversed(ids)), 6, "grupo1"),
        )
        self.assertEqual(len(set(a)), 6)
        self.assertNotEqual(
            a,
            b.seleccionar(ids, 6, "grupo2"),
        )

        with self.assertRaisesRegex(ValueError, "repetidos"):
            b.seleccionar(["a", "a"], 1, "grupo")

    def test_decodificacion_hasta_fin_y_audio_invalido(self):
        bueno = self.hito / "bueno.wav"
        malo = self.hito / "malo.wav"
        bueno.write_bytes(wav_bytes())
        malo.write_bytes(b"no hay audio")

        aceptado = b.construir_fila(
            "prueba", "a", "original",
            bueno, esperado=1.0, ultimo=1.2,
        )

        self.assertEqual(
            aceptado["estado"], "decodificable"
        )
        self.assertEqual(
            aceptado["frecuencia_hz"], 16000
        )
        self.assertEqual(
            aceptado["canales"], 1
        )
        self.assertAlmostEqual(
            aceptado["diferencia_duracion_s"], 0
        )
        self.assertAlmostEqual(
            aceptado["exceso_anotacion_s"], 0.2
        )
        self.assertEqual(
            b.construir_fila(
                "prueba", "b", "original", malo
            )["estado"],
            "no_decodificable",
        )
        self.assertEqual(
            b.construir_fila(
                "prueba", "c", "original", None
            )["estado"],
            "ausente",
        )

    def test_hash_de_normalizacion_incorrecto_no_se_acepta(self):
        archivos = self.muestra / "normalizado"

        (archivos / "MANIFIESTO_NORMALIZADO.json").write_text(
            json.dumps({
                "estado": "validado_estructuralmente_no_evaluado",
                "tablas": {
                    nombre: {
                        "sha256": "0" * 64,
                        "filas": 1,
                    }
                    for nombre in b.TABLAS
                },
            })
        )
        (archivos / "asr_instancias.parquet").write_bytes(
            b"contenido"
        )

        with self.assertRaisesRegex(ValueError, "SHA-256"):
            b._verificar_normalizado(archivos)

    def test_auditoria_integrada_publica_datos_no_sensibles(self):
        import csv
        import hashlib

        (self.hito / "fuentes.toml").write_text(
            '[common_voice]\narchivo="cv.tar.gz"\n',
            encoding="utf-8",
        )

        cv_root = self.cache / "common_voice"
        cv_root.mkdir(parents=True)

        with tarfile.open(cv_root / "cv.tar.gz", "w:gz") as tar:
            for nombre in ("train", "dev", "test"):
                archivo = f"cv-corpus/clips/{nombre}.mp3"
                dato = b"audiosintetico"
                info = tarfile.TarInfo(archivo)
                info.size = len(dato)
                tar.addfile(info, io.BytesIO(dato))

        filas_asr = [
            dict(
                source="common_voice",
                recording_id=f"{s}.mp3",
                source_split=s,
                audio_status="no_verificado",
                duration_s=None,
            )
            for s in ("train", "dev", "test")
        ]
        filas_asr += [
            dict(
                source="slr61",
                recording_id="slr1",
                source_split=None,
                audio_status="valido",
                duration_s=1.0,
            )
        ]
        filas_asr += [
            dict(
                source="cordeba",
                recording_id="cord1.mp3",
                source_split=None,
                audio_status="ilegible",
                duration_s=1.0,
            )
        ]

        (self.muestra / "slr61" / "clips").mkdir(
            parents=True
        )
        pd.DataFrame({
            "archivo": ["slr1"],
            "en_muestra_de_audio": [True],
        }).to_csv(
            self.muestra / "slr61" / "transcripciones.csv",
            index=False,
        )
        (
            self.muestra / "slr61" / "clips" / "slr1.flac"
        ).write_bytes(wav_bytes())

        (self.cache / "cordeba").mkdir()
        (
            self.cache / "cordeba" / "cord1.mp3"
        ).write_bytes(b"mp3")

        (
            self.muestra / "uba_games_figshare" / "audio_muestra"
        ).mkdir(parents=True)

        pd.DataFrame([
            dict(
                recording_id="fig1",
                archivo="audio_muestra/f1.flac",
                duracion_s=1.0,
            )
        ]).to_csv(
            self.muestra / "uba_games_figshare" / "extractos.csv",
            index=False,
        )

        (
            self.muestra
            / "uba_games_figshare"
            / "audio_muestra"
            / "f1.flac"
        ).write_bytes(wav_bytes())

        ch_root = self.cache / "callhome"
        ch_root.mkdir()
        shards = {}

        for shard in range(5):
            ruta = (
                ch_root
                / f"data-{shard:05d}-of-00005.parquet"
            )
            ruta.write_bytes(b"parquet-sintetico")
            shards[ruta.name] = [
                dict(audio={
                    "bytes": wav_bytes(),
                    "path": None,
                })
                for _ in range(4)
            ]

        ch_ids = [
            f"{Path(nombre).stem}:row{i:04d}"
            for nombre in shards
            for i in range(4)
        ]
        df_dia = pd.DataFrame([
            {
                "source": "uba_games_figshare",
                "recording_id": "fig1",
            },
            *(
                {
                    "source": "callhome",
                    "recording_id": ident,
                }
                for ident in ch_ids
            ),
        ])
        df_seg = pd.DataFrame([
            {
                "source": "callhome",
                "recording_id": ident,
                "end_s": 0.5,
            }
            for ident in ch_ids
        ])

        tablas = {
            "asr_instancias": pd.DataFrame(filas_asr),
            "asr_hablantes": pd.DataFrame(),
            "diarizacion_grabaciones": df_dia,
            "diarizacion_segmentos": df_seg,
            "diarizacion_hablantes": pd.DataFrame(),
        }
        manifest = {
            "tablas": {
                nombre: {
                    "sha256": hashlib.sha256(
                        nombre.encode()
                    ).hexdigest(),
                }
                for nombre in b.TABLAS
            }
        }

        class Parquet:
            def __init__(self, ruta):
                self.rows = shards[Path(ruta).name]
                self.metadata = types.SimpleNamespace(
                    num_rows=len(self.rows)
                )

            def iter_batches(self, batch_size=1, columns=None):
                for row in self.rows:
                    yield types.SimpleNamespace(
                        to_pylist=lambda r=row: [r]
                    )

        paquete = types.ModuleType("pyarrow")
        paquete.__path__ = []
        modulo = types.ModuleType("pyarrow.parquet")
        modulo.ParquetFile = Parquet
        paquete.parquet = modulo

        def verificar(path):
            return manifest, tablas

        def revisar(path, timeout=120):
            return {
                "estado": "decodificable",
                "motivo": "",
                "duracion_observada_s": 1.0,
                "frecuencia_hz": 16000,
                "canales": 1,
            }

        with (
            patch.object(
                b, "_verificar_normalizado",
                side_effect=verificar,
            ),
            patch.object(
                b, "revisar_audio",
                side_effect=revisar,
            ),
            patch.dict(
                sys.modules,
                {
                    "pyarrow": paquete,
                    "pyarrow.parquet": modulo,
                },
            ),
        ):
            reporte = b.auditar(self.hito)
            reporte2 = b.auditar(self.hito)

        self.assertEqual(reporte, reporte2)
        self.assertEqual(
            reporte["resumen"]["common_voice"]["audios_inspeccionados"],
            3,
        )
        self.assertEqual(
            reporte["resumen"]["slr61"]["decodificables"],
            1,
        )
        self.assertEqual(
            reporte["resumen"]["callhome"]["audios_inspeccionados"],
            15,
        )
        self.assertEqual(
            reporte["resumen"]["uba_games_figshare"]["audios_inspeccionados"],
            1,
        )

        destino = self.muestra / "normalizado" / "aptitud"
        with (destino / "RESULTADOS_B.csv").open(
            encoding="utf-8", newline=""
        ) as f:
            filas = list(csv.DictReader(f))

        self.assertEqual(len(filas), 21)
        self.assertEqual(
            {
                fila["particion_original"]
                for fila in filas
                if fila["fuente"] == "common_voice"
            },
            {"train", "dev", "test"},
        )

        informe = (
            destino / "INFORME_B.json"
        ).read_text(encoding="utf-8")

        self.assertNotIn(
            "audiosintetico", informe
        )
        self.assertNotIn(
            "audiosintetico",
            (destino / "RESULTADOS_B.csv").read_text(),
        )


if __name__ == "__main__":
    unittest.main()