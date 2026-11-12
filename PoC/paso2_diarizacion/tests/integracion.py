"""Verificaciones reutilizables del nivel 2 (design.md §10.1): bloque A (contrato de la Etapa 1) y bloque D
(compatibilidad entre etapas), más el resumen para la revisión manual.

Las usan `test_integracion_cpu.py` (tarea 5.3, con el modelo real) y los tests de nivel 1 de la tarea 5.4
(WAV y reportes sintéticos). No importan pyannote; TorchCodec y FFmpeg solo se usan si se piden.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

from entrada import validar_audio
from resultados import NOMBRE_JSON, NOMBRE_META, carpeta_reunion

DURACION_MIN_S = 30.0
DURACION_MAX_S = 60.0
ESTADO_COMPLETA = "completa"
PREFIJO_INTERRUMPIDA = "grabando"  # "grabando (si queda así, la grabación se interrumpió)"
PRUEBA_PROCESABLE = "salida procesable (mono, 16 kHz, PCM 16)"


@dataclass
class InfoEtapa1:
    wav: Path
    duracion: float
    cuadros: int
    estado: str
    interrumpida: bool


def ruta_reporte(wav: Path) -> Path:
    """El reporte que la Etapa 1 escribe junto al WAV: `<nombre>.json`."""
    return wav.with_suffix(".json")


def leer_reporte(wav: Path) -> dict:
    ruta = ruta_reporte(wav)
    if not ruta.is_file():
        raise AssertionError(f"{wav.name}: falta el reporte de la Etapa 1 ({ruta.name}); "
                             "la grabación no salió de la interfaz")
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except ValueError as e:
        raise AssertionError(f"{wav.name}: el reporte {ruta.name} no es JSON válido ({e})") from None


def validar_reporte(wav: Path, reporte: dict) -> tuple[str, bool]:
    """Devuelve (estado, interrumpida). Completa: exige "salida procesable" en OK. Interrumpida: acepta "grabando"."""
    estado = str(reporte.get("estado", ""))
    if estado.startswith(PREFIJO_INTERRUMPIDA):
        return estado, True
    if estado != ESTADO_COMPLETA:
        raise AssertionError(f"{wav.name}: estado de la Etapa 1 {estado!r} (se espera 'completa' o 'grabando ...')")
    pruebas = {p.get("prueba"): p.get("ok") for p in reporte.get("pruebas", [])}
    if pruebas.get(PRUEBA_PROCESABLE) is not True:
        raise AssertionError(f"{wav.name}: la prueba '{PRUEBA_PROCESABLE}' de la Etapa 1 no está en OK")
    return estado, False


def lectura_completa_wave(wav: Path) -> tuple[int, int]:
    """(bytes leídos, bytes esperados por la cabecera) leyendo todos los cuadros con `wave`."""
    with wave.open(str(wav), "rb") as w:
        n, ancho, canales = w.getnframes(), w.getsampwidth(), w.getnchannels()
        datos = w.readframes(n)
    return len(datos), n * ancho * canales


def muestras_torchcodec(wav: Path) -> int:
    from torchcodec.decoders import AudioDecoder
    return int(AudioDecoder(str(wav)).get_all_samples().data.shape[-1])


def errores_ffmpeg(wav: Path) -> str | None:
    """Salida de error de `ffmpeg -v error -i WAV -f null -` (cadena vacía si no hay errores); None sin ffmpeg."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    r = subprocess.run([ffmpeg, "-v", "error", "-i", str(wav), "-f", "null", "-"], capture_output=True, text=True)
    return (r.stderr or "").strip() + ("" if r.returncode == 0 else f" (código {r.returncode})")


def verificar_bloque_a(wav: Path, *, torchcodec: bool = True, ffmpeg: bool = True) -> InfoEtapa1:
    """Bloque A: cabecera, duración, reporte y decodificación completa. Lanza AssertionError con el motivo."""
    wav = Path(wav)
    reporte = leer_reporte(wav)                      # sin reporte: falla antes que todo lo demás
    estado, interrumpida = validar_reporte(wav, reporte)
    duracion = validar_audio(wav)                    # 16 kHz, mono, PCM16 (DiarizacionError si no)
    if not DURACION_MIN_S <= duracion <= DURACION_MAX_S:
        raise AssertionError(f"{wav.name}: dura {duracion:.2f} s, fuera de {DURACION_MIN_S:.0f}-{DURACION_MAX_S:.0f} s")
    leidos, esperados = lectura_completa_wave(wav)
    if leidos != esperados:
        raise AssertionError(f"{wav.name}: lectura incompleta con wave ({leidos} de {esperados} bytes)")
    cuadros = esperados // 2
    if torchcodec:
        n = muestras_torchcodec(wav)
        if n != cuadros:
            raise AssertionError(f"{wav.name}: TorchCodec decodificó {n} muestras y la cabecera declara {cuadros}")
    if ffmpeg:
        errores = errores_ffmpeg(wav)
        if errores is None:
            raise AssertionError("no hay ffmpeg en PATH para la verificación de decodificación")
        if errores:
            raise AssertionError(f"{wav.name}: ffmpeg informó errores al decodificar: {errores[:200]}")
    return InfoEtapa1(wav=wav, duracion=duracion, cuadros=cuadros, estado=estado, interrumpida=interrumpida)


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def huellas_etapa1(wav: Path) -> dict[str, str]:
    """SHA-256 del WAV y de su reporte, para comprobar después que la Etapa 2 no los modificó."""
    return {"wav": sha256(wav), "reporte": sha256(ruta_reporte(wav))}


def verificar_bloque_d(wav: Path, huellas_antes: dict[str, str], carpeta_resultados: Path) -> None:
    """Bloque D: originales intactos y resultados en `<carpeta>/<nombre>/`, sin pisar `<nombre>.json`."""
    wav, carpeta_resultados = Path(wav), Path(carpeta_resultados)
    despues = huellas_etapa1(wav)
    if despues != huellas_antes:
        cambiados = [k for k in despues if despues[k] != huellas_antes[k]]
        raise AssertionError(f"{wav.name}: la Etapa 2 modificó archivos de la Etapa 1: {cambiados}")
    esperada = carpeta_reunion(wav)
    if carpeta_resultados.resolve() != esperada.resolve():
        raise AssertionError(f"{wav.name}: resultados en {carpeta_resultados}, se esperaba {esperada}")
    if carpeta_resultados.resolve() == ruta_reporte(wav).resolve() or not ruta_reporte(wav).is_file():
        raise AssertionError(f"{wav.name}: la carpeta de resultados pisó el reporte de la Etapa 1")
    for nombre in (NOMBRE_JSON, NOMBRE_META):
        if not (carpeta_resultados / nombre).is_file():
            raise AssertionError(f"{wav.name}: falta {nombre} en {carpeta_resultados}")


def resumen_revision(wav: Path, info: InfoEtapa1, datos: dict, meta: dict) -> dict:
    """Contenido de `tests/reportes/integracion_<nombre>.json` para la revisión manual (tarea 5.5)."""
    segs = datos["segments"]
    por_hablante = {}
    for h in sorted({s["speaker"] for s in segs}):
        propios = [s for s in segs if s["speaker"] == h]
        por_hablante[h] = {
            "segmentos": len(propios),
            "habla_s": round(sum(s["end"] - s["start"] for s in propios), 3),
            "primeros_segmentos": propios[:3],
        }
    return {
        "grabacion": wav.name,
        "estado_etapa1": info.estado,
        "interrumpida": info.interrumpida,
        "duracion_s": info.duracion,
        "run_id": meta["run_id"],
        "dispositivo": meta["dispositivo"],
        "tiempo_s": meta["tiempo_s"],
        "hablantes": len(por_hablante),
        "segmentos": len(segs),
        "segmentos_corregidos": meta["segmentos_corregidos"],
        "segmentos_descartados": meta["segmentos_descartados"],
        "por_hablante": por_hablante,
    }
