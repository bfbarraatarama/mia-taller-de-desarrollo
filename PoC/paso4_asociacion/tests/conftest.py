"""Configuración común de las pruebas de la Etapa 4.

Cada test lleva el nombre del escenario de `openspec/changes/etapa-4-asociacion-etiquetado/specs/` que comprueba.
Los helpers arman reuniones chicas escritas a mano: un WAV de silencio y los JSON de las Etapas 2 y 3.
"""

from __future__ import annotations

import hashlib
import json
import sys
import wave
from pathlib import Path

import pytest

MODULO = Path(__file__).resolve().parents[1]
if str(MODULO) not in sys.path:
    sys.path.insert(0, str(MODULO))


def escribir_wav(ruta: Path, duracion: float, fs: int = 16000, canales: int = 1, ancho: int = 2) -> Path:
    """WAV de silencio con la cabecera pedida (solo biblioteca estándar)."""
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(canales)
        w.setsampwidth(ancho)
        w.setframerate(fs)
        w.writeframes(b"\x00" * round(duracion * fs) * canales * ancho)
    return ruta


def palabras(*items: tuple[str, float, float]) -> list[dict]:
    return [{"word": p, "start": s, "end": e} for p, s, e in items]


def segmento(*items: tuple[str, float, float]) -> dict:
    """Segmento de asr.json a partir de sus palabras."""
    ws = palabras(*items)
    return {"start": ws[0]["start"], "end": ws[-1]["end"], "text": " ".join(w["word"] for w in ws), "words": ws}


def crear_reunion(carpeta: Path, duracion: float, turnos: list[tuple[float, float, str]],
                  segmentos: list[dict]) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    escribir_wav(carpeta / "audio.wav", duracion)
    (carpeta / "diarization.json").write_text(json.dumps(
        {"segments": [{"start": s, "end": e, "speaker": h} for s, e, h in turnos]}), encoding="utf-8")
    (carpeta / "asr.json").write_text(json.dumps({"language": "es", "segments": segmentos}), encoding="utf-8")
    return carpeta


def sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def leer(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8"))


@pytest.fixture
def reunion(tmp_path) -> Path:
    """Dos hablantes que alternan sin superponerse; cada palabra cae dentro de un turno."""
    return crear_reunion(
        tmp_path / "reunion", 10.0,
        [(0.5, 3.0, "SPEAKER_00"), (3.5, 6.0, "SPEAKER_01"), (6.5, 9.0, "SPEAKER_00")],
        [segmento(("Arrancamos", 0.6, 1.2), ("con", 1.2, 1.4), ("el", 1.4, 1.5), ("presupuesto.", 1.5, 2.6)),
         segmento(("De", 3.6, 3.8), ("acuerdo.", 3.8, 4.5), ("Sigamos.", 4.6, 5.5)),
         segmento(("Cerramos", 6.6, 7.4), ("acá.", 7.4, 8.0))],
    )
