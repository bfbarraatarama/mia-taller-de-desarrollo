"""Catálogo cerrado, selección legible y autorización de proveedores."""

from __future__ import annotations

import io
import sys
import types
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from minutas import ConfiguracionMinutas, MODELO_PREDETERMINADO, listar_modelos
from minutas.__main__ import main
from minutas.modelos import obtener_modelo
from minutas.proveedores import construir_cliente


class CatalogoModelos(unittest.TestCase):
    def test_catalogo_cerrado_y_etiquetas_para_gui(self):
        modelos = listar_modelos()
        self.assertEqual(
            [m.clave for m in modelos],
            ["qwen2.5-7b", "nova-lite", "claude-opus-4.5"],
        )
        self.assertEqual(MODELO_PREDETERMINADO, "qwen2.5-7b")
        self.assertEqual(len({m.clave for m in modelos}), len(modelos))
        self.assertTrue(all(m.nombre and m.descripcion for m in modelos))
        self.assertEqual(
            [m.requiere_remoto for m in modelos],
            [False, True, True],
        )
        self.assertEqual(
            [m.proveedor for m in modelos],
            ["ollama", "bedrock", "bedrock"],
        )

    def test_identificadores_resueltos_desde_catalogo(self):
        self.assertEqual(
            obtener_modelo("qwen2.5-7b").identificador,
            "qwen2.5:7b",
        )
        self.assertEqual(
            obtener_modelo("nova-lite").identificador,
            "us.amazon.nova-lite-v1:0",
        )
        self.assertEqual(
            obtener_modelo("claude-opus-4.5").identificador,
            "us.anthropic.claude-opus-4-5-20251101-v1:0",
        )

    def test_rechaza_modelos_arbitrarios_en_api(self):
        opciones_invalidas = (
            "llama3.1",
            "qwen2.5:7b",
            "bedrock:us.amazon.nova-lite-v1:0",
            "amazon.nova-lite-v1:0",
            "otro",
            "",
        )
        for clave in opciones_invalidas:
            with self.subTest(clave=clave):
                with self.assertRaisesRegex(ValueError, "Modelo no disponible"):
                    ConfiguracionMinutas(modelo=clave)

                with self.assertRaisesRegex(ValueError, "Modelo no disponible"):
                    construir_cliente(
                        clave,
                        permitir_remoto=True,
                        temperatura=0,
                        num_ctx=16384,
                        max_tokens=4096,
                    )

    def test_bedrock_exige_autorizacion_antes_de_crear_cliente(self):
        for clave in ("nova-lite", "claude-opus-4.5"):
            with self.subTest(clave=clave):
                with self.assertRaisesRegex(ValueError, "permitir_remoto"):
                    construir_cliente(
                        clave,
                        permitir_remoto=False,
                        temperatura=0,
                        num_ctx=16384,
                        max_tokens=4096,
                    )

    def test_resuelve_los_tres_proveedores_sin_red(self):
        solicitudes = []

        class OllamaFalso:
            def __init__(self, **kwargs):
                solicitudes.append(("ollama", kwargs))

        class BotoFalso:
            @staticmethod
            def client(*args, **kwargs):
                solicitudes.append(("bedrock", args, kwargs))
                return object()

        with patch.dict(sys.modules, {
            "ollama": types.SimpleNamespace(Client=OllamaFalso),
            "boto3": BotoFalso,
        }):
            qwen = construir_cliente(
                "qwen2.5-7b",
                permitir_remoto=False,
                temperatura=0,
                num_ctx=16384,
                max_tokens=4096,
            )
            nova = construir_cliente(
                "nova-lite",
                permitir_remoto=True,
                temperatura=0,
                num_ctx=16384,
                max_tokens=4096,
            )
            claude = construir_cliente(
                "claude-opus-4.5",
                permitir_remoto=True,
                temperatura=0,
                num_ctx=16384,
                max_tokens=4096,
            )

        self.assertEqual(
            [qwen.nombre, nova.nombre, claude.nombre],
            [
                "qwen2.5:7b",
                "us.amazon.nova-lite-v1:0",
                "us.anthropic.claude-opus-4-5-20251101-v1:0",
            ],
        )
        self.assertEqual(
            [s[0] for s in solicitudes],
            ["ollama", "bedrock", "bedrock"],
        )

    def test_cli_rechaza_identificador_tecnico(self):
        with redirect_stderr(io.StringIO()) as stderr:
            with self.assertRaises(SystemExit) as contexto:
                main([
                    "--entrada", "entrada.json",
                    "--salida", "salida",
                    "--modelo", "bedrock:us.amazon.nova-lite-v1:0",
                ])

        self.assertEqual(contexto.exception.code, 2)
        self.assertIn("invalid choice", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()