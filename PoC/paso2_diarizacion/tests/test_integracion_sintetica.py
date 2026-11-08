"""Tarea 5.4 — nivel 1: lógica del bloque A del nivel 2 (design.md §10.1) con archivos sintéticos.

Reutiliza `integracion.verificar_bloque_a`, la misma función que corre el test de integración real
(tarea 5.3), con `torchcodec=False` y `ffmpeg=False`: no usa pyannote, GPU, TorchCodec ni FFmpeg, y corre
en cualquier máquina. Los WAV y los reportes de la Etapa 1 se arman en `tmp_path`.

    python -m pytest PoC/paso2_diarizacion -k integracion
"""

from __future__ import annotations

import json

import pytest

import integracion
from conftest import escribir_wav

ESTADO_INTERRUMPIDA = "grabando (si queda así, la grabación se interrumpió)"


def _reporte_completo(nombre_wav: str, procesable: bool = True) -> dict:
    """Reporte final de la Etapa 1 con la forma de `captura.py` (solo los campos que mira el bloque A)."""
    return {
        "archivo": nombre_wav,
        "estado": "completa",
        "modo": "manual",
        "pruebas": [
            {"prueba": "ambas fuentes registran señal", "ok": True},
            {"prueba": "sin pérdidas", "ok": True},
            {"prueba": "sin desincronización", "ok": True},
            {"prueba": integracion.PRUEBA_PROCESABLE, "ok": procesable},
        ],
    }


def _reporte_interrumpido(nombre_wav: str) -> dict:
    """Reporte inicial que queda tras un cierre forzado: sin pruebas finales."""
    return {"archivo": nombre_wav, "estado": ESTADO_INTERRUMPIDA, "modo": "manual", "dispositivos": []}


def _grabacion(tmp_path, nombre="2026_11_08_10_00_00", segundos=31.0, reporte="completa"):
    """Escribe <nombre>.wav (16 kHz, mono, PCM16) y, según `reporte`, su <nombre>.json de la Etapa 1."""
    wav = escribir_wav(tmp_path / f"{nombre}.wav", segundos=segundos)
    if reporte is None:  # sin reporte de la Etapa 1
        return wav
    contenido = {"completa": lambda: _reporte_completo(wav.name),
                 "procesable_falla": lambda: _reporte_completo(wav.name, procesable=False),
                 "interrumpida": lambda: _reporte_interrumpido(wav.name),
                 "procesando": lambda: {"archivo": wav.name, "estado": "procesando"}}[reporte]()
    integracion.ruta_reporte(wav).write_text(json.dumps(contenido, ensure_ascii=False), encoding="utf-8")
    return wav


def _bloque_a(wav):
    return integracion.verificar_bloque_a(wav, torchcodec=False, ffmpeg=False)


# 1 y 2: casos que se aceptan -----------------------------------------------------------------------

def test_integracion_1_completa_y_procesable_se_acepta(tmp_path):
    wav = _grabacion(tmp_path, reporte="completa")
    info = _bloque_a(wav)
    assert info.estado == "completa" and info.interrumpida is False
    assert info.duracion == 31.0 and info.cuadros == 31 * 16000


def test_integracion_2_interrumpida_se_acepta(tmp_path):
    wav = _grabacion(tmp_path, reporte="interrumpida", segundos=32.5)
    info = _bloque_a(wav)
    assert info.estado == ESTADO_INTERRUMPIDA and info.interrumpida is True
    assert info.duracion == 32.5 and info.cuadros == 520000


# 3 a 8: casos que se rechazan por el motivo esperado ------------------------------------------------

def test_integracion_3_sin_reporte_se_rechaza(tmp_path):
    wav = _grabacion(tmp_path, reporte=None)
    with pytest.raises(AssertionError, match=r"falta el reporte de la Etapa 1 \(2026_11_08_10_00_00\.json\)"):
        _bloque_a(wav)


def test_integracion_4_wav_truncado_se_rechaza_por_lectura_incompleta(tmp_path):
    wav = _grabacion(tmp_path, reporte="completa")
    datos = wav.read_bytes()
    wav.write_bytes(datos[:-16000])  # se pierden 8000 cuadros; la cabecera sigue declarando 496 000
    declarados = 31 * 16000 * 2
    with pytest.raises(AssertionError, match=rf"lectura incompleta con wave \({declarados - 16000} de {declarados} bytes\)"):
        _bloque_a(wav)


def test_integracion_5_completa_con_salida_procesable_en_falla_se_rechaza(tmp_path):
    wav = _grabacion(tmp_path, reporte="procesable_falla")
    with pytest.raises(AssertionError, match=r"la prueba 'salida procesable \(mono, 16 kHz, PCM 16\)' .* no está en OK"):
        _bloque_a(wav)


def test_integracion_6_estado_desconocido_se_rechaza(tmp_path):
    wav = _grabacion(tmp_path, reporte="procesando")
    with pytest.raises(AssertionError, match=r"estado de la Etapa 1 'procesando'"):
        _bloque_a(wav)


def test_integracion_7_wav_de_15_s_se_rechaza_por_duracion(tmp_path):
    wav = _grabacion(tmp_path, reporte="completa", segundos=15.0)
    with pytest.raises(AssertionError, match=r"dura 15\.00 s, fuera de 30-60 s"):
        _bloque_a(wav)


def test_integracion_8_reporte_json_malformado_se_rechaza(tmp_path):
    wav = _grabacion(tmp_path, reporte=None)
    integracion.ruta_reporte(wav).write_text('{"estado": "completa", "pruebas": [', encoding="utf-8")
    with pytest.raises(AssertionError, match=r"no es JSON válido"):
        _bloque_a(wav)
