"""Pruebas de integración de adaptadores sin acceso remoto."""
import hashlib
import importlib.util
import io
import json
import sys
import tarfile
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

HITO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HITO / "scripts"))

spec = importlib.util.spec_from_file_location(
    "descargar_fuentes",
    HITO / "scripts" / "descargar_fuentes.py",
)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class PruebaFuentes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.raiz = Path(self.temp.name)
        self.cache = self.raiz / ".cache"
        self.lockfile = self.raiz / "fuentes.lock.json"

        self.patcher = patch.multiple(
            d,
            CACHE=self.cache,
            LOCK_PATH=self.lockfile,
            LOCK={
                "version": 1,
                "archivos": {},
                "repos": {},
            },
            HISTORICO={},
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_hf_fija_revision_y_reutiliza(self):
        audio = self.raiz / "archivo.mp3"
        audio.write_bytes(b"audio ficticio")

        metadata = self.raiz / "metadata.csv"
        metadata.write_text(
            "file_name,text\n"
            "CordeBA_0001.mp3,texto\n"
        )

        archivos = {
            "data/CordeBA_0001.mp3": audio,
            "metadata.csv": metadata,
        }
        visitas = []

        class ApiFalso:
            def __init__(self, token=None):
                pass

            def repo_info(self, **kw):
                visitas.append(("info", kw))
                return types.SimpleNamespace(
                    sha="a" * 40
                )

            def list_repo_files(self, **kw):
                visitas.append(("files", kw))
                return [
                    "metadata.csv",
                    "data/CordeBA_0001.mp3",
                    "README.md",
                ]

        def descargar(**kw):
            visitas.append(("download", kw))
            return str(archivos[kw["filename"]])

        modulo = types.ModuleType("huggingface_hub")
        modulo.HfApi = ApiFalso
        modulo.hf_hub_download = descargar

        with patch.dict(
            sys.modules,
            {"huggingface_hub": modulo},
        ):
            d.repositorio_hf("cordeba")

            self.assertEqual(
                d.LOCK["repos"]["cordeba"]["revision"],
                "a" * 40,
            )
            self.assertEqual(len(d.LOCK["archivos"]), 2)

            visitas.clear()
            d.repositorio_hf("cordeba")

        self.assertFalse(
            any(nombre == "download" for nombre, _ in visitas)
        )
        self.assertFalse(
            any(nombre == "info" for nombre, _ in visitas)
        )

    def test_common_voice(self):
        cfg = d.REGISTRO["common_voice"]
        archivo = self.raiz / cfg["archivo"]

        with tarfile.open(archivo, "w:gz") as z:
            contenido = b"contenido"
            info = tarfile.TarInfo("dataset/README")
            info.size = len(contenido)
            z.addfile(info, io.BytesIO(contenido))

        ids = []
        modulo = types.ModuleType("datacollective")

        def sdk(dataset_id, download_directory=None):
            ids.append(dataset_id)
            return archivo

        modulo.download_dataset = sdk

        with patch.dict(
            sys.modules,
            {"datacollective": modulo},
        ), patch.dict(
            "os.environ",
            {"MDC_API_KEY": "prueba"},
        ):
            d.common_voice()

        self.assertEqual(ids, [cfg["id"]])
        self.assertEqual(len(d.LOCK["archivos"]), 1)

    def test_uba_sin_urls_verificadas(self):
        with patch.object(d, "descarga_http") as descargar:
            with self.assertRaisesRegex(
                RuntimeError, "URLs individuales verificadas"
            ):
                d.uba_games()

            descargar.assert_not_called()

    def test_uba_con_urls_individuales(self):
        cfg = d.REGISTRO["uba_games"].copy()
        cfg["urls"] = {
            nombre: f"https://example.invalid/{nombre}"
            for nombre in cfg["archivos"]
        }

        registro = {**d.REGISTRO, "uba_games": cfg}
        encontrados = []

        def descargar(url, destino, esperado=None):
            encontrados.append((url, destino.name))
            return {
                "bytes": 3,
                "sha256": hashlib.sha256(b"abc").hexdigest(),
            }

        with patch.object(
            d, "REGISTRO", registro
        ), patch.object(
            d, "descarga_http", side_effect=descargar
        ):
            d.uba_games()

        self.assertEqual(
            encontrados,
            [
                (cfg["urls"][nombre], nombre)
                for nombre in cfg["archivos"]
            ],
        )

    def test_comprobar_detecta_repositorio_parcial(self):
        d.LOCK["repos"]["cordeba"] = {
            "repo": "ejemplo/cordeba",
            "revision": "a" * 40,
            "archivos": [
                "metadata.csv",
                "data/CordeBA_0001.mp3",
            ],
        }

        d.LOCK["archivos"]["cordeba/metadata.csv"] = {
            "bytes": 1,
            "sha256": "a" * 64,
        }

        with self.assertRaisesRegex(
            ValueError, "adquirido parcialmente"
        ):
            d.comprobar()

    def test_cli_en_modo_aislado(self):
        import subprocess

        resultado = subprocess.run(
            [
                sys.executable,
                "-I",
                str(HITO / "scripts" / "descargar_fuentes.py"),
                "--grupo-invalido",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            resultado.returncode, 2, resultado.stderr
        )
        self.assertIn(
            "Argumentos desconocidos", resultado.stdout
        )
        self.assertNotIn(
            "ModuleNotFoundError", resultado.stderr
        )

    def test_argumento_invalido(self):
        self.assertEqual(
            d.main(["una-fuente-inexistente"]),
            2,
        )


if __name__ == "__main__":
    unittest.main()