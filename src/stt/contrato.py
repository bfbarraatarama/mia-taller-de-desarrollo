"""Conversión y validación de asr.json, sin dependencias de inferencia."""

from __future__ import annotations

import math

from ..tiempos import cuantizar_intervalo

LANGUAGE = "es"
DURATION_TOLERANCE_S = 1.0


def _is_time(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def build_asr(result: dict, language: str = LANGUAGE) -> dict:
    """
    Convert a Whisper result into the asr.json contract.

    Segments without text are dropped, as are words with empty text or
    invalid timing. A segment with unusable timing retains its text and
    valid words, with both interval endpoints null.
    """
    segments = []
    for seg in result.get("segments", []):
        text = seg.get("text", "").strip()
        if not text:
            if any(w.get("word", "").strip() for w in seg.get("words", [])):
                raise ValueError("Segment: empty text with non-empty words")
            continue

        words = []
        for w in seg.get("words", []):
            word = w.get("word", "").strip()
            w_start, w_end = w.get("start"), w.get("end")
            if not word:
                continue
            if not _is_time(w_start) or not _is_time(w_end) or w_start >= w_end:
                continue
            inicio, fin = cuantizar_intervalo(w_start, w_end)
            words.append({"word": word, "start": inicio, "end": fin})

        inicio, fin = seg.get("start"), seg.get("end")
        if not _is_time(inicio) or not _is_time(fin) or inicio >= fin:
            inicio, fin = None, None
        else:
            inicio, fin = cuantizar_intervalo(inicio, fin)
        segments.append({
            "start": inicio,
            "end": fin,
            "text": text,
            "words": words,
        })

    return {"language": language, "segments": segments}


def validate_asr_contract(asr: dict, audio_duration: float | None = None) -> None:
    """
    Validate asr.json structure against the contract.

    Args:
        asr: Dict with structure {"language": str, "segments": [...]}.
        audio_duration: If given, segment and word ends cannot exceed it
            (beyond a small tolerance).

    Raises:
        ValueError: If structure or semantics are invalid.
    """
    if not isinstance(asr, dict):
        raise ValueError("ASR output must be a dict")

    language = asr.get("language")
    if not isinstance(language, str) or not language.strip():
        raise ValueError("ASR output must have a non-empty 'language'")

    segments = asr.get("segments")
    if not isinstance(segments, list):
        raise ValueError("'segments' must be a list")

    limit = None if audio_duration is None else audio_duration + DURATION_TOLERANCE_S

    def check_times(label: str, item: dict) -> None:
        for key in ("start", "end"):
            if key not in item:
                raise ValueError(f"{label} missing '{key}'")
        start, end = item["start"], item["end"]
        if not _is_time(start) or not _is_time(end):
            raise ValueError(f"{label}: 'start' and 'end' must be finite, non-negative numbers")
        if start >= end:
            raise ValueError(f"{label}: start ({start}) must be < end ({end})")
        if limit is not None and end > limit:
            raise ValueError(f"{label}: end ({end}) exceeds audio duration ({audio_duration})")

    for i, seg in enumerate(segments):
        label = f"Segment {i}"
        if not isinstance(seg, dict):
            raise ValueError(f"{label} must be a dict")
        if not ("start" in seg and "end" in seg and seg["start"] is None and seg["end"] is None):
            check_times(label, seg)

        text = seg.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{label}: 'text' must be non-empty string")

        words = seg.get("words")
        if not isinstance(words, list):
            raise ValueError(f"{label}: 'words' must be a list")

        for j, w in enumerate(words):
            w_label = f"{label}, word {j}"
            if not isinstance(w, dict):
                raise ValueError(f"{w_label} must be a dict")
            check_times(w_label, w)
            word = w.get("word")
            if not isinstance(word, str) or not word.strip():
                raise ValueError(f"{w_label}: 'word' must be non-empty string")
