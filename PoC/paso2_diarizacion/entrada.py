"""Validación de la entrada (cabecera del WAV y `num_speakers`) y obtención del token de Hugging Face.

La cabecera se lee con `wave` (biblioteca estándar): no se decodifica el audio. La decodificación la hace
pyannote con FFmpeg (design.md §2).
"""

from __future__ import annotations

import os
import wave
from pathlib import Path

from errores import DiarizacionError

FRECUENCIA_HZ = 16000
CANALES = 1
BYTES_POR_MUESTRA = 2  # PCM16
MODELO = "pyannote/speaker-diarization-community-1"

MENSAJE_TOKEN_AUSENTE = (
    "No hay token de Hugging Face y el modelo no está en la caché local. Creá tu propio token de lectura en "
    "https://huggingface.co/settings/tokens y guardalo en un archivo .env (HF_TOKEN=...) en la carpeta desde "
    "la que ejecutás, o corré `hf auth login`. Además tenés que aceptar las condiciones del modelo en "
    f"https://huggingface.co/{MODELO}."
)


def validar_num_speakers(num_speakers) -> None:
    if num_speakers is None:
        return
    if isinstance(num_speakers, bool) or not isinstance(num_speakers, int) or num_speakers < 1:
        raise DiarizacionError("parametros",
                               f"num_speakers tiene que ser un entero mayor o igual que 1 (se recibió {num_speakers!r})")


def validar_audio(ruta) -> float:
    """Comprueba que el WAV exista y sea de 16 kHz, mono y PCM16. Devuelve su duración en segundos."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise DiarizacionError("audio", f"El audio no existe: {ruta}")
    try:
        with wave.open(str(ruta), "rb") as w:
            hz, canales, ancho = w.getframerate(), w.getnchannels(), w.getsampwidth()
            cuadros, compresion = w.getnframes(), w.getcomptype()
    except (wave.Error, EOFError) as e:
        raise DiarizacionError("audio", f"{ruta.name} no es un WAV PCM16 legible ({e}). Se espera WAV, 16 kHz, "
                                        "mono, PCM16, como lo genera la Etapa 1.") from None
    problemas = []
    if hz != FRECUENCIA_HZ:
        problemas.append(f"frecuencia {hz} Hz (se espera {FRECUENCIA_HZ} Hz)")
    if canales != CANALES:
        problemas.append(f"{canales} canales (se espera {CANALES}, mono)")
    if ancho != BYTES_POR_MUESTRA:
        problemas.append(f"{ancho * 8} bits por muestra (se espera {BYTES_POR_MUESTRA * 8}, PCM16)")
    if compresion != "NONE":
        problemas.append(f"compresión {compresion} (se espera PCM sin comprimir)")
    if problemas:
        raise DiarizacionError("audio", f"{ruta.name} no está normalizado: " + "; ".join(problemas))
    if cuadros == 0:
        raise DiarizacionError("audio", f"{ruta.name} no tiene muestras")
    return cuadros / hz


def obtener_token() -> str | None:
    """`HF_TOKEN` del entorno; si falta, el `.env` más cercano subiendo desde la carpeta actual.

    No sobrescribe variables ya definidas. Devuelve None si no hay token (se intenta usar la caché local
    o el login de `hf auth login`). El valor nunca se imprime ni se serializa.
    """
    token = os.environ.get("HF_TOKEN")
    if token:
        return token
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:
        return None
    ruta = find_dotenv(usecwd=True)
    if ruta:
        load_dotenv(ruta, override=False)
    return os.environ.get("HF_TOKEN") or None


def ocultar_token(texto: str, token: str | None) -> str:
    """Reemplaza el token en un mensaje, por si una biblioteca lo incluyera."""
    if token and texto:
        return texto.replace(token, "***")
    return texto
