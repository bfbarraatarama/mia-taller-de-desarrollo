"""Contratos de la Etapa 4 (solo biblioteca estándar): entradas y `transcription.json`.

- `validar_audio`: WAV 16 kHz, mono, PCM16; devuelve la duración de la cabecera.
- `validar_diarizacion`: mismas reglas y mensajes que `validar_diarizacion` de la Etapa 2 (PR #8, `contrato.py`).
- `validar_asr`: reglas de `validate_asr_contract` de la Etapa 3 (PR #9), con su margen de 1,0 s; devuelve una
  copia recortada a la duración del audio y los conteos de lo recortado o descartado.
- `validar_transcripcion`: contrato de salida (spec «Estructura de transcription.json» y «Valores de las
  intervenciones»).
"""

from __future__ import annotations

import copy
import math
import wave
from pathlib import Path

from errores import AsociacionError

FS = 16000
CANALES = 1
BYTES_POR_MUESTRA = 2
MARGEN_ASR_S = 1.0
CAMPOS_INTERVENCION = ("start", "end", "speaker", "name", "text", "overlap", "ambiguous")


def _es_numero(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def techo_3_decimales(duracion: float) -> float:
    """Mayor valor con 3 decimales que no supera `duracion` (mismo criterio que la Etapa 2)."""
    d3 = math.floor(duracion * 1000) / 1000
    if d3 > duracion:
        d3 = (math.floor(duracion * 1000) - 1) / 1000
    return max(d3, 0.0)


# ---------- audio.wav ----------


def validar_audio(ruta: str | Path) -> float:
    ruta = Path(ruta)
    if not ruta.is_file():
        raise AsociacionError("audio", f"{ruta}: no existe", archivo=ruta)
    try:
        with wave.open(str(ruta), "rb") as w:
            fs, canales, ancho, cuadros = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
    except (wave.Error, EOFError) as e:
        raise AsociacionError("audio", f"{ruta}: no es un WAV PCM legible ({e})", archivo=ruta) from e
    problemas = []
    if canales != CANALES:
        problemas.append(f"canales: esperado {CANALES}, encontrado {canales}")
    if fs != FS:
        problemas.append(f"frecuencia: esperado {FS} Hz, encontrado {fs} Hz")
    if ancho != BYTES_POR_MUESTRA:
        problemas.append(f"profundidad: esperado {8 * BYTES_POR_MUESTRA} bits, encontrado {8 * ancho} bits")
    if problemas:
        raise AsociacionError("audio", f"{ruta}: audio no normalizado ({'; '.join(problemas)})", archivo=ruta)
    return cuadros / fs


# ---------- diarization.json (copia de las reglas de la Etapa 2) ----------

CLAVES_RAIZ_DIARIZACION = {"segments"}
CLAVES_SEGMENTO_DIARIZACION = {"start", "end", "speaker"}


def validar_diarizacion(datos, duracion: float) -> list[str]:
    """Devuelve todas las violaciones, cada una con su ubicación. Lista vacía = válido."""
    if not isinstance(datos, dict):
        return ["raíz: no es un objeto JSON"]
    violaciones = []
    for clave in sorted(set(datos) - CLAVES_RAIZ_DIARIZACION):
        violaciones.append(f"raíz: campo no permitido '{clave}'")
    if "segments" not in datos:
        violaciones.append("raíz: falta 'segments'")
        return violaciones
    segmentos = datos["segments"]
    if not isinstance(segmentos, list):
        violaciones.append("raíz: 'segments' no es una lista")
        return violaciones

    inicio_previo = None
    for i, seg in enumerate(segmentos):
        lugar = f"segments[{i}]"
        if not isinstance(seg, dict):
            violaciones.append(f"{lugar}: no es un objeto")
            continue
        for clave in sorted(set(seg) - CLAVES_SEGMENTO_DIARIZACION):
            violaciones.append(f"{lugar}: campo no permitido '{clave}'")
        for clave in sorted(CLAVES_SEGMENTO_DIARIZACION - set(seg)):
            violaciones.append(f"{lugar}: falta '{clave}'")
        inicio, fin = seg.get("start"), seg.get("end")
        for nombre, valor in (("start", inicio), ("end", fin)):
            if nombre in seg and not _es_numero(valor):
                violaciones.append(f"{lugar}: '{nombre}' no es un número finito ({valor!r})")
        if "speaker" in seg and not (isinstance(seg["speaker"], str) and seg["speaker"].strip()):
            violaciones.append(f"{lugar}: 'speaker' vacío o no es texto ({seg['speaker']!r})")
        if _es_numero(inicio) and _es_numero(fin):
            if inicio < 0:
                violaciones.append(f"{lugar}: start={inicio} es negativo")
            if not inicio < fin:
                violaciones.append(f"{lugar}: start={inicio} no es menor que end={fin}")
            if fin > duracion:
                violaciones.append(f"{lugar}: end={fin} supera la duración del audio ({duracion} s)")
        if _es_numero(inicio):
            if inicio_previo is not None and inicio < inicio_previo:
                violaciones.append(f"{lugar}: start={inicio} rompe el orden por start (anterior {inicio_previo})")
            inicio_previo = inicio
    return violaciones


# ---------- asr.json ----------


def _violaciones_asr(datos, duracion: float) -> list[str]:
    if not isinstance(datos, dict):
        return ["raíz: no es un objeto JSON"]
    violaciones = []
    idioma = datos.get("language")
    if not (isinstance(idioma, str) and idioma.strip()):
        violaciones.append("raíz: 'language' falta o está vacío")
    segmentos = datos.get("segments")
    if not isinstance(segmentos, list):
        return violaciones + ["raíz: 'segments' falta o no es una lista"]
    limite = duracion + MARGEN_ASR_S

    def tiempos(lugar: str, item: dict) -> None:
        for clave in ("start", "end"):
            if clave not in item:
                violaciones.append(f"{lugar}: falta '{clave}'")
            elif not (_es_numero(item[clave]) and item[clave] >= 0):
                violaciones.append(f"{lugar}: '{clave}' no es un número finito no negativo ({item[clave]!r})")
        inicio, fin = item.get("start"), item.get("end")
        if _es_numero(inicio) and _es_numero(fin):
            if not inicio < fin:
                violaciones.append(f"{lugar}: start={inicio} no es menor que end={fin}")
            if fin > limite:
                violaciones.append(f"{lugar}: end={fin} supera la duración del audio ({duracion} s) "
                                   f"más el margen de {MARGEN_ASR_S} s de la Etapa 3")

    for i, seg in enumerate(segmentos):
        lugar = f"segments[{i}]"
        if not isinstance(seg, dict):
            violaciones.append(f"{lugar}: no es un objeto")
            continue
        tiempos(lugar, seg)
        if not (isinstance(seg.get("text"), str) and seg["text"].strip()):
            violaciones.append(f"{lugar}: 'text' falta o está vacío")
        palabras = seg.get("words")
        if not isinstance(palabras, list):
            violaciones.append(f"{lugar}: 'words' falta o no es una lista")
            continue
        for j, w in enumerate(palabras):
            lugar_w = f"{lugar}.words[{j}]"
            if not isinstance(w, dict):
                violaciones.append(f"{lugar_w}: no es un objeto")
                continue
            tiempos(lugar_w, w)
            if not (isinstance(w.get("word"), str) and w["word"].strip()):
                violaciones.append(f"{lugar_w}: 'word' falta o está vacía")
    return violaciones


def validar_asr(datos, duracion: float, archivo: str | Path | None = None) -> tuple[dict, dict]:
    """Valida y devuelve (copia redondeada a 3 decimales y recortada a la duración, conteos de recortes)."""
    violaciones = _violaciones_asr(datos, duracion)
    if violaciones:
        nombre = archivo or "asr.json"
        raise AsociacionError("asr", f"{nombre} no cumple el contrato ({len(violaciones)} violaciones; "
                              f"primera: {violaciones[0]})", archivo=archivo, violaciones=violaciones)
    d3 = techo_3_decimales(duracion)
    recortes = dict.fromkeys(("segmentos_recortados", "segmentos_descartados",
                              "palabras_recortadas", "palabras_descartadas"), 0)

    def acotar(item: dict, tipo: str) -> bool:
        """Redondea y recorta `item` en el lugar; devuelve False si queda vacío."""
        inicio, fin = round(item["start"], 3), min(round(item["end"], 3), d3)
        if inicio >= fin:
            recortes[f"{tipo}_descartadas" if tipo == "palabras" else f"{tipo}_descartados"] += 1
            return False
        if item["end"] > duracion:
            recortes[f"{tipo}_recortadas" if tipo == "palabras" else f"{tipo}_recortados"] += 1
        item["start"], item["end"] = inicio, fin
        return True

    normal = copy.deepcopy(datos)
    segmentos = []
    for seg in normal["segments"]:
        habia_palabras = bool(seg["words"])
        seg["words"] = [w for w in seg["words"] if acotar(w, "palabras")]
        if habia_palabras and not seg["words"]:
            recortes["segmentos_descartados"] += 1
            continue
        if acotar(seg, "segmentos"):
            segmentos.append(seg)
    normal["segments"] = segmentos
    return normal, recortes


# ---------- transcription.json ----------


def validar_transcripcion(datos, duracion: float, etiquetas) -> list[str]:
    """Devuelve todas las violaciones del contrato de salida. Lista vacía = válido."""
    if not isinstance(datos, dict):
        return ["raíz: no es un objeto JSON"]
    violaciones = [f"raíz: campo no permitido '{c}'" for c in sorted(set(datos) - {"segments"})]
    segmentos = datos.get("segments")
    if not isinstance(segmentos, list):
        return violaciones + ["raíz: 'segments' falta o no es una lista"]
    etiquetas = set(etiquetas)
    inicio_previo = None
    for i, s in enumerate(segmentos):
        lugar = f"segments[{i}]"
        if not isinstance(s, dict):
            violaciones.append(f"{lugar}: no es un objeto")
            continue
        violaciones += [f"{lugar}: campo no permitido '{c}'" for c in sorted(set(s) - set(CAMPOS_INTERVENCION))]
        violaciones += [f"{lugar}: falta el campo '{c}'" for c in CAMPOS_INTERVENCION if c not in s]
        inicio, fin = s.get("start"), s.get("end")
        for nombre, valor in (("start", inicio), ("end", fin)):
            if not _es_numero(valor):
                violaciones.append(f"{lugar}: '{nombre}' no es un número finito ({valor!r})")
            elif round(valor, 3) != valor:
                violaciones.append(f"{lugar}: '{nombre}'={valor} tiene más de 3 decimales")
        if _es_numero(inicio) and _es_numero(fin):
            if inicio < 0 or not inicio < fin:
                violaciones.append(f"{lugar}: no cumple 0 <= start < end (start={inicio}, end={fin})")
            if fin > duracion:
                violaciones.append(f"{lugar}: end={fin} supera la duración del audio ({duracion} s)")
            if inicio_previo is not None and inicio < inicio_previo:
                violaciones.append(f"{lugar}: start={inicio} rompe el orden por start (anterior {inicio_previo})")
            inicio_previo = inicio
        if "speaker" in s and s["speaker"] is not None and s["speaker"] not in etiquetas:
            violaciones.append(f"{lugar}: 'speaker'={s['speaker']!r} no está en diarization.json")
        if "name" in s and s["name"] is not None and not (isinstance(s["name"], str) and s["name"].strip()):
            violaciones.append(f"{lugar}: 'name' vacío o no es texto ({s['name']!r})")
        texto = s.get("text")
        if "text" in s and not (isinstance(texto, str) and texto.strip() and texto == texto.strip()):
            violaciones.append(f"{lugar}: 'text' vacío o con espacios en los extremos ({texto!r})")
        for marca in ("overlap", "ambiguous"):
            if marca in s and not isinstance(s[marca], bool):
                violaciones.append(f"{lugar}: '{marca}' no es booleano ({s[marca]!r})")
    return violaciones
