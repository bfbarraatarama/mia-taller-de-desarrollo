"""Regresiones sobre manejo de modelos, persistencia y fallos de proveedores."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from botocore.exceptions import ClientError

from minutas import generar_minuta
from minutas.proveedores import (
    RespuestaEstructuradaAusente, RespuestaModelo, construir_cliente,
)


def _transcripcion():
    return {"segments": [{
        "start": 0, "end": 1, "speaker": "SPEAKER_00", "name": "Ana",
        "text": "Hoy se revisó el informe.", "overlap": False, "ambiguous": False,
    }]}


class _Cliente:
    nombre = "modelo-de-prueba"
    proveedor = "ollama"

    def __init__(self, error_inicial=None):
        self.error_inicial = error_inicial
        self.llamadas = 0

    def responder(self, instrucciones, datos, esquema):
        self.llamadas += 1
        if self.error_inicial is not None and self.llamadas == 1:
            raise self.error_inicial
        return RespuestaModelo(
            {"resumen": "Se revisó el informe.", "temas": [], "decisiones": [],
             "problemas": [], "acciones": []}, 10, 7,
        )


class RegresionesRevision(unittest.TestCase):
    def test_error_de_formato_del_proveedor_se_reintenta(self):
        cliente = _Cliente(RespuestaEstructuradaAusente("Falta herramienta."))
        with tempfile.TemporaryDirectory() as carpeta:
            resultado = generar_minuta(_transcripcion(), carpeta, cliente=cliente)
            self.assertEqual(cliente.llamadas, 2)
            manifiesto = json.loads(resultado.manifiesto.read_text())
            self.assertEqual(manifiesto["llamadas_modelo"], 2)

    def test_error_no_recuperable_del_proveedor_no_se_reintenta(self):
        cliente = _Cliente(RuntimeError("Fallo de red"))
        with tempfile.TemporaryDirectory() as carpeta:
            with self.assertRaisesRegex(RuntimeError, "Fallo de red"):
                generar_minuta(_transcripcion(), carpeta, cliente=cliente)
            self.assertEqual(cliente.llamadas, 1)

    def test_fallo_publicacion_no_deja_archivos_parciales(self):
        reemplazo_real = os.replace
        def fallar_segundo(origen, destino):
            if Path(destino).name == "minutes.md":
                raise OSError("Fallo de disco simulado")
            return reemplazo_real(origen, destino)

        with tempfile.TemporaryDirectory() as carpeta:
            with patch("minutas.generacion.os.replace", side_effect=fallar_segundo):
                with self.assertRaisesRegex(OSError, "Fallo de disco"):
                    generar_minuta(_transcripcion(), carpeta, cliente=_Cliente())
            self.assertFalse((Path(carpeta) / "minutes.json").exists())
            self.assertFalse((Path(carpeta) / "minutes.md").exists())
            self.assertFalse((Path(carpeta) / "ejecucion_minutas.json").exists())
            self.assertEqual(list(Path(carpeta).glob(".minutas-*")), [])
            generar_minuta(_transcripcion(), carpeta, cliente=_Cliente())

    def test_fallo_sobrescribir_restaura_resultados_previos(self):
        reemplazo_real = os.replace
        def fallar_segundo(origen, destino):
            if Path(destino).name == "minutes.md":
                raise OSError("Fallo de disco simulado")
            return reemplazo_real(origen, destino)

        with tempfile.TemporaryDirectory() as carpeta:
            generar_minuta(_transcripcion(), carpeta, cliente=_Cliente())
            antes = {f.name: f.read_bytes() for f in Path(carpeta).iterdir()}
            with patch("minutas.generacion.os.replace", side_effect=fallar_segundo):
                with self.assertRaisesRegex(OSError, "Fallo de disco"):
                    generar_minuta(_transcripcion(), carpeta, cliente=_Cliente(), sobrescribir=True)
            despues = {f.name: f.read_bytes() for f in Path(carpeta).iterdir()}
            self.assertEqual(antes, despues)

    def test_resultados_no_publicos_por_defecto_en_posix(self):
        if os.name != "posix":
            self.skipTest("Requiere POSIX")
        with tempfile.TemporaryDirectory() as carpeta:
            generar_minuta(_transcripcion(), carpeta, cliente=_Cliente())
            for ruta in Path(carpeta).glob("*"):
                self.assertEqual(ruta.stat().st_mode & 0o777, 0o600)

    def test_ollama_error_de_conexion_tiene_mensaje_controlado(self):
        import sys
        import types

        class _Falso:
            def __init__(self, **kwargs):
                pass

            def chat(self, **kwargs):
                raise ConnectionError("Ollama no responde")

        with patch.dict(sys.modules, {
            "ollama": types.SimpleNamespace(Client=_Falso),
        }):
            cliente = construir_cliente(
                "qwen2.5-7b", permitir_remoto=False, temperatura=0,
                num_ctx=16384, max_tokens=4096,
            )
            with self.assertRaisesRegex(RuntimeError, "Error al invocar Ollama"):
                cliente.responder("instrucciones", "datos", {"type": "object"})

    def test_bedrock_error_de_api_tiene_mensaje_controlado(self):
        class _Falso:
            def converse(self, **kwargs):
                raise ClientError(
                    {"Error": {"Code": "AccessDeniedException", "Message": "Sin permiso"}},
                    "Converse",
                )
        with patch("boto3.client", return_value=_Falso()):
            cliente = construir_cliente(
                "nova-lite", permitir_remoto=True, temperatura=0,
                num_ctx=16384, max_tokens=4096,
            )
            with self.assertRaisesRegex(RuntimeError, "Error al invocar AWS Bedrock"):
                cliente.responder("instrucciones", "datos", {"type": "object"})


if __name__ == "__main__":
    unittest.main()