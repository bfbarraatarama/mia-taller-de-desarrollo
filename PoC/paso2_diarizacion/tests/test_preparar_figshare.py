"""Tarea 6.2: verificación de originales, de los extraídos contra el listado y selección de S26 (datos sintéticos)."""

import hashlib
import json
import subprocess

import pytest

from evaluacion.preparar_figshare import (ErrorPreparacion, normalizar_seleccion, rutas_tarea, verificar_entradas,
                                          verificar_originales)

WAV_DIR = "wavs/Sin separar canales/S26_falta_separar_canales"
FRASES_DIR = "phrases/S26"


def _contenido(tarea: str) -> dict[str, bytes]:
    b = f"s26.objects.{tarea}"
    return {f"{WAV_DIR}/{b}.wav": (b"RIFF" + tarea.encode()) * 500,
            f"{FRASES_DIR}/{b}.channel1.phrases": f"0.0\t1.0\t#\n1.0\t2.0\thola {tarea}\n".encode(),
            f"{FRASES_DIR}/{b}.channel2.phrases": f"0.0\t2.0\t#\n".encode()}


def _hashes(ruta):
    datos = ruta.read_bytes()
    return {"bytes": len(datos), "md5": hashlib.md5(datos).hexdigest(), "sha256": hashlib.sha256(datos).hexdigest()}


@pytest.fixture
def dataset(tmp_path, siete_zip):
    """Caché sintética: extraidos/ con las tareas 03 y 04, y phrases.rar/wavs.rar (formato 7z) con lo mismo."""
    def fabricar(tareas=("03", "04"), extra: dict[str, bytes] | None = None):
        cache = tmp_path / "cache"
        extraidos = cache / "extraidos"
        archivos = {}
        for t in tareas:
            archivos.update(_contenido(t))
        archivos.update(extra or {})
        for ruta, datos in archivos.items():
            (extraidos / ruta).parent.mkdir(parents=True, exist_ok=True)
            (extraidos / ruta).write_bytes(datos)
        for rar, carpeta in (("wavs.rar", "wavs"), ("phrases.rar", "phrases")):
            r = subprocess.run([siete_zip, "a", "-t7z", "-bso0", "-bsp0", str(cache / rar), carpeta],
                               cwd=extraidos, capture_output=True, text=True)
            assert r.returncode == 0, r.stderr
        registro = {n: _hashes(cache / n) for n in ("phrases.rar", "wavs.rar")}
        return cache, extraidos, registro
    return fabricar


def test_seleccion_04_verificada_y_las_demas_ignoradas(dataset):
    cache, extraidos, registro = dataset()
    r = verificar_entradas(["04"], cache=cache, extraidos=extraidos, registro=registro)
    assert r["seleccion"] == ["04"] and r["ignoradas"] == ["03"] and r["tareas_en_los_rar"] == ["03", "04"]
    assert list(r["grabaciones"]) == ["figshare_v2_S26_objects_04"]
    archivos = r["grabaciones"]["figshare_v2_S26_objects_04"]["archivos"]
    assert set(archivos) == {"wav_completo", "channel1", "channel2"}
    for clave, a in archivos.items():
        datos = (extraidos / a["ruta"]).read_bytes()
        assert a["tamano"] == len(datos) and a["sha256"] == hashlib.sha256(datos).hexdigest()
        assert a["rar"] == ("wavs.rar" if clave == "wav_completo" else "phrases.rar")
    assert r["originales"] == registro


def test_sha256_distinto_del_lock_falla(dataset):
    cache, extraidos, registro = dataset()
    registro["wavs.rar"]["sha256"] = "0" * 64
    with pytest.raises(ErrorPreparacion, match=r"wavs\.rar: sha256"):
        verificar_entradas(["04"], cache=cache, extraidos=extraidos, registro=registro)


@pytest.mark.parametrize("campo, valor", [("bytes", 1), ("md5", "0" * 32)])
def test_tamano_o_md5_distintos_fallan(dataset, campo, valor):
    cache, extraidos, registro = dataset()
    registro["phrases.rar"][campo] = valor
    with pytest.raises(ErrorPreparacion, match=rf"phrases\.rar: {campo}"):
        verificar_originales(cache, registro)


def test_original_ausente_falla(dataset):
    cache, extraidos, registro = dataset()
    (cache / "phrases.rar").unlink()
    with pytest.raises(ErrorPreparacion, match="falta el original"):
        verificar_entradas(["04"], cache=cache, extraidos=extraidos, registro=registro)


def test_extraido_con_crc_distinto_falla(dataset):
    cache, extraidos, registro = dataset()
    wav = extraidos / rutas_tarea("04")["wav_completo"]
    datos = bytearray(wav.read_bytes())
    datos[10] ^= 0xFF
    wav.write_bytes(bytes(datos))
    with pytest.raises(ErrorPreparacion, match=r"CRC32 [0-9A-F]{8} distinto"):
        verificar_entradas(["04"], cache=cache, extraidos=extraidos, registro=registro)


def test_tarea_fuera_de_la_seleccion_se_ignora(dataset):
    cache, extraidos, registro = dataset()
    otra = extraidos / rutas_tarea("03")["channel1"]
    otra.write_bytes(b"alterado")  # la tarea 03 no coincide con su RAR, pero no está seleccionada
    r = verificar_entradas(["04"], cache=cache, extraidos=extraidos, registro=registro)
    assert list(r["grabaciones"]) == ["figshare_v2_S26_objects_04"] and r["ignoradas"] == ["03"]
    with pytest.raises(ErrorPreparacion, match="tamaño"):
        verificar_entradas(["03"], cache=cache, extraidos=extraidos, registro=registro)


@pytest.mark.parametrize("ruta_extra", [f"{FRASES_DIR}/s26.objetos.04.channel1.phrases",
                                        f"{FRASES_DIR}/s27.objects.04.channel1.phrases",
                                        f"{WAV_DIR}/s26.objects.04.channel1.wav",
                                        f"{FRASES_DIR}/s26.objects.04.channel1.wav"])
def test_nombre_fuera_del_patron_falla(dataset, ruta_extra):
    cache, extraidos, registro = dataset(extra={ruta_extra: b"x"})
    with pytest.raises(ErrorPreparacion, match=r"fuera del patrón|inesperado"):
        verificar_entradas(["04"], cache=cache, extraidos=extraidos, registro=registro)


def test_otras_sesiones_y_canales_separados_no_cuentan(dataset):
    extra = {"wavs/S26/s26.objects.04.channel1.wav": b"sep", "phrases/S27/s27.objects.04.channel1.phrases": b"x"}
    cache, extraidos, registro = dataset(extra=extra)
    r = verificar_entradas(["04"], cache=cache, extraidos=extraidos, registro=registro)
    assert r["tareas_en_los_rar"] == ["03", "04"]


def test_tarea_seleccionada_ausente_falla(dataset):
    cache, extraidos, registro = dataset(tareas=("03",))
    with pytest.raises(ErrorPreparacion, match="tarea 04 de S26 no tiene en los RAR"):
        verificar_entradas(["04"], cache=cache, extraidos=extraidos, registro=registro)


def test_normalizar_seleccion():
    assert normalizar_seleccion(["4", "04", 5]) == ["04", "05"]
    for mala in (["4a"], [], [" "]):
        with pytest.raises(ErrorPreparacion):
            normalizar_seleccion(mala)


def test_no_escribe_nada(dataset, tmp_path):
    cache, extraidos, registro = dataset()
    antes = sorted((p.relative_to(tmp_path), p.stat().st_size, p.stat().st_mtime_ns) for p in tmp_path.rglob("*"))
    verificar_entradas(["04"], cache=cache, extraidos=extraidos, registro=registro)
    despues = sorted((p.relative_to(tmp_path), p.stat().st_size, p.stat().st_mtime_ns) for p in tmp_path.rglob("*"))
    assert antes == despues


def test_registro_real_tiene_los_dos_rar():
    from evaluacion.preparar_figshare import leer_registro
    reg = leer_registro()
    assert set(reg) == {"phrases.rar", "wavs.rar"}
    assert reg["wavs.rar"]["bytes"] == 721854279 and len(reg["wavs.rar"]["sha256"]) == 64
    assert json.dumps(reg)  # serializable
