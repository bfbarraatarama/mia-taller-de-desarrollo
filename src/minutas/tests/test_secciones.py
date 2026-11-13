"""Pruebas adicionales de rutas, secciones configurables y prompts en español."""

from __future__ import annotations

import json
import tempfile
import unittest
from itertools import combinations
from pathlib import Path

from minutas import ConfiguracionMinutas, SECCIONES_MINUTA, generar_minuta
from minutas.__main__ import _secciones_cli
from minutas.contratos import modelo_minuta
from minutas.generacion import _preparar_prompts
from minutas.proveedores import RespuestaModelo
from rutas import (
    DEFINICIONES_SECCIONES_MINUTAS, PROMPT_CONSOLIDACION_MINUTAS,
    PROMPT_EXTRACCION_MINUTAS, rutas_resultado_minutas,
)


ENTRADA = {"segments": [
    {"start": i * 4, "end": i * 4 + 3, "speaker": f"SPEAKER_{i % 2:02d}",
     "name": "Luisa" if i % 2 else "Bruno", "text": "Enviar el informe el viernes. " * 5,
     "overlap": False, "ambiguous": False}
    for i in range(12)
]}


class ClienteSimulado:
    nombre = "simulado"
    proveedor = "ollama"

    def __init__(self, incluir_extra: bool = False):
        self.llamadas: list[tuple[str, dict]] = []
        self.incluir_extra = incluir_extra

    def responder(self, instrucciones, datos, esquema):
        self.llamadas.append((instrucciones, esquema))
        datos_cargados = json.loads(datos.split("\n\nLa respuesta anterior fue inválida.", 1)[0])
        if "intervenciones" in datos_cargados:
            ancla = datos_cargados["intervenciones"][0]["id"]
        else:
            parcial = datos_cargados["minutas_parciales"][0]
            ancla = next(
                (elemento["id_ancla"] for seccion in ("temas", "decisiones", "problemas", "acciones")
                 for elemento in parcial.get(seccion, [])), "I000001"
            )
        elemento = {"texto": "Se trató el informe", "ids_intervenciones": [ancla], "id_ancla": ancla}
        valores = {
            "resumen": "Se trató el informe.",
            "temas": [elemento],
            "decisiones": [],
            "problemas": [],
            "acciones": [{**elemento, "responsable": None, "plazo": None}],
        }
        salida = {seccion: valores[seccion] for seccion in esquema["properties"]}
        if self.incluir_extra:
            salida["temas" if "temas" not in salida else "otra"] = [elemento]
        return RespuestaModelo(salida)


class SeccionesConfigurables(unittest.TestCase):
    def test_todas_las_combinaciones_son_estrictas(self):
        for cantidad in range(1, len(SECCIONES_MINUTA) + 1):
            for seleccion in combinations(SECCIONES_MINUTA, cantidad):
                with self.subTest(seleccion=seleccion):
                    esquema = modelo_minuta(seleccion).model_json_schema()
                    self.assertEqual(list(esquema["properties"]), list(seleccion))
                    self.assertEqual(set(esquema["required"]), set(seleccion))
                    self.assertFalse(esquema["additionalProperties"])

    def test_selecciones_invalidas(self):
        for seleccion in ((), ("resumen", "resumen"), ("otro",), ("RESUMEN",)):
            with self.subTest(seleccion=seleccion), self.assertRaises(ValueError):
                ConfiguracionMinutas(secciones=seleccion)
        self.assertEqual(_secciones_cli("resumen, acciones"), ("resumen", "acciones"))

    def test_rutas_centralizadas_y_prompts_version_1(self):
        rutas = rutas_resultado_minutas("reunion")
        self.assertEqual(rutas.json.name, "minutes.json")
        self.assertEqual(rutas.markdown.name, "minutes.md")
        self.assertEqual(rutas.manifiesto.name, "ejecucion_minutas.json")
        for ruta in (PROMPT_EXTRACCION_MINUTAS, PROMPT_CONSOLIDACION_MINUTAS,
                     DEFINICIONES_SECCIONES_MINUTAS):
            self.assertTrue(ruta.is_file())
            self.assertIn("_v1.", ruta.name)

    def test_prompt_contiene_solo_definiciones_solicitadas(self):
        extraccion, consolidacion, hashes = _preparar_prompts(("resumen", "acciones"))
        for texto in (extraccion, consolidacion):
            self.assertIn("`resumen`:", texto)
            self.assertIn("`acciones`:", texto)
            self.assertNotIn("`temas`:", texto)
            self.assertNotIn("`decisiones`:", texto)
            self.assertNotIn("`problemas`:", texto)
            self.assertNotIn("{{SECCIONES_SOLICITADAS}}", texto)
        self.assertEqual(len(hashes), 3)

    def test_solicitud_ami_sin_temas(self):
        seleccion = ("resumen", "decisiones", "problemas", "acciones")
        cliente = ClienteSimulado()
        with tempfile.TemporaryDirectory() as carpeta:
            salida = generar_minuta(ENTRADA, carpeta, cliente=cliente, secciones=seleccion)
            self.assertEqual(list(json.loads(salida.json.read_text())), list(seleccion))
            self.assertNotIn("## Temas tratados", salida.markdown.read_text())
            self.assertEqual(json.loads(salida.manifiesto.read_text())["secciones"], list(seleccion))
            self.assertEqual(list(cliente.llamadas[0][1]["properties"]), list(seleccion))

    def test_solo_acciones_con_consolidacion(self):
        cliente = ClienteSimulado()
        configuracion = ConfiguracionMinutas(secciones=("acciones",), max_caracteres_bloque=1100)
        with tempfile.TemporaryDirectory() as carpeta:
            salida = generar_minuta(ENTRADA, carpeta, cliente=cliente, configuracion=configuracion)
            self.assertGreater(salida.llamadas_modelo, 2)
            self.assertEqual(list(json.loads(salida.json.read_text())), ["acciones"])
            self.assertIn("## Acciones pendientes", salida.markdown.read_text())
            self.assertNotIn("## Resumen", salida.markdown.read_text())
            self.assertTrue(all(list(schema["properties"]) == ["acciones"]
                                for _, schema in cliente.llamadas))

    def test_solo_resumen(self):
        with tempfile.TemporaryDirectory() as carpeta:
            salida = generar_minuta(ENTRADA, carpeta, secciones=("resumen",),
                                   cliente=ClienteSimulado())
            self.assertEqual(list(json.loads(salida.json.read_text())), ["resumen"])
            self.assertNotIn("## Acciones pendientes", salida.markdown.read_text())

    def test_campos_adicionales_prohibidos(self):
        with tempfile.TemporaryDirectory() as carpeta:
            with self.assertRaisesRegex(ValueError, "no produjo una minuta"):
                generar_minuta(ENTRADA, carpeta, secciones=("acciones",),
                              cliente=ClienteSimulado(incluir_extra=True))
            self.assertFalse((Path(carpeta) / "minutes.json").exists())

    def test_configuracion_y_argumento_no_se_superponen(self):
        with tempfile.TemporaryDirectory() as carpeta:
            with self.assertRaisesRegex(ValueError, "no en ambos"):
                generar_minuta(ENTRADA, carpeta, secciones=("acciones",),
                              configuracion=ConfiguracionMinutas(), cliente=ClienteSimulado())


if __name__ == "__main__":
    unittest.main()