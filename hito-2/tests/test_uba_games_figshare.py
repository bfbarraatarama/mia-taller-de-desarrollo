"""Pruebas de integración Figshare: originales simulados, sin red."""
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path
from unittest.mock import patch

import soundfile as sf

HITO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HITO / "scripts"))
import descargar_fuentes as d

spec = importlib.util.spec_from_file_location(
    "armar_muestra", HITO / "scripts" / "armar_muestra.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def wav_bytes(duracion=1, amplitud=0):
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(
            int(amplitud).to_bytes(2, "little", signed=True)
            * int(duracion * 16000)
        )
    return out.getvalue()


class FigshareTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.hito = self.root / "hito-2"
        self.cache = self.hito / ".cache"
        self.out = self.hito / "muestra"
        self.raw = self.cache / "uba_games" / "figshare-v2"
        self.raw.mkdir(parents=True)
        self.fuentes = {"phrases.rar": {}, "wavs.rar": {}}
        self.crear()

    def crear(self, omitir_audio=None, mal_tiempo=False, extra=False,
              exceso_terminal_s=0.0):
        self.fuentes = {}
        for nombre in ("phrases.rar", "wavs.rar"):
            ruta = self.raw / nombre
            with zipfile.ZipFile(ruta, "w") as archive:
                for sesion in (21, 22):
                    for canal in (1, 2):
                        stem = f"s{sesion}.objects.01.channel{canal}"
                        if nombre == "phrases.rar":
                            contenido = "0\t0.3\t#\n0.3\t1\thola\n"
                            if mal_tiempo and sesion == 21 and canal == 1:
                                contenido = "0\t0.3\t#\n0.1\t1\thola\n"
                            elif exceso_terminal_s and sesion == 21 and canal == 1:
                                contenido = (
                                    "0\t0.3\t#\n"
                                    f"0.3\t{1 + exceso_terminal_s:.3f}\thola\n"
                                )
                            archive.writestr(
                                f"phrases/S{sesion}/{stem}.phrases",
                                contenido,
                            )
                        elif (sesion, canal) != omitir_audio:
                            archive.writestr(
                                f"wavs/S{sesion}/{stem}.wav",
                                wav_bytes(
                                    amplitud=12000 if canal == 1 else 16000
                                ),
                            )
                if nombre == "wavs.rar":
                    archive.writestr(
                        "wavs/Downsample.sh", "#!/bin/sh\n"
                    )
                    if extra:
                        archive.writestr(
                            "wavs/readme.txt", "texto auxiliar"
                        )
                        archive.writestr(
                            "wavs/Sin separar canales/S26_falta_separar_canales/s26.objects.01.wav",
                            wav_bytes(),
                        )
            b = ruta.read_bytes()
            self.fuentes[nombre] = {
                "file_id": 1 if nombre == "phrases.rar" else 2,
                "bytes": len(b),
                "md5": hashlib.md5(b).hexdigest(),
            }

        # Los datos simulados son ZIP, pero las rutas imitan los RAR.
        # El lector compartido detecta el formato automáticamente.
        s = '\n[uba_games_figshare]\nlicencia_declarada = "CC BY 4.0"\n'
        for name, item in self.fuentes.items():
            s += (
                f'\n[uba_games_figshare.archivos."{name}"]\n'
                f'file_id = {item["file_id"]}\n'
                f'bytes = {item["bytes"]}\n'
                f'md5 = "{item["md5"]}"\n'
            )
        (self.hito / "fuentes.toml").write_text(s)

        lock = {"version": 1, "archivos": {}, "repos": {}}
        for name, item in self.fuentes.items():
            raw = self.raw / name
            lock["archivos"][f"uba_games/figshare-v2/{name}"] = {
                "bytes": item["bytes"],
                "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
            }
        (self.hito / "fuentes.lock.json").write_text(json.dumps(lock))
        self.lock = lock

    def ejecutar(self):
        # Se sustituye solamente el serializador durante las pruebas.
        tablas = {}

        def guardar_test(df, ruta):
            tablas[ruta.name] = df.copy()

        with patch.multiple(
            m, HITO=self.hito, CACHE=self.cache, OUT=self.out
        ), patch.object(m, "guardar", side_effect=guardar_test):
            resumen = m.armar_uba_games_figshare()
        return resumen, tablas

    def test_dos_sesiones_clips_sin_perdida_de_overlap(self):
        resumen, tablas = self.ejecutar()
        self.assertEqual(
            resumen,
            {
                "sesiones": 2,
                "grabaciones": 2,
                "anotaciones": 8,
                "extractos": 2,
                "grabaciones_con_anomalias": 0,
                "grabaciones_aceptadas_por_precision": 0,
            },
        )
        self.assertEqual(len(tablas["grabaciones.csv"]), 2)
        self.assertEqual(len(tablas["intervalos.parquet"]), 8)
        self.assertEqual(
            tablas["intervalos.parquet"]["silencio_marcado"].sum(), 4
        )
        self.assertEqual(
            tablas["grabaciones.csv"]["group_id"].nunique(), 2
        )
        clip = (
            self.out
            / "uba_games_figshare/audio_muestra/"
            / "figshare_v2_S21_objects_01.flac"
        )
        self.assertTrue(clip.exists())
        datos, hz = sf.read(clip, dtype="int16")
        self.assertEqual(hz, 16000)
        self.assertEqual(int(datos[0]), 14000)
        self.assertFalse((self.out / "MANIFIESTO.json").exists())

    def test_archivos_auxiliares_no_se_interpretan_como_wav(self):
        self.crear(extra=True)
        self.ejecutar()
        proc = json.loads(
            (self.out / "uba_games_figshare/procedencia.json").read_text()
        )
        self.assertEqual(
            set(proc["auxiliares"]["wavs"]),
            {
                "wavs/Downsample.sh",
                "wavs/readme.txt",
                "wavs/Sin separar canales/S26_falta_separar_canales/s26.objects.01.wav",
            },
        )

    def test_omision_de_auxiliar_con_datos_integros_en_pistas_necesarias(self):
        # Se altera solo el contenido de un ZIP sintético: su CRC deja de
        # coincidir. Si se descomprime el auxiliar, libarchive debe fallar.
        ruta = self.root / "auxiliar_con_crc_invalido.zip"
        pista1 = "wavs/S21/s21.objects.01.channel1.wav"
        auxiliar = (
            "wavs/Sin separar canales/"
            "S29_falta_separar_canales/s29.objects.18.wav"
        )
        pista2 = "wavs/S21/s21.objects.01.channel2.wav"
        marca = b"AUXILIAR_PRUEBA_EXCLUSIVA"
        with zipfile.ZipFile(ruta, "w", compression=zipfile.ZIP_STORED) as arc:
            arc.writestr(pista1, b"pista-1")
            arc.writestr(auxiliar, marca)
            arc.writestr(pista2, b"pista-2")
        datos = ruta.read_bytes()
        self.assertEqual(datos.count(marca), 1)
        ruta.write_bytes(datos.replace(marca, b"X" + marca[1:], 1))

        with self.assertRaisesRegex(ValueError, "Error leyendo"):
            for nombre, contenido in m.entradas_comprimidas(ruta):
                contenido.read()

        resultado = [
            (nombre, contenido.read() if contenido is not None else None)
            for nombre, contenido in m.entradas_comprimidas(
                ruta,
                incluir=lambda nombre: m._uba_identidad(nombre, "wav") is not None,
            )
        ]
        self.assertEqual(
            resultado,
            [(pista1, b"pista-1"), (auxiliar, None), (pista2, b"pista-2")],
        )

    def test_exceso_terminal_9_ms_aceptado_y_preservado(self):
        self.crear(exceso_terminal_s=0.009)
        resumen, tablas = self.ejecutar()
        fila = tablas["grabaciones.csv"].iloc[0]
        self.assertTrue(fila["anotacion_fuera_del_audio"])
        self.assertTrue(fila["exceso_aceptado_por_precision"])
        self.assertFalse(fila["exceso_superior_a_tolerancia"])
        self.assertTrue(fila["par_audio_referencia_valido"])
        self.assertAlmostEqual(fila["exceso_terminal_max_s"], 0.009)
        self.assertEqual(resumen["grabaciones_aceptadas_por_precision"], 1)
        self.assertEqual(resumen["extractos"], 2)
        original = tablas["intervalos.parquet"]
        intervalo = original.loc[
            (original["recording_id"] == fila["recording_id"])
            & (original["canal"] == 1)
        ].iloc[-1]
        self.assertAlmostEqual(intervalo["fin_s"], 1.009)
        procedencia = json.loads(
            (self.out / "uba_games_figshare/procedencia.json").read_text()
        )
        self.assertEqual(procedencia["tolerancia_terminal_figshare_s"], 0.01)
        self.assertEqual(
            procedencia["grabaciones_aceptadas_por_precision"],
            [fila["recording_id"]],
        )

    def test_exceso_terminal_11_ms_rechazado_sin_perder_anotacion(self):
        self.crear(exceso_terminal_s=0.011)
        resumen, tablas = self.ejecutar()
        fila = tablas["grabaciones.csv"].iloc[0]
        self.assertTrue(fila["exceso_superior_a_tolerancia"])
        self.assertFalse(fila["exceso_aceptado_por_precision"])
        self.assertFalse(fila["par_audio_referencia_valido"])
        self.assertAlmostEqual(fila["exceso_terminal_max_s"], 0.011)
        self.assertEqual(resumen["grabaciones_con_anomalias"], 1)
        self.assertEqual(resumen["extractos"], 1)
        intervalo = tablas["intervalos.parquet"].loc[
            (tablas["intervalos.parquet"]["recording_id"] == fila["recording_id"])
            & (tablas["intervalos.parquet"]["canal"] == 1)
        ].iloc[-1]
        self.assertAlmostEqual(intervalo["fin_s"], 1.011)

    def test_pista_faltante_termina_en_anomalia(self):
        self.crear(omitir_audio=(22, 2))
        resumen, tablas = self.ejecutar()
        self.assertEqual(resumen["grabaciones_con_anomalias"], 1)
        self.assertEqual(resumen["extractos"], 1)
        self.assertFalse(
            tablas["grabaciones.csv"].iloc[1]["par_audio_referencia_valido"]
        )

    def test_intervalo_invalido_detiene_preparacion(self):
        self.crear(mal_tiempo=True)
        with self.assertRaisesRegex(ValueError, "desordenados"):
            self.ejecutar()

    def test_md5_incorrecto_detiene_preparacion(self):
        ruta = self.raw / "phrases.rar"
        datos = bytearray(ruta.read_bytes())
        datos[-1] ^= 1
        ruta.write_bytes(datos)
        with self.assertRaisesRegex(ValueError, "Original no fijado"):
            self.ejecutar()

    def test_entrada_corrupta_no_se_registra(self):
        (self.raw / "wavs.rar").write_bytes(b"incorrecto")
        with patch.multiple(
            d,
            CACHE=self.cache,
            LOCK_PATH=self.hito / "otro-lock.json",
            LOCK={"version": 1, "archivos": {}, "repos": {}},
            HISTORICO={},
            REGISTRO={"uba_games_figshare": {"archivos": self.fuentes}},
        ):
            with self.assertRaisesRegex(ValueError, "Tamaño diferente"):
                d.uba_games_figshare()
            self.assertNotIn(
                "uba_games/figshare-v2/wavs.rar", d.LOCK["archivos"]
            )

    def test_adquisicion_registra_original_local_sin_red(self):
        with patch.multiple(
            d,
            CACHE=self.cache,
            LOCK_PATH=self.hito / "fuentes.lock.json",
            LOCK={"version": 1, "archivos": {}, "repos": {}},
            HISTORICO={},
            REGISTRO={"uba_games_figshare": {"archivos": self.fuentes}},
        ), patch.object(
            d, "descarga_http", wraps=d.descarga_http
        ) as fetch:
            d.uba_games_figshare()
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(len(d.LOCK["archivos"]), 2)
            d.comprobar()


if __name__ == "__main__":
    unittest.main()