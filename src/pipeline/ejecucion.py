"""API pública: ejecución aislada, identificaciones y checkpoints de la PoC.

Los procesos hijos solo poseen una etapa pesada cada uno. La API nunca importa
Torch, Whisper ni Qt, y GUI/notebook/CLI comparten estas mismas funciones.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict, replace
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Callable, Mapping

from ..asociacion.asociacion import asociar
from ..asociacion.contrato import validar_asr, validar_diarizacion
from ..asociacion.etiquetado import Decision, ModeloFichas, aplicar
from ..asociacion.salida import resultado_vigente
from ..ingesta.audio import ingestar, sha256, verificar_wav
from ..minutas.contratos import SECCIONES_MINUTA
from ..minutas.generacion import ConfiguracionMinutas
from ..minutas.modelos import obtener_modelo
from ..minutas.proveedores import destino_modelo
from ..rutas import (
    ARCHIVO_ASR, ARCHIVO_AUDIO, ARCHIVO_DIARIZACION, ARCHIVO_DIARIZACION_META,
    ARCHIVO_HABLANTES, ARCHIVO_INGESTA, ARCHIVO_TRANSCRIPCION, ARCHIVO_TRANSCRIPCION_META,
    DEFINICIONES_SECCIONES_MINUTAS, PROMPT_CONSOLIDACION_MINUTAS, PROMPT_EXTRACCION_MINUTAS,
)
from .configuracion import SolicitudReunion
from .estado import artefactos_vigentes, huella, leer, publicar, registrar, vigente

Emisor = Callable[[dict], None]


class Cancelado(RuntimeError):
    pass


def _emitir(emisor: Emisor | None, evento: str, **campos):
    if emisor:
        emisor({'evento': evento, **campos})


def _paquetes(*nombres):
    versiones = {}
    for nombre in nombres:
        try:
            versiones[nombre] = version(nombre)
        except PackageNotFoundError:
            versiones[nombre] = None
    return versiones


def _consentimiento(config: ConfiguracionMinutas) -> str:
    """No transmitir información a proveedores externos sin autorización."""
    destino = destino_modelo(config.modelo)
    if destino != 'ollama_local' and not config.permitir_remoto:
        raise PermissionError(f'{destino} requiere autorización explícita para esta ejecución.')
    return destino


@contextmanager
def _exclusivo(carpeta: Path):
    """Bloqueo no bloqueante por reunión, liberado incluso ante cierre abrupto.

    Los bloqueos de sistema operativo evitan interpretar un PID reutilizado como
    una ejecución activa. El único archivo .workflow.lock no guarda estados.
    """
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / '.workflow.lock'
    with ruta.open('a+b') as archivo:
        bloqueado = False
        try:
            if os.name == 'nt':
                import msvcrt
                archivo.seek(0)
                if archivo.read(1) != b'0':
                    archivo.seek(0)
                    archivo.write(b'0')
                    archivo.flush()
                archivo.seek(0)
                try:
                    msvcrt.locking(archivo.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    raise RuntimeError('Otra ejecución está utilizando esta reunión.') from exc
            else:
                import fcntl
                try:
                    fcntl.flock(archivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise RuntimeError('Otra ejecución está utilizando esta reunión.') from exc
            bloqueado = True
            yield
        finally:
            if bloqueado:
                if os.name == 'nt':
                    archivo.seek(0)
                    msvcrt.locking(archivo.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(archivo.fileno(), fcntl.LOCK_UN)


def _trabajador(modulo: str, args: list[str], *, emisor: Emisor | None):
    """Ejecuta una etapa con nuevo intérprete; no retiene GPU en el orquestador."""
    kwargs = {}
    if os.name == 'posix':
        kwargs['start_new_session'] = True
    elif os.name == 'nt':
        kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    comando = [sys.executable, '-m', modulo, *args]
    proceso = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               cwd=Path(__file__).resolve().parents[2], text=True, **kwargs)
    try:
        stdout, stderr = proceso.communicate()
    except BaseException:
        if proceso.poll() is None:
            if os.name == 'posix':
                os.killpg(proceso.pid, signal.SIGKILL)
            else:
                proceso.kill()
            proceso.wait()
        raise
    if proceso.returncode:
        detalle = stderr.strip()[-1500:] or stdout.strip()[-1500:]
        # Secretos comunes nunca aparecen en los errores persistidos.
        for nombre in ('HF_TOKEN', 'AWS_SECRET_ACCESS_KEY', 'AWS_ACCESS_KEY_ID', 'AWS_SESSION_TOKEN'):
            secreto = os.getenv(nombre)
            if secreto:
                detalle = detalle.replace(secreto, '[REDACTED]')
        raise RuntimeError(f'{modulo} terminó con código {proceso.returncode}: {detalle}')
    return stdout


def _fase(carpeta: Path, estado: dict, nombre: str, clave: str, archivos: tuple[str, ...],
          funcion: Callable[[], object], *, emisor: Emisor | None = None, validar: Callable[[], None] | None = None):
    if vigente(carpeta, estado, nombre, clave):
        try:
            if validar:
                validar()
            _emitir(emisor, 'etapa', etapa=nombre, estado='ok', detalle='Reutilizado')
            return
        except (OSError, ValueError, KeyError, TypeError):
            pass
    estado['estado'], estado['etapa'], estado['error'] = 'procesando', nombre, None
    # Toda etapa posterior depende de la clave anterior; invalidarla en el manifiesto.
    etapas = ['preparar', 'diarizar', 'transcribir', 'asociar', 'minuta']
    for posterior in etapas[etapas.index(nombre):]:
        estado['etapas'].pop(posterior, None)
    publicar(carpeta, estado)
    _emitir(emisor, 'etapa', etapa=nombre, estado='en curso')
    inicio = time.monotonic()
    metadata = funcion()
    if validar:
        validar()
    duracion = round(time.monotonic() - inicio, 3)
    paquetes_etapa = {
        'preparar': (), 'diarizar': ('pyannote.audio', 'torch', 'torchcodec'),
        'transcribir': ('openai-whisper', 'torch'), 'asociar': (),
        'minuta': ('pydantic', 'ollama', 'boto3'),
    }
    detalles = dict(metadata) if isinstance(metadata, dict) else {}
    detalles.update({'duracion_s': duracion,
                     'versiones': {'python': sys.version.split()[0],
                                  **_paquetes(*paquetes_etapa[nombre])}})
    registrar(carpeta, estado, nombre, clave, archivos, detalles)
    _emitir(emisor, 'etapa', etapa=nombre, estado='ok', segundos=duracion)


def _validar_diar(carpeta):
    from ..diarizacion.contrato import validar_par
    problemas = validar_par(carpeta / ARCHIVO_DIARIZACION, carpeta / ARCHIVO_DIARIZACION_META)
    if problemas:
        raise ValueError('Diarización inválida: ' + '; '.join(problemas))
    meta = json.loads((carpeta / ARCHIVO_DIARIZACION_META).read_text(encoding='utf-8'))
    if meta.get('audio', {}).get('sha256') != sha256(carpeta / ARCHIVO_AUDIO):
        raise ValueError('La diarización no corresponde al audio vigente.')


def _validar_stt(carpeta):
    duracion = verificar_wav(carpeta / ARCHIVO_AUDIO) / 16000
    asr = json.loads((carpeta / ARCHIVO_ASR).read_text(encoding='utf-8'))
    validar_asr(asr, duracion, archivo=carpeta / ARCHIVO_ASR)


def _validar_transcripcion(carpeta):
    from ..minutas.entrada import leer_transcripcion
    if not resultado_vigente(carpeta):
        raise ValueError('La pareja de archivos de transcripción no es vigente.')
    leer_transcripcion(carpeta / ARCHIVO_TRANSCRIPCION)


def _validar_minutas(carpeta):
    meta = json.loads((carpeta / 'ejecucion_minutas.json').read_text(encoding='utf-8'))
    if meta['sha256_entrada'] != sha256(carpeta / ARCHIVO_TRANSCRIPCION):
        raise ValueError('La minuta no corresponde a la transcripción vigente.')
    if meta['sha256_minuta_json'] != sha256(carpeta / 'minutes.json'):
        raise ValueError('La minuta no pasa su validación SHA-256.')
    if not (carpeta / 'minutes.md').is_file():
        raise ValueError('Falta minutes.md.')
    from ..minutas.contratos import modelo_minuta, validar_evidencias
    from ..minutas.entrada import leer_transcripcion
    secciones = tuple(meta['secciones'])
    minuta = modelo_minuta(secciones).model_validate_json((carpeta / 'minutes.json').read_text(encoding='utf-8'))
    intervenciones, _ = leer_transcripcion(carpeta / ARCHIVO_TRANSCRIPCION)
    validar_evidencias(minuta, intervenciones)


def _config_serializada(config: ConfiguracionMinutas) -> dict:
    """Forma estable en memoria y en JSON (sin diferencias tupla/lista)."""
    datos = asdict(config)
    datos['secciones'] = list(datos['secciones'])
    return datos


def _solicitud_serializada(s: SolicitudReunion) -> dict:
    return {'fuentes': [str(Path(p).resolve()) for p in s.fuentes],
            'salida': str(Path(s.salida).resolve()), 'dispositivo_diarizacion': s.dispositivo_diarizacion,
            'num_speakers': s.num_speakers, 'modelo_stt': s.modelo_stt,
            'dispositivo_stt': s.dispositivo_stt, 'minutas': _config_serializada(s.minutas),
            'identificacion': s.identificacion}


def _preparar(s: SolicitudReunion, emisor: Emisor | None):
    carpeta = Path(s.salida).resolve()
    estado = leer(carpeta)
    # No gastar inferencias si el destino de minutas carece de autorización.
    _consentimiento(s.minutas)
    nueva_solicitud = _solicitud_serializada(s)
    anterior = estado.get('solicitud', {})
    if anterior.get('minutas') != nueva_solicitud['minutas']:
        estado['etapas'].pop('minuta', None)
    estado['solicitud'] = nueva_solicitud
    estado['inicio_s'] = time.time()
    estado['error'] = None
    _emitir(emisor, 'inicio', carpeta=str(carpeta))
    fuentes = [Path(x).resolve(strict=True) for x in s.fuentes]
    clave = huella([(str(f), sha256(f)) for f in fuentes], 16000, 1, 16, 'ffmpeg')

    _fase(carpeta, estado, 'preparar', clave, (ARCHIVO_AUDIO, ARCHIVO_INGESTA),
          lambda: ingestar(fuentes, carpeta), emisor=emisor,
          validar=lambda: verificar_wav(carpeta / ARCHIVO_AUDIO))
    digest_audio = sha256(carpeta / ARCHIVO_AUDIO)
    clave = huella(digest_audio, s.dispositivo_diarizacion, s.num_speakers,
                  'pyannote/speaker-diarization-community-1', _paquetes('pyannote.audio', 'torch'))
    _fase(carpeta, estado, 'diarizar', clave, (ARCHIVO_DIARIZACION, ARCHIVO_DIARIZACION_META),
          lambda: _trabajador('src.diarizacion.diarizar', [str(carpeta / ARCHIVO_AUDIO), '--salida', str(carpeta),
                 '--device', s.dispositivo_diarizacion] +
                 (['--num-speakers', str(s.num_speakers)] if s.num_speakers is not None else []), emisor=emisor),
          emisor=emisor, validar=lambda: _validar_diar(carpeta))
    clave = huella(digest_audio, s.modelo_stt, s.dispositivo_stt, _paquetes('openai-whisper', 'torch'))
    _fase(carpeta, estado, 'transcribir', clave, (ARCHIVO_ASR,),
          lambda: _trabajador('src.stt', [str(carpeta / ARCHIVO_AUDIO), '-o', str(carpeta / ARCHIVO_ASR),
                 '--model', s.modelo_stt] + (['--device', s.dispositivo_stt] if s.dispositivo_stt else []),
                 emisor=emisor), emisor=emisor, validar=lambda: _validar_stt(carpeta))
    # Asociación solo se construye con los resultados originales de ambas etapas.
    _validar_diar(carpeta)
    _validar_stt(carpeta)
    asociar(carpeta)
    estado['estado'], estado['etapa'] = 'esperando_identificacion', 'asociar'
    publicar(carpeta, estado)
    _emitir(emisor, 'etapa', etapa='asociar', estado='ok')
    return carpeta, estado


def preparar_reunion(solicitud: SolicitudReunion, *, emisor: Emisor | None = None) -> dict:
    carpeta = Path(solicitud.salida).resolve()
    with _exclusivo(carpeta):
        try:
            carpeta, estado = _preparar(solicitud, emisor)
            _emitir(emisor, 'fin', estado='esperando_identificacion', carpeta=str(carpeta))
        except BaseException as exc:
            _fallo(carpeta, exc, emisor)
            raise
    return consultar_reunion(carpeta)


def _fallo(carpeta: Path, error: BaseException, emisor: Emisor | None):
    estado = leer(carpeta)
    estado['estado'] = 'cancelado' if isinstance(error, (Cancelado, KeyboardInterrupt)) else 'fallido'
    estado['error'] = f'{type(error).__name__}: {error}'
    publicar(carpeta, estado)
    _emitir(emisor, 'etapa', etapa=estado.get('etapa', 'preparar'), estado='error', detalle=estado['error'])
    _emitir(emisor, 'fin', estado=estado['estado'], carpeta=str(carpeta))


def _continuar(carpeta: Path, decision: Decision, config: ConfiguracionMinutas, emisor: Emisor | None):
    estado = leer(carpeta)
    if estado['estado'] not in {'esperando_identificacion', 'completado', 'fallido', 'cancelado'}:
        raise ValueError('La reunión no tiene una asociación preparada para continuar.')
    for etapa in ('preparar', 'diarizar', 'transcribir'):
        registro = estado.get('etapas', {}).get(etapa) or {}
        if not registro or not vigente(carpeta, estado, etapa, registro.get('clave')):
            raise ValueError(f'La etapa {etapa} no tiene un checkpoint íntegro; prepará la reunión nuevamente.')
    if decision.accion not in {'escribir', 'cancelar'}:
        raise ValueError('La decisión de fichas no es ejecutable.')
    if decision.accion == 'cancelar':
        estado['estado'], estado['etapa'] = 'cancelado', 'asociar'
        publicar(carpeta, estado)
        return
    # Se verifica el propio contenido de los insumos al retomar; nunca confiar solo en nombres.
    _validar_diar(carpeta)
    _validar_stt(carpeta)
    asociacion = asociar(carpeta)
    clave = huella(asociacion.sha256, asdict(decision.etiquetado) if decision.etiquetado else None)
    archivos = (ARCHIVO_TRANSCRIPCION, ARCHIVO_TRANSCRIPCION_META)
    if decision.etiquetado is not None:
        archivos += (ARCHIVO_HABLANTES,)
    _fase(carpeta, estado, 'asociar', clave, archivos,
          lambda: aplicar(asociacion, decision, salida=carpeta),
          emisor=emisor, validar=lambda: _validar_transcripcion(carpeta))
    _generar(carpeta, estado, config, emisor)


def _generar(carpeta: Path, estado: dict, config: ConfiguracionMinutas, emisor: Emisor | None):
    destino = _consentimiento(config)
    # La configuración efectiva debe quedar registrada aun si se cambió al continuar.
    estado['solicitud']['minutas'] = _config_serializada(config)
    estado['destino_minutas'] = destino
    publicar(carpeta, estado)
    clave = huella(sha256(carpeta / ARCHIVO_TRANSCRIPCION), asdict(config),
                  [(p.name, sha256(p)) for p in (PROMPT_EXTRACCION_MINUTAS,
                   PROMPT_CONSOLIDACION_MINUTAS, DEFINICIONES_SECCIONES_MINUTAS)],
                  _paquetes('ollama', 'boto3', 'pydantic'))
    args = ['--entrada', str(carpeta / ARCHIVO_TRANSCRIPCION), '--salida', str(carpeta),
            '--modelo', config.modelo, '--secciones', ','.join(config.secciones),
            '--temperatura', str(config.temperatura),
            '--max-tokens-salida', str(config.max_tokens_salida),
            '--reintentos-formato', str(config.reintentos_formato),
            '--num-ctx', str(config.num_ctx), '--max-caracteres-bloque', str(config.max_caracteres_bloque),
            '--sobrescribir']
    if config.permitir_remoto:
        args.append('--permitir-remoto')
    # El proceso separado garantiza que Ollama/AWS no retienen memoria en el proceso GUI.
    _fase(carpeta, estado, 'minuta', clave,
          ('minutes.json', 'minutes.md', 'ejecucion_minutas.json'),
          lambda: _trabajador('src.minutas', args, emisor=emisor),
          emisor=emisor, validar=lambda: _validar_minutas(carpeta))
    estado['estado'], estado['etapa'] = 'completado', None
    estado['error'] = None
    publicar(carpeta, estado)
    _emitir(emisor, 'fin', estado='completa', carpeta=str(carpeta), latencia_s=None)


def continuar_reunion(reunion: str | Path, decision: Decision | None = None, *,
                      configuracion: ConfiguracionMinutas | None = None, emisor: Emisor | None = None) -> dict:
    carpeta = Path(reunion).resolve()
    with _exclusivo(carpeta):
        try:
            estado = leer(carpeta)
            cfg = configuracion or ConfiguracionMinutas(**{**estado['solicitud']['minutas'],
                                 'secciones': tuple(estado['solicitud']['minutas']['secciones'])})
            _continuar(carpeta, decision or Decision('escribir'), cfg, emisor)
        except BaseException as exc:
            _fallo(carpeta, exc, emisor)
            raise
    return consultar_reunion(carpeta)


def procesar_reunion(solicitud: SolicitudReunion, *, emisor: Emisor | None = None) -> dict:
    if solicitud.identificacion == 'pausa':
        return preparar_reunion(solicitud, emisor=emisor)
    preparar_reunion(solicitud, emisor=emisor)
    return continuar_reunion(solicitud.salida, emisor=emisor)


def consultar_reunion(reunion: str | Path) -> dict:
    carpeta = Path(reunion).resolve()
    estado = leer(carpeta)
    return {'carpeta': str(carpeta), 'estado': estado['estado'], 'etapa': estado.get('etapa'),
            'error': estado.get('error'), 'artefactos': artefactos_vigentes(carpeta, estado),
            'solicitud': estado.get('solicitud')}


def reetiquetar_reunion(reunion: str | Path, nombres: Mapping[str, str | None], *,
                        configuracion: ConfiguracionMinutas | None = None, emisor: Emisor | None = None) -> dict:
    carpeta = Path(reunion).resolve()
    asociacion = asociar(carpeta)
    fichas = ModeloFichas(asociacion)
    desconocidas = set(nombres).difference(f.etiqueta for f in fichas.fichas)
    if desconocidas:
        raise ValueError(f'Etiquetas desconocidas: {sorted(desconocidas)}')
    for ficha in fichas.fichas:
        fichas.escribir_nombre(ficha.etiqueta, nombres.get(ficha.etiqueta, ''))
    return continuar_reunion(carpeta, fichas.confirmar(), configuracion=configuracion, emisor=emisor)


def cancelar_reunion(reunion: str | Path) -> None:
    """Cancelación para ejecuciones no activas; procesos activos reciben SIGTERM del cliente."""
    carpeta = Path(reunion).resolve()
    with _exclusivo(carpeta):
        estado = leer(carpeta)
        estado['estado'] = 'cancelado'
        publicar(carpeta, estado)
