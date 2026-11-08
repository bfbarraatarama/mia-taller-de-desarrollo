"""Tarea 5.3 — nivel 2: integración Etapa 1 → Etapa 2 en CPU con el modelo real (design.md §10.1).

Recorre cada WAV de `DIARIZACION_AUDIOS_CPU` (grabaciones hechas con la interfaz de la Etapa 1, con su
reporte `.json`) y aplica los bloques A (contrato de la Etapa 1), B (recepción), C (salida) y D
(compatibilidad). Por grabación escribe `tests/reportes/integracion_<nombre>.json` para la revisión manual.

    $env:DIARIZACION_AUDIOS_CPU = (Resolve-Path PoC/paso1_captura/grabaciones/nivel2).Path
    python -m pytest PoC/paso2_diarizacion -m slow -rs
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

import integracion
from conftest import MODULO
from contrato import validar_diarizacion, validar_par
from diarizar import diarizar
from resultados import NOMBRE_JSON, NOMBRE_META, carpeta_reunion

REPORTES = MODULO / "tests" / "reportes"
ETIQUETA = re.compile(r"SPEAKER_\d{2}")


def _wavs() -> list[Path]:
    ruta = os.environ.get("DIARIZACION_AUDIOS_CPU")
    return sorted(Path(ruta).glob("*.wav")) if ruta and Path(ruta).is_dir() else []


WAVS = _wavs()
_SIN_AUDIOS = pytest.param(None, marks=pytest.mark.skip(
    reason="falta DIARIZACION_AUDIOS_CPU o no tiene WAV (grabaciones de 30 a 60 s de la interfaz del paso 1)"))
PARAMETROS = [pytest.param(w, id=w.stem) for w in WAVS] or [_SIN_AUDIOS]


@pytest.mark.slow
@pytest.mark.parametrize("wav", PARAMETROS)
def test_integracion_etapa1_etapa2(wav, token_hf, ffmpeg):
    # A. Contrato de la Etapa 1 (falla antes de diarizar si no se cumple).
    antes = integracion.huellas_etapa1(wav) if integracion.ruta_reporte(wav).is_file() else None
    info = integracion.verificar_bloque_a(wav)

    # B. Recepción: la Etapa 2 acepta el WAV tal como lo dejó la Etapa 1 y pyannote corre en CPU.
    r = diarizar(wav, device="cpu")
    carpeta = Path(r["carpeta"])

    # C. Salida: contrato al 100 %, etiquetas SPEAKER_NN, meta en CPU con la misma duración, par consistente.
    datos = json.loads((carpeta / NOMBRE_JSON).read_text(encoding="utf-8"))
    meta = json.loads((carpeta / NOMBRE_META).read_text(encoding="utf-8"))
    assert validar_diarizacion(datos, info.duracion) == []
    segs = datos["segments"]
    assert len(segs) >= 1, f"{wav.name}: diarization.json sin segmentos"
    etiquetas = {s["speaker"] for s in segs}
    assert etiquetas and all(ETIQUETA.fullmatch(e) for e in etiquetas), etiquetas
    assert meta["dispositivo"] == "cpu"
    assert meta["audio"]["duracion_s"] == info.duracion
    assert meta["hablantes"] == len(etiquetas) and meta["segmentos"] == len(segs)
    assert validar_par(carpeta / NOMBRE_JSON, carpeta / NOMBRE_META) == []

    # D. Compatibilidad: originales intactos y resultados en <carpeta>/<nombre>/ sin pisar <nombre>.json.
    integracion.verificar_bloque_d(wav, antes, carpeta)

    # Reporte para la revisión manual (tarea 5.5).
    REPORTES.mkdir(parents=True, exist_ok=True)
    resumen = integracion.resumen_revision(wav, info, datos, meta)
    (REPORTES / f"integracion_{wav.stem}.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.mark.slow
def test_carpetas_de_resultados_distintas_por_grabacion():
    if not WAVS:
        pytest.skip("falta DIARIZACION_AUDIOS_CPU o no tiene WAV")
    carpetas = [carpeta_reunion(w).resolve() for w in WAVS]
    assert len(set(carpetas)) == len(WAVS)
    assert not any(c == integracion.ruta_reporte(w).resolve() for c, w in zip(carpetas, WAVS))
