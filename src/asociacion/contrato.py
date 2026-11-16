"""Contratos de la Etapa 4 (solo biblioteca estándar): entradas, `transcription.json` y `speakers.json`.

- `validar_audio`: WAV 16 kHz, mono, PCM16; devuelve la duración de la cabecera.
- `validar_diarizacion`: mismas reglas y mensajes que `validar_diarizacion` de la Etapa 2 (PR #8, `contrato.py`).
- `validar_asr`: reglas de `validate_asr_contract` de la Etapa 3 (PR #9), con su margen de 1,0 s; devuelve una
  copia con tiempos recortados al audio e intervalos de segmento nulos cuando no son representables.
- `validar_speakers`: contrato de speakers.json (spec «Contrato de speakers.json»).
- `validar_transcripcion`: contrato de salida (spec «Estructura de transcription.json» y «Valores de las
  intervenciones»).
"""

from __future__ import annotations

import copy
import math
import wave
from pathlib import Path

from ..tiempos import cuantizar_intervalo, techo_3_decimales
from .errores import AsociacionError
from .texto import alinear, intervalo_segmento

FS = 16000
CANALES = 1
BYTES_POR_MUESTRA = 2
MARGEN_ASR_S = 1.0
CAMPOS_HISTORICOS = ("start", "end", "speaker", "name", "text", "overlap", "ambiguous")
CAMPOS_INTERVENCION = (*CAMPOS_HISTORICOS, "timing", "speakers_detected", "source")


def _es_numero(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


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
        if not ("start" in seg and "end" in seg and seg["start"] is None and seg["end"] is None):
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
    recortes = dict.fromkeys(("segmentos_recortados", "intervalos_segmento_descartados",
                              "palabras_recortadas", "palabras_descartadas"), 0)

    def acotar(item: dict, tipo: str) -> bool:
        """Redondea y recorta `item` en el lugar; devuelve False si queda vacío."""
        if item["start"] is None:
            return False
        inicio, fin = item["start"], min(item["end"], d3)
        if inicio >= fin:
            recortes["palabras_descartadas" if tipo == "palabras" else "intervalos_segmento_descartados"] += 1
            return False
        inicio, fin = cuantizar_intervalo(inicio, fin)
        if item["end"] > duracion:
            recortes[f"{tipo}_recortadas" if tipo == "palabras" else f"{tipo}_recortados"] += 1
        item["start"], item["end"] = inicio, fin
        return True

    normal = copy.deepcopy(datos)
    for seg in normal["segments"]:
        seg.pop("_palabras_fuera_audio", None)
        originales = seg["words"]
        seg["words"] = [w for w in originales if acotar(w, "palabras")]
        # Una palabra que estaba fuera del dominio no respalda la atribución del segmento.
        if len(originales) != len(seg["words"]):
            seg["_palabras_fuera_audio"] = True
        if not acotar(seg, "segmentos"):
            seg["start"] = seg["end"] = None
    return normal, recortes


# ---------- transcription.json ----------


def validar_transcripcion(datos, duracion: float, etiquetas, *, asr=None) -> list[str]:
    """Valida el contrato histórico o actual; con ASR verifica la partición literal."""
    if not isinstance(datos, dict):
        return ["raíz: no es un objeto JSON"]
    violaciones = [f"raíz: campo no permitido '{c}'" for c in sorted(set(datos) - {"segments"})]
    segmentos = datos.get("segments")
    if not isinstance(segmentos, list):
        return violaciones + ["raíz: 'segments' falta o no es una lista"]
    etiquetas = set(etiquetas)
    inicio_previo = None
    fuente_previa = None
    actual = any(isinstance(s, dict) and set(s).intersection(set(CAMPOS_INTERVENCION) - set(CAMPOS_HISTORICOS))
                 for s in segmentos)
    campos = CAMPOS_INTERVENCION if actual else CAMPOS_HISTORICOS
    fuentes = {}
    for i, s in enumerate(segmentos):
        lugar = f"segments[{i}]"
        if not isinstance(s, dict):
            violaciones.append(f"{lugar}: no es un objeto")
            continue
        def error(mensaje):
            violaciones.append(f"{lugar}: {mensaje}")
        for c in sorted(set(s) - set(campos)):
            error(f"campo no permitido '{c}'")
        for c in campos:
            if c not in s:
                error(f"falta el campo '{c}'")
        inicio, fin = s.get("start"), s.get("end")
        timing = s.get("timing")
        desconocido = actual and timing == "unknown"
        if actual and timing not in ("word", "segment", "unknown"):
            error("timing inválido")
        if desconocido:
            if any(s.get(k) is not None for k in ("start", "end", "speaker", "name", "overlap", "speakers_detected")) or s.get("ambiguous") is not True:
                error("evidencia incompatible con timing unknown")
        else:
            for nombre, valor in (("start", inicio), ("end", fin)):
                if not _es_numero(valor):
                    error(f"'{nombre}' no es un número finito ({valor!r})")
                elif round(valor, 3) != valor:
                    error(f"'{nombre}'={valor} tiene más de 3 decimales")
            if _es_numero(inicio) and _es_numero(fin):
                if not 0 <= inicio < fin:
                    error("no cumple 0 <= start < end")
                if fin > duracion:
                    error(f"end={fin} supera la duración del audio ({duracion} s)")
                if not actual and inicio_previo is not None and inicio < inicio_previo:
                    error("rompe el orden por start")
                inicio_previo = inicio
            if not isinstance(s.get("overlap"), bool):
                error("'overlap' no es booleano")
        speaker = s.get("speaker")
        if speaker is not None and (not isinstance(speaker, str) or speaker not in etiquetas):
            error(f"'speaker'={speaker!r} no está en diarization.json")
        name = s.get("name")
        if name is not None and not (isinstance(name, str) and name.strip()):
            error("'name' vacío o no es texto")
        texto = s.get("text")
        if not (isinstance(texto, str) and texto.strip() and texto == texto.strip()):
            error("'text' vacío o con espacios en los extremos")
        if not isinstance(s.get("ambiguous"), bool):
            error("'ambiguous' no es booleano")
        if not actual:
            continue
        if speaker is None and (name is not None or s.get("ambiguous") is not True):
            error("atribución nula incompatible con name o ambiguous")
        if not desconocido:
            detectados = s.get("speakers_detected")
            ids = []
            if not isinstance(detectados, list):
                error("speakers_detected debe ser una lista")
            else:
                for d in detectados:
                    if (not isinstance(d, dict) or set(d) != {"speaker", "name"}
                            or not isinstance(d["speaker"], str) or d["speaker"] not in etiquetas
                            or (d["name"] is not None and (not isinstance(d["name"], str) or not d["name"].strip()))):
                        error("hablante detectado inválido")
                    else:
                        ids.append(d["speaker"])
                        if d["speaker"] == speaker and d["name"] != name:
                            error("nombre discordante para el hablante atribuido")
                if ids != sorted(set(ids)):
                    error("hablantes detectados repetidos o desordenados")
                if speaker is not None and s.get("ambiguous") is False and speaker not in ids:
                    error("atribución inequívoca sin actividad detectada")
                if timing == "segment" and speaker is not None and (ids != [speaker] or s.get("ambiguous") is not False):
                    error("atribución por segmento no exclusiva")
        fuente = s.get("source")
        if (not isinstance(fuente, dict) or set(fuente) != {"segment", "start", "end"}
                or any(type(v) is not int for v in fuente.values())
                or not 0 <= fuente["start"] < fuente["end"] or fuente["segment"] < 0):
            error("source inválido")
            continue
        indice, a, b = fuente["segment"], fuente["start"], fuente["end"]
        if fuente_previa is not None and (indice < fuente_previa[0] or (indice == fuente_previa[0] and a < fuente_previa[1])):
            error("source desordenado o superpuesto")
        fuente_previa = indice, b
        fuentes.setdefault(indice, []).append((a, b, texto, s))
    if asr is not None and not actual:
        violaciones.append("source: falta el contrato actual de trazabilidad")
    if actual and asr is not None:
        originales = asr["segments"]
        if set(fuentes) != set(range(len(originales))):
            violaciones.append("source: no cubre exactamente los segmentos de ASR")
        for indice, fragmentos in fuentes.items():
            if indice >= len(originales):
                continue
            seg = originales[indice]
            texto = seg["text"]
            cursor = 0
            palabras = alinear(seg) or []
            por_inicio = {w["char_start"]: j for j, w in enumerate(palabras)}
            por_fin = {w["char_end"]: j for j, w in enumerate(palabras)}
            ultimo_inicio = None
            for a, b, fragmento, fila in fragmentos:
                if a < cursor or b > len(texto) or texto[cursor:a].strip() or texto[a:b] != fragmento:
                    violaciones.append(f"source: cobertura textual inválida del segmento {indice}")
                cursor = b
                timing = fila.get("timing")
                intervalo = (fila.get("start"), fila.get("end"))
                if timing == "word":
                    ini, fin = por_inicio.get(a), por_fin.get(b)
                    if ini is None or fin is None or ini > fin:
                        violaciones.append(f"source: palabras sin correspondencia en el segmento {indice}")
                        continue
                    grupo = palabras[ini:fin + 1]
                    esperado = (min(w["start"] for w in grupo), max(w["end"] for w in grupo))
                    if intervalo != esperado:
                        violaciones.append(f"source: intervalo de palabra discordante en el segmento {indice}")
                    if ultimo_inicio is not None and esperado[0] < ultimo_inicio:
                        violaciones.append(f"source: orden temporal contradictorio en el segmento {indice}")
                    ultimo_inicio = esperado[0]
                elif timing in ("segment", "unknown"):
                    respaldo = intervalo_segmento(seg)
                    esperado = respaldo if respaldo is not None else (None, None)
                    if len(fragmentos) != 1 or intervalo != esperado or (timing == "unknown") != (respaldo is None):
                        violaciones.append(f"source: respaldo discordante en el segmento {indice}")
            if texto[cursor:].strip():
                violaciones.append(f"source: texto final no cubierto del segmento {indice}")
    return violaciones


# ---------- speakers.json ----------

CAMPOS_SPEAKER = ("name", "clip_start", "clip_end")


def validar_speakers(datos, duracion: float, etiquetas) -> list[str]:
    """Una entrada por etiqueta de diarization.json con exactamente name, clip_start y clip_end."""
    if not isinstance(datos, dict):
        return ["raíz: no es un objeto JSON"]
    violaciones = [f"raíz: falta la etiqueta '{e}'" for e in etiquetas if e not in datos]
    violaciones += [f"raíz: la etiqueta '{e}' no está en diarization.json" for e in datos if e not in etiquetas]
    for etiqueta, v in datos.items():
        if not isinstance(v, dict):
            violaciones.append(f"{etiqueta}: no es un objeto")
            continue
        violaciones += [f"{etiqueta}: campo no permitido '{c}'" for c in sorted(set(v) - set(CAMPOS_SPEAKER))]
        violaciones += [f"{etiqueta}: falta el campo '{c}'" for c in CAMPOS_SPEAKER if c not in v]
        if "name" in v and v["name"] is not None and not (isinstance(v["name"], str) and v["name"].strip()):
            violaciones.append(f"{etiqueta}: 'name' vacío o no es texto ({v['name']!r})")
        inicio, fin = v.get("clip_start"), v.get("clip_end")
        for nombre, valor in (("clip_start", inicio), ("clip_end", fin)):
            if not _es_numero(valor):
                violaciones.append(f"{etiqueta}: '{nombre}' no es un número finito ({valor!r})")
            elif round(valor, 3) != valor:
                violaciones.append(f"{etiqueta}: '{nombre}'={valor} tiene más de 3 decimales")
        if _es_numero(inicio) and _es_numero(fin):
            if inicio < 0 or not inicio < fin:
                violaciones.append(f"{etiqueta}: no cumple 0 <= clip_start < clip_end "
                                   f"(clip_start={inicio}, clip_end={fin})")
            if fin > duracion:
                violaciones.append(f"{etiqueta}: clip_end={fin} supera la duración del audio ({duracion} s)")
    return violaciones
