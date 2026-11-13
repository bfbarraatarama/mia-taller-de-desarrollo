"""Etapa 2 del pipeline: diarización de `audio.wav` con pyannote `speaker-diarization-community-1`.

Uso por línea de comandos:
    python diarizar.py AUDIO.wav [--salida DIR] [--device auto|cpu|cuda] [--num-speakers N]

Uso como función:
    from diarizar import diarizar
    resultado = diarizar("audio.wav", device="auto")   # lanza DiarizacionError si falla

Códigos de salida: 0 éxito, 1 fallo de la ejecución, 2 parámetros inválidos.
Quien invoque esta etapa decide por el código de salida o por la excepción, nunca por la presencia de
`diarization.json` (design.md §5).

PyTorch y pyannote se importan dentro de las funciones: `--help`, la validación de la entrada y las pruebas
de nivel 1 no los cargan.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import platform
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path

from contrato import validar_diarizacion
from dispositivo import MODOS, elegir_dispositivo
from entrada import (MENSAJE_TOKEN_AUSENTE, MODELO, obtener_token, ocultar_token, validar_audio,
                     validar_num_speakers)
from errores import DiarizacionError
from resultados import NOMBRE_ERROR, carpeta_reunion, escribir_par, registrar_error
from segmentos import TOLERANCIA_FIN_S, normalizar

URL_MODELO = f"https://huggingface.co/{MODELO}"
_PISTAS_FFMPEG = ("ffmpeg", "torchcodec", "libav", "avcodec", "avformat")


def _cargar_pipeline(token: str | None):
    """Carga el pipeline de pyannote. Las pruebas lo reemplazan por uno falso."""
    from pyannote.audio import Pipeline
    return Pipeline.from_pretrained(MODELO, token=token)


def _version(paquete: str) -> str | None:
    from importlib import metadata
    try:
        return metadata.version(paquete)
    except metadata.PackageNotFoundError:
        return None


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _es_error_ffmpeg(e: BaseException) -> bool:
    texto = f"{type(e).__module__} {type(e).__name__} {e}".lower()
    return any(p in texto for p in _PISTAS_FFMPEG)


def _error_ffmpeg(e: BaseException, token: str | None) -> DiarizacionError:
    return DiarizacionError(
        "decodificacion",
        "FFmpeg no disponible o incompatible: pyannote no pudo leer el audio. Verificá FFmpeg (build *shared* con "
        "su carpeta bin en PATH) siguiendo la sección FFmpeg del README. Detalle: "
        + ocultar_token(f"{type(e).__name__}: {e}", token),
        tipo=type(e).__name__)


def _error_modelo(e: BaseException, token: str | None) -> DiarizacionError:
    if _es_error_ffmpeg(e):
        return _error_ffmpeg(e, token)
    detalle = ocultar_token(f"{type(e).__name__}: {e}", token)
    if token is None:
        return DiarizacionError("token", f"{MENSAJE_TOKEN_AUSENTE} Detalle: {detalle}", tipo=type(e).__name__)
    return DiarizacionError(
        "modelo",
        f"No se pudo cargar {MODELO}. Comprobá que tu token sea válido y que aceptaste las condiciones en "
        f"{URL_MODELO}. Detalle: {detalle}", tipo=type(e).__name__)


def _ejecutar_modelo(audio: Path, dispositivo: str, num_speakers: int | None, token: str | None) -> dict:
    """Carga el pipeline, lo ejecuta y libera la memoria (design.md §7). Devuelve datos sin tensores."""
    import torch

    es_cuda = dispositivo == "cuda"
    oom = (getattr(torch.cuda, "OutOfMemoryError", None) or getattr(torch, "OutOfMemoryError", None)
           or type("_SinOutOfMemoryError", (Exception,), {}))
    pipeline = None
    out = None
    fallo = None
    resultado = None
    try:
        if es_cuda:
            torch.cuda.reset_peak_memory_stats()
        try:
            pipeline = _cargar_pipeline(token)
            if pipeline is None:
                raise RuntimeError("from_pretrained devolvió None")
            pipeline.to(torch.device(dispositivo))
        except Exception as e:  # el error se arma dentro del except y se lanza afuera (ver abajo)
            fallo = _error_modelo(e, token)
        if fallo is None:
            kwargs = {"num_speakers": num_speakers} if num_speakers is not None else {}
            try:
                out = pipeline(str(audio), **kwargs)
                turnos = [(float(t.start), float(t.end), str(s)) for t, s in out.speaker_diarization]
                resultado = {
                    "turnos": turnos,
                    "gpu": torch.cuda.get_device_name() if es_cuda else None,
                    "vram_pico_mib": round(torch.cuda.max_memory_allocated() / 2**20, 1) if es_cuda else None,
                }
            except oom as e:
                fallo = DiarizacionError(
                    "ejecucion",
                    "La GPU se quedó sin memoria durante la diarización. Probá con --device cpu, o liberá la GPU "
                    "de otros procesos. Detalle: " + ocultar_token(str(e), token),
                    tipo=type(e).__name__)
            except Exception as e:
                fallo = (_error_ffmpeg(e, token) if _es_error_ffmpeg(e) else
                         DiarizacionError("ejecucion", ocultar_token(f"{type(e).__name__}: {e}", token),
                                          tipo=type(e).__name__))
    finally:
        del out
        del pipeline
        gc.collect()
        if es_cuda:
            torch.cuda.empty_cache()
    # Se lanza fuera de los except: así la excepción original (y su traceback, que referencia al modelo y a
    # sus tensores) ya no está viva y la memoria de la GPU queda liberada.
    if fallo is not None:
        raise fallo
    return resultado


def diarizar(audio, salida=None, device: str = "auto", num_speakers: int | None = None) -> dict:
    """Diariza `audio` y escribe `diarization.json` y `diarization.meta.json` en la carpeta de la reunión.

    Lanza `DiarizacionError` si falla; en ese caso escribe `diarization.error.json` (salvo que el audio no
    exista o los parámetros sean inválidos) y no toca un resultado válido anterior.
    """
    inicio = datetime.now().astimezone()
    t0 = time.perf_counter()
    run_id = f"{inicio:%Y%m%dT%H%M%S}-{secrets.token_hex(3)}"
    audio = Path(audio).absolute()

    # Errores sin archivos: parámetros inválidos o audio inexistente.
    validar_num_speakers(num_speakers)
    if device not in MODOS:
        raise DiarizacionError("parametros", f"Modo de dispositivo desconocido: {device!r} (opciones: {', '.join(MODOS)})")
    if not audio.is_file():
        raise DiarizacionError("audio", f"El audio no existe: {audio}")

    carpeta = carpeta_reunion(audio, salida)
    token = None
    try:
        duracion = validar_audio(audio)
        sha_audio = _sha256(audio)
        token = obtener_token()
        dispositivo = elegir_dispositivo(device)
        modelo = _ejecutar_modelo(audio, dispositivo, num_speakers, token)

        segmentos, corregidos, descartados, exceso_fin_max = normalizar(modelo["turnos"], duracion)
        diarizacion = {"segments": segmentos}
        violaciones = validar_diarizacion(diarizacion, duracion)
        if violaciones:
            raise DiarizacionError("contrato", "La salida normalizada no cumple el contrato: " + "; ".join(violaciones))

        import torch
        hablantes = sorted({s["speaker"] for s in segmentos})
        meta = {
            "run_id": run_id,
            "inicio": inicio.isoformat(timespec="seconds"),
            "audio": {"ruta": str(audio), "duracion_s": duracion, "sha256": sha_audio},
            "modo_dispositivo": device,
            "dispositivo": dispositivo,
            "gpu": modelo["gpu"],
            "modelo": MODELO,
            "versiones": {"python": platform.python_version(), "torch": torch.__version__,
                          "pyannote.audio": _version("pyannote.audio")},
            "num_speakers": num_speakers,
            "tolerancia_fin_s": TOLERANCIA_FIN_S,  # heredado: ya no controla descartes (design.md §4)
            "exceso_fin_max_s": exceso_fin_max,
            "hablantes": len(hablantes),
            "segmentos": len(segmentos),
            "segmentos_corregidos": corregidos,
            "segmentos_descartados": descartados,
            "tiempo_s": round(time.perf_counter() - t0, 3),
            "vram_pico_mib": modelo["vram_pico_mib"],
        }
        try:
            meta = escribir_par(carpeta, diarizacion, meta)
        except OSError as e:
            raise DiarizacionError("escritura", f"No se pudo escribir el resultado en {carpeta}: {e}",
                                   tipo=type(e).__name__) from None
    except DiarizacionError as e:
        _registrar(e, carpeta, run_id, inicio, device, token)
        raise
    except Exception as e:  # fallo inesperado: se informa igual, con su etapa
        error = DiarizacionError("ejecucion", ocultar_token(f"{type(e).__name__}: {e}", token), tipo=type(e).__name__)
        _registrar(error, carpeta, run_id, inicio, device, token)
        raise error from None

    resumen = {h: round(sum(s["end"] - s["start"] for s in segmentos if s["speaker"] == h), 3) for h in hablantes}
    return {"run_id": run_id, "carpeta": str(carpeta), "dispositivo": dispositivo, "hablantes": len(hablantes),
            "segmentos": len(segmentos), "tiempo_s": meta["tiempo_s"], "habla_por_hablante_s": resumen,
            "meta": meta}


def _registrar(error: DiarizacionError, carpeta: Path, run_id: str, inicio: datetime, device: str, token):
    error.mensaje = ocultar_token(error.mensaje, token)
    try:
        error.archivo_error = registrar_error(
            carpeta, run_id=run_id, inicio=inicio.isoformat(timespec="seconds"), etapa=error.etapa,
            tipo=error.tipo, mensaje=error.mensaje, modo_dispositivo=device)
    except OSError:
        error.archivo_error = None  # el fallo se informa igual por la excepción y el código de salida


def _entero_positivo(texto: str) -> int:
    try:
        n = int(texto)
    except ValueError:
        raise argparse.ArgumentTypeError(f"no es un entero: {texto!r}") from None
    if n < 1:
        raise argparse.ArgumentTypeError(f"tiene que ser mayor o igual que 1: {n}")
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="diarizar.py",
        description="Etapa 2: diariza un WAV de 16 kHz, mono, PCM16 y escribe diarization.json.")
    parser.add_argument("audio", type=Path, help="WAV normalizado generado por la Etapa 1")
    parser.add_argument("--salida", type=Path, help="carpeta de resultados (por defecto <carpeta>/<nombre del audio>/)")
    parser.add_argument("--device", choices=MODOS, default="auto", help="dispositivo (por defecto: auto)")
    parser.add_argument("--num-speakers", type=_entero_positivo, help="cantidad exacta de hablantes (opcional)")
    args = parser.parse_args(argv)

    try:
        r = diarizar(args.audio, salida=args.salida, device=args.device, num_speakers=args.num_speakers)
    except DiarizacionError as e:
        print(f"Error en la etapa '{e.etapa}': {e.mensaje}", file=sys.stderr)
        if e.archivo_error:
            print(f"Registrado en {e.archivo_error}", file=sys.stderr)
        print("La ejecución falló: no usar un diarization.json anterior como resultado de esta ejecución.",
              file=sys.stderr)
        return 1

    print(f"Diarización completa ({r['dispositivo']}, {r['tiempo_s']} s): {r['hablantes']} hablantes, "
          f"{r['segmentos']} segmentos -> {r['carpeta']}")
    for hablante, segundos in r["habla_por_hablante_s"].items():
        print(f"  {hablante}: {segundos:.1f} s de habla")
    return 0


if __name__ == "__main__":
    sys.exit(main())
