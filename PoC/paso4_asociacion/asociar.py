"""Etapa 4 por línea de comandos, sin interfaz: asocia y escribe `transcription.json` con `name: null`.

Uso (desde PoC/paso4_asociacion/):
    python asociar.py CARPETA_DE_LA_REUNION
    python asociar.py --audio A.wav --diarizacion D.json --asr ASR.json --salida CARPETA

Código de salida: 0 si terminó bien, 1 si falló (el motivo va a la salida de errores y a
`transcription.error.json` en la carpeta de salida). Quien lo invoca decide por el código, no por los archivos.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from asociacion import asociar, resolver_rutas
from errores import AsociacionError
from salida import escribir, registrar_error


def procesar(carpeta=None, *, audio=None, diarizacion=None, asr=None, salida=None) -> Path:
    rutas = resolver_rutas(carpeta, audio=audio, diarizacion=diarizacion, asr=asr, salida=salida)
    try:
        return escribir(asociar(audio=rutas.audio, diarizacion=rutas.diarizacion, asr=rutas.asr,
                                salida=rutas.salida))
    except AsociacionError as e:
        registrar_error(rutas.salida, e)
        raise
    except Exception as e:  # error no previsto: se registra igual y se informa como fallo de la etapa
        error = AsociacionError("interno", f"{type(e).__name__}: {e}")
        error.__cause__ = e
        registrar_error(rutas.salida, error)
        raise error from e


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Etapa 4: asociación de hablantes, sin etiquetado.")
    parser.add_argument("carpeta", nargs="?", type=Path,
                        help="carpeta de la reunión con audio.wav, diarization.json y asr.json")
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--diarizacion", type=Path)
    parser.add_argument("--asr", type=Path)
    parser.add_argument("--salida", type=Path, help="carpeta de salida (por defecto, la de la reunión)")
    args = parser.parse_args(argv)
    try:
        ruta = procesar(args.carpeta, audio=args.audio, diarizacion=args.diarizacion, asr=args.asr,
                        salida=args.salida)
    except AsociacionError as e:
        print(f"Etapa 4 · {e.paso}: {e.mensaje}", file=sys.stderr)
        return 1
    print(f"Etapa 4 · {ruta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
