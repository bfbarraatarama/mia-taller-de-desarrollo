"""Pruebas técnicas sin modelos ni credenciales; no evalúan calidad semántica."""

from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from minutas import ConfiguracionMinutas, generar_minuta
from minutas.contratos import MinutaEstructurada, validar_evidencias
from minutas.entrada import leer_transcripcion
from minutas.formato import a_markdown
from minutas.proveedores import RespuestaModelo, construir_cliente


def transcripcion(cantidad: int = 2) -> dict:
    return {"segments": [
        {
            "start": i * 4, "end": i * 4 + 3,
            "speaker": f"SPEAKER_{i % 2:02d}",
            "name": "Luisa" if i % 2 else "Bruno",
            "text": ("Luisa va a enviar el informe el viernes. " if i % 2 else
                     "Revisemos el estado del proyecto. ") + ("Detalle del proyecto. " * 4),
            "overlap": False, "ambiguous": False,
        }
        for i in range(cantidad)
    ]}


def minuta(ids: list[str]) -> dict:
    return {
        "resumen": "Se revisó el proyecto y se habló del informe.",
        "temas": [{"texto": "Estado del proyecto", "ids_intervenciones": [ids[0]], "id_ancla": ids[0]}],
        "decisiones": [], "problemas": [],
        "acciones": [{
            "texto": "Enviar el informe", "responsable": None, "plazo": None,
            "ids_intervenciones": [ids[-1]], "id_ancla": ids[-1],
        }],
    }


class ClienteSimulado:
    nombre = "simulado-es"
    proveedor = "ollama"

    def __init__(self, respuestas: list[dict | str] | None = None):
        self.respuestas = respuestas or []
        self.mensajes: list[str] = []

    def responder(self, instrucciones, datos, esquema):
        self.mensajes.append(datos)
        if self.respuestas:
            contenido = self.respuestas.pop(0)
        else:
            objeto = json.loads(datos)
            if "intervenciones" in objeto:
                ids = [fila["id"] for fila in objeto["intervenciones"]]
            else:
                ids = [
                    item["id_ancla"] for parcial in objeto["minutas_parciales"]
                    for item in parcial["temas"]
                ]
            contenido = minuta(ids)
        return RespuestaModelo(contenido, tokens_entrada=12, tokens_salida=15)


class Contratos(unittest.TestCase):
    def test_lectura_orden_y_solapamiento(self):
        datos = transcripcion()
        datos["segments"].reverse()
        datos["segments"][0]["overlap"] = True
        resultado, _ = leer_transcripcion(datos)
        self.assertEqual([r.inicio for r in resultado], [0.0, 4.0])
        self.assertEqual([r.id for r in resultado], ["I000001", "I000002"])
        self.assertTrue(resultado[1].superposicion)

    def test_tiempos_y_campos_invalidos(self):
        for cambio in ({"start": -1}, {"end": 0}, {"start": True},
                       {"start": "0"}, {"start": float("nan")},
                       {"overlap": None}, {"ambiguous": "false"}):
            datos = transcripcion(1)
            datos["segments"][0].update(cambio)
            with self.subTest(cambio=cambio), self.assertRaises(ValueError):
                leer_transcripcion(datos)
        with self.assertRaises(ValueError):
            leer_transcripcion({"segments": []})

    def test_referencia_inexistente(self):
        intervenciones, _ = leer_transcripcion(transcripcion())
        resultado = MinutaEstructurada.model_validate(minuta(["I999999"]))
        with self.assertRaisesRegex(ValueError, "referencias inexistentes"):
            validar_evidencias(resultado, intervenciones)

    def test_markdown_escape_y_sin_asignar(self):
        intervenciones, _ = leer_transcripcion(transcripcion())
        objeto = minuta(["I000001", "I000002"])
        objeto["acciones"][0]["texto"] = "Enviar [informe]\ncon *datos*"
        texto = a_markdown(MinutaEstructurada.model_validate(objeto), intervenciones)
        self.assertIn("[00:04]", texto)
        self.assertIn("Responsable: Sin asignar", texto)
        self.assertIn("\\[informe\\]", texto)
        self.assertIn("\\*datos\\*", texto)


class Flujo(unittest.TestCase):
    def test_ejecucion_completa_y_trazabilidad(self):
        cliente = ClienteSimulado()
        with tempfile.TemporaryDirectory() as carpeta:
            salida = generar_minuta(transcripcion(), carpeta, cliente=cliente)
            self.assertEqual(salida.llamadas_modelo, 1)
            self.assertTrue(salida.json.is_file())
            self.assertTrue(salida.markdown.is_file())
            contenido = json.loads(salida.json.read_text())
            self.assertEqual(contenido["acciones"][0]["id_ancla"], "I000002")
            ejecucion = json.loads(salida.manifiesto.read_text())
            self.assertEqual(
                set(ejecucion["prompts"]),
                {"extraccion_v1.md", "consolidacion_v1.md", "secciones_v1.json"},
            )
            self.assertEqual(ejecucion["tokens_entrada"], 12)
            self.assertIn("intervenciones", cliente.mensajes[0])
            with self.assertRaises(FileExistsError):
                generar_minuta(transcripcion(), carpeta, cliente=cliente)
            generar_minuta(transcripcion(), carpeta, cliente=cliente, sobrescribir=True)

    def test_entrada_desde_archivo_y_no_borra_fuente(self):
        cliente = ClienteSimulado()
        with tempfile.TemporaryDirectory() as carpeta:
            origen = Path(carpeta) / "transcription.json"
            origen.write_text(json.dumps(transcripcion(), ensure_ascii=False), encoding="utf-8")
            salida = generar_minuta(origen, Path(carpeta) / "salida", cliente=cliente)
            self.assertTrue(origen.exists())
            self.assertEqual(json.loads(salida.json.read_text())["resumen"],
                             "Se revisó el proyecto y se habló del informe.")

    def test_reintentos_por_referencias_inexistentes(self):
        cliente = ClienteSimulado([minuta(["I999999"]), minuta(["I000001", "I000002"])])
        with tempfile.TemporaryDirectory() as carpeta:
            salida = generar_minuta(transcripcion(), carpeta, cliente=cliente)
            self.assertEqual(salida.llamadas_modelo, 2)
            self.assertIn("referencias inexistentes", cliente.mensajes[1])

    def test_normaliza_ancla_omitida_de_evidencias(self):
        for como_json in (False, True):
            with self.subTest(como_json=como_json):
                defectuosa = minuta(["I000001", "I000002"])
                defectuosa["temas"][0]["id_ancla"] = "I000002"
                respuesta = (
                    json.dumps(defectuosa, ensure_ascii=False)
                    if como_json else defectuosa
                )
                cliente = ClienteSimulado([respuesta])

                with tempfile.TemporaryDirectory() as carpeta:
                    salida = generar_minuta(
                        transcripcion(), carpeta, cliente=cliente
                    )
                    self.assertEqual(salida.llamadas_modelo, 1)

                    contenido = json.loads(
                        salida.json.read_text(encoding="utf-8")
                    )
                    tema = contenido["temas"][0]
                    self.assertEqual(tema["id_ancla"], "I000002")
                    self.assertEqual(
                        tema["ids_intervenciones"],
                        ["I000001", "I000002"],
                    )

                    manifiesto = json.loads(
                        salida.manifiesto.read_text(encoding="utf-8")
                    )
                    self.assertEqual(manifiesto["normalizaciones_ancla"], 1)

    def test_ancla_inexistente_sigue_siendo_invalida(self):
        defectuosa = minuta(["I000001", "I000002"])
        defectuosa["temas"][0]["id_ancla"] = "I999999"
        cliente = ClienteSimulado([defectuosa] * 3)

        with tempfile.TemporaryDirectory() as carpeta:
            with self.assertRaisesRegex(ValueError, "no produjo una minuta"):
                generar_minuta(transcripcion(), carpeta, cliente=cliente)

            self.assertEqual(len(cliente.mensajes), 3)
            self.assertFalse((Path(carpeta) / "minutes.json").exists())

    def test_evidencias_duplicadas_siguen_siendo_invalidas(self):
        defectuosa = minuta(["I000001", "I000002"])
        defectuosa["temas"][0]["ids_intervenciones"] = [
            "I000001", "I000001"
        ]
        cliente = ClienteSimulado([defectuosa] * 3)

        with tempfile.TemporaryDirectory() as carpeta:
            with self.assertRaisesRegex(ValueError, "no produjo una minuta"):
                generar_minuta(transcripcion(), carpeta, cliente=cliente)

            self.assertFalse((Path(carpeta) / "minutes.json").exists())

    def test_agota_reintentos_sin_escribir_resultados(self):
        cliente = ClienteSimulado(["contenido inválido"] * 3)
        with tempfile.TemporaryDirectory() as carpeta:
            with self.assertRaisesRegex(ValueError, "no produjo una minuta"):
                generar_minuta(transcripcion(), carpeta, cliente=cliente)
            self.assertFalse((Path(carpeta) / "minutes.md").exists())

    def test_fragmentacion_y_consolidacion(self):
        cliente = ClienteSimulado()
        config = ConfiguracionMinutas(max_caracteres_bloque=1100)
        with tempfile.TemporaryDirectory() as carpeta:
            salida = generar_minuta(transcripcion(12), carpeta, cliente=cliente, configuracion=config)
            ejecucion = json.loads(salida.manifiesto.read_text())
            self.assertGreater(ejecucion["bloques_extraccion"], 1)
            self.assertGreater(salida.llamadas_modelo, ejecucion["bloques_extraccion"])
            self.assertTrue(any("minutas_parciales" in m for m in cliente.mensajes))

    def test_consolidacion_jerarquica(self):
        cliente = ClienteSimulado()
        config = ConfiguracionMinutas(max_caracteres_bloque=1100)
        with tempfile.TemporaryDirectory() as carpeta:
            salida = generar_minuta(transcripcion(90), carpeta, cliente=cliente,
                                    configuracion=config)
            datos = json.loads(salida.json.read_text())
            self.assertTrue(datos["temas"])
            self.assertGreater(salida.llamadas_modelo, 15)

    def test_no_permite_proveedor_remoto_implícito(self):
        class ClienteRemoto(ClienteSimulado):
            proveedor = "bedrock"
        with tempfile.TemporaryDirectory() as carpeta:
            with self.assertRaisesRegex(ValueError, "no está habilitado"):
                generar_minuta(transcripcion(), carpeta, cliente=ClienteRemoto())


class Proveedores(unittest.TestCase):
    def test_bedrock_requiere_autorizacion(self):
        with self.assertRaisesRegex(ValueError, "permitir_remoto"):
            construir_cliente("nova-lite", permitir_remoto=False, temperatura=0,
                              num_ctx=16384, max_tokens=4096)

    def test_ollama_esquema_y_opciones(self):
        solicitudes = []

        class ClienteFalso:
            def __init__(self, **kwargs):
                self.host = kwargs["host"]

            def chat(self, **kwargs):
                solicitudes.append(kwargs)
                return {"message": {"content": "{}"}, "prompt_eval_count": 15, "eval_count": 6}

        with patch.dict(sys.modules, {"ollama": types.SimpleNamespace(Client=ClienteFalso)}):
            cliente = construir_cliente("qwen2.5-7b", permitir_remoto=False,
                                        temperatura=0, num_ctx=16384, max_tokens=4096)
            cliente.responder("Instrucciones", "Datos", {"type": "object"})
        self.assertEqual(solicitudes[0]["model"], "qwen2.5:7b")
        self.assertEqual(solicitudes[0]["options"]["num_ctx"], 16384)
        self.assertEqual(solicitudes[0]["options"]["num_predict"], 4096)
        self.assertIn("format", solicitudes[0])

    def test_bedrock_herramienta_estructurada(self):
        solicitudes = []

        class ClienteFalso:
            def converse(self, **kwargs):
                solicitudes.append(kwargs)
                return {
                    "output": {"message": {"content": [
                        {"toolUse": {"name": "finalizar_minuta", "input": minuta(["I000001"])}}
                    ]}},
                    "usage": {"inputTokens": 12, "outputTokens": 34},
                    "stopReason": "tool_use",
                }

        falso_boto = types.SimpleNamespace(client=lambda *args, **kwargs: ClienteFalso())
        with patch.dict(sys.modules, {"boto3": falso_boto}):
            cliente = construir_cliente("nova-lite", permitir_remoto=True,
                                        temperatura=0, num_ctx=16384, max_tokens=4096)
            respuesta = cliente.responder("Instrucciones", "Datos", {"type": "object"})
        self.assertEqual(respuesta.tokens_salida, 34)
        self.assertEqual(solicitudes[0]["modelId"], "us.amazon.nova-lite-v1:0")
        self.assertIn("toolConfig", solicitudes[0])


if __name__ == "__main__":
    unittest.main()