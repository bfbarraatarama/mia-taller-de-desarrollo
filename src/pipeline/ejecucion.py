"""API pública: ejecución aislada, identificaciones y checkpoints de la PoC.

Los procesos hijos solo poseen una etapa pesada cada uno. La API nunca importa
Torch, Whisper ni Qt, y GUI/notebook/CLI comparten estas mismas funciones.
"""
from __future__ import annotations

import errno
import json
import os
import signal
import subprocess
import sys
from time import monotonic
import wave
from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import asdict, replace
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Callable, Mapping

from ..asociacion.asociacion import asociar
from ..asociacion.contrato import validar_asr, validar_diarizacion, validar_transcripcion, validar_speakers
from ..asociacion.errores import AsociacionError
from ..asociacion.etiquetado import Decision, Etiquetado, ModeloFichas, aplicar
from ..asociacion.salida import resultado_vigente
from ..ingesta.audio import ingestar, sha256, verificar_wav
from ..minutas.generacion import ConfiguracionMinutas, _preparar_prompts
from ..minutas.modelos import obtener_modelo
from ..minutas.proveedores import resolver_destino, comprobar_autorizacion
from ..rutas import (
    ARCHIVO_ASR, ARCHIVO_AUDIO, ARCHIVO_DIARIZACION, ARCHIVO_DIARIZACION_META,
    ARCHIVO_HABLANTES, ARCHIVO_TRANSCRIPCION, ARCHIVO_TRANSCRIPCION_META,
    DEFINICIONES_SECCIONES_MINUTAS, PROMPT_CONSOLIDACION_MINUTAS, PROMPT_EXTRACCION_MINUTAS,
)
from .configuracion import SolicitudReunion
from .estado import (ARCHIVOS, artefactos_vigentes, etapas_vigentes, huella, invalidar,
                     leer, publicar, registrar, vigente)
from .fuentes import (clave_ingesta, comprobar_identidades, conservar_fuentes, resolver_fuentes, validar_ingesta)
from .temporalidad import Medicion, ahora

Emisor = Callable[[dict], None]
ERRORES_CHECKPOINT = (OSError, ValueError, KeyError, TypeError, AttributeError, wave.Error, EOFError, AsociacionError)


class Cancelado(RuntimeError):
    pass


class ReunionOcupada(RuntimeError):
    pass


class AutorizacionRechazada(PermissionError):
    """Rechazo previo a publicar cambios de una continuación."""


_descriptor_lock: ContextVar[int | None] = ContextVar('descriptor_lock', default=None)


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
    destino = resolver_destino(config.modelo)
    comprobar_autorizacion(destino, config.permitir_remoto, config.destino_autorizado)
    return destino.tipo


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
                    if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                        raise
                    raise ReunionOcupada('Otra ejecución está utilizando esta reunión.') from exc
            else:
                import fcntl
                try:
                    fcntl.flock(archivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise ReunionOcupada('Otra ejecución está utilizando esta reunión.') from exc
            bloqueado = True
            token = _descriptor_lock.set(archivo.fileno() if os.name == 'posix' else None)
            try:
                yield
            finally:
                _descriptor_lock.reset(token)
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
        # Si el padre muere abruptamente, el hijo conserva el bloqueo hasta salir.
        descriptor = _descriptor_lock.get()
        if descriptor is not None:
            kwargs['pass_fds'] = (descriptor,)
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
        for nombre in ('HF_TOKEN', 'AWS_SECRET_ACCESS_KEY', 'AWS_ACCESS_KEY_ID', 'AWS_SESSION_TOKEN', 'OLLAMA_API_KEY'):
            secreto = os.getenv(nombre)
            if secreto:
                detalle = detalle.replace(secreto, '[REDACTED]')
        raise RuntimeError(f'{modulo} terminó con código {proceso.returncode}: {detalle}')
    return stdout


def _fase(carpeta: Path, estado: dict, nombre: str, clave: str, archivos: tuple[str, ...],
          funcion: Callable[[], object], *, medicion: Medicion, emisor: Emisor | None = None,
          validar: Callable[[], None] | None = None):
    if vigente(carpeta, estado, nombre, clave):
        try:
            if validar:
                validar()
        except ERRORES_CHECKPOINT:
            pass
        else:
            medicion.etapa(nombre, 'reutilizada', 0.0)
            medicion.actualizar()
            publicar(carpeta, estado)
            _emitir(emisor, 'etapa', etapa=nombre, estado='ok', detalle='Reutilizado')
            return
    estado['estado'], estado['etapa'], estado['error'] = 'procesando', nombre, None
    invalidar(estado, nombre)
    medicion.etapa(nombre, 'en_curso')
    medicion.actualizar()
    publicar(carpeta, estado)
    _emitir(emisor, 'etapa', etapa=nombre, estado='en curso')
    inicio = monotonic()
    try:
        metadata = funcion()
        if validar:
            validar()
    except BaseException as exc:
        estado_etapa = 'cancelada' if isinstance(exc, (Cancelado, KeyboardInterrupt)) else 'fallida'
        medicion.etapa(nombre, estado_etapa, round(monotonic() - inicio, 3))
        raise
    duracion = round(monotonic() - inicio, 3)
    paquetes_etapa = {
        'preparar': (), 'diarizar': ('pyannote.audio', 'torch', 'torchcodec'),
        'transcribir': ('openai-whisper', 'torch'), 'asociar': (),
        'minuta': ('pydantic', 'ollama', 'boto3'),
    }
    detalles = dict(metadata) if isinstance(metadata, dict) else {}
    detalles.update({'tiempo_procesamiento_s': duracion,
                     'versiones': {'python': sys.version.split()[0],
                                  **_paquetes(*paquetes_etapa[nombre])}})
    medicion.etapa(nombre, 'ejecutada', duracion)
    medicion.actualizar()
    registrar(carpeta, estado, nombre, clave, archivos, detalles)
    _emitir(emisor, 'etapa', etapa=nombre, estado='ok', segundos=duracion)


def _validar_diar(carpeta, solicitud=None):
    from ..diarizacion.contrato import validar_par
    problemas = validar_par(carpeta / ARCHIVO_DIARIZACION, carpeta / ARCHIVO_DIARIZACION_META)
    if problemas:
        raise ValueError('Diarización inválida: ' + '; '.join(problemas))
    meta = json.loads((carpeta / ARCHIVO_DIARIZACION_META).read_text(encoding='utf-8'))
    datos = json.loads((carpeta / ARCHIVO_DIARIZACION).read_text(encoding='utf-8'))
    problemas = validar_diarizacion(datos, verificar_wav(carpeta / ARCHIVO_AUDIO) / 16000)
    if problemas:
        raise ValueError('Diarización inválida: ' + '; '.join(problemas))
    if meta.get('audio', {}).get('sha256') != sha256(carpeta / ARCHIVO_AUDIO):
        raise ValueError('La diarización no corresponde al audio vigente.')
    if solicitud is not None:
        modo = solicitud['dispositivo_diarizacion']
        from ..diarizacion.entrada import MODELO
        if (meta.get('modelo') != MODELO or meta.get('modo_dispositivo') != modo
                or meta.get('num_speakers') != solicitud['num_speakers']
                or meta.get('dispositivo') not in {'cpu', 'cuda'}
                or (modo != 'auto' and meta['dispositivo'] != modo)):
            raise ValueError('La diarización no corresponde a su configuración.')


def _validar_stt(carpeta):
    duracion = verificar_wav(carpeta / ARCHIVO_AUDIO) / 16000
    asr = json.loads((carpeta / ARCHIVO_ASR).read_text(encoding='utf-8'))
    validar_asr(asr, duracion, archivo=carpeta / ARCHIVO_ASR)


def _validar_transcripcion(carpeta):
    from ..minutas.entrada import leer_transcripcion
    if not resultado_vigente(carpeta):
        raise ValueError('La pareja de archivos de transcripción no es vigente.')
    leer_transcripcion(carpeta / ARCHIVO_TRANSCRIPCION)
    meta = json.loads((carpeta / ARCHIVO_TRANSCRIPCION_META).read_text(encoding='utf-8'))
    datos = json.loads((carpeta / ARCHIVO_TRANSCRIPCION).read_text(encoding='utf-8'))
    etiquetas = {s['speaker'] for s in json.loads((carpeta / ARCHIVO_DIARIZACION).read_text())['segments']}
    duracion = verificar_wav(carpeta / ARCHIVO_AUDIO) / 16000
    nombres = (ARCHIVO_AUDIO, ARCHIVO_DIARIZACION, ARCHIVO_ASR, ARCHIVO_TRANSCRIPCION)
    if meta['etiquetado']:
        nombres += (ARCHIVO_HABLANTES,)
        speakers = json.loads((carpeta / ARCHIVO_HABLANTES).read_text(encoding='utf-8'))
        if validar_speakers(speakers, duracion, etiquetas):
            raise ValueError('Fichas de hablantes inválidas.')
    if any(meta['sha256'].get(n) != sha256(carpeta / n) for n in nombres):
        raise ValueError('La asociación no corresponde a sus insumos.')
    if validar_transcripcion(datos, duracion, etiquetas):
        raise ValueError('Transcripción fuera de contrato.')


def _validar_minutas(carpeta, config=None, *, prompts_actuales=False, destino=None):
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
    from ..minutas.formato import a_markdown
    if (carpeta / 'minutes.md').read_text(encoding='utf-8') != a_markdown(minuta, intervenciones):
        raise ValueError('La minuta Markdown no corresponde a la minuta estructurada.')
    if config is not None:
        modelo = obtener_modelo(config.modelo)
        datos = _config_serializada(config)
        guardados = dict(meta['configuracion'])
        # Una autorización histórica no forma parte de la identidad de la salida.
        guardados.pop('permitir_remoto', None)
        guardados.pop('destino_autorizado', None)
        if (secciones != tuple(config.secciones) or meta['modelo'] != modelo.identificador
                or meta['proveedor'] != modelo.proveedor or guardados != datos):
            raise ValueError('La minuta no corresponde a su configuración.')
        if prompts_actuales and meta['prompts'] != _preparar_prompts(config.secciones)[2]:
            raise ValueError('La minuta no corresponde a los prompts vigentes.')
        if destino is not None and 'huella_destino' in meta and (
                meta['huella_destino'] != destino.huella or meta.get('destino') != destino.tipo):
            raise ValueError('La minuta no corresponde al destino configurado.')


def _config_serializada(config: ConfiguracionMinutas) -> dict:
    """Forma estable en memoria y en JSON (sin diferencias tupla/lista)."""
    datos = asdict(config)
    datos['secciones'] = list(datos['secciones'])
    datos.pop('permitir_remoto')
    datos.pop('destino_autorizado')
    return datos


def _solicitud_serializada(s: SolicitudReunion) -> dict:
    return {'fuentes': [str(Path(p).expanduser().resolve()) for p in s.fuentes],
            'salida': str(Path(s.salida).resolve()), 'dispositivo_diarizacion': s.dispositivo_diarizacion,
            'num_speakers': s.num_speakers, 'modelo_stt': s.modelo_stt,
            'dispositivo_stt': s.dispositivo_stt, 'minutas': _config_serializada(s.minutas),
            'identificacion': s.identificacion}


def _clave_diar(digest: str, solicitud: dict, versiones: dict | None = None) -> str:
    from ..diarizacion.entrada import MODELO
    paquetes = ('pyannote.audio', 'torch')
    identidad = _paquetes(*paquetes) if versiones is None else {p: versiones[p] for p in paquetes}
    return huella(digest, solicitud['dispositivo_diarizacion'], solicitud['num_speakers'], MODELO, identidad)


def _clave_stt(digest: str, solicitud: dict, versiones: dict | None = None) -> str:
    paquetes = ('openai-whisper', 'torch')
    identidad = _paquetes(*paquetes) if versiones is None else {p: versiones[p] for p in paquetes}
    return huella(digest, solicitud['modelo_stt'], solicitud['dispositivo_stt'], identidad)


def _config_desde_estado(estado: dict) -> ConfiguracionMinutas:
    if not estado.get('solicitud'):
        raise ValueError('La reunión no tiene una solicitud de procesamiento.')
    datos = estado['solicitud']['minutas']
    return ConfiguracionMinutas(**{**datos, 'secciones': tuple(datos['secciones']),
                                  'permitir_remoto': False, 'destino_autorizado': None})


def _clave_minutas(carpeta: Path, config: ConfiguracionMinutas, destino=None) -> str:
    # La autorización no altera el resultado de una inferencia. Unidad de identidad: modelo y destino.
    modelo = obtener_modelo(config.modelo)
    destino = (destino or resolver_destino(config.modelo)).identidad[1:]
    datos = _config_serializada(config)
    return huella(sha256(carpeta / ARCHIVO_TRANSCRIPCION), datos, modelo.identificador, destino,
                  [(p.name, sha256(p)) for p in (PROMPT_EXTRACCION_MINUTAS,
                   PROMPT_CONSOLIDACION_MINUTAS, DEFINICIONES_SECCIONES_MINUTAS)],
                  _paquetes('ollama', 'boto3', 'pydantic'))


def _actualizar_minutas(carpeta: Path, estado: dict, config: ConfiguracionMinutas, destino=None):
    if 'asociar' not in etapas_vigentes(carpeta, estado) or not vigente(
            carpeta, estado, 'minuta', _clave_minutas(carpeta, config, destino)):
        invalidar(estado, 'minuta')
    estado['solicitud']['minutas'] = _config_serializada(config)


def _preparar(s: SolicitudReunion, estado: dict, medicion: Medicion, emisor: Emisor | None):
    carpeta = Path(s.salida).resolve()
    nueva = _solicitud_serializada(s)
    conservar_fuentes(carpeta, estado)
    identidades = [Path(p) for p in nueva['fuentes']]
    fuentes, hashes = resolver_fuentes(carpeta, estado, identidades)
    clave = clave_ingesta(nueva['fuentes'], hashes)
    # Antes de publicar una nueva solicitud, invalidar todas las ramas afectadas.
    if not vigente(carpeta, estado, 'preparar', clave):
        invalidar(estado, 'preparar')
    else:
        try:
            _validar_checkpoint(carpeta, estado, 'preparar')
        except ERRORES_CHECKPOINT:
            invalidar(estado, 'preparar')
        digest = sha256(carpeta / ARCHIVO_AUDIO)
        for etapa, llave in (('diarizar', _clave_diar(digest, nueva)),
                             ('transcribir', _clave_stt(digest, nueva))):
            if vigente(carpeta, estado, etapa, llave):
                try:
                    _validar_checkpoint(carpeta, estado, etapa)
                except ERRORES_CHECKPOINT:
                    invalidar(estado, etapa)
            else:
                invalidar(estado, etapa)
    estado['solicitud'] = nueva
    _actualizar_minutas(carpeta, estado, s.minutas)
    estado['estado'], estado['etapa'], estado['error'] = 'procesando', 'preparar', None
    medicion.actualizar()
    publicar(carpeta, estado)
    _emitir(emisor, 'inicio', carpeta=str(carpeta))

    _fase(carpeta, estado, 'preparar', clave, ARCHIVOS['preparar'],
          lambda: ingestar(fuentes, carpeta, identidades=identidades, hashes=hashes),
          emisor=emisor, medicion=medicion, validar=lambda: validar_ingesta(carpeta))
    conservar_fuentes(carpeta, estado)
    publicar(carpeta, estado)
    digest_audio = sha256(carpeta / ARCHIVO_AUDIO)
    _fase(carpeta, estado, 'diarizar', _clave_diar(digest_audio, nueva), ARCHIVOS['diarizar'],
          lambda: _trabajador('src.diarizacion.diarizar', [str(carpeta / ARCHIVO_AUDIO), '--salida', str(carpeta),
                 '--device', s.dispositivo_diarizacion] +
                 (['--num-speakers', str(s.num_speakers)] if s.num_speakers is not None else []), emisor=emisor),
          emisor=emisor, medicion=medicion, validar=lambda: _validar_diar(carpeta, nueva))
    _fase(carpeta, estado, 'transcribir', _clave_stt(digest_audio, nueva), ARCHIVOS['transcribir'],
          lambda: _stt(carpeta, s, digest_audio, emisor),
          emisor=emisor, medicion=medicion, validar=lambda: _validar_stt(carpeta))
    estado['etapa'] = 'asociar'
    medicion.actualizar()
    publicar(carpeta, estado)


def _stt(carpeta, s, digest, emisor):
    stdout = _trabajador('src.stt', [str(carpeta / ARCHIVO_AUDIO), '-o', str(carpeta / ARCHIVO_ASR),
                '--model', s.modelo_stt] + (['--device', s.dispositivo_stt] if s.dispositivo_stt else []),
                emisor=emisor)
    metadata = {'sha256_audio': digest, 'modelo': s.modelo_stt, 'dispositivo_solicitado': s.dispositivo_stt,
                'dispositivo': None}
    if not isinstance(stdout, str) or not stdout.strip():
        raise ValueError('El trabajador STT no devolvió metadata de ejecución.')
    resultado = json.loads(stdout.strip().splitlines()[-1])
    if (resultado['model'] != s.modelo_stt or resultado['status'] != 'success'
            or resultado['device'] not in {'cpu', 'cuda'}
            or (s.dispositivo_stt is not None and resultado['device'] != s.dispositivo_stt)
            or resultado['duration'] != verificar_wav(carpeta / ARCHIVO_AUDIO) / 16000):
        raise ValueError('La metadata de STT no corresponde a la solicitud.')
    metadata['dispositivo'] = resultado['device']
    return metadata


def _fin(carpeta, estado, medicion, emisor, terminal, etapa=None):
    estado['estado'], estado['etapa'], estado['error'] = terminal, etapa, None
    medicion.cerrar(pausa=terminal == 'esperando_identificacion')
    publicar(carpeta, estado)
    _emitir(emisor, 'fin', estado=terminal, carpeta=str(carpeta),
            latencia_s=estado['tiempos']['latencia_activa_s'])


def _pausar(carpeta, estado, medicion, emisor):
    inicio = monotonic()
    asociar(carpeta)  # Verifica que pueden construirse las fichas; no publica transcripción.
    medicion.datos['preparacion_identificacion_s'] = round(monotonic() - inicio, 3)
    _emitir(emisor, 'etapa', etapa='asociar', estado='esperando_identificacion', detalle='Fichas disponibles')
    _fin(carpeta, estado, medicion, emisor, 'esperando_identificacion', 'asociar')


def _fallo(carpeta: Path, estado: dict, medicion: Medicion, error: BaseException, emisor: Emisor | None):
    estado['estado'] = 'cancelado' if isinstance(error, (Cancelado, KeyboardInterrupt)) else 'fallido'
    estado['error'] = f'{type(error).__name__}: {error}'
    medicion.cerrar()
    persistido = True
    try:
        publicar(carpeta, estado)
    except Exception as fallo_publicacion:
        persistido = False
        error.add_note(f'No se pudo publicar el fallo: {fallo_publicacion}')
    try:
        _emitir(emisor, 'etapa', etapa=estado.get('etapa') or 'preparar', estado='error', detalle=estado['error'])
        _emitir(emisor, 'fin', estado=estado['estado'], carpeta=str(carpeta), persistido=persistido,
                latencia_s=estado['tiempos']['latencia_activa_s'])
    except Exception as fallo_emisor:
        error.add_note(f'No se pudo emitir el fallo: {fallo_emisor}')


def _validar_checkpoint(carpeta, estado, etapa):
    """Contratos y procedencia de la solicitud persistida, no del entorno futuro."""
    solicitud = estado['solicitud']
    registro = estado['etapas'][etapa]
    if etapa == 'preparar':
        datos = validar_ingesta(carpeta)
        comprobar_identidades(estado, datos['fuentes'])
        return datos
    if etapa in {'diarizar', 'transcribir'}:
        digest = estado['etapas']['preparar']['archivos'][ARCHIVO_AUDIO]
        versiones = registro['metadata']['versiones']
        clave = (_clave_diar if etapa == 'diarizar' else _clave_stt)(digest, solicitud, versiones)
        if clave != registro['clave']:
            raise ValueError('El checkpoint no corresponde a sus parámetros.')
        if etapa == 'diarizar':
            _validar_diar(carpeta, solicitud)
        else:
            _validar_stt(carpeta)
            meta = registro['metadata']
            # En registros anteriores no existe evidencia del dispositivo efectivo.
            if 'sha256_audio' in meta:
                if (meta['sha256_audio'] != digest or meta['modelo'] != solicitud['modelo_stt']
                        or meta['dispositivo_solicitado'] != solicitud['dispositivo_stt']
                        or meta['dispositivo'] not in {'cpu', 'cuda'}
                        or (solicitud['dispositivo_stt'] is not None
                            and meta['dispositivo'] != solicitud['dispositivo_stt'])):
                    raise ValueError('La metadata de STT no corresponde a su configuración.')
    elif etapa == 'asociar':
        _validar_transcripcion(carpeta)
    elif etapa == 'minuta':
        _validar_minutas(carpeta, _config_desde_estado(estado))


def _validar_preparada(carpeta, estado, medicion):
    validas = etapas_vigentes(carpeta, estado)
    for etapa in ('preparar', 'diarizar', 'transcribir'):
        if etapa not in validas:
            raise ValueError(f'La etapa {etapa} no tiene un checkpoint íntegro; prepará la reunión nuevamente.')
        _validar_checkpoint(carpeta, estado, etapa)
        if medicion.datos['etapas'][etapa]['estado'] == 'no_ejecutada':
            medicion.etapa(etapa, 'reutilizada', 0.0)


def _clave_asociacion(carpeta: Path, decision: Decision) -> str:
    hashes = {n: sha256(carpeta / n) for n in (ARCHIVO_AUDIO, ARCHIVO_DIARIZACION, ARCHIVO_ASR)}
    return huella(hashes, asdict(decision.etiquetado) if decision.etiquetado else None)


def _reutilizable_minuta(carpeta, estado, clave_asociacion, config, destino) -> bool:
    validas = _consulta(carpeta, estado)['etapas_vigentes']
    if not ('asociar' in validas and 'minuta' in validas
            and vigente(carpeta, estado, 'asociar', clave_asociacion)
            and vigente(carpeta, estado, 'minuta', _clave_minutas(carpeta, config, destino))):
        return False
    try:
        _validar_minutas(carpeta, config, prompts_actuales=True, destino=destino)
    except ERRORES_CHECKPOINT:
        return False
    return True


def requiere_autorizacion_minutas(reunion: str | Path, decision: Decision,
                                   configuracion: ConfiguracionMinutas, *, huella_fichas: str) -> bool:
    """Consulta sin transferencia; la ejecución comprueba otra vez bajo su propio bloqueo."""
    carpeta = Path(reunion).resolve()
    with _exclusivo(carpeta):
        estado = leer(carpeta)
        _comprobar_fichas(carpeta, estado, huella_fichas)
        if decision.accion == 'cancelar':
            return False
        if decision.accion != 'escribir':
            raise ValueError('La decisión de fichas no es ejecutable.')
        destino = resolver_destino(configuracion.modelo)
        if configuracion.destino_autorizado not in (None, destino.huella):
            raise ValueError('El destino configurado cambió; revisá la configuración.')
        return destino.tipo != 'ollama_local' and not _reutilizable_minuta(
            carpeta, estado, _clave_asociacion(carpeta, decision), configuracion, destino)


def _continuar(carpeta: Path, estado: dict, decision: Decision, config: ConfiguracionMinutas,
               medicion: Medicion, emisor: Emisor | None, *, nombres=None):
    _validar_preparada(carpeta, estado, medicion)
    if decision.accion not in {'escribir', 'cancelar'}:
        raise ValueError('La decisión de fichas no es ejecutable.')
    if decision.accion == 'cancelar':
        _fin(carpeta, estado, medicion, emisor, 'cancelado', 'asociar')
        return
    asociacion = None
    if nombres is not None:
        inicio = monotonic()
        asociacion = asociar(carpeta)
        fichas = ModeloFichas(asociacion)
        desconocidas = set(nombres).difference(f.etiqueta for f in fichas.fichas)
        if desconocidas:
            raise ValueError(f'Etiquetas desconocidas: {sorted(desconocidas)}')
        for ficha in fichas.fichas:
            fichas.escribir_nombre(ficha.etiqueta, nombres.get(ficha.etiqueta, ''))
        decision = fichas.confirmar()
        medicion.datos['preparacion_identificacion_s'] = round(monotonic() - inicio, 3)
    clave = _clave_asociacion(carpeta, decision)
    destino = resolver_destino(config.modelo)
    if not _reutilizable_minuta(carpeta, estado, clave, config, destino):
        try:
            comprobar_autorizacion(destino, config.permitir_remoto, config.destino_autorizado)
        except PermissionError as exc:
            raise AutorizacionRechazada(str(exc)) from None
    _actualizar_minutas(carpeta, estado, config, destino)
    estado['estado'], estado['etapa'], estado['error'] = 'procesando', 'asociar', None
    publicar(carpeta, estado)
    archivos = ARCHIVOS['asociar']
    if decision.etiquetado is not None:
        archivos += (ARCHIVO_HABLANTES,)
    _fase(carpeta, estado, 'asociar', clave, archivos,
          lambda: aplicar(asociacion or asociar(carpeta), decision, salida=carpeta),
          emisor=emisor, medicion=medicion, validar=lambda: _validar_transcripcion(carpeta))
    _generar(carpeta, estado, config, medicion, emisor, destino)


def _generar(carpeta: Path, estado: dict, config: ConfiguracionMinutas, medicion: Medicion, emisor: Emisor | None, destino):
    clave = _clave_minutas(carpeta, config, destino)
    args = ['--entrada', str(carpeta / ARCHIVO_TRANSCRIPCION), '--salida', str(carpeta),
            '--modelo', config.modelo, '--secciones', ','.join(config.secciones),
            '--temperatura', str(config.temperatura),
            '--max-tokens-salida', str(config.max_tokens_salida),
            '--reintentos-formato', str(config.reintentos_formato),
            '--num-ctx', str(config.num_ctx), '--max-caracteres-bloque', str(config.max_caracteres_bloque),
            '--sobrescribir', '--destino-autorizado', destino.huella]
    if config.permitir_remoto:
        args.append('--permitir-remoto')
    def generar():
        comprobar_autorizacion(resolver_destino(config.modelo), config.permitir_remoto, destino.huella)
        comprobar_autorizacion(destino, config.permitir_remoto, config.destino_autorizado)
        estado['ultima_solicitud_minutas'] = {
            'modelo': config.modelo, 'destino': destino.tipo, 'huella_destino': destino.huella,
            'autorizacion_externa': destino.tipo != 'ollama_local' and config.permitir_remoto,
            'inicio_utc': ahora(),
        }
        estado['destino_minutas'] = destino.tipo
        publicar(carpeta, estado)
        _trabajador('src.minutas', args, emisor=emisor)
        meta = json.loads((carpeta / 'ejecucion_minutas.json').read_text(encoding='utf-8'))
        if meta.get('huella_destino') != destino.huella or meta.get('destino') != destino.tipo:
            raise ValueError('La ejecución no acredita el destino configurado.')

    _fase(carpeta, estado, 'minuta', clave, ARCHIVOS['minuta'],
          generar,
          emisor=emisor, medicion=medicion, validar=lambda: _validar_minutas(carpeta, config, prompts_actuales=True, destino=destino))
    _fin(carpeta, estado, medicion, emisor, 'completado')


def _consulta(carpeta, estado):
    duracion = None

    def comprobar(etapa):
        nonlocal duracion
        try:
            datos = _validar_checkpoint(carpeta, estado, etapa)
            if etapa == 'preparar':
                duracion = datos['duracion_s']
            return True
        except ERRORES_CHECKPOINT:
            return False

    validas = etapas_vigentes(carpeta, estado, comprobar=comprobar)
    terminal, etapa, error = estado['estado'], estado.get('etapa'), estado.get('error')
    if terminal == 'procesando':
        terminal, error = 'fallido', 'Ejecución interrumpida sin cierre; consultar checkpoints y reanudar.'
    elif ((terminal == 'completado' and 'minuta' not in validas) or
          (terminal == 'esperando_identificacion' and not {'preparar', 'diarizar', 'transcribir'} <= validas)):
        terminal, error = 'fallido', 'Uno o más checkpoints perdieron su vigencia.'
        etapa = next(e for e in ARCHIVOS if e not in validas)
    return {'carpeta': str(carpeta), 'estado': terminal, 'etapa': etapa, 'error': error,
            'artefactos': artefactos_vigentes(carpeta, estado, validas), 'solicitud': estado.get('solicitud'),
            'activa': False, 'etapas_vigentes': [e for e in ARCHIVOS if e in validas],
            'duracion_audio_s': duracion, 'tiempos': estado.get('tiempos')}


def _solicitud_reutilizable(carpeta, estado, solicitud, destino) -> bool:
    """Verifica una solicitud completa sin publicar ni iniciar inferencias."""
    try:
        nueva = _solicitud_serializada(solicitud)
        conservar_fuentes(carpeta, estado)
        fuentes = [Path(p) for p in nueva['fuentes']]
        _, hashes = resolver_fuentes(carpeta, estado, fuentes)
        if not vigente(carpeta, estado, 'preparar', clave_ingesta(nueva['fuentes'], hashes)):
            return False
        digest = sha256(carpeta / ARCHIVO_AUDIO)
        if not (vigente(carpeta, estado, 'diarizar', _clave_diar(digest, nueva)) and
                vigente(carpeta, estado, 'transcribir', _clave_stt(digest, nueva))):
            return False
        return _reutilizable_minuta(carpeta, estado, _clave_asociacion(carpeta, Decision('escribir')),
                                    solicitud.minutas, destino)
    except ERRORES_CHECKPOINT:
        return False


def _ejecutar(solicitud: SolicitudReunion, *, pausa: bool, emisor: Emisor | None) -> dict:
    carpeta = Path(solicitud.salida).resolve()
    with _exclusivo(carpeta):
        estado = leer(carpeta)
        if not pausa:
            destino = resolver_destino(solicitud.minutas.modelo)
            config = solicitud.minutas
            if config.destino_autorizado is None:
                config = replace(config, destino_autorizado=destino.huella)
                solicitud = replace(solicitud, minutas=config)
            # Sin permiso para inferencia nueva solo se admite reutilización completa.
            try:
                comprobar_autorizacion(destino, config.permitir_remoto, config.destino_autorizado)
            except PermissionError:
                if not _solicitud_reutilizable(carpeta, estado, solicitud, destino):
                    raise
        estado.pop('inicio_s', None)
        medicion = Medicion(estado)
        try:
            _preparar(solicitud, estado, medicion, emisor)
            if pausa:
                _pausar(carpeta, estado, medicion, emisor)
            else:
                _continuar(carpeta, estado, Decision('escribir'), solicitud.minutas, medicion, emisor)
        except BaseException as exc:
            _fallo(carpeta, estado, medicion, exc, emisor)
            raise
        return _consulta(carpeta, estado)


def preparar_reunion(solicitud: SolicitudReunion, *, emisor: Emisor | None = None) -> dict:
    return _ejecutar(solicitud, pausa=True, emisor=emisor)


def procesar_reunion(solicitud: SolicitudReunion, *, emisor: Emisor | None = None) -> dict:
    return _ejecutar(solicitud, pausa=solicitud.identificacion == 'pausa', emisor=emisor)


def _decision_anterior(carpeta: Path, estado: dict) -> Decision:
    if 'asociar' not in etapas_vigentes(carpeta, estado):
        return Decision('escribir')
    try:
        _validar_checkpoint(carpeta, estado, 'asociar')
    except ERRORES_CHECKPOINT:
        return Decision('escribir')
    if ARCHIVO_HABLANTES not in estado['etapas']['asociar']['archivos']:
        return Decision('escribir')
    datos = json.loads((carpeta / ARCHIVO_HABLANTES).read_text(encoding='utf-8'))
    return Decision('escribir', Etiquetado(
        nombres={k: v['name'] for k, v in datos.items()},
        clips={k: (v['clip_start'], v['clip_end']) for k, v in datos.items()}))


def _huella_identificacion(estado: dict) -> str:
    return huella({e: estado['etapas'].get(e) for e in ('preparar', 'diarizar', 'transcribir', 'asociar')})


def consultar_identificacion(reunion: str | Path):
    """Instantánea de fichas y decisión previa, bajo el bloqueo de la reunión."""
    carpeta = Path(reunion).resolve()
    with _exclusivo(carpeta):
        estado = leer(carpeta)
        consulta = _consulta(carpeta, estado)
        if not {'preparar', 'diarizar', 'transcribir'} <= set(consulta['etapas_vigentes']):
            raise ValueError('Los insumos para identificación no están vigentes.')
        return asociar(carpeta), _decision_anterior(carpeta, estado).etiquetado, _huella_identificacion(estado), consulta


def _comprobar_fichas(carpeta, estado, huella_fichas):
    if (huella_fichas != _huella_identificacion(estado) or
            not {'preparar', 'diarizar', 'transcribir'} <= set(_consulta(carpeta, estado)['etapas_vigentes'])):
        raise ValueError('Los insumos de las fichas cambiaron; volvé a abrirlas.')


def _retomar(carpeta, decision, configuracion, emisor, nombres=None, huella_fichas=None, cambios_minutas=None):
    with _exclusivo(carpeta):
        estado = leer(carpeta)
        if huella_fichas is not None:
            _comprobar_fichas(carpeta, estado, huella_fichas)
        if decision is not None and decision.accion == 'cancelar' and estado['estado'] != 'esperando_identificacion':
            return _consulta(carpeta, estado)
        estado.pop('inicio_s', None)
        medicion = Medicion(estado, continuar=True)
        try:
            if configuracion is not None and cambios_minutas is not None:
                raise ValueError('Indicá una configuración completa o cambios parciales, no ambos.')
            cfg = configuracion or _config_desde_estado(estado)
            if cambios_minutas is not None:
                cfg = replace(cfg, **cambios_minutas)
            if cfg.destino_autorizado is None and not (decision and decision.accion == 'cancelar'):
                cfg = replace(cfg, destino_autorizado=resolver_destino(cfg.modelo).huella)
            _continuar(carpeta, estado, decision or _decision_anterior(carpeta, estado), cfg, medicion, emisor, nombres=nombres)
        except AutorizacionRechazada:
            # Todavía no se publicó ninguna transición de esta solicitud.
            raise
        except BaseException as exc:
            _fallo(carpeta, estado, medicion, exc, emisor)
            raise
        return _consulta(carpeta, estado)


def continuar_reunion(reunion: str | Path, decision: Decision | None = None, *,
                      configuracion: ConfiguracionMinutas | None = None, emisor: Emisor | None = None,
                      huella_fichas: str | None = None, cambios_minutas: Mapping | None = None) -> dict:
    """Continúa con configuración explícita o cambios sobre la guardada, bajo bloqueo."""
    return _retomar(Path(reunion).resolve(), decision, configuracion, emisor,
                    huella_fichas=huella_fichas, cambios_minutas=cambios_minutas)


def consultar_reunion(reunion: str | Path, *, incluir_fuentes: bool = False) -> dict:
    carpeta = Path(reunion).resolve()
    if not carpeta.exists():
        return _consulta(carpeta, leer(carpeta))
    try:
        with _exclusivo(carpeta):
            estado = leer(carpeta)
            consulta = _consulta(carpeta, estado)
            if incluir_fuentes and estado.get('solicitud'):
                conservar_fuentes(carpeta, estado)
                consulta['fuentes_disponibles'] = []
                for original in estado['solicitud']['fuentes']:
                    ruta, situacion = None, 'no_disponible'
                    try:
                        rutas, hashes = resolver_fuentes(carpeta, estado, [Path(original)])
                        ruta = str(rutas[0])
                        conservadas = estado.get('fuentes_conservadas')
                        guardados = {f['sha256'] for f in (conservadas if isinstance(conservadas, list) else [])
                                     if isinstance(f, dict) and f.get('original') == original
                                     and isinstance(f.get('sha256'), str)}
                        if ruta != original:
                            situacion = 'copia'
                        elif not guardados:
                            situacion = 'no_verificada'
                        elif guardados == {hashes[0]}:
                            situacion = 'original'
                        else:
                            situacion = 'modificada'
                    except ERRORES_CHECKPOINT:
                        pass
                    consulta['fuentes_disponibles'].append({'original': original, 'disponible': ruta,
                                                            'situacion': situacion})
            return consulta
    except ReunionOcupada:
        # Una lectura activa no adquiere un bloqueo compartido ni expone archivos
        # sujetos a sustitución. El lector puede volver a consultar al terminar.
        estado = leer(carpeta)
        return {'carpeta': str(carpeta), 'estado': 'procesando', 'etapa': estado.get('etapa'),
                'error': None, 'artefactos': {}, 'solicitud': estado.get('solicitud'), 'activa': True,
                'etapas_vigentes': None, 'duracion_audio_s': None, 'tiempos': estado.get('tiempos')}


def leer_resultado_texto(reunion: str | Path, nombre: str) -> str:
    """Lee una instantánea vigente bajo el mismo bloqueo que su validación."""
    if nombre not in {ARCHIVO_TRANSCRIPCION, 'minutes.md'}:
        raise ValueError('El archivo no corresponde a un resultado de texto del visor.')
    carpeta = Path(reunion).resolve()
    if not carpeta.is_dir():
        raise ValueError('La reunión no existe.')
    with _exclusivo(carpeta):
        consulta = _consulta(carpeta, leer(carpeta))
        if nombre not in consulta['artefactos']:
            raise ValueError('El resultado no está vigente.')
        return Path(consulta['artefactos'][nombre]).read_text(encoding='utf-8')


def reetiquetar_reunion(reunion: str | Path, nombres: Mapping[str, str | None], *,
                        configuracion: ConfiguracionMinutas | None = None, emisor: Emisor | None = None) -> dict:
    return _retomar(Path(reunion).resolve(), None, configuracion, emisor, nombres=nombres)


def cancelar_reunion(reunion: str | Path) -> None:
    """Cancela una espera o reunión no activa; el cliente señaliza al proceso activo."""
    carpeta = Path(reunion).resolve()
    with _exclusivo(carpeta):
        estado = leer(carpeta)
        estado.pop('inicio_s', None)
        medicion = Medicion(estado, continuar=True)
        _fin(carpeta, estado, medicion, None, 'cancelado', estado.get('etapa'))
