"""Correspondencia literal entre texto de STT y evidencia temporal por palabra."""

from __future__ import annotations

import re


def alinear(seg: dict) -> list[dict] | None:
    """Partición ordenada completa; solo admite espacios equivalentes.

    Los índices se refieren al texto original, sin normalizar ni reescribirlo.
    Una correspondencia incompleta o discordante no se usa para reconstruirlo.
    """
    if seg.get("_palabras_fuera_audio"):
        return None
    texto = seg["text"]
    cursor = 0
    resultado = []
    for w in seg["words"]:
        while cursor < len(texto) and texto[cursor].isspace():
            cursor += 1
        patron = r"\s+".join(re.escape(p) for p in w["word"].split())
        match = re.compile(patron).match(texto, cursor) if patron else None
        if match is None:
            return None
        fin = match.end()
        # No admitir una división artificial en el interior de una palabra.
        if fin < len(texto) and texto[fin - 1].isalnum() and texto[fin].isalnum():
            return None
        resultado.append({**w, "char_start": cursor, "char_end": fin})
        cursor = fin
    return resultado if resultado and not texto[cursor:].strip() else None


def intervalo_segmento(seg: dict) -> tuple[float, float] | None:
    """Un intervalo de segmento no puede contradecir las palabras conservadas."""
    a, b = seg["start"], seg["end"]
    if a is None or any(w["start"] < a or w["end"] > b for w in seg["words"]):
        return None
    return a, b
