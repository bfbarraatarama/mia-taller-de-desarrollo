"""Pruebas de adquisición sin acceso a Internet."""
import hashlib
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "scripts"),
)

from adquisicion import (
    bajar,
    cargar_json,
    guardar_json,
    pedir_rango,
    sha256,
)


class Respuesta:
    def __init__(self, contenido, status=200, headers=None):
        self.stream = io.BytesIO(contenido)
        self.status = status
        self.headers = (
            {"Content-Length": str(len(contenido))}
            if headers is None
            else headers
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, size=-1):
        return self.stream.read(size)


class AdquisicionTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.base = Path(self.dir.name)

    def test_descarga_y_reutilizacion(self):
        ruta = self.base / "datos.bin"
        llamadas = []

        def abrir(req, timeout=120):
            llamadas.append(req)
            return Respuesta(b"ABC")

        esperado = bajar(
            "https://example.invalid/x",
            ruta,
            abrir=abrir,
        )

        self.assertEqual(esperado["bytes"], 3)
        self.assertEqual(
            esperado["sha256"],
            sha256(ruta),
        )

        bajar(
            "https://example.invalid/x",
            ruta,
            esperado,
            abrir=lambda *_args, **_kw: self.fail(
                "Descarga redundante"
            ),
        )

        self.assertEqual(len(llamadas), 1)

    def test_existente_sin_hash_falla(self):
        ruta = self.base / "datos.bin"
        ruta.write_bytes(b"ABC")

        with self.assertRaises(ValueError):
            bajar("https://example.invalid/x", ruta)

    def test_reanudacion_verificada(self):
        ruta = self.base / "datos.bin"
        (self.base / "datos.bin.part").write_bytes(b"ABC")

        esperado = {
            "bytes": 6,
            "sha256": hashlib.sha256(b"ABCDEF").hexdigest(),
        }

        def abrir(req, timeout=120):
            self.assertEqual(
                req.get_header("Range"),
                "bytes=3-",
            )
            return Respuesta(
                b"DEF",
                206,
                {
                    "Content-Range": "bytes 3-5/6",
                    "Content-Length": "3",
                },
            )

        bajar(
            "https://example.invalid/x",
            ruta,
            esperado,
            abrir=abrir,
        )

        self.assertEqual(ruta.read_bytes(), b"ABCDEF")

    def test_servidor_ignora_range(self):
        ruta = self.base / "datos.bin"
        (self.base / "datos.bin.part").write_bytes(b"ABC")

        resultado = bajar(
            "https://example.invalid/x",
            ruta,
            abrir=lambda req, timeout=120: Respuesta(
                b"ABCDEF"
            ),
        )

        self.assertEqual(resultado["bytes"], 6)
        self.assertEqual(ruta.read_bytes(), b"ABCDEF")

    def test_range_rechaza_200(self):
        with self.assertRaises(ValueError):
            pedir_rango(
                "https://example.invalid/x",
                0,
                3,
                abrir=lambda req, timeout=120: Respuesta(
                    b"ABCD"
                ),
            )

    def test_range_valido(self):
        datos, total = pedir_rango(
            "https://example.invalid/x",
            2,
            4,
            abrir=lambda req, timeout=120: Respuesta(
                b"CDE",
                206,
                {"Content-Range": "bytes 2-4/10"},
            ),
        )

        self.assertEqual((datos, total), (b"CDE", 10))

    def test_zip_corrupto_no_se_publica(self):
        ruta = self.base / "datos.zip"

        with self.assertRaises(zipfile.BadZipFile):
            bajar(
                "https://example.invalid/x",
                ruta,
                abrir=lambda req, timeout=120: Respuesta(
                    b"zip-invalido"
                ),
            )

        self.assertFalse(ruta.exists())

    def test_hash_incorrecto(self):
        ruta = self.base / "datos.bin"
        esperado = {
            "bytes": 3,
            "sha256": hashlib.sha256(b"ABC").hexdigest(),
        }

        with self.assertRaises(ValueError):
            bajar(
                "https://example.invalid/x",
                ruta,
                esperado,
                abrir=lambda req, timeout=120: Respuesta(
                    b"XYZ"
                ),
            )

        self.assertFalse(ruta.exists())

    def test_longitud_incorrecta(self):
        ruta = self.base / "datos.bin"

        with self.assertRaises(RuntimeError):
            bajar(
                "https://example.invalid/x",
                ruta,
                intentos=1,
                abrir=lambda req, timeout=120: Respuesta(
                    b"AB",
                    headers={"Content-Length": "3"},
                ),
            )

        self.assertFalse(ruta.exists())

    def test_html_no_es_csv(self):
        ruta = self.base / "datos.csv"

        with self.assertRaises(ValueError):
            bajar(
                "https://example.invalid/x",
                ruta,
                abrir=lambda req, timeout=120: Respuesta(
                    b"<html>error</html>"
                ),
            )

        self.assertFalse(ruta.exists())

    def test_sin_longitud_ni_checksum(self):
        ruta = self.base / "datos.bin"

        with self.assertRaises(ValueError):
            bajar(
                "https://example.invalid/x",
                ruta,
                abrir=lambda req, timeout=120: Respuesta(
                    b"XYZ",
                    headers={},
                ),
            )

        self.assertFalse(ruta.exists())

    def test_json_atomico(self):
        ruta = self.base / "manifest.json"

        guardar_json(ruta, {"clave": [1, 2]})

        self.assertEqual(
            cargar_json(ruta),
            {"clave": [1, 2]},
        )

        self.assertFalse(
            ruta.with_suffix(".json.tmp").exists()
        )


if __name__ == "__main__":
    unittest.main()