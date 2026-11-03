"""Paso 1 del workflow de minutas: captura de micrófono y audio del sistema con sounddevice.

Salidas en <salida>/, con el nombre del momento en que empieza la grabación:
  YYYY_MM_DD_HH_MM_SS.wav    micrófono + audio del sistema, mono, 16 kHz, PCM 16 (entrada de pyannote)
  YYYY_MM_DD_HH_MM_SS.json   mediciones y pruebas del paso 1
El WAV se escribe mientras se graba: si el programa se corta, queda válido hasta los últimos ~0,3 s
y el .json queda con estado "grabando".

Uso:
  python captura.py --listar
  python captura.py --duracion 60 --tono
  python captura.py --mic "USB Audio:0" --sistema "CABLE Output:0,1"
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy.signal import butter, resample_poly, sosfiltfilt

FS_SALIDA = 16_000
TONO_HZ = 1_000
TONO_SEG = 0.5
TONO_INICIO_SEG = 1.0
CALENTAMIENTO_SEG = 0.5  # bloques descartados al abrir los streams (conexión de puertos)
SEG_REMUESTREO = 0.25    # bloque del remuestreo en vivo (demora de escritura ≈ este valor + 0,05 s)
SEG_PRUEBAS = 10.0       # segundos iniciales que se guardan en memoria para las pruebas del tono
SYNC_SEG = 5.0           # cada cuánto se fuerza el volcado del WAV a disco (fsync)
SFC_SET_UPDATE_HEADER_AUTO = 0x1061  # libsndfile: reescribe la cabecera WAV tras cada escritura


# ---------------------------------------------------------------------------
# Selección de dispositivos
# ---------------------------------------------------------------------------

class ErrorCaptura(RuntimeError):
    pass


@dataclass
class Fuente:
    nombre: str  # "mic" o "sistema"
    dispositivo: int
    canales: list[int]
    origen: dict = field(default_factory=dict)  # puertos detectados (solo modo automático)


def _sh(*cmd: str) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def _parsear_spec(spec: str, nombre: str) -> Fuente:
    """'DISPOSITIVO[:c1,c2]' → Fuente. DISPOSITIVO es un índice o una parte del nombre."""
    canales = None
    m = re.fullmatch(r"(.*):(\d+(?:,\d+)*)", spec)
    if m:
        spec, canales = m.group(1), [int(c) for c in m.group(2).split(",")]
    disp = int(spec) if spec.isdigit() else spec
    info = sd.query_devices(disp, "input")
    idx = info["index"]
    if canales is None:
        canales = list(range(min(2, info["max_input_channels"])))
    if max(canales) >= info["max_input_channels"]:
        raise ErrorCaptura(f"{nombre}: el dispositivo {info['name']!r} tiene {info['max_input_channels']} canales de entrada")
    return Fuente(nombre, idx, canales)


def _puertos_pipewire() -> set[str]:
    return set(_sh("pw-link", "-i").split("\n")) - {""}


def _enlaces_pipewire() -> dict[str, str]:
    """Puerto de entrada → puerto de salida conectado, según `pw-link -l`."""
    enlaces, actual = {}, None
    for linea in _sh("pw-link", "-l").splitlines():
        if not linea.startswith(" "):
            actual = linea.strip()
        elif "|<-" in linea and actual:
            enlaces[actual] = linea.split("|<-", 1)[1].strip()
    return enlaces


def _mapear_canales_jack(dispositivo: int, n_canales: int) -> dict[int, str]:
    """Abre el dispositivo JACK un instante y devuelve canal → puerto de PipeWire que lo alimenta."""
    antes = _puertos_pipewire()
    with sd.InputStream(device=dispositivo, channels=n_canales, callback=lambda *a: None):
        nuevos: set[str] = set()
        for _ in range(20):
            time.sleep(0.05)
            nuevos = _puertos_pipewire() - antes
            if len(nuevos) >= n_canales:
                break
        time.sleep(0.1)
        enlaces = _enlaces_pipewire()
    # PortAudio numera los puertos `in_N` de forma correlativa en todo el proceso (no por stream):
    # el canal es la posición del puerto dentro de este stream, no N.
    numerados = sorted((int(m.group(1)), p) for p in nuevos if (m := re.search(r"in_(\d+)$", p)))
    mapa = {}
    for canal, (_, puerto) in enumerate(numerados):
        if puerto in enlaces:
            mapa[canal] = enlaces[puerto]
    return dict(sorted(mapa.items()))


def detectar_pipewire() -> tuple[Fuente, Fuente]:
    """Linux + PipeWire: ubica la fuente por defecto (micrófono) y el monitor del sink por defecto
    (audio del sistema) entre los dispositivos JACK que expone PortAudio."""
    if platform.system() != "Linux" or not all(shutil.which(c) for c in ("pactl", "pw-link")):
        raise ErrorCaptura("Detección automática solo disponible en Linux con PipeWire. Usar --mic y --sistema.")
    jack = [i for i, h in enumerate(sd.query_hostapis()) if "JACK" in h["name"]]
    if not jack:
        raise ErrorCaptura("PortAudio no expone JACK (instalar pipewire-jack-audio-connection-kit) o usar --mic y --sistema.")
    sink = _sh("pactl", "get-default-sink").strip()
    source = _sh("pactl", "get-default-source").strip()

    mic = sistema = None
    for d in sd.query_devices():
        if d["hostapi"] != jack[0] or d["max_input_channels"] == 0:
            continue
        mapa = _mapear_canales_jack(d["index"], d["max_input_channels"])
        c_mic = {c: p for c, p in mapa.items() if p.split(":")[0] == source}
        c_sis = {c: p for c, p in mapa.items() if p.split(":")[0] == sink and ":monitor_" in p}
        if c_mic and mic is None:
            mic = Fuente("mic", d["index"], sorted(c_mic), c_mic)
        if c_sis and sistema is None:
            sistema = Fuente("sistema", d["index"], sorted(c_sis), c_sis)
    if mic is None or sistema is None:
        faltan = [n for n, f in (("micrófono", mic), ("audio del sistema", sistema)) if f is None]
        raise ErrorCaptura(f"No se encontró {' ni '.join(faltan)} (source={source}, sink={sink}). Usar --mic y --sistema.")
    return mic, sistema


def listar() -> None:
    print(sd.query_devices())
    if platform.system() == "Linux" and shutil.which("pw-link"):
        mic, sistema = detectar_pipewire()
        print("\nDetección automática (PipeWire):")
        for f in (mic, sistema):
            print(f"  {f.nombre:8s} dispositivo {f.dispositivo}, canales {f.canales}: {f.origen}")


# ---------------------------------------------------------------------------
# Grabación
# ---------------------------------------------------------------------------

class Grabador:
    """Un InputStream de sounddevice; reparte sus canales entre una o más fuentes.

    El callback solo copia el bloque a la cola de la sesión; el procesamiento ocurre en otro hilo.
    (La lectura bloqueante de PortAudio 19.7 sobre JACK pone en cero la mitad de cada bloque.)"""

    def __init__(self, dispositivo: int, fuentes: list[Fuente], cola: queue.Queue, fs: int | None):
        info = sd.query_devices(dispositivo, "input")
        self.fs = int(fs or info["default_samplerate"])
        self.nombre_disp = f"{info['name']} ({sd.query_hostapis(info['hostapi'])['name']})"
        self.fuentes = fuentes
        self.cola = cola
        self.frames = 0
        self.bloques = 0
        self.overflows: list[float] = []  # segundo de captura de cada bloque con overflow
        self.overflows_calentamiento = 0
        self.desde = math.inf  # time.monotonic() a partir del cual se guardan bloques
        self.t_primera = None  # time.monotonic() estimado de la primera muestra
        self.t_ultima = None   # time.monotonic() estimado del final de la última muestra
        self.vivo = {f.nombre: (0.0, 0.0) for f in fuentes}  # (RMS, pico) lineales del último bloque
        n_canales = max(c for f in fuentes for c in f.canales) + 1
        self.stream = sd.InputStream(device=dispositivo, channels=n_canales, samplerate=self.fs,
                                     dtype="float32", callback=self._callback)

    def _callback(self, indata, frames, tiempo, status):
        ahora = time.monotonic()
        if ahora < self.desde:
            self.overflows_calentamiento += bool(status.input_overflow)
            return
        self.cola.put((self, indata.copy(), bool(status.input_overflow), ahora))

    def registrar(self, n: int, overflow: bool, t: float):
        if self.t_primera is None:
            self.t_primera = t - n / self.fs
        self.t_ultima = t
        self.frames += n
        self.bloques += 1
        if overflow:
            self.overflows.append(round((self.frames - n) / self.fs, 3))


# ---------------------------------------------------------------------------
# Escritura en vivo: remuestreo a 16 kHz, alineación y mezcla
# ---------------------------------------------------------------------------

class Remuestreador:
    """Pasa una señal mono de fs a 16 kHz por bloques de ~0,25 s, con contexto a ambos lados para que el
    filtro no deje marcas en las uniones (mismo resultado que remuestrear la señal entera)."""

    def __init__(self, fs: int):
        g = math.gcd(fs, FS_SALIDA)
        self.up, self.down = FS_SALIDA // g, fs // g
        self.bloque = self.down * max(1, math.ceil(fs * SEG_REMUESTREO / self.down))
        self.ctx = self.down * (2000 // self.down + 1)
        self.buf = np.zeros(0, dtype="float32")
        self.pos = 0  # buf[:pos] es contexto izquierdo ya emitido; buf[pos:] falta emitir

    def _tramo(self, fin: int, n_salida: int) -> np.ndarray:
        izq = min(self.ctx, self.pos)
        y = resample_poly(self.buf[self.pos - izq : fin], self.up, self.down)
        y0 = izq * self.up // self.down
        return y[y0 : y0 + n_salida].astype("float32")

    def agregar(self, x: np.ndarray) -> np.ndarray:
        self.buf = np.concatenate([self.buf, x.astype("float32")])
        salidas = []
        while len(self.buf) - self.pos >= self.bloque + self.ctx:
            salidas.append(self._tramo(self.pos + self.bloque + self.ctx, self.bloque * self.up // self.down))
            self.pos += self.bloque
            corte = max(0, self.pos - self.ctx)
            self.buf, self.pos = self.buf[corte:], self.pos - corte
        return np.concatenate(salidas) if salidas else np.zeros(0, dtype="float32")

    def terminar(self) -> np.ndarray:
        resto = len(self.buf) - self.pos
        if resto <= 0:
            return np.zeros(0, dtype="float32")
        y = self._tramo(len(self.buf), math.ceil(resto * self.up / self.down))
        self.buf, self.pos = self.buf[:0], 0
        return y


class Mezclador:
    """Alinea las fuentes ya remuestreadas y escribe su suma en el WAV final a medida que llegan.
    Guarda en memoria los primeros SEG_PRUEBAS s de cada fuente (alineados) para las pruebas del tono."""

    def __init__(self, nombres: list[str], archivo: sf.SoundFile):
        self.archivo = archivo
        self.pendiente = {n: np.zeros(0, dtype="float32") for n in nombres}
        self.alineado = False
        self.escritas = 0
        self.saturadas = 0
        self.suma2 = {n: 0.0 for n in nombres}
        self.pico = {n: 0.0 for n in nombres}
        self.iniciales = {n: [] for n in nombres}

    def alinear(self, silencio: dict[str, int]):
        for n, k in silencio.items():
            self.pendiente[n] = np.concatenate([np.zeros(k, dtype="float32"), self.pendiente[n]])
        self.alineado = True

    def agregar(self, nombre: str, y: np.ndarray):
        if len(y):
            self.pendiente[nombre] = np.concatenate([self.pendiente[nombre], y])

    def emitir(self, final: bool = False):
        if not self.alineado:
            return
        largos = [len(v) for v in self.pendiente.values()]
        k = max(largos) if final else min(largos)
        if k == 0:
            return
        total = np.zeros(k, dtype="float32")
        for n, v in self.pendiente.items():
            parte = np.pad(v[:k], (0, k - min(k, len(v))))
            self.pendiente[n] = v[k:]
            total += parte
            self.suma2[n] += float(np.sum(parte.astype("float64") ** 2))
            self.pico[n] = max(self.pico[n], float(np.max(np.abs(parte))))
            if self.escritas < SEG_PRUEBAS * FS_SALIDA:
                self.iniciales[n].append(parte)
        self.saturadas += int(np.sum(np.abs(total) > 1))
        self.archivo.write(np.clip(total, -1, 1))
        self.escritas += k

    def niveles(self, nombre: str) -> tuple[float, float]:
        rms = math.sqrt(self.suma2[nombre] / self.escritas) if self.escritas else 0.0
        return _dbfs(rms), _dbfs(self.pico[nombre])

    def inicio(self, nombre: str) -> np.ndarray:
        return np.concatenate(self.iniciales[nombre]) if self.iniciales[nombre] else np.zeros(0, dtype="float32")


# ---------------------------------------------------------------------------
# Mediciones
# ---------------------------------------------------------------------------

def _dbfs(v: float) -> float:
    return round(20 * math.log10(v), 1) if v > 0 else -math.inf


def inicio_tono(x: np.ndarray, hasta_seg: float) -> float | None:
    """Segundo en que aparece el tono de prueba en una señal mono 16 kHz: primeros 100 ms seguidos
    con más de la mitad de la energía en 900–1100 Hz y nivel en banda sobre -60 dBFS."""
    fs = FS_SALIDA
    x = x[: int(fs * hasta_seg)]
    trama = fs // 100
    n = len(x) // trama * trama
    if n < 10 * trama:
        return None
    y = sosfiltfilt(butter(4, [TONO_HZ - 100, TONO_HZ + 100], "bandpass", fs=fs, output="sos"), x)
    e_banda = np.mean(y[:n].reshape(-1, trama) ** 2, axis=1)
    e_total = np.mean(x[:n].reshape(-1, trama) ** 2, axis=1) + 1e-12
    tono = (e_banda / e_total > 0.5) & (e_banda > 1e-6)
    for i in np.flatnonzero(tono):
        if tono[i : i + 10].all():
            return round(float(i * trama / fs), 3)
    return None


def continuidad_tono(x: np.ndarray, fs: int, inicio_seg: float) -> float:
    """Fracción de muestras no nulas (|x| > 1e-4) en la parte central del tono, en la señal original.
    Un tono continuo da ~1; huecos digitales (bloques en cero) la bajan."""
    a = max(0, int((inicio_seg + 0.1) * fs))
    x = x[a : a + int((TONO_SEG - 0.2) * fs)]
    return round(float(np.mean(np.abs(x).max(axis=1) > 1e-4)), 3) if len(x) else 0.0


class Tono:
    """Salida abierta antes de grabar (emite silencio) para no reconfigurar el grafo de audio en
    medio de la captura; `disparar()` reproduce el tono de prueba."""

    def __init__(self):
        self.fs = int(sd.query_devices(kind="output")["default_samplerate"])
        t = np.arange(int(self.fs * TONO_SEG)) / self.fs
        self.senal = (0.3 * np.sin(2 * np.pi * TONO_HZ * t)).astype("float32")
        self.pos = None
        self.t_salida = None  # time.monotonic() estimado en que el tono sale por el dispositivo
        self.stream = sd.OutputStream(samplerate=self.fs, channels=1, dtype="float32", callback=self._callback)

    def _callback(self, outdata, frames, tiempo, status):
        outdata.fill(0)
        if self.pos is None or self.pos >= len(self.senal):
            return
        if self.pos == 0:
            latencia = tiempo.outputBufferDacTime - tiempo.currentTime
            self.t_salida = time.monotonic() + (latencia if 0 < latencia < 1 else 0)
        trozo = self.senal[self.pos : self.pos + frames]
        outdata[: len(trozo), 0] = trozo
        self.pos += len(trozo)

    def disparar(self):
        self.pos = 0


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def resolver_fuentes(mic: str | None, sistema: str | None) -> tuple[list[Fuente], str]:
    """Fuentes manuales (`DISPOSITIVO[:canales]`) o detección automática si no se indica ninguna."""
    if mic or sistema:
        if not (mic and sistema):
            raise ErrorCaptura("Indicar micrófono y sistema juntos (o ninguno para detección automática).")
        return [_parsear_spec(mic, "mic"), _parsear_spec(sistema, "sistema")], "manual"
    return list(detectar_pipewire()), "automático (PipeWire/JACK)"


class Sesion:
    """Una grabación: iniciar() → avanzar() periódicamente → detener() → procesar().

    El WAV final se escribe mientras se graba (cabecera actualizada en cada escritura y fsync cada
    SYNC_SEG s): si el programa se corta, el archivo queda válido hasta los últimos ~0,3 s."""

    def __init__(self, fuentes: list[Fuente], modo: str, salida: str | Path, fs: int | None = None,
                 tono: bool = False, umbral_silencio: float = -60.0):
        self.fuentes, self.modo, self.umbral_silencio = fuentes, modo, umbral_silencio
        self.salida = Path(salida)
        self.salida.mkdir(parents=True, exist_ok=True)
        self.cola: queue.Queue = queue.Queue()
        por_disp: dict[int, list[Fuente]] = {}
        for f in fuentes:
            por_disp.setdefault(f.dispositivo, []).append(f)
        self.grabadores = [Grabador(d, fs_disp, self.cola, fs) for d, fs_disp in por_disp.items()]
        self.tono = Tono() if tono else None
        self.remuestreadores = {f.nombre: Remuestreador(g.fs) for g in self.grabadores for f in g.fuentes}
        self.originales = {f.nombre: [] for f in fuentes}  # primeros SEG_PRUEBAS s, frecuencia original
        self.hilo = threading.Thread(target=self._procesar_cola, daemon=True)
        self.error: Exception | None = None
        self.desfase: dict[str, float] = {}
        self.t_inicio = self.t_fin = None
        self.inicio: datetime | None = None  # fecha y hora de la primera muestra guardada
        self.archivo: Path | None = None
        self.wav: sf.SoundFile | None = None
        self.mezclador: Mezclador | None = None

    # --- ciclo de vida ----------------------------------------------------

    def iniciar(self) -> None:
        if self.tono:
            self.tono.stream.start()
            time.sleep(0.5)
        # El callback corre en Python: con un intervalo corto recupera el GIL rápido aunque
        # otro hilo (por ejemplo, la interfaz gráfica) esté ejecutando código.
        sys.setswitchinterval(0.001)
        self.hilo.start()
        for g in self.grabadores:
            g.stream.start()
        time.sleep(CALENTAMIENTO_SEG)
        self.t_inicio = time.monotonic()
        self.inicio = datetime.now()
        self.archivo = self._nombre_final()
        self.wav = sf.SoundFile(self.archivo, "w", FS_SALIDA, 1, "PCM_16")
        sf._snd.sf_command(self.wav._file, SFC_SET_UPDATE_HEADER_AUTO, sf._ffi.NULL, 1)
        self.mezclador = Mezclador([f.nombre for f in self.fuentes], self.wav)
        self._escribir_json({"archivo": self.archivo.name, "inicio": self.inicio.isoformat(timespec="seconds"),
                             "estado": "grabando (si queda así, la grabación se interrumpió)",
                             "modo": self.modo, "dispositivos": self.descripcion()})
        for g in self.grabadores:
            g.desde = self.t_inicio

    def transcurrido(self) -> float:
        return (self.t_fin or time.monotonic()) - self.t_inicio if self.t_inicio else 0.0

    def avanzar(self) -> None:
        """Llamar seguido mientras se graba: dispara el tono de prueba a su tiempo."""
        if self.tono and self.tono.pos is None and self.transcurrido() >= TONO_INICIO_SEG:
            self.tono.disparar()

    def niveles_vivo(self) -> dict[str, tuple[float, float]]:
        return {k: v for g in self.grabadores for k, v in g.vivo.items()}

    def descripcion(self) -> list[str]:
        return [f"{g.nombre_disp} @ {g.fs} Hz → " + ", ".join(f"{f.nombre} {f.canales}" for f in g.fuentes)
                for g in self.grabadores]

    def detener(self) -> None:
        """Cierra los dispositivos, vacía lo pendiente al WAV y lo cierra."""
        self.t_fin = time.monotonic()
        try:
            for g in self.grabadores:
                g.stream.stop()
                g.stream.close()
        finally:
            self.cola.put(None)
            self.hilo.join()
            if self.tono:
                self.tono.stream.stop()
                self.tono.stream.close()
            if self.wav is not None:
                try:
                    if self.error is None and self.mezclador.alineado:
                        for nombre, r in self.remuestreadores.items():
                            self.mezclador.agregar(nombre, r.terminar())
                        self.mezclador.emitir(final=True)
                finally:
                    self.wav.close()
        if self.error is not None:
            raise ErrorCaptura(f"Error durante la grabación ({type(self.error).__name__}: {self.error}). "
                               f"El audio hasta ese momento quedó en {self.archivo}")
        for g in self.grabadores:
            if g.t_primera is None:
                raise ErrorCaptura(f"{g.nombre_disp} no entregó audio.")

    def procesar(self) -> dict:
        """Calcula las pruebas y escribe el reporte .json junto al WAV. Devuelve el reporte."""
        t_tono = self.tono.t_salida if self.tono else None
        t0 = min(g.t_primera for g in self.grabadores)
        reporte = construir_reporte(self, t_tono, t0)
        self._escribir_json(reporte)
        return reporte

    # --- internos ---------------------------------------------------------

    def _procesar_cola(self):
        ultimo_sync = time.monotonic()
        try:
            while (item := self.cola.get()) is not None:
                g, bloque, overflow, t = item
                g.registrar(len(bloque), overflow, t)
                for f in g.fuentes:
                    x = bloque[:, f.canales]
                    g.vivo[f.nombre] = (float(np.sqrt(np.mean(x**2))), float(np.max(np.abs(x))))
                    if (g.frames - len(bloque)) < SEG_PRUEBAS * g.fs:
                        self.originales[f.nombre].append(x)
                    self.mezclador.agregar(f.nombre, self.remuestreadores[f.nombre].agregar(x.mean(axis=1)))
                if not self.mezclador.alineado and all(gr.t_primera is not None for gr in self.grabadores):
                    # Alineación: cada fuente arranca con silencio hasta la primera muestra del stream más tardío
                    t0 = min(gr.t_primera for gr in self.grabadores)
                    self.desfase = {f.nombre: gr.t_primera - t0 for gr in self.grabadores for f in gr.fuentes}
                    self.mezclador.alinear({n: round(d * FS_SALIDA) for n, d in self.desfase.items()})
                self.mezclador.emitir()
                if time.monotonic() - ultimo_sync >= SYNC_SEG:
                    self.wav.flush()  # sf_write_sync → fsync: protege también ante cortes de luz
                    ultimo_sync = time.monotonic()
        except Exception as e:  # noqa: BLE001 — se informa al detener
            self.error = e
            while self.cola.get() is not None:  # vacía la cola para que detener() no se bloquee
                pass

    def _nombre_final(self) -> Path:
        base = self.inicio.strftime("%Y_%m_%d_%H_%M_%S")
        destino, n = self.salida / f"{base}.wav", 2
        while destino.exists():
            destino, n = self.salida / f"{base}_{n}.wav", n + 1
        return destino

    def _escribir_json(self, datos: dict):
        self.archivo.with_suffix(".json").write_text(json.dumps(datos, indent=2, ensure_ascii=False))


def grabar(args) -> Path:
    fuentes, modo = resolver_fuentes(args.mic, args.sistema)
    sesion = Sesion(fuentes, modo, args.salida, args.fs, args.tono, args.umbral_silencio)
    print(f"Modo {modo}. Salida en {sesion.salida}")
    for linea in sesion.descripcion():
        print(f"  {linea}")
    print("Ctrl+C para terminar." if args.duracion is None else f"Duración: {args.duracion} s.")
    sesion.iniciar()
    try:
        while args.duracion is None or sesion.transcurrido() < args.duracion:
            sesion.avanzar()
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    sesion.detener()
    print("Grabación detenida. Procesando...")
    imprimir_reporte(sesion.procesar())
    print(f"\nArchivo: {sesion.archivo}")
    return sesion.archivo


def construir_reporte(sesion: Sesion, t_tono: float | None, t0: float) -> dict:
    m, desfase = sesion.mezclador, sesion.desfase
    g_de = {f.nombre: g for g in sesion.grabadores for f in g.fuentes}
    rep_fuentes = {}
    for f in sesion.fuentes:
        g = g_de[f.nombre]
        dur_muestras = g.frames / g.fs
        dur_reloj = g.t_ultima - g.t_primera
        rms, pico = m.niveles(f.nombre)
        rep_fuentes[f.nombre] = {
            "dispositivo": g.nombre_disp,
            "canales": f.canales,
            "puertos": f.origen or None,
            "fs_original_hz": g.fs,
            "muestras": g.frames,
            "duracion_muestras_s": round(dur_muestras, 3),
            "duracion_reloj_s": round(dur_reloj, 3),
            "faltante_s": round(dur_reloj - dur_muestras, 3),
            "overflows": len(g.overflows),
            "overflows_en_s": g.overflows,
            "overflows_calentamiento_descartado": g.overflows_calentamiento,
            "bloques": g.bloques,
            "desfase_inicio_s": round(desfase[f.nombre], 4),
            "rms_dbfs": rms,
            "pico_dbfs": pico,
        }

    salida = sf.info(str(sesion.archivo))
    t_inicio, t_fin, umbral = sesion.t_inicio, sesion.t_fin, sesion.umbral_silencio
    tol = 0.05 + 0.001 * (t_fin - t_inicio)
    mismo_stream = len(sesion.grabadores) == 1
    pruebas = [
        {
            "prueba": "ambas fuentes registran señal",
            "ok": all(v["rms_dbfs"] > umbral for v in rep_fuentes.values()),
            "detalle": {k: v["rms_dbfs"] for k, v in rep_fuentes.items()} | {"umbral_dbfs": umbral},
        },
        {
            "prueba": "sin pérdidas",
            "ok": all(v["overflows"] == 0 and abs(v["faltante_s"]) <= tol for v in rep_fuentes.values()),
            "detalle": {k: {"overflows": v["overflows"], "faltante_s": v["faltante_s"]} for k, v in rep_fuentes.items()}
            | {"tolerancia_s": round(tol, 3)},
        },
        {
            "prueba": "sin desincronización",
            "ok": mismo_stream or abs(rep_fuentes["mic"]["faltante_s"] - rep_fuentes["sistema"]["faltante_s"]) <= tol,
            "detalle": "mismo stream: sincronía por muestra" if mismo_stream else {
                "desfase_inicio_compensado_s": {k: v["desfase_inicio_s"] for k, v in rep_fuentes.items()},
                "deriva_s": round(rep_fuentes["mic"]["faltante_s"] - rep_fuentes["sistema"]["faltante_s"], 3),
            },
        },
        {
            "prueba": "salida procesable (mono, 16 kHz, PCM 16)",
            "ok": salida.samplerate == FS_SALIDA and salida.channels == 1 and salida.subtype == "PCM_16"
            and salida.frames > 0,
            "detalle": {"fs_hz": salida.samplerate, "canales": salida.channels, "formato": salida.subtype,
                        "duracion_s": round(salida.duration, 3), "muestras_saturadas": m.saturadas},
        },
    ]
    if t_tono is not None:
        esperado = round(t_tono - t0, 3)
        en_sis = inicio_tono(m.inicio("sistema"), esperado + 2)
        en_mic = inicio_tono(m.inicio("mic"), esperado + 2)
        continuidad = None
        if en_sis is not None:
            orig = np.concatenate(sesion.originales["sistema"])
            continuidad = continuidad_tono(orig, g_de["sistema"].fs, en_sis - desfase["sistema"])
        pruebas.append({
            "prueba": "tono de prueba capturado como audio del sistema",
            "ok": en_sis is not None and -0.1 <= en_sis - esperado <= 0.5 and continuidad >= 0.98,
            "detalle": {"enviado_s": esperado, "detectado_sistema_s": en_sis, "continuidad": continuidad,
                        "detectado_mic_s": en_mic,
                        "retardo_mic_vs_sistema_s": round(en_mic - en_sis, 3)
                        if en_mic is not None and en_sis is not None else None},
        })

    return {
        "archivo": sesion.archivo.name,
        "inicio": sesion.inicio.isoformat(timespec="seconds"),
        "estado": "completa",
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "modo": sesion.modo,
        "equipo": {"so": platform.platform(), "python": platform.python_version(),
                   "sounddevice": sd.__version__, "portaudio": sd.get_portaudio_version()[1]},
        "duracion_total_s": round(t_fin - t_inicio, 3),
        "fuentes": rep_fuentes,
        "pruebas": pruebas,
    }


def imprimir_reporte(rep: dict) -> None:
    print(f"\n{'fuente':8s} {'fs':>6s} {'dur s':>8s} {'falt. s':>8s} {'overfl.':>7s} {'desf. s':>8s} {'RMS dB':>7s} {'pico dB':>7s}")
    for k, v in rep["fuentes"].items():
        print(f"{k:8s} {v['fs_original_hz']:6d} {v['duracion_muestras_s']:8.2f} {v['faltante_s']:8.3f} "
              f"{v['overflows']:7d} {v['desfase_inicio_s']:8.4f} {v['rms_dbfs']:7.1f} {v['pico_dbfs']:7.1f}")
    print()
    for p in rep["pruebas"]:
        print(f"[{'OK' if p['ok'] else 'FALLA':5s}] {p['prueba']}: {json.dumps(p['detalle'], ensure_ascii=False)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listar", action="store_true", help="lista dispositivos y la detección automática")
    ap.add_argument("--mic", help="DISPOSITIVO[:canales] del micrófono (índice o parte del nombre)")
    ap.add_argument("--sistema", help="DISPOSITIVO[:canales] del audio del sistema (loopback, monitor, cable virtual)")
    ap.add_argument("--duracion", type=float, help="segundos a grabar (sin este valor: hasta Ctrl+C)")
    ap.add_argument("--fs", type=int, help="frecuencia de captura (por defecto, la del dispositivo)")
    ap.add_argument("--tono", action="store_true", help=f"reproduce un tono de {TONO_HZ} Hz a los {TONO_INICIO_SEG} s para verificar la captura del sistema")
    ap.add_argument("--umbral-silencio", type=float, default=-60.0, help="RMS mínimo en dBFS para considerar que una fuente registró señal")
    ap.add_argument("--salida", default=str(Path(__file__).parent / "grabaciones"))
    args = ap.parse_args()
    try:
        listar() if args.listar else grabar(args)
    except ErrorCaptura as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
