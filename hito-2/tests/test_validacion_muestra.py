"""Contratos normalizados con tablas sintéticas, sin red ni corpus auténtico."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validar_muestra",
    BASE / "scripts" / "validar_muestra.py",
)
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)


def tabla(nombre, registros):
    return pd.DataFrame(registros, columns=v.COLUMNAS[nombre])


def caso_base():
    asr = tabla("asr_instancias", [dict(
        source="cv",
        recording_id="r1",
        source_recording_id="original1",
        session_id=None,
        group_id="g1",
        speaker_id="s1",
        duration_s=3.0,
        audio_ref="cv/r1.flac",
        audio_status="valido",
        reference_raw="Hola",
        reference_norm=None,
        reference_origin="metadata.tsv",
        reference_scope="recording",
        language="es-AR",
        source_split="train",
        project_split=None,
    )])

    ash = tabla("asr_hablantes", [dict(
        source="cv",
        speaker_id="s1",
        source_speaker_id=None,
        speaker_scope="recording",
        session_id=None,
        recording_id="r1",
    )])

    dgr = tabla("diarizacion_grabaciones", [
        dict(
            source="uba",
            recording_id="r1",
            source_recording_id="S21_1",
            session_id="S21",
            group_id="g21",
            duration_s=3.0,
            audio_ref="uba/r1.flac",
            audio_status="valido",
            reference_origin="phrases.rar",
            source_split=None,
            project_split=None,
        ),
        dict(
            source="uba",
            recording_id="r2",
            source_recording_id="S21_2",
            session_id="S21",
            group_id="g21",
            duration_s=3.0,
            audio_ref="uba/r2.flac",
            audio_status="valido",
            reference_origin="phrases.rar",
            source_split=None,
            project_split=None,
        ),
    ])

    dse = tabla("diarizacion_segmentos", [
        dict(
            source="uba",
            recording_id="r1",
            speaker_id="sp1",
            start_s=0.0,
            end_s=1.5,
            annotation_raw="hola",
            is_silence_marker=False,
            scored_as_speech=None,
            reference_origin="phrases1",
        ),
        dict(
            source="uba",
            recording_id="r1",
            speaker_id="sp2",
            start_s=1.0,
            end_s=2.0,
            annotation_raw="chau",
            is_silence_marker=False,
            scored_as_speech=None,
            reference_origin="phrases2",
        ),
        dict(
            source="uba",
            recording_id="r2",
            speaker_id=None,
            start_s=2.0,
            end_s=2.9,
            annotation_raw="#",
            is_silence_marker=True,
            scored_as_speech=False,
            reference_origin="phrases2",
        ),
    ])

    dh = tabla("diarizacion_hablantes", [
        dict(
            source="uba",
            speaker_id="sp1",
            source_speaker_id="channel1",
            speaker_scope="session",
            session_id="S21",
            recording_id=None,
        ),
        dict(
            source="uba",
            speaker_id="sp2",
            source_speaker_id="channel2",
            speaker_scope="session",
            session_id="S21",
            recording_id=None,
        ),
    ])

    return dict(zip(v.ARCHIVOS, [asr, ash, dgr, dse, dh]))


def codigos(issues):
    return {issue["codigo"] for issue in issues}


class ContratoMuestraTest(unittest.TestCase):

    def test_tolerancia_terminal_solo_figshare(self):
        datos = caso_base()
        datos["diarizacion_grabaciones"].loc[0, "source"] = "uba_games_figshare"
        datos["diarizacion_segmentos"].loc[0, "source"] = "uba_games_figshare"
        datos["diarizacion_segmentos"].loc[1, "source"] = "uba_games_figshare"
        datos["diarizacion_hablantes"].loc[:, "source"] = "uba_games_figshare"
        datos["diarizacion_segmentos"].loc[0, "end_s"] = 3.009
        self.assertEqual(v.validar_tablas(datos), [])
        datos["diarizacion_segmentos"].loc[0, "end_s"] = 3.011
        self.assertIn("intervalo_invalido", codigos(v.validar_tablas(datos)))
        datos["diarizacion_segmentos"].loc[0, "source"] = "uba"
        datos["diarizacion_grabaciones"].loc[0, "source"] = "uba"
        datos["diarizacion_segmentos"].loc[1, "source"] = "uba"
        datos["diarizacion_hablantes"].loc[:, "source"] = "uba"
        datos["diarizacion_segmentos"].loc[0, "end_s"] = 3.009
        self.assertIn("intervalo_invalido", codigos(v.validar_tablas(datos)))

    def test_base_valida_con_nulos_y_habla_simultanea(self):
        self.assertEqual(
            v.validar_tablas(caso_base()), []
        )

    def test_componentes_independientes(self):
        datos = caso_base()

        asr = {
            k: datos[k]
            for k in ("asr_instancias", "asr_hablantes")
        }
        dia = {
            k: datos[k]
            for k in (
                "diarizacion_grabaciones",
                "diarizacion_segmentos",
                "diarizacion_hablantes",
            )
        }

        self.assertEqual(v.validar_tablas(asr, "asr"), [])
        self.assertEqual(
            v.validar_tablas(dia, "diarizacion"), []
        )
        self.assertIn(
            "tabla_ausente",
            codigos(v.validar_tablas({}, "asr")),
        )

    def test_columnas_faltantes_y_tabla_vacia(self):
        datos = caso_base()
        datos["asr_instancias"] = datos[
            "asr_instancias"
        ].drop(columns=["audio_status"])

        self.assertIn(
            "columnas_ausentes",
            codigos(v.validar_tablas(datos)),
        )

        datos = caso_base()
        datos["asr_instancias"] = datos[
            "asr_instancias"
        ].iloc[0:0]

        self.assertIn(
            "tabla_vacia",
            codigos(v.validar_tablas(datos)),
        )

    def test_claves_duplicadas(self):
        datos = caso_base()
        datos["asr_instancias"] = pd.concat(
            [datos["asr_instancias"]] * 2,
            ignore_index=True,
        )
        self.assertIn(
            "clave_duplicada",
            codigos(v.validar_tablas(datos)),
        )

    def test_tipos_y_categorias_invalidas(self):
        datos = caso_base()
        datos["asr_instancias"].loc[
            0, "audio_status"
        ] = "no existe"

        datos["diarizacion_segmentos"].loc[
            0, "start_s"
        ] = np.inf

        datos["diarizacion_segmentos"][
            "is_silence_marker"
        ] = datos["diarizacion_segmentos"][
            "is_silence_marker"
        ].astype(object)

        datos["diarizacion_segmentos"].loc[
            1, "is_silence_marker"
        ] = "False"

        self.assertIn(
            "campo_invalido",
            codigos(v.validar_tablas(datos)),
        )

    def test_audio_valido_exige_audio_y_duracion(self):
        datos = caso_base()
        datos["asr_instancias"].loc[
            0, "audio_ref"
        ] = None
        datos["asr_instancias"].loc[
            0, "duration_s"
        ] = -1

        issues = codigos(v.validar_tablas(datos))

        self.assertIn("audio_valido_sin_soporte", issues)
        self.assertIn("duracion_no_positiva", issues)

    def test_normalizacion_sin_texto_original(self):
        datos = caso_base()
        datos["asr_instancias"].loc[
            0, "reference_raw"
        ] = None
        datos["asr_instancias"].loc[
            0, "reference_norm"
        ] = "hola"

        self.assertIn(
            "normalizacion_sin_original",
            codigos(v.validar_tablas(datos)),
        )

    def test_segmento_fuera_de_grabacion_o_invalido(self):
        datos = caso_base()
        datos["diarizacion_segmentos"].loc[
            0, "end_s"
        ] = 3.5
        datos["diarizacion_segmentos"].loc[
            1, "start_s"
        ] = 2.5
        datos["diarizacion_segmentos"].loc[
            2, "recording_id"
        ] = "perdida"

        issues = codigos(v.validar_tablas(datos))

        self.assertIn("intervalo_invalido", issues)
        self.assertIn("grabacion_inexistente", issues)

    def test_hablante_ajeno_y_ambito(self):
        datos = caso_base()
        datos["diarizacion_segmentos"].loc[
            1, "speaker_id"
        ] = "desconocido"

        self.assertIn(
            "hablante_inexistente",
            codigos(v.validar_tablas(datos)),
        )

        datos = caso_base()
        datos["diarizacion_hablantes"].loc[
            0, "session_id"
        ] = "S99"

        self.assertIn(
            "ambito_hablante_incompatible",
            codigos(v.validar_tablas(datos)),
        )

        datos = caso_base()
        datos["asr_hablantes"].loc[
            0, "recording_id"
        ] = None

        self.assertIn(
            "ambito_hablante_incompleto",
            codigos(v.validar_tablas(datos)),
        )

    def test_silencio_y_habla_sin_hablante(self):
        datos = caso_base()
        datos["diarizacion_segmentos"].loc[
            2, "scored_as_speech"
        ] = True

        issues = codigos(v.validar_tablas(datos))

        self.assertIn(
            "silencio_puntuado_como_habla", issues
        )
        self.assertIn("habla_sin_hablante", issues)

    def test_solapamiento_entre_hablantes_valido_pero_evento_duplicado_no(self):
        datos = caso_base()
        segmentos = datos["diarizacion_segmentos"]
        datos["diarizacion_segmentos"] = pd.concat(
            [segmentos, segmentos.iloc[[0]]],
            ignore_index=True,
        )

        self.assertIn(
            "segmento_duplicado",
            codigos(v.validar_tablas(datos)),
        )

    def test_misma_sesion_grupos_distintos(self):
        datos = caso_base()
        datos["diarizacion_grabaciones"].loc[
            1, "group_id"
        ] = "otro"

        self.assertIn(
            "sesion_en_grupos_distintos",
            codigos(v.validar_tablas(datos)),
        )

    def test_mismo_grupo_en_particiones_distintas(self):
        datos = caso_base()
        datos["diarizacion_grabaciones"].loc[
            0, "project_split"
        ] = "train"
        datos["diarizacion_grabaciones"].loc[
            1, "project_split"
        ] = "test"

        self.assertIn(
            "grupo_en_distintas_particiones",
            codigos(v.validar_tablas(datos)),
        )

    def test_hablantes_desconocidos_no_exigen_filas_inventadas(self):
        datos = caso_base()
        datos["asr_instancias"].loc[
            0, "speaker_id"
        ] = None
        datos["asr_hablantes"] = datos[
            "asr_hablantes"
        ].iloc[0:0]

        self.assertEqual(v.validar_tablas(datos), [])

    def test_bool_numpy_es_interpretado_como_bool(self):
        datos = caso_base()
        datos["diarizacion_segmentos"][
            "scored_as_speech"
        ] = datos["diarizacion_segmentos"][
            "scored_as_speech"
        ].astype(object)

        datos["diarizacion_segmentos"].at[
            2, "scored_as_speech"
        ] = np.bool_(True)

        self.assertIn(
            "silencio_puntuado_como_habla",
            codigos(v.validar_tablas(datos)),
        )

    def test_na_literal_en_id_no_se_confunde_con_valor_nulo(self):
        with tempfile.TemporaryDirectory() as t:
            carpeta = Path(t)
            datos = caso_base()
            datos["asr_hablantes"].loc[
                0, "speaker_id"
            ] = "NA"

            datos["asr_hablantes"].to_csv(
                carpeta / "asr_hablantes.csv",
                index=False,
            )

            leidas, fallos = v.cargar(carpeta, "asr")
            self.assertFalse(fallos)
            self.assertEqual(
                leidas["asr_hablantes"].at[0, "speaker_id"],
                "NA",
            )

    def test_particion_fijada_sin_grupo_no_se_acepta(self):
        datos = caso_base()
        datos["asr_instancias"].loc[
            0, "project_split"
        ] = "eval"
        datos["asr_instancias"].loc[
            0, "group_id"
        ] = None

        self.assertIn(
            "particion_sin_grupo",
            codigos(v.validar_tablas(datos)),
        )

    def test_grabacion_multimodal_con_identidad_contradictoria(self):
        datos = caso_base()
        datos["asr_instancias"].loc[
            0, "source"
        ] = "uba"
        datos["asr_instancias"].loc[
            0, "session_id"
        ] = "S99"
        datos["asr_hablantes"].loc[
            0, "source"
        ] = "uba"
        datos["asr_instancias"].loc[
            0, "group_id"
        ] = "otro"

        self.assertIn(
            "identidad_multimodal_incompatible",
            codigos(v.validar_tablas(datos)),
        )

    def test_no_imputa_ni_muta_entradas(self):
        datos = caso_base()
        antes = {
            k: df.copy(deep=True)
            for k, df in datos.items()
        }

        v.validar_tablas(datos)

        for k in datos:
            pd.testing.assert_frame_equal(
                datos[k], antes[k]
            )

    def test_cli_falla_sin_tablas_y_informe_json(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            destino = root / "out.json"

            self.assertEqual(
                v.main([
                    "--raiz", str(root),
                    "--componente", "asr",
                    "--informe", str(destino),
                ]),
                1,
            )

            registro = json.loads(
                destino.read_text()
            )
            self.assertEqual(
                registro["estado"], "ERROR"
            )
            self.assertEqual(
                {
                    x["codigo"]
                    for x in registro["errores"]
                },
                {"tabla_ausente"},
            )

    def test_intervalo_sin_duracion_no_inventa_limites(self):
        datos = caso_base()
        datos["diarizacion_grabaciones"].loc[
            0, "audio_status"
        ] = "no_verificado"
        datos["diarizacion_grabaciones"].loc[
            0, "duration_s"
        ] = None

        self.assertEqual(v.validar_tablas(datos), [])

    def test_csv_ilegible_se_informa_sin_excepcion_incontrolada(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "asr_hablantes.csv").write_bytes(
                b"\xff\xfe"
            )

            tablas, fallos = v.cargar(root, "asr")

            self.assertNotIn("asr_hablantes", tablas)
            self.assertIn(
                "lectura_fallida",
                codigos(fallos),
            )

    def test_cli_diarizacion_sin_errores(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            datos = caso_base()

            datos["diarizacion_grabaciones"].to_csv(
                root / "diarizacion_grabaciones.csv",
                index=False,
            )
            datos["diarizacion_hablantes"].to_csv(
                root / "diarizacion_hablantes.csv",
                index=False,
            )
            (root / "diarizacion_segmentos.parquet").write_bytes(
                b"fixture sintetico"
            )

            with patch.object(
                v.pd,
                "read_parquet",
                return_value=datos["diarizacion_segmentos"],
            ):
                self.assertEqual(
                    v.main([
                        "--raiz", str(root),
                        "--componente", "diarizacion",
                    ]),
                    0,
                )

    def test_cli_asr_reproduce_resultado_de_tablas(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            datos = caso_base()
            ruta = root / v.ARCHIVOS["asr_instancias"]
            ruta.write_bytes(
                b"datos parquet (mock de lectura)"
            )

            datos["asr_hablantes"].to_csv(
                root / v.ARCHIVOS["asr_hablantes"],
                index=False,
            )

            with patch.object(
                v.pd,
                "read_parquet",
                return_value=datos["asr_instancias"],
            ):
                self.assertEqual(
                    v.main([
                        "--raiz", str(root),
                        "--componente", "asr",
                    ]),
                    0,
                )


if __name__ == "__main__":
    unittest.main()