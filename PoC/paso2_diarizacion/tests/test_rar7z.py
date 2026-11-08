"""Tarea 6.1: verificación de archivos extraídos contra el listado de 7-Zip (sin extraer), con archivos sintéticos."""

import hashlib
import subprocess
import zlib
from pathlib import Path

import pytest

from evaluacion.rar7z import (MENSAJE_INSTALAR, Entrada, ErrorVerificacion, huella, listar, localizar_7zip,
                              parsear_listado, ruta_segura, verificar, verificar_extraido, version_7zip)

CONTENIDO = {
    "wavs/Sin separar canales/S26_falta_separar_canales/s26.objects.04.wav": bytes(range(256)) * 40,
    "phrases/S26/s26.objects.04.channel1.phrases": "0.0\t3.1\t#\n3.1\t5.0\tel búho\n".encode("utf-8"),
    "phrases/S26/s26.objects.04.channel2.phrases": "0.0\t5.0\t#\n".encode("utf-8"),
}


@pytest.fixture
def comprimido(tmp_path, siete_zip):
    """Fábrica: crea una carpeta 'extraidos' y un archivo comprimido con las mismas rutas (formato 7z o zip)."""
    def fabricar(formato="7z"):
        extraidos = tmp_path / f"extraidos_{formato}"
        for ruta, datos in CONTENIDO.items():
            destino = extraidos / ruta
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(datos)
        archivo = tmp_path / f"sintetico.{formato}"
        r = subprocess.run([siete_zip, "a", f"-t{formato}", "-bso0", "-bsp0", str(archivo), "wavs", "phrases"],
                           cwd=extraidos, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return archivo, extraidos
    return fabricar


# --- localización de 7-Zip --------------------------------------------------------------------------------------

def test_localiza_7zip_de_la_variable_siete_zip(tmp_path):
    exe = tmp_path / "7z.exe"
    exe.write_bytes(b"")
    assert localizar_7zip({"SIETE_ZIP": str(exe)}) == exe


def test_7zip_ausente_da_un_mensaje_de_instalacion(monkeypatch, tmp_path):
    monkeypatch.setattr("evaluacion.rar7z.shutil.which", lambda nombre: None)
    with pytest.raises(ErrorVerificacion) as e:
        localizar_7zip({"ProgramFiles": str(tmp_path)})  # sin SIETE_ZIP ni 7-Zip instalado ahí
    assert str(e.value) == MENSAJE_INSTALAR
    assert "7-zip.org" in MENSAJE_INSTALAR and "SIETE_ZIP" in MENSAJE_INSTALAR


def test_version_de_7zip(siete_zip):
    assert version_7zip(Path(siete_zip)).startswith("7-Zip")


# --- rutas inseguras y listado ----------------------------------------------------------------------------------

@pytest.mark.parametrize("ruta", ["../evil.wav", "wavs/../../evil.wav", "wavs\\..\\evil.wav", "/etc/passwd",
                                  "\\\\servidor\\x.wav", "C:\\Windows\\x.wav", "c:/x.wav", "", "   "])
def test_ruta_insegura_se_rechaza(ruta):
    with pytest.raises(ErrorVerificacion):
        ruta_segura(ruta)


def test_ruta_segura_normaliza_separadores():
    assert ruta_segura("wavs\\Sin separar canales\\S26\\a.wav") == "wavs/Sin separar canales/S26/a.wav"
    assert ruta_segura("./phrases/S26/a.phrases") == "phrases/S26/a.phrases"


def test_listado_con_ruta_insegura_falla_nombrando_la_entrada():
    texto = "Path = wavs\\ok.wav\nSize = 3\nCRC = 00000001\n\nPath = ..\\evil.wav\nSize = 3\nCRC = 00000002\n"
    with pytest.raises(ErrorVerificacion, match=r"evil\.wav"):
        parsear_listado(texto)


def test_parsear_listado_reconoce_archivos_y_carpetas():
    texto = ("Path = wavs\nFolder = +\nSize = 0\n\n"
             "Path = wavs\\S26\\a.wav\nFolder = -\nSize = 10\nPacked Size = 8\nCRC = BB4E71F7\nAttributes = A\n")
    listado = parsear_listado(texto)
    assert listado["wavs"].es_carpeta is True and listado["wavs"].crc32 is None
    assert listado["wavs/S26/a.wav"] == Entrada("wavs/S26/a.wav", 10, 0xBB4E71F7, False)


@pytest.mark.parametrize("formato", ["7z", "zip"])
def test_listar_un_comprimido_sintetico(comprimido, formato):
    archivo, extraidos = comprimido(formato)
    listado = listar(archivo)
    archivos = {r: e for r, e in listado.items() if not e.es_carpeta}
    assert set(archivos) == set(CONTENIDO)  # rutas con espacios y separadores normalizados
    for ruta, datos in CONTENIDO.items():
        assert archivos[ruta].tamano == len(datos)
        assert archivos[ruta].crc32 == zlib.crc32(datos) & 0xFFFFFFFF


def test_listar_un_archivo_inexistente_o_no_comprimido(tmp_path, siete_zip):
    with pytest.raises(ErrorVerificacion, match="no existe"):
        listar(tmp_path / "no_existe.rar")
    falso = tmp_path / "falso.rar"
    falso.write_bytes(b"esto no es un RAR")
    with pytest.raises(ErrorVerificacion, match="no pudo listar"):
        listar(falso)


# --- verificación de los extraídos ------------------------------------------------------------------------------

def test_extraidos_que_coinciden_devuelven_tamano_crc_y_sha256(comprimido):
    archivo, extraidos = comprimido("7z")
    resultados = verificar(archivo, extraidos, list(CONTENIDO))
    assert [r.ruta_interna for r in resultados] == list(CONTENIDO)
    for r in resultados:
        datos = CONTENIDO[r.ruta_interna]
        assert r.tamano == len(datos)
        assert r.crc32 == f"{zlib.crc32(datos) & 0xFFFFFFFF:08X}"
        assert r.sha256 == hashlib.sha256(datos).hexdigest()


def test_un_byte_cambiado_falla_por_crc(comprimido):
    archivo, extraidos = comprimido("7z")
    wav = extraidos / "wavs/Sin separar canales/S26_falta_separar_canales/s26.objects.04.wav"
    datos = bytearray(wav.read_bytes())
    datos[100] ^= 0xFF  # mismo tamaño, contenido distinto
    wav.write_bytes(bytes(datos))
    with pytest.raises(ErrorVerificacion, match=r"CRC32 [0-9A-F]{8} distinto"):
        verificar(archivo, extraidos, ["wavs/Sin separar canales/S26_falta_separar_canales/s26.objects.04.wav"])


def test_tamano_distinto_falla(comprimido):
    archivo, extraidos = comprimido("7z")
    anotacion = extraidos / "phrases/S26/s26.objects.04.channel2.phrases"
    anotacion.write_bytes(anotacion.read_bytes() + b"\n")
    with pytest.raises(ErrorVerificacion, match="tamaño"):
        verificar(archivo, extraidos, ["phrases/S26/s26.objects.04.channel2.phrases"])


def test_extraido_ausente_falla(comprimido):
    archivo, extraidos = comprimido("7z")
    (extraidos / "phrases/S26/s26.objects.04.channel1.phrases").unlink()
    with pytest.raises(ErrorVerificacion, match="falta el archivo extraído"):
        verificar(archivo, extraidos, ["phrases/S26/s26.objects.04.channel1.phrases"])


def test_ruta_que_no_esta_en_el_comprimido_falla(comprimido):
    archivo, extraidos = comprimido("7z")
    with pytest.raises(ErrorVerificacion, match="no está en"):
        verificar(archivo, extraidos, ["phrases/S26/s26.objects.05.channel1.phrases"])


def test_ruta_pedida_insegura_falla_antes_de_leer(comprimido):
    archivo, extraidos = comprimido("7z")
    with pytest.raises(ErrorVerificacion, match=r"'\.\.'"):
        verificar(archivo, extraidos, ["../fuera.wav"])


def test_verificar_extraido_rechaza_carpetas_y_entradas_sin_crc(tmp_path):
    archivo = tmp_path / "a.bin"
    archivo.write_bytes(b"abc")
    with pytest.raises(ErrorVerificacion, match="carpeta"):
        verificar_extraido(archivo, Entrada("a.bin", 3, None, True))
    with pytest.raises(ErrorVerificacion, match="no tiene CRC"):
        verificar_extraido(archivo, Entrada("a.bin", 3, None, False))


def test_la_verificacion_no_modifica_nada(comprimido):
    archivo, extraidos = comprimido("7z")
    antes = {p: huella(p) for p in [archivo, *extraidos.rglob("*")] if p.is_file()}
    verificar(archivo, extraidos, list(CONTENIDO))
    despues = {p: huella(p) for p in [archivo, *extraidos.rglob("*")] if p.is_file()}
    assert antes == despues
    assert sorted(p.name for p in archivo.parent.iterdir()) == sorted([archivo.name, extraidos.name])  # nada extraído
