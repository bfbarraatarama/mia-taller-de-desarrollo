"""Tarea 6.3: validación por grabación de S26 (WAV estéreo, anotaciones, exceso terminal, correspondencia de canales).

Todo con datos sintéticos en tmp_path; los archivos reales de Figshare no se tocan.
"""

import hashlib
import re
import subprocess
import wave

import numpy as np
import pytest

from conftest import MODULO
from evaluacion import preparar_figshare as pf
from evaluacion.preparar_figshare import (ErrorPreparacion, Exclusion, leer_anotacion, leer_wav, ruta_separado,
                                          rutas_tarea, validar, validar_grabacion)

FS = 16000
SEGUNDOS = 3.0
CH1 = "0.0\t1.0\t#\n1.0\t2.5\thola\n2.5\t3.0\t#\n"
CH2 = "0.0\t0.8\tbuen día\n0.8\t3.005\t#\n"   # termina 0,005 s después del WAV: dentro de la tolerancia


def _escribir(ruta, muestras: np.ndarray, fs=FS, ancho=2):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    muestras = muestras if muestras.ndim == 2 else muestras[:, None]
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(muestras.shape[1])
        w.setsampwidth(ancho)
        w.setframerate(fs)
        w.writeframes(muestras.astype("<i2").tobytes() if ancho == 2 else muestras.astype("u1").tobytes())


def _voces(n):
    rng = np.random.default_rng(7)
    return (rng.normal(0, 3000, n).astype(np.int16), rng.normal(0, 3000, n).astype(np.int16))


@pytest.fixture
def grabacion(tmp_path):
    """Fábrica de una tarea 04 sintética en extraidos/: WAV completo estéreo, dos anotaciones y dos WAV separados."""
    def fabricar(ch1=CH1, ch2=CH2, invertir=False, fs=FS, canales=2, omitir=()):
        extraidos = tmp_path / "extraidos"
        n = int(SEGUNDOS * FS)
        izq, der = _voces(n)
        rutas = rutas_tarea("04")
        estereo = np.stack([izq, der], axis=1)
        _escribir(extraidos / rutas["wav_completo"], estereo if canales == 2 else izq, fs=fs)
        for clave, texto in (("channel1", ch1), ("channel2", ch2)):
            if clave not in omitir:
                (extraidos / rutas[clave]).parent.mkdir(parents=True, exist_ok=True)
                (extraidos / rutas[clave]).write_text(texto, encoding="utf-8")
        separados = (der, izq) if invertir else (izq, der)
        ruido = np.random.default_rng(1).integers(-30, 30, n)  # los separados no son copias exactas
        for c, sep in zip((1, 2), separados):
            if f"sep{c}" not in omitir:
                _escribir(extraidos / ruta_separado("04", c), np.clip(sep + ruido, -32768, 32767))
        return extraidos
    return fabricar


def test_grabacion_valida_registra_lo_medido(grabacion):
    v = validar_grabacion("04", grabacion())
    assert v["estado"] == "valida" and v["motivo"] is None
    assert v["recording_id"] == "figshare_v2_S26_objects_04"
    assert v["cuadros"] == 48000 and v["duracion_s"] == pytest.approx(3.0)
    a = v["anotaciones"]
    assert a["channel1"]["intervalos"] == 3 and a["channel1"]["intervalos_habla"] == 1
    assert a["channel1"]["exceso_terminal_s"] == 0.0
    assert a["channel2"]["exceso_terminal_s"] == pytest.approx(0.005)
    for c in ("channel1", "channel2"):
        k = v["correspondencia"][c]
        assert k["con_su_canal"] > 0.99 and abs(k["con_el_otro"]) < 0.05
    assert v["correspondencia"]["channel1"]["canal_estereo"] == "izquierdo"


def test_la_tolerancia_es_la_del_hito_2():
    assert pf.TOLERANCIA_FIN_S == 0.01
    assert pf.TOLERANCIA_ORDEN_S == 1e-4


@pytest.mark.parametrize("cambio, motivo", [
    ({"canales": 1}, r"1 canales \(se esperan 2\)"),
    ({"fs": 44100}, r"44100 Hz"),
    ({"omitir": ("channel2",)}, r"falta la anotación s26\.objects\.04\.channel2\.phrases"),
    ({"ch1": CH1.replace("3.0\t#", "3.3\t#")}, r"channel1: la anotación termina 0\.3000 s después"),
    ({"ch2": "0.0\t0.8\n"}, r"channel2\.phrases:1: línea mal formada"),
    ({"ch2": "0.0\t0.8\t   \n"}, r"channel2\.phrases:1: línea mal formada"),
    ({"ch1": "0.0\tuno\thola\n"}, r"channel1\.phrases:1: tiempos no numéricos"),
    ({"ch1": "1.0\t1.0\thola\n"}, r"channel1\.phrases:1: tiempos inválidos"),
    ({"ch1": "-0.5\t1.0\thola\n"}, r"tiempos inválidos"),
    ({"ch1": "0.0\tnan\thola\n"}, r"tiempos inválidos"),
    ({"ch1": "0.0\t2.0\thola\n1.0\t2.5\tchau\n"}, r"channel1\.phrases:2: inicio 1\.0 anterior al fin previo 2\.0"),
    ({"ch1": ""}, r"anotación vacía"),
    ({"invertir": True}, r"canales invertidos"),
    ({"omitir": ("sep2",)}, r"falta el WAV separado s26\.objects\.04\.channel2\.wav"),
])
def test_motivos_de_exclusion(grabacion, cambio, motivo):
    v = validar_grabacion("04", grabacion(**cambio))
    assert v["estado"] == "excluida"
    assert re.search(motivo, v["motivo"]), v["motivo"]


def test_exceso_justo_en_la_tolerancia_es_valido(grabacion):
    v = validar_grabacion("04", grabacion(ch1=CH1.replace("3.0\t#", "3.01\t#")))
    assert v["estado"] == "valida"
    assert v["anotaciones"]["channel1"]["exceso_terminal_s"] == pytest.approx(0.01)
    v = validar_grabacion("04", grabacion(ch1=CH1.replace("3.0\t#", "3.0101\t#")))
    assert v["estado"] == "excluida"


def test_solapamiento_dentro_de_la_tolerancia_de_orden_se_acepta(tmp_path):
    ruta = tmp_path / "a.phrases"
    ruta.write_text("﻿0.0\t1.0\t#\n0.99995\t2.0\thola\n", encoding="utf-8")  # con BOM, como lee el Hito 2
    assert [f[1:4] for f in leer_anotacion(ruta)] == [(0.0, 1.0, "#"), (0.99995, 2.0, "hola")]


def test_wav_truncado_se_excluye(grabacion):
    extraidos = grabacion()
    wav = extraidos / rutas_tarea("04")["wav_completo"]
    wav.write_bytes(wav.read_bytes()[:-1000])  # el encabezado declara más cuadros de los que hay
    v = validar_grabacion("04", extraidos)
    assert v["estado"] == "excluida" and "lectura incompleta" in v["motivo"]


def test_wav_8_bits_y_archivo_que_no_es_wav_se_excluyen(tmp_path):
    _escribir(tmp_path / "ocho.wav", np.full((100, 2), 128), ancho=1)
    with pytest.raises(Exclusion, match="8 bits"):
        leer_wav(tmp_path / "ocho.wav", canales=2)
    (tmp_path / "basura.wav").write_bytes(b"no es un wav")
    with pytest.raises(Exclusion, match="no es un WAV PCM legible"):
        leer_wav(tmp_path / "basura.wav")


def test_separado_con_otra_duracion_se_excluye(grabacion):
    extraidos = grabacion()
    _escribir(extraidos / ruta_separado("04", 1), np.zeros(1000, dtype=np.int16))
    v = validar_grabacion("04", extraidos)
    assert v["estado"] == "excluida" and "1000 cuadros" in v["motivo"]


def test_separado_con_un_cuadro_de_mas_al_final_se_acepta(grabacion):
    extraidos = grabacion()
    _, estereo = leer_wav(extraidos / rutas_tarea("04")["wav_completo"], canales=2)
    for c in (1, 2):
        _, sep = leer_wav(extraidos / ruta_separado("04", c), canales=1)
        _escribir(extraidos / ruta_separado("04", c), np.concatenate([sep[:, 0], [5]]))
    v = validar_grabacion("04", extraidos)
    assert v["estado"] == "valida"
    k = v["correspondencia"]["channel1"]
    assert k["diferencia_cuadros"] == 1 and k["cuadros_separado"] == estereo.shape[0] + 1
    assert k["con_su_canal"] > 0.99


@pytest.mark.parametrize("cambio", ["dos_de_mas", "uno_de_menos"])
def test_separado_con_otra_diferencia_de_cuadros_se_excluye(grabacion, cambio):
    extraidos = grabacion()
    _, sep = leer_wav(extraidos / ruta_separado("04", 2), canales=1)
    nuevo = np.concatenate([sep[:, 0], [0, 0]]) if cambio == "dos_de_mas" else sep[:-1, 0]
    _escribir(extraidos / ruta_separado("04", 2), nuevo)
    v = validar_grabacion("04", extraidos)
    assert v["estado"] == "excluida" and "hasta 1 cuadro de más al final" in v["motivo"]


def test_la_validacion_no_modifica_nada(grabacion, tmp_path):
    extraidos = grabacion()
    huellas = lambda: {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob("*") if p.is_file()}
    antes = huellas()
    validar_grabacion("04", extraidos)
    assert huellas() == antes


def test_validar_verifica_los_separados_contra_el_rar(grabacion, tmp_path, siete_zip):
    extraidos = grabacion()
    cache = extraidos.parent
    for rar, carpeta in (("wavs.rar", "wavs"), ("phrases.rar", "phrases")):
        r = subprocess.run([siete_zip, "a", "-t7z", "-bso0", "-bsp0", str(cache / rar), carpeta],
                           cwd=extraidos, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    registro = {}
    for n in ("phrases.rar", "wavs.rar"):
        d = (cache / n).read_bytes()
        registro[n] = {"bytes": len(d), "md5": hashlib.md5(d).hexdigest(), "sha256": hashlib.sha256(d).hexdigest()}
    r = validar(["04"], cache=cache, extraidos=extraidos, registro=registro)
    assert r["validacion"]["figshare_v2_S26_objects_04"]["estado"] == "valida"
    sep = extraidos / ruta_separado("04", 2)
    datos = bytearray(sep.read_bytes())
    datos[-1] ^= 0xFF
    sep.write_bytes(bytes(datos))  # un separado alterado es un fallo de integridad, no una exclusión
    with pytest.raises(ErrorPreparacion, match="CRC32"):
        validar(["04"], cache=cache, extraidos=extraidos, registro=registro)


def test_paridad_del_patron_con_armar_muestra():
    """El patrón de nombres y el criterio de orden coinciden con `hito-2/scripts/armar_muestra.py` (lectura del
    código fuente: ese script importa soundfile y lxml, que no están en el entorno de la Etapa 2)."""
    fuente = (MODULO.parents[1] / "hito-2" / "scripts" / "armar_muestra.py").read_text(encoding="utf-8")
    m = re.search(r'_UBA_ARCHIVO = re\.compile\(r"(.+?)", re\.I\)', fuente)
    assert m, "no se encontró _UBA_ARCHIVO en armar_muestra.py"
    assert m.group(1) == pf.PATRON_CANAL.pattern + r"\Z" and pf.PATRON_CANAL.flags & re.I
    assert "inicio < anterior - 1e-4" in fuente and 'split("\\t", 2)' in fuente
    assert "from validar_muestra import TOLERANCIA_FIN_FIGSHARE_S" in fuente
