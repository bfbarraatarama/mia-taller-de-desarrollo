"""Preparación del dataset de test de UBA Games (Figshare v2), sesión S26 (design.md §11).

Implementado hasta ahora:
- Tarea 6.2: verificación de los RAR originales contra `hito-2/fuentes.toml` (bytes y MD5) y
  `hito-2/fuentes.lock.json` (SHA-256), verificación de los archivos ya extraídos de cada tarea seleccionada
  contra el listado de su RAR (tamaño y CRC32, sin extraer) y selección por lista de tareas.
- Tarea 6.3: validación por grabación (WAV completo estéreo de 16 kHz y PCM16, leído completo; anotaciones de
  los dos canales bien formadas; exceso terminal <= 0,01 s; correspondencia canal ↔ hablante por correlación con
  los WAV separados). Una grabación inválida queda `excluida` con su motivo; un fallo de integridad es fatal.
No escribe nada: si algo falla, lanza `ErrorPreparacion` antes de producir derivados.

Uso (desde la raíz del repo, con el Python del venv de la Etapa 2):
    python PoC/paso2_diarizacion/evaluacion/preparar_figshare.py --verificar-entradas
    python PoC/paso2_diarizacion/evaluacion/preparar_figshare.py --validar [--seleccion 04 05]
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import sys
import tomllib
import wave
from pathlib import Path

import numpy as np

if __package__ in (None, ""):  # ejecución como script: hace importable el paquete `evaluacion`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluacion import referencia as ref  # noqa: E402
from evaluacion.rar7z import ErrorVerificacion, listar, localizar_7zip, ruta_segura, verificar  # noqa: E402

RAIZ = Path(__file__).resolve().parents[3]
HITO2 = RAIZ / "hito-2"
CACHE = HITO2 / ".cache" / "uba_games" / "figshare-v2"
EXTRAIDOS = CACHE / "extraidos"
FUENTES_TOML = HITO2 / "fuentes.toml"
LOCK_JSON = HITO2 / "fuentes.lock.json"

SESION = "S26"
SELECCION_INICIAL = ("04",)
ORIGINALES = ("phrases.rar", "wavs.rar")
CARPETA_WAV_COMPLETO = "wavs/Sin separar canales/S26_falta_separar_canales"
CARPETA_FRASES = "phrases/S26"
PATRON_COMPLETO = re.compile(r"s(\d+)\.objects\.(\d+)\.wav", re.I)                        # s26.objects.04.wav
PATRON_CANAL = re.compile(r"s(\d+)\.objects\.(\d+)\.channel([12])\.(phrases|wav)", re.I)  # patrón del Hito 2


class ErrorPreparacion(Exception):
    """La preparación no puede continuar; no se escribió ningún derivado."""


def _tolerancia_hito2() -> float:
    """`TOLERANCIA_FIN_FIGSHARE_S` importada de `hito-2/scripts/validar_muestra.py`, sin modificar ese script."""
    ruta = HITO2 / "scripts" / "validar_muestra.py"
    spec = importlib.util.spec_from_file_location("validar_muestra_hito2", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return float(modulo.TOLERANCIA_FIN_FIGSHARE_S)


TOLERANCIA_FIN_S = _tolerancia_hito2()   # 0,01 s
TOLERANCIA_ORDEN_S = 1e-4                # criterio de orden del Hito 2 (armar_muestra.py)
FS_ESPERADA, CANALES_ESPERADOS, BITS_ESPERADOS = 16000, 2, 16
# Decisión del 08/11/2026: 9 tareas de S26 tienen WAV separados con 1 cuadro de más al final (alineados en desfase 0).
# Solo se usan para la correspondencia canal ↔ hablante, que se calcula sobre los cuadros en común.
TOLERANCIA_CUADROS_SEPARADO = 1


# --- originales ---------------------------------------------------------------------------------------------

def leer_registro(fuentes_toml: Path = FUENTES_TOML, lock_json: Path = LOCK_JSON) -> dict[str, dict]:
    """{nombre: {bytes, md5, sha256}} de los dos RAR, según fuentes.toml y fuentes.lock.json."""
    try:
        cfg = tomllib.loads(Path(fuentes_toml).read_text(encoding="utf-8"))["uba_games_figshare"]["archivos"]
        lock = json.loads(Path(lock_json).read_text(encoding="utf-8"))["archivos"]
    except (OSError, ValueError, KeyError) as e:
        raise ErrorPreparacion(f"no se pudo leer el registro de fuentes ({type(e).__name__}: {e})") from None
    registro = {}
    for nombre in ORIGINALES:
        clave = f"uba_games/figshare-v2/{nombre}"
        if nombre not in cfg or clave not in lock:
            raise ErrorPreparacion(f"{nombre} no está registrado en fuentes.toml o en fuentes.lock.json")
        if cfg[nombre]["bytes"] != lock[clave]["bytes"]:
            raise ErrorPreparacion(f"{nombre}: fuentes.toml y fuentes.lock.json declaran tamaños distintos")
        registro[nombre] = {"bytes": cfg[nombre]["bytes"], "md5": cfg[nombre]["md5"].lower(),
                            "sha256": lock[clave]["sha256"].lower()}
    return registro


def _hashes(ruta: Path) -> tuple[int, str, str]:
    md5, sha, n = hashlib.md5(), hashlib.sha256(), 0
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            md5.update(bloque)
            sha.update(bloque)
            n += len(bloque)
    return n, md5.hexdigest(), sha.hexdigest()


def verificar_originales(cache: Path = CACHE, registro: dict | None = None) -> dict[str, dict]:
    """Comprueba tamaño, MD5 y SHA-256 de phrases.rar y wavs.rar. Devuelve lo verificado."""
    registro = leer_registro() if registro is None else registro
    verificados = {}
    for nombre in ORIGINALES:
        ruta = Path(cache) / nombre
        if not ruta.is_file():
            raise ErrorPreparacion(f"falta el original {ruta}")
        n, md5, sha = _hashes(ruta)
        esperado = registro[nombre]
        for campo, valor in (("bytes", n), ("md5", md5), ("sha256", sha)):
            if valor != esperado[campo]:
                raise ErrorPreparacion(f"{nombre}: {campo} {valor} distinto del registrado ({esperado[campo]})")
        verificados[nombre] = {"bytes": n, "md5": md5, "sha256": sha}
    return verificados


# --- inventario y selección de S26 --------------------------------------------------------------------------

def normalizar_seleccion(seleccion) -> list[str]:
    tareas = []
    for t in seleccion:
        texto = str(t).strip()
        if not texto.isdigit():
            raise ErrorPreparacion(f"tarea inválida en la selección: {t!r} (se espera un número, por ejemplo 04)")
        tareas.append(f"{int(texto):02d}")
    if not tareas:
        raise ErrorPreparacion("la selección está vacía")
    return sorted(set(tareas))


def rutas_tarea(tarea: str) -> dict[str, str]:
    """Rutas internas (iguales en el RAR y en extraidos/) del WAV completo y las dos anotaciones de una tarea."""
    base = f"s{SESION[1:]}.objects.{tarea}"
    return {"wav_completo": f"{CARPETA_WAV_COMPLETO}/{base}.wav",
            "channel1": f"{CARPETA_FRASES}/{base}.channel1.phrases",
            "channel2": f"{CARPETA_FRASES}/{base}.channel2.phrases"}


def _sesion_ok(numero: str) -> bool:
    return int(numero) == int(SESION[1:])


def inventario_s26(listado_wavs: dict, listado_frases: dict) -> dict[str, dict[str, str]]:
    """{tarea: {wav_completo, channel1, channel2}} de S26. Un nombre fuera del patrón en esas carpetas falla."""
    inventario: dict[str, dict[str, str]] = {}
    for listado, carpeta, patron, rol in ((listado_wavs, CARPETA_WAV_COMPLETO, PATRON_COMPLETO, "wav_completo"),
                                          (listado_frases, CARPETA_FRASES, PATRON_CANAL, None)):
        for ruta, entrada in listado.items():
            if entrada.es_carpeta or not ruta.startswith(carpeta + "/") or "/" in ruta[len(carpeta) + 1:]:
                continue
            nombre = ruta[len(carpeta) + 1:]
            m = patron.fullmatch(nombre)
            if m is None or not _sesion_ok(m[1]):
                raise ErrorPreparacion(f"nombre fuera del patrón en {carpeta}/: {nombre}")
            if rol is None and m[4].lower() != "phrases":
                raise ErrorPreparacion(f"archivo inesperado en {carpeta}/: {nombre}")
            tarea = f"{int(m[2]):02d}"
            clave = rol or f"channel{m[3]}"
            if clave in inventario.setdefault(tarea, {}):
                raise ErrorPreparacion(f"entrada duplicada para la tarea {tarea} ({clave}): {nombre}")
            inventario[tarea][clave] = ruta
    return inventario


def verificar_entradas(seleccion=SELECCION_INICIAL, cache: Path = CACHE, extraidos: Path = EXTRAIDOS,
                       registro: dict | None = None, siete_zip: Path | None = None) -> dict:
    """Tarea 6.2: originales, inventario de S26, selección y verificación de los extraídos de cada tarea elegida."""
    tareas = normalizar_seleccion(seleccion)
    originales = verificar_originales(cache, registro)
    try:
        exe = siete_zip or localizar_7zip()
        listados = {n: listar(Path(cache) / n, exe) for n in ORIGINALES}
        inventario = inventario_s26(listados["wavs.rar"], listados["phrases.rar"])
        grabaciones = {}
        for tarea in tareas:
            esperado = rutas_tarea(tarea)
            disponibles = inventario.get(tarea, {})
            faltan = [k for k in esperado if k not in disponibles]
            if faltan:
                raise ErrorPreparacion(f"la tarea {tarea} de {SESION} no tiene en los RAR: {', '.join(faltan)}")
            archivos = {}
            for clave, ruta in esperado.items():
                rar = "wavs.rar" if clave == "wav_completo" else "phrases.rar"
                v = verificar(Path(cache) / rar, extraidos, [ruta], listado=listados[rar])[0]
                archivos[clave] = {"ruta": ruta_segura(ruta), "rar": rar, "tamano": v.tamano, "crc32": v.crc32,
                                   "sha256": v.sha256}
            grabaciones[f"figshare_v2_{SESION}_objects_{tarea}"] = {"tarea": tarea, "archivos": archivos}
    except ErrorVerificacion as e:
        raise ErrorPreparacion(str(e)) from None
    return {"sesion": SESION, "seleccion": tareas, "originales": originales, "grabaciones": grabaciones,
            "tareas_en_los_rar": sorted(inventario), "ignoradas": sorted(set(inventario) - set(tareas))}


# --- tarea 6.3: validación por grabación ----------------------------------------------------------------

class Exclusion(Exception):
    """La grabación no cumple un criterio de validez; se excluye con este motivo (no es un fallo fatal)."""


def leer_wav(ruta: Path, canales: int | None = None) -> tuple[int, np.ndarray]:
    """(frecuencia, muestras int16 de forma (cuadros, canales)) leyendo todo el archivo; Exclusion si no se puede."""
    try:
        with wave.open(str(ruta), "rb") as w:
            fs, ch, ancho, comp, n = (w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getcomptype(),
                                      w.getnframes())
            datos = w.readframes(n)
    except (wave.Error, EOFError, OSError) as e:
        raise Exclusion(f"{ruta.name}: no es un WAV PCM legible ({e})") from None
    if comp != "NONE" or ancho * 8 != BITS_ESPERADOS:
        raise Exclusion(f"{ruta.name}: {ancho * 8} bits, compresión {comp} (se espera PCM{BITS_ESPERADOS})")
    if fs != FS_ESPERADA:
        raise Exclusion(f"{ruta.name}: {fs} Hz (se espera {FS_ESPERADA} Hz)")
    if canales is not None and ch != canales:
        raise Exclusion(f"{ruta.name}: {ch} canales (se esperan {canales})")
    if n == 0:
        raise Exclusion(f"{ruta.name}: sin muestras")
    if len(datos) != n * ch * ancho:
        raise Exclusion(f"{ruta.name}: lectura incompleta ({len(datos)} de {n * ch * ancho} bytes)")
    return fs, np.frombuffer(datos, dtype="<i2").reshape(-1, ch)


def leer_anotacion(ruta: Path) -> list[tuple[int, float, float, str, str]]:
    """[(línea, inicio, fin, texto, fin tal como está escrito)] con los criterios del Hito 2; Exclusion con
    archivo y línea si no cumple."""
    if not ruta.is_file():
        raise Exclusion(f"falta la anotación {ruta.name}")
    try:
        lineas = ruta.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError) as e:
        raise Exclusion(f"{ruta.name}: no se pudo leer ({e})") from None
    filas, fin_previo = [], 0.0
    for numero, linea in enumerate(lineas, 1):
        campos = linea.split("\t", 2)
        if len(campos) != 3 or not campos[2].strip():
            raise Exclusion(f"{ruta.name}:{numero}: línea mal formada (se esperan inicio, fin y texto)")
        try:
            inicio, fin = float(campos[0]), float(campos[1])
        except ValueError:
            raise Exclusion(f"{ruta.name}:{numero}: tiempos no numéricos") from None
        if not (math.isfinite(inicio) and math.isfinite(fin) and 0 <= inicio < fin):
            raise Exclusion(f"{ruta.name}:{numero}: tiempos inválidos ({inicio}, {fin})")
        if inicio < fin_previo - TOLERANCIA_ORDEN_S:
            raise Exclusion(f"{ruta.name}:{numero}: inicio {inicio} anterior al fin previo {fin_previo}")
        filas.append((numero, inicio, fin, campos[2].strip(), campos[1].strip()))
        fin_previo = fin
    if not filas:
        raise Exclusion(f"{ruta.name}: anotación vacía")
    return filas


def _correlacion(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a.astype(np.float64), b.astype(np.float64)
    a, b = a - a.mean(), b - b.mean()
    den = math.sqrt(float(np.dot(a, a)) * float(np.dot(b, b)))
    return float(np.dot(a, b) / den) if den else 0.0


def ruta_separado(tarea: str, canal: int) -> str:
    return f"wavs/{SESION}/s{SESION[1:]}.objects.{tarea}.channel{canal}.wav"


def validar_grabacion(tarea: str, extraidos: Path = EXTRAIDOS) -> dict:
    """Valida una tarea de S26. Devuelve {estado: 'valida' | 'excluida', motivo, ...} con lo medido."""
    rutas = rutas_tarea(tarea)
    resultado = {"recording_id": f"figshare_v2_{SESION}_objects_{tarea}", "tarea": tarea, "estado": "valida",
                 "motivo": None}
    try:
        fs, estereo = leer_wav(Path(extraidos) / rutas["wav_completo"], canales=CANALES_ESPERADOS)
        cuadros = int(estereo.shape[0])
        duracion = cuadros / fs
        resultado.update({"cuadros": cuadros, "duracion_s": duracion})
        anotaciones = {}
        for c in (1, 2):
            filas = leer_anotacion(Path(extraidos) / rutas[f"channel{c}"])
            exceso = max(0.0, filas[-1][2] - duracion)
            if exceso > TOLERANCIA_FIN_S + 1e-12:
                raise Exclusion(f"channel{c}: la anotación termina {exceso:.4f} s después del WAV "
                                f"(tolerancia {TOLERANCIA_FIN_S} s)")
            anotaciones[f"channel{c}"] = {"intervalos": len(filas), "fin_s": filas[-1][2], "exceso_terminal_s": exceso,
                                          "intervalos_habla": sum(1 for f in filas if f[3] != "#")}
        resultado["anotaciones"] = anotaciones
        correlaciones = {}
        for c in (1, 2):
            sep_ruta = Path(extraidos) / ruta_separado(tarea, c)
            if not sep_ruta.is_file():
                raise Exclusion(f"falta el WAV separado {sep_ruta.name} para comprobar la correspondencia")
            _, sep = leer_wav(sep_ruta, canales=1)
            diferencia = int(sep.shape[0]) - cuadros
            if not 0 <= diferencia <= TOLERANCIA_CUADROS_SEPARADO:
                raise Exclusion(f"{sep_ruta.name}: {sep.shape[0]} cuadros, el WAV completo tiene {cuadros} "
                                f"(se admite hasta {TOLERANCIA_CUADROS_SEPARADO} cuadro de más al final)")
            sep = sep[:cuadros]   # el cuadro sobrante está al final (alineado en desfase 0)
            propio = _correlacion(estereo[:, c - 1], sep[:, 0])
            ajeno = _correlacion(estereo[:, 2 - c], sep[:, 0])
            correlaciones[f"channel{c}"] = {"canal_estereo": "izquierdo" if c == 1 else "derecho",
                                            "con_su_canal": round(propio, 6), "con_el_otro": round(ajeno, 6),
                                            "cuadros_separado": int(cuadros + diferencia),
                                            "diferencia_cuadros": diferencia}
            if not propio > ajeno:
                raise Exclusion(f"channel{c}.wav se parece más al otro canal del WAV completo "
                                f"({ajeno:.4f} contra {propio:.4f}): canales invertidos o mal asignados")
        resultado["correspondencia"] = correlaciones
    except Exclusion as e:
        resultado.update({"estado": "excluida", "motivo": str(e)})
    return resultado


def validar(seleccion=SELECCION_INICIAL, cache: Path = CACHE, extraidos: Path = EXTRAIDOS,
            registro: dict | None = None, siete_zip: Path | None = None) -> dict:
    """Tareas 6.2 y 6.3: verifica las entradas (fatal si falla) y valida cada grabación seleccionada."""
    r = verificar_entradas(seleccion, cache, extraidos, registro, siete_zip)
    try:  # los WAV separados solo se usan para la correspondencia; también se verifican contra el RAR
        listado = listar(Path(cache) / "wavs.rar", siete_zip or localizar_7zip())
        r["separados"] = {}
        for tarea in r["seleccion"]:
            r["separados"][tarea] = verificar(Path(cache) / "wavs.rar", extraidos,
                                              [ruta_separado(tarea, c) for c in (1, 2)], listado=listado)
    except ErrorVerificacion as e:
        raise ErrorPreparacion(str(e)) from None
    r["validacion"] = {f"figshare_v2_{SESION}_objects_{t}": validar_grabacion(t, extraidos) for t in r["seleccion"]}
    return r


# --- tarea 6.4: conversión a mono ----------------------------------------------------------------------------------

FORMULA_MONO = "int16(floor_divide(int32(izquierda) + int32(derecha), 2))"


def mezclar_mono(estereo: np.ndarray) -> np.ndarray:
    """(izquierda + derecha) // 2, como el Hito 2: int32, división entera hacia abajo, int16."""
    return np.floor_divide(estereo[:, 0].astype(np.int32) + estereo[:, 1].astype(np.int32), 2).astype("<i2")


def bytes_wav_mono(mono: np.ndarray, fs: int = FS_ESPERADA) -> bytes:
    """WAV de 16 kHz, mono y PCM16 escrito con `wave`, en memoria (cabecera determinista)."""
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(mono.astype("<i2").tobytes())
    return buf.getvalue()


def convertir_a_mono(estereo_wav: Path, destino: Path) -> dict:
    """Lee el WAV estéreo (sin modificarlo) y escribe el mono en `destino`. Devuelve cuadros y SHA-256."""
    fs, estereo = leer_wav(Path(estereo_wav), canales=CANALES_ESPERADOS)
    datos = bytes_wav_mono(mezclar_mono(estereo), fs)
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    Path(destino).write_bytes(datos)
    return {"cuadros": int(estereo.shape[0]), "sha256": hashlib.sha256(datos).hexdigest()}


# --- tareas 6.5 a 6.7: referencia, cobertura, manifiesto y verificación ----------------------------------------

MODULO_DIR = Path(__file__).resolve().parents[1]
DATOS = MODULO_DIR / "datos" / "figshare_test" / SESION
MANIFIESTO = Path(__file__).resolve().parent / "figshare_test.manifest.json"
VERSION_SCRIPT = "1"
ORIGEN, LICENCIA = "figshare:22647313:v2", "CC BY 4.0"


def serializacion_canonica(contenido: dict) -> bytes:
    return json.dumps(contenido, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def politica_sha256(politica: dict[str, str]) -> str:
    """SHA-256 de la política parseada en forma canónica (no depende del fin de línea del archivo)."""
    return hashlib.sha256(serializacion_canonica({"etiquetas": politica})).hexdigest()


def _anotaciones(tarea: str, extraidos: Path) -> dict[int, list]:
    rutas = rutas_tarea(tarea)
    return {c: leer_anotacion(Path(extraidos) / rutas[f"channel{c}"]) for c in (1, 2)}


def inventario(seleccion=SELECCION_INICIAL, extraidos: Path = EXTRAIDOS, politica_json: Path = ref.POLITICA_JSON,
               **kw) -> dict:
    """Etiquetas sin letras (distintas de '#') de la selección, con cantidad y clase. No prepara nada."""
    r = verificar_entradas(seleccion, extraidos=extraidos, **kw)
    politica = _leer_politica(politica_json)
    por_tarea, excluidas = {}, {}
    for t in r["seleccion"]:
        try:
            por_tarea[t] = ref.inventario_etiquetas(_anotaciones(t, extraidos), politica)
        except Exclusion as e:
            excluidas[t] = str(e)
    total = {}
    for d in por_tarea.values():
        for e, v in d.items():
            total.setdefault(e, {"apariciones": 0, "clase": v["clase"]})["apariciones"] += v["apariciones"]
    return {"seleccion": r["seleccion"], "por_tarea": por_tarea, "total": dict(sorted(total.items())),
            "sin_clasificar": sorted(e for e, v in total.items() if v["clase"] == "sin_clasificar"),
            "no_legibles": excluidas}


def _leer_politica(ruta: Path) -> dict[str, str]:
    try:
        return ref.leer_politica(ruta)
    except ref.ErrorReferencia as e:
        raise ErrorPreparacion(str(e)) from None


def preparar(seleccion=SELECCION_INICIAL, cache: Path = CACHE, extraidos: Path = EXTRAIDOS, registro: dict | None = None,
             siete_zip: Path | None = None, datos: Path = DATOS, manifiesto: Path = MANIFIESTO,
             politica_json: Path = ref.POLITICA_JSON, ejecucion_extra: dict | None = None) -> dict:
    """Prepara la selección: verifica, valida, construye mono, RTTM y cobertura, y escribe el manifiesto.

    Todo se calcula en memoria antes de escribir: si algo falla, no se escribe ningún derivado.
    """
    import platform
    import time
    t0 = time.perf_counter()
    exe = siete_zip or localizar_7zip()
    r = validar(seleccion, cache, extraidos, registro, exe)
    politica = _leer_politica(politica_json)
    grabaciones, escribir = [], {}
    for t in r["seleccion"]:
        gid = f"figshare_v2_{SESION}_objects_{t}"
        v = r["validacion"][gid]
        archivos = dict(r["grabaciones"][gid]["archivos"])
        g = {"recording_id": gid, "tarea": t, "estado": v["estado"], "motivo": v["motivo"]}
        if v["estado"] == "valida":
            for c, h in zip((1, 2), r["separados"][t]):
                archivos[f"channel{c}_separado"] = {"ruta": h.ruta_interna, "rar": "wavs.rar",
                                                    "tamano": h.tamano, "crc32": h.crc32, "sha256": h.sha256}
            fs, estereo = leer_wav(Path(extraidos) / rutas_tarea(t)["wav_completo"], canales=CANALES_ESPERADOS)
            anot = _anotaciones(t, extraidos)
            try:
                referencia = ref.construir(anot, estereo.shape[0], fs, politica, SESION, TOLERANCIA_FIN_S)
            except ref.ErrorReferencia as e:
                raise ErrorPreparacion(f"{gid}: {e}") from None
            wav_mono = bytes_wav_mono(mezclar_mono(estereo), fs)
            texto_rttm = ref.rttm(referencia["segmentos"], gid).encode("utf-8")
            duracion = estereo.shape[0] / fs
            g.update({
                "cuadros_estereo": int(estereo.shape[0]), "cuadros_mono": int(estereo.shape[0]), "fs": fs,
                "correspondencia": v["correspondencia"],
                "exceso_terminal_s": {c: round(a["exceso_terminal_s"], 6) for c, a in v["anotaciones"].items()},
                "conteos": referencia["conteos"], "ajustes_fin": referencia["ajustes_fin"],
                "segmentos_referencia": len(referencia["segmentos"]),
                "validacion_referencia": ref.validar_referencia(referencia["segmentos"], duracion),
                "cobertura": ref.cobertura(estereo, fs, anot, politica),
                "derivados": {"wav_mono": {"ruta": f"{gid}.wav", "sha256": hashlib.sha256(wav_mono).hexdigest()},
                              "rttm": {"ruta": f"{gid}.rttm", "sha256": hashlib.sha256(texto_rttm).hexdigest()}},
            })
            escribir[f"{gid}.wav"], escribir[f"{gid}.rttm"] = wav_mono, texto_rttm
        g["archivos"] = [{"clave": k, **a} for k, a in sorted(archivos.items())]
        grabaciones.append(g)
    contenido = {
        "origen": ORIGEN, "licencia": LICENCIA,
        "originales": [{"nombre": n, **r["originales"][n]} for n in sorted(r["originales"])],
        "politica_etiquetas_sha256": politica_sha256(politica),
        "tolerancias": {"fin_s": TOLERANCIA_FIN_S, "orden_s": TOLERANCIA_ORDEN_S},
        "formula_mono": FORMULA_MONO, "cobertura_parametros": ref.COBERTURA,
        "sesion": SESION, "seleccion": r["seleccion"],
        "carpeta_derivados": f"datos/figshare_test/{SESION}",
        "grabaciones": sorted(grabaciones, key=lambda g: g["recording_id"]),
    }
    contenido = json.loads(serializacion_canonica(contenido))  # normaliza tuplas y claves a lo que se relee
    ejecucion = {"fecha_hora_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "sistema": platform.platform(), "python": platform.python_version(),
                 "siete_zip": _version_7zip(exe), "version_script": VERSION_SCRIPT, "commit": _commit(),
                 "ruta_cache": _relativa(cache),"tiempo_preparacion_s": None, **(ejecucion_extra or {})}
    for nombre, b in escribir.items():
        Path(datos).mkdir(parents=True, exist_ok=True)
        (Path(datos) / nombre).write_bytes(b)
    ejecucion["tiempo_preparacion_s"] = round(time.perf_counter() - t0, 2)
    escribir_manifiesto(manifiesto, contenido, ejecucion)
    return {"contenido": contenido, "ejecucion": ejecucion, "contenido_sha256": contenido_sha256(contenido)}


def contenido_sha256(contenido: dict) -> str:
    return hashlib.sha256(serializacion_canonica(contenido)).hexdigest()


def escribir_manifiesto(ruta: Path, contenido: dict, ejecucion: dict) -> None:
    doc = {"contenido_sha256": contenido_sha256(contenido), "contenido": contenido, "ejecucion": ejecucion}
    texto = json.dumps(doc, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    Path(ruta).write_bytes(texto.encode("utf-8"))


def verificar_dataset(manifiesto: Path = MANIFIESTO, datos: Path = DATOS) -> list[str]:
    """Recalcula `contenido_sha256` y los SHA-256 de los derivados; ignora `ejecucion`. Lanza si algo no coincide."""
    try:
        doc = json.loads(Path(manifiesto).read_text(encoding="utf-8"))
        contenido = doc["contenido"]
    except (OSError, ValueError, KeyError) as e:
        raise ErrorPreparacion(f"no se pudo leer el manifiesto {manifiesto}: {e}") from None
    if contenido_sha256(contenido) != doc.get("contenido_sha256"):
        raise ErrorPreparacion("contenido_sha256 no coincide con la sección 'contenido' del manifiesto")
    problemas, verificadas = [], []
    for g in contenido["grabaciones"]:
        if g["estado"] != "valida":
            continue
        for tipo, d in sorted(g["derivados"].items()):
            ruta = Path(datos) / d["ruta"]
            if not ruta.is_file():
                problemas.append(f"{g['recording_id']}: falta {tipo} ({ruta.name})")
            elif hashlib.sha256(ruta.read_bytes()).hexdigest() != d["sha256"]:
                problemas.append(f"{g['recording_id']}: {tipo} ({ruta.name}) tiene otro SHA-256")
        verificadas.append(g["recording_id"])
    if problemas:
        raise ErrorPreparacion("; ".join(problemas))
    return verificadas


def _version_7zip(exe) -> str | None:
    from evaluacion.rar7z import version_7zip
    try:
        return version_7zip(Path(exe))
    except Exception:  # solo trazabilidad
        return None


def _relativa(ruta: Path) -> str:
    """Ruta relativa a la raíz del repo si está dentro (el manifiesto se versiona: sin rutas personales)."""
    try:
        return Path(ruta).resolve().relative_to(RAIZ).as_posix()
    except ValueError:
        return Path(ruta).name


def _commit() -> str | None:
    import subprocess
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preparación del dataset de test de UBA Games (S26).")
    accion = parser.add_mutually_exclusive_group(required=True)
    accion.add_argument("--verificar-entradas", action="store_true",
                        help="verifica originales y extraídos de la selección, sin escribir nada (tarea 6.2)")
    accion.add_argument("--validar", action="store_true",
                        help="además valida cada grabación seleccionada, sin escribir nada (tarea 6.3)")
    accion.add_argument("--inventario", action="store_true",
                        help="lista las etiquetas sin letras de la selección y su clase, sin preparar nada")
    accion.add_argument("--preparar", action="store_true",
                        help="prepara la selección: mono, RTTM, cobertura y manifiesto")
    accion.add_argument("--verificar", action="store_true",
                        help="verifica los derivados contra el manifiesto (ignora 'ejecucion')")
    parser.add_argument("--seleccion", nargs="+", default=list(SELECCION_INICIAL), help="tareas de S26 (por defecto: 04)")
    args = parser.parse_args(argv)
    try:
        if args.verificar:
            for gid in verificar_dataset():
                print(f"OK  {gid}: WAV mono y RTTM coinciden con el manifiesto")
            print("OK  contenido_sha256 coincide")
            return 0
        if args.inventario:
            inv = inventario(args.seleccion)
            for t, d in inv["por_tarea"].items():
                print(f"tarea {t}: " + (", ".join(f"{e!r} x{v['apariciones']} ({v['clase']})" for e, v in d.items())
                                        or "sin etiquetas sin letras"))
            for t, motivo in inv["no_legibles"].items():
                print(f"tarea {t}: no legible ({motivo})")
            print("sin clasificar: " + (", ".join(repr(e) for e in inv["sin_clasificar"]) or "ninguna"))
            return 1 if inv["sin_clasificar"] else 0
        if args.preparar:
            p = preparar(args.seleccion)
            for g in p["contenido"]["grabaciones"]:
                print(f"{g['estado'].upper()}  {g['recording_id']}" + (f": {g['motivo']}" if g["motivo"] else
                      f": {g['cuadros_mono']} cuadros, {g['segmentos_referencia']} segmentos, referencia "
                      f"{'utilizable' if g['validacion_referencia']['utilizable'] else 'NO utilizable'}"))
            print(f"OK  manifiesto {MANIFIESTO.name}: contenido_sha256 {p['contenido_sha256']}")
            return 0
        r = validar(args.seleccion) if args.validar else verificar_entradas(args.seleccion)
    except ErrorPreparacion as e:
        print(f"FALLA: {e}", file=sys.stderr)
        return 1
    for nombre, v in r["originales"].items():
        print(f"OK  original {nombre}: {v['bytes']} bytes, MD5 y SHA-256 coinciden con el registro")
    print(f"OK  {r['sesion']}: {len(r['tareas_en_los_rar'])} tareas en los RAR; selección {r['seleccion']}; "
          f"{len(r['ignoradas'])} ignoradas")
    for gid, g in r["grabaciones"].items():
        for clave, a in g["archivos"].items():
            print(f"OK  {gid} {clave}: {a['ruta']} · {a['tamano']} bytes · CRC32 {a['crc32']} · SHA-256 {a['sha256']}")
    for gid, v in r.get("validacion", {}).items():
        if v["estado"] != "valida":
            print(f"EXCLUIDA  {gid}: {v['motivo']}")
            continue
        print(f"VÁLIDA  {gid}: {v['cuadros']} cuadros = {v['duracion_s']:.3f} s, estéreo {FS_ESPERADA} Hz PCM{BITS_ESPERADOS}")
        for c, a in v["anotaciones"].items():
            print(f"        {c}: {a['intervalos']} intervalos ({a['intervalos_habla']} de habla), fin {a['fin_s']:.3f} s, "
                  f"exceso {a['exceso_terminal_s']:.4f} s (tolerancia {TOLERANCIA_FIN_S} s)")
        for c, k in v["correspondencia"].items():
            print(f"        {c}.wav ↔ canal {k['canal_estereo']}: correlación {k['con_su_canal']:.5f} "
                  f"(con el otro canal {k['con_el_otro']:.5f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
