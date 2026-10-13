"""Contrato de E/S común de la muestra, sin fuentes originales ni red."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

HITO = Path(__file__).resolve().parents[1]
ESPECIFICACION = importlib.util.spec_from_file_location(
    "armar_muestra", HITO / "scripts" / "armar_muestra.py"
)
armar_muestra = importlib.util.module_from_spec(ESPECIFICACION)
ESPECIFICACION.loader.exec_module(armar_muestra)


class SerializacionMuestraTest(unittest.TestCase):
    def test_tablas_csv_y_parquet_reales(self):
        datos = pd.DataFrame({
            "recording_id": ["sesion_01", "sesion_02"],
            "duracion_s": [1.25, 2.5],
            "texto": ["hola", "chau"],
        })

        with tempfile.TemporaryDirectory() as directorio:
            raiz = Path(directorio)
            carpeta = raiz / "muestra"

            with patch.object(armar_muestra, "HITO", raiz):
                armar_muestra.guardar(datos, carpeta / "prueba.csv")
                armar_muestra.guardar(datos, carpeta / "prueba.parquet")

            pd.testing.assert_frame_equal(
                pd.read_csv(carpeta / "prueba.csv"), datos
            )
            pd.testing.assert_frame_equal(
                pd.read_parquet(carpeta / "prueba.parquet"), datos
            )


if __name__ == "__main__":
    unittest.main()