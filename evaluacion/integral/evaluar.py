"""Protocolo integral de §2.3 del Hito 3; cliente del workflow, sin inferencias propias."""
from __future__ import annotations

import argparse
import json
import math
import platform
import re
import shutil
import subprocess
import tempfile
import wave
from dataclasses import asdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit

from src.ingesta.audio import FS, ingestar, sha256, verificar_wav
from src.rutas import DIRECTORIO_PROYECTO

MODALIDADES = ('unico', 'multiple', 'unico', 'multiple', 'unico')
ETAPAS = ('preparar', 'diarizar', 'transcribir', 'asociar', 'minuta')
UMBRAL_S = 1800
# Los manifiestos con rutas locales permanecen en el directorio de trabajo.
PUBLICABLES = ('diarization.json', 'asr.json', 'transcription.json',
               'speakers.json', 'minutes.json', 'minutes.md', 'ejecucion_minutas.json')
CALIDAD = '''# Evaluación independiente de calidad

Evaluador (autor de las notas de referencia): pendiente.
Fecha: pendiente.

Contrastar las notas de referencia y las evidencias temporales con las minutas
`corridas/01/minutes.md` y `corridas/02/minutes.md`. Las corridas a evaluar quedaron
fijadas antes del procesamiento.
Aceptar reformulaciones equivalentes, no inferir compromisos ausentes de la fuente.

| Ítem | Único (01) | Múltiple (02) |
|---|---|---|
| Tema 1 recuperado (sí/no) | pendiente | pendiente |
| Tema 2 recuperado (sí/no) | pendiente | pendiente |
| Acción recuperada con responsable correcto (sí/no) | pendiente | pendiente |
| Cantidad de acciones inventadas | pendiente | pendiente |
| Cumple (2/2, 1/1 y 0 inventadas) | pendiente | pendiente |

## Evidencia y observaciones

Pendiente. Identificar las marcas temporales y justificar el juicio; registrar
cada acción inventada, si la hubiera. No evaluar las corridas 03–05 para sustituir 01–02.
'''


def ahora():
    return datetime.now(timezone.utc).isoformat()


def leer(ruta):
    return json.loads(ruta.read_text(encoding='utf-8'))


def guardar(ruta, datos):
    temporal = ruta.with_name(ruta.name + '.tmp')
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporal.replace(ruta)


def _texto(valor, campo):
    if not valor.strip():
        raise ValueError(f'{campo} no puede estar vacío.')
    return valor.strip()


def _cortes(audio, carpeta, muestras):
    partes = []
    with wave.open(str(audio), 'rb') as entrada:
        for i in range(3):
            inicio, fin = i * muestras // 3, (i + 1) * muestras // 3
            nombre = f'{i + 1:02d}.wav'
            ruta = carpeta / nombre
            with wave.open(str(ruta), 'wb') as salida:
                salida.setparams((1, 2, FS, 0, 'NONE', 'not compressed'))
                restantes = fin - inicio
                while restantes:
                    bloque = entrada.readframes(min(restantes, 65536))
                    if not bloque:
                        raise ValueError('Audio truncado durante el corte.')
                    salida.writeframesraw(bloque)
                    restantes -= len(bloque) // 2
            partes.append({'archivo': nombre, 'inicio_muestra': inicio, 'fin_muestra': fin,
                           'sha256': sha256(ruta)})
    return partes


def _configuracion_base():
    from src.minutas.generacion import ConfiguracionMinutas
    config = asdict(ConfiguracionMinutas(modelo='qwen2.5-7b'))
    config.pop('permitir_remoto')
    config.pop('destino_autorizado')
    config['secciones'] = list(config['secciones'])
    return config


def _validar_procedencia(datos, digest, muestras):
    """Comprueba trazabilidad declarada; no certifica jurídicamente la licencia."""
    if not isinstance(datos, dict):
        raise ValueError('Procedencia externa inválida.')
    for campo in ('titulo', 'licencia', 'evidencia', 'seleccion'):
        if not isinstance(datos.get(campo), str) or not datos[campo].strip():
            raise ValueError(f'Procedencia externa: falta {campo}.')
    for campo in ('url', 'url_metadatos'):
        valor = datos.get(campo)
        url = urlsplit(valor) if isinstance(valor, str) else None
        if not url or url.scheme not in {'https', 'http'} or not url.hostname:
            raise ValueError(f'Procedencia externa: falta URL válida en {campo}.')
    for campo in ('sha256_original', 'sha256_fragmento'):
        if not isinstance(datos.get(campo), str) or not re.fullmatch(r'[0-9a-f]{64}', datos[campo]):
            raise ValueError(f'Procedencia externa: hash inválido en {campo}.')
    inicio, fin = datos.get('inicio_s'), datos.get('fin_s')
    if (type(inicio) is not int or type(fin) is not int or inicio < 0 or fin <= inicio or
            (fin - inicio) * FS != muestras or datos['sha256_fragmento'] != digest):
        raise ValueError('Procedencia externa: intervalo o hash no coincide con el fragmento.')


def preparar(sesion, audio, notas, *, autor, tipo, equipo, consentimiento=False, procedencia=None):
    """Normaliza una vez y congela la fuente y las notas antes de cualquier corrida."""
    if bool(consentimiento) == (procedencia is not None):
        raise ValueError('Se requiere consentimiento o procedencia externa autorizada, no ambos.')
    if tipo not in {'prueba', 'formal'}:
        raise ValueError('Tipo de sesión inválido.')
    autor, equipo = _texto(autor, 'Autor de referencia'), _texto(equipo, 'Equipo')
    audio, notas = audio.resolve(strict=True), notas.resolve(strict=True)
    externa = leer(Path(procedencia)) if procedencia is not None else None
    if procedencia is not None:
        _validar_procedencia(externa, sha256(audio), verificar_wav(audio))
    if not notas.read_text(encoding='utf-8').strip():
        raise ValueError('Las notas de referencia están vacías.')
    sesion = sesion.resolve()
    sesion.parent.mkdir(parents=True, exist_ok=True)
    if sesion.exists():
        raise FileExistsError('La sesión ya existe; no se sobrescribe.')
    # La preparación no deja una sesión aparentemente congelada si falla.
    with tempfile.TemporaryDirectory(dir=sesion.parent) as temporal:
        base = Path(temporal) / 'sesion'
        muestra = base / 'muestra'
        muestra.mkdir(parents=True)
        ingesta = ingestar([audio], Path(temporal) / 'normalizada')
        shutil.copyfile(Path(temporal) / 'normalizada/audio.wav', muestra / 'audio.wav')
        muestras = verificar_wav(muestra / 'audio.wav')
        if muestras < 300 * FS:
            raise ValueError('La reunión debe durar al menos cinco minutos.')
        partes = _cortes(muestra / 'audio.wav', muestra, muestras)
        conjunta = ingestar([muestra / p['archivo'] for p in partes], Path(temporal) / 'combinada')
        digest = sha256(muestra / 'audio.wav')
        if conjunta['sha256_audio'] != digest:
            raise ValueError('El audio normalizado de ambas modalidades no es idéntico.')
        shutil.copyfile(notas, muestra / 'referencia.md')
        manifiesto = {'version': 1, 'creado_utc': ahora(), 'tipo': tipo, 'equipo': equipo,
                      'consentimiento_declarado': bool(consentimiento), 'autor_referencia': autor,
                      'configuracion_minutas': _configuracion_base(),
                      'sha256_original': ingesta['fuentes'][0]['sha256_fuente'],
                      'frecuencia_hz': FS, 'muestras': muestras, 'duracion_s': muestras / FS,
                      'sha256_audio': digest, 'sha256_referencia': sha256(muestra / 'referencia.md'),
                      'cortes': partes}
        if externa is not None:
            manifiesto['procedencia_externa'] = externa
        guardar(muestra / 'manifiesto.json', manifiesto)
        (base / 'corridas').mkdir()
        (base / 'calidad.md').write_text(CALIDAD, encoding='utf-8')
        verificar_muestra(base)
        base.rename(sesion)
    return manifiesto


def verificar_muestra(sesion):
    muestra = sesion / 'muestra'
    m = leer(muestra / 'manifiesto.json')
    if (m['version'] != 1 or m['tipo'] not in {'formal', 'prueba'} or
            m['frecuencia_hz'] != FS or
            not ((m.get('consentimiento_declarado') is True and 'procedencia_externa' not in m) or
                 (m.get('consentimiento_declarado') is False and 'procedencia_externa' in m))):
        raise ValueError('Manifiesto de muestra inválido.')
    audio = muestra / 'audio.wav'
    muestras = verificar_wav(audio)
    if (muestras != m['muestras'] or muestras < 300 * FS or m['duracion_s'] != muestras / FS or
            sha256(audio) != m['sha256_audio'] or
            sha256(muestra / 'referencia.md') != m['sha256_referencia']):
        raise ValueError('Cambió el audio o la referencia congelada.')
    if 'procedencia_externa' in m:
        _validar_procedencia(m['procedencia_externa'], m['sha256_original'], muestras)
    if len(m['cortes']) != 3:
        raise ValueError('Cantidad de cortes inválida.')
    # Verificación del PCM sin volver a usar FFmpeg ni realizar inferencias.
    with wave.open(str(audio), 'rb') as original:
        for i, p in enumerate(m['cortes']):
            inicio, fin = i * muestras // 3, (i + 1) * muestras // 3
            nombre = f'{i + 1:02d}.wav'
            ruta = muestra / nombre
            if (p['archivo'] != nombre or p['inicio_muestra'] != inicio or p['fin_muestra'] != fin or
                    verificar_wav(ruta) != fin - inicio or sha256(ruta) != p['sha256']):
                raise ValueError('Cambió un corte o su orden.')
            with wave.open(str(ruta), 'rb') as parte:
                while bloque := parte.readframes(65536):
                    if original.readframes(len(bloque) // 2) != bloque:
                        raise ValueError('El PCM de los cortes no coincide con el original.')
    return m


def _comando(args):
    try:
        r = subprocess.run(args, cwd=DIRECTORIO_PROYECTO, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _entorno():
    git = _comando(['git', 'rev-parse', 'HEAD'])
    cambios = _comando(['git', 'status', '--porcelain'])
    ffmpeg = _comando(['ffmpeg', '-version'])
    return {'sistema': platform.system(), 'version_sistema': platform.release(),
            'arquitectura': platform.machine(), 'python': platform.python_version(),
            'commit': git, 'arbol_con_cambios': None if cambios is None else bool(cambios),
            'ffmpeg': ffmpeg.splitlines()[0] if ffmpeg else None,
            'gpu': _comando(['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'])}


def _ollama(destino):
    """Metadatos del servidor local, sin descargar/cargar un modelo ni consultar otros destinos."""
    import httpx
    datos = {'version': None, 'digest_qwen': None, 'qwen_residente': None}
    if destino.tipo != 'ollama_local':
        raise ValueError('El baseline requiere un servidor Ollama local.')
    try:
        with httpx.Client(base_url=destino.host, timeout=5, trust_env=False, follow_redirects=False) as cliente:
            for ruta, clave in [('/api/version', 'version'), ('/api/tags', 'digest_qwen'),
                                ('/api/ps', 'qwen_residente')]:
                respuesta = cliente.get(ruta)
                respuesta.raise_for_status()
                contenido = respuesta.json()
                if clave == 'version':
                    datos[clave] = contenido['version']
                else:
                    modelo = next((m for m in contenido['models'] if m.get('name') == 'qwen2.5:7b'), None)
                    datos[clave] = modelo.get('digest') if clave == 'digest_qwen' and modelo else (
                        modelo is not None if clave == 'qwen_residente' else None)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        pass  # Un dato no disponible se registra como null, no como una versión inferida.
    return datos


def _revision_diarizacion():
    try:
        from huggingface_hub import try_to_load_from_cache
        from src.diarizacion.entrada import MODELO
        ruta = try_to_load_from_cache(MODELO, 'config.yaml')
        return Path(ruta).parent.name if isinstance(ruta, str) else None
    except (ImportError, OSError, ValueError):
        return None


def _dialogo(asociacion):
    """Construye las fichas antes de cronometrar la intervención humana."""
    from src.asociacion.etiquetado import Decision, ModeloFichas
    from src.interfaz.fichas import DialogoFichas, Reproductor
    modelo = ModeloFichas(asociacion)
    if not modelo.hay_fichas:
        return lambda: Decision('escribir'), False
    dialogo = DialogoFichas(modelo, Reproductor(asociacion.rutas.audio))

    def identificar():
        dialogo.exec()
        return dialogo.decision or Decision('cancelar')

    return identificar, True


@lru_cache(maxsize=1)
def _app():
    from PySide6.QtWidgets import QApplication
    from src.interfaz.estilo import aplicar_estilo
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    aplicar_estilo(app)
    return app


def _artefactos(carpeta):
    return {n: sha256(carpeta / n) for n in PUBLICABLES if (carpeta / n).is_file()}


def _registro_workflow(carpeta):
    """Derivado de los manifiestos originales, que no se modifican ni se publican automáticamente."""
    estado = leer(carpeta / 'workflow.json')
    solicitud = {k: v for k, v in estado.get('solicitud', {}).items() if k not in {'fuentes', 'salida'}}
    ingesta = leer(carpeta / 'ingesta.json') if (carpeta / 'ingesta.json').is_file() else {}
    fuentes = [{k: f[k] for k in ('orden', 'sha256_fuente', 'inicio_muestra', 'fin_muestra')}
               for f in ingesta.get('fuentes', [])]
    diar = carpeta / 'diarization.meta.json'
    diarizacion = leer(diar) if diar.is_file() else None
    if diarizacion is not None:
        diarizacion['audio'].pop('ruta', None)
    meta = carpeta / 'transcription.meta.json'
    asociacion = {k: v for k, v in leer(meta).items() if k != 'entradas'} if meta.is_file() else None
    return {'solicitud': solicitud, 'tiempos': estado.get('tiempos'),
            'checkpoints': {e: {'clave': v['clave'], 'archivos': v['archivos'],
                                'versiones': v['metadata'].get('versiones'),
                                'dispositivo': v['metadata'].get('dispositivo')}
                            for e, v in estado['etapas'].items()},
            'fuentes': fuentes, 'sha256_audio': ingesta.get('sha256_audio'),
            'diarizacion': diarizacion, 'asociacion': asociacion, 'sha256_manifiestos_originales': {
                n: sha256(carpeta / n) for n in ('workflow.json', 'ingesta.json', 'diarization.meta.json',
                                                'transcription.meta.json')
                if (carpeta / n).is_file()}}


def ejecutar(sesion, numero, *, operador, condiciones):
    from src.pipeline import SolicitudReunion, preparar_reunion, consultar_identificacion, continuar_reunion
    from src.minutas.generacion import ConfiguracionMinutas
    from src.minutas.proveedores import resolver_destino

    if type(numero) is not int or not 1 <= numero <= len(MODALIDADES):
        raise ValueError('La corrida debe estar entre 1 y 5.')
    m = verificar_muestra(sesion)
    operador, condiciones = _texto(operador, 'Operador'), _texto(condiciones, 'Condiciones')
    if operador.casefold() == m['autor_referencia'].casefold():
        raise ValueError('El operador debe ser independiente del autor de las notas.')
    digest_muestra = sha256(sesion / 'muestra/manifiesto.json')
    for anterior in (sesion / 'corridas').glob('*/medicion.json'):
        if leer(anterior)['sha256_muestra'] != digest_muestra:
            raise ValueError('La muestra cambió respecto de una corrida anterior.')
    carpeta = sesion / 'corridas' / f'{numero:02d}'
    carpeta.mkdir(exist_ok=False)  # nunca continuar ni sustituir una corrida experimental
    ruta = carpeta / 'medicion.json'
    modalidad = MODALIDADES[numero - 1]
    fuentes = [sesion / 'muestra/audio.wav'] if modalidad == 'unico' else [
        sesion / 'muestra' / p['archivo'] for p in m['cortes']]
    registro = {'version': 1, 'corrida': numero, 'modalidad': modalidad, 'estado': 'iniciada',
                'inicio_utc': ahora(), 'operador': operador, 'condiciones': condiciones,
                'sha256_muestra': digest_muestra,
                'entorno': _entorno(), 'latencia_s': None}
    guardar(ruta, registro)
    try:
        cfg = m['configuracion_minutas']
        if cfg != _configuracion_base():
            raise ValueError('La configuración congelada difiere del baseline de este código.')
        config = ConfiguracionMinutas(**{**cfg, 'secciones': tuple(cfg['secciones'])})
        destino = resolver_destino(config.modelo)
        if destino.tipo != 'ollama_local':
            raise ValueError('El baseline requiere Ollama local.')
        registro['ollama_antes'] = _ollama(destino)
        guardar(ruta, registro)
        app = _app()  # conservar una referencia durante las fichas; fuera de la latencia
        solicitud = SolicitudReunion(tuple(fuentes), salida=carpeta, dispositivo_diarizacion='cuda',
                                    modelo_stt='medium', dispositivo_stt='cuda', minutas=config,
                                    identificacion='pausa')
        fin = None

        def emisor(evento):
            nonlocal fin
            if evento['evento'] == 'fin' and evento['estado'] == 'completado':
                fin = monotonic()  # publicación de la minuta y del estado, antes de la consulta final
            if evento['evento'] == 'etapa':
                print(f"{evento['etapa']}: {evento['estado']}", flush=True)

        print(f'Corrida {numero}: {modalidad}', flush=True)
        inicio = monotonic()
        resultado = preparar_reunion(solicitud, emisor=emisor)
        if resultado['estado'] != 'esperando_identificacion':
            raise RuntimeError('No se alcanzó la pausa de identificación.')
        asociacion, _, huella, _ = consultar_identificacion(carpeta)
        identificar, hay_fichas = _dialogo(asociacion)
        desde = monotonic()
        decision = identificar()
        intervencion = monotonic() - desde if hay_fichas else 0.0
        resultado = continuar_reunion(carpeta, decision, emisor=emisor, huella_fichas=huella)
        registro['identificacion'] = {'fichas': hay_fichas, 'etiquetado_confirmado': decision.etiquetado is not None,
                                      'tiempo_s': intervencion}
        if resultado['estado'] == 'cancelado':
            registro['estado'] = 'cancelada'
            return registro
        if resultado['estado'] != 'completado' or fin is None:
            raise RuntimeError('El workflow no terminó correctamente.')
        wf = _registro_workflow(carpeta)
        registro['workflow'] = wf
        _validar_ejecucion(wf, m, modalidad)
        verificar_muestra(sesion)
        if sha256(sesion / 'muestra/manifiesto.json') != registro['sha256_muestra']:
            raise ValueError('Cambió el manifiesto durante la corrida.')
        registro['ollama_despues'] = _ollama(destino)
        antes, despues = registro['ollama_antes']['digest_qwen'], registro['ollama_despues']['digest_qwen']
        if antes and despues and antes != despues:
            raise ValueError('Cambió la identidad de Qwen durante la corrida.')
        registro['revision_diarizacion_cache'] = _revision_diarizacion()
        registro['tiempo_total_s'] = fin - inicio
        registro['latencia_s'] = fin - inicio - intervencion
        if registro['latencia_s'] < 0:
            raise ValueError('Latencia activa negativa.')
        registro['estado'] = 'completada'
        return registro
    except BaseException as exc:
        registro['estado'] = 'fallida'
        registro['latencia_s'] = None
        registro['error_tipo'] = type(exc).__name__
        # No incorporar automáticamente mensajes con rutas o datos privados al reporte publicable.
        raise
    finally:
        registro['fin_utc'] = ahora()
        registro['artefactos'] = _artefactos(carpeta)
        if 'workflow' not in registro and (carpeta / 'workflow.json').is_file():
            try:
                registro['workflow'] = _registro_workflow(carpeta)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                registro['error_registro_workflow'] = type(exc).__name__
        guardar(ruta, registro)


def _validar_ejecucion(wf, muestra, modalidad):
    tiempos = wf['tiempos']
    if (not tiempos['medicion_cerrada'] or set(tiempos['etapas']) != set(ETAPAS) or
            set(wf['checkpoints']) != set(ETAPAS) or
            any(v['estado'] != 'ejecutada' for v in tiempos['etapas'].values())):
        raise ValueError('La corrida debe ejecutar todas las etapas sin reutilización.')
    if wf['sha256_audio'] != muestra['sha256_audio']:
        raise ValueError('Audio procesado distinto del congelado.')
    esperadas = [{'orden': 1, 'sha256_fuente': muestra['sha256_audio'], 'inicio_muestra': 0,
                  'fin_muestra': muestra['muestras']}] if modalidad == 'unico' else [
        {'orden': i, 'sha256_fuente': p['sha256'], 'inicio_muestra': p['inicio_muestra'],
         'fin_muestra': p['fin_muestra']} for i, p in enumerate(muestra['cortes'], 1)]
    if wf['fuentes'] != esperadas:
        raise ValueError('Orden o contenido de fuentes distinto del congelado.')
    if wf['checkpoints']['transcribir']['dispositivo'] != 'cuda':
        raise ValueError('La transcripción no acredita ejecución en CUDA.')
    s = wf['solicitud']
    if (s['modelo_stt'] != 'medium' or s['dispositivo_stt'] != 'cuda' or
            s['dispositivo_diarizacion'] != 'cuda' or s['num_speakers'] is not None or
            s['identificacion'] != 'pausa' or s['minutas'] != muestra['configuracion_minutas']):
        raise ValueError('Configuración distinta del baseline.')


def reporte(sesion):
    m = verificar_muestra(sesion)
    digest = sha256(sesion / 'muestra/manifiesto.json')
    corridas = []
    for i, modalidad in enumerate(MODALIDADES, 1):
        carpeta = sesion / 'corridas' / f'{i:02d}'
        ruta = carpeta / 'medicion.json'
        if not ruta.exists():
            corridas.append({'corrida': i, 'modalidad': modalidad,
                             'estado': 'interrumpida' if carpeta.exists() else 'pendiente', 'latencia_s': None})
            continue
        r = leer(ruta)
        if (r['estado'] not in {'iniciada', 'fallida', 'cancelada', 'completada'} or
                r['corrida'] != i or r['modalidad'] != modalidad or r['sha256_muestra'] != digest):
            raise ValueError(f'Corrida {i}: registro incompatible con la muestra.')
        if r['estado'] == 'iniciada':
            r = {**r, 'estado': 'iniciada_sin_cierre', 'artefactos': _artefactos(carpeta)}
        artefactos = r.get('artefactos', {})
        if set(artefactos) - set(PUBLICABLES) or _artefactos(carpeta) != artefactos:
            raise ValueError(f'Corrida {i}: artefactos modificados o faltantes.')
        if r['estado'] == 'completada':
            _validar_ejecucion(r['workflow'], m, modalidad)
            requeridos = set(PUBLICABLES) - {'speakers.json'}
            if r['identificacion']['etiquetado_confirmado']:
                requeridos.add('speakers.json')
            if not requeridos <= set(artefactos):
                raise ValueError(f'Corrida {i}: faltan artefactos de una ejecución completa.')
            for etapa in r['workflow']['checkpoints'].values():
                for nombre, hash_ in etapa['archivos'].items():
                    if nombre in artefactos and artefactos[nombre] != hash_:
                        raise ValueError(f'Corrida {i}: hash no corresponde al checkpoint.')
            diar = r['workflow']['diarizacion']
            minuta = leer(carpeta / 'ejecucion_minutas.json')
            if (diar['modelo'] != 'pyannote/speaker-diarization-community-1' or diar['dispositivo'] != 'cuda' or
                    diar['diarization_sha256'] != artefactos['diarization.json'] or
                    diar['audio']['sha256'] != m['sha256_audio'] or
                    minuta['modelo'] != 'qwen2.5:7b' or minuta['destino'] != 'ollama_local'):
                raise ValueError(f'Corrida {i}: modelos o dispositivos distintos del baseline.')
            latencia, total, humano = r['latencia_s'], r['tiempo_total_s'], r['identificacion']['tiempo_s']
            if (any(not math.isfinite(v) or v < 0 for v in (latencia, total, humano)) or
                    latencia != total - humano):
                raise ValueError(f'Corrida {i}: medición inválida.')
        corridas.append(r)
    latencias = [r['latencia_s'] for r in corridas if r['estado'] == 'completada']
    maximo = max(latencias) if len(latencias) == len(MODALIDADES) else None
    gpus = [r.get('entorno', {}).get('gpu') for r in corridas if r['estado'] == 'completada']
    gpu_objetivo = (all('RTX 3050' in g and 'Laptop' in g for g in gpus)
                    if len(gpus) == len(MODALIDADES) and all(gpus) else None)
    datos = {'gpu_objetivo_reportada': gpu_objetivo, 'tipo': m['tipo'], 'equipo_declarado': m['equipo'], 'duracion_audio_s': m['duracion_s'],
             'sha256_muestra': digest, 'corridas': corridas, 'maximo_s': maximo, 'umbral_s': UMBRAL_S,
             'cumple_umbral_latencia': None if maximo is None else maximo <= UMBRAL_S,
             'calidad': 'Ver juicio independiente en calidad.md.'}
    guardar(sesion / 'reporte.json', datos)
    lineas = ['# Evaluación integral del baseline', '', f"Sesión {m['tipo']}; equipo declarado: {m['equipo']}.",
              f"Duración del audio: {m['duracion_s']:.3f} s.", '',
              '| Corrida | Modalidad | Estado | Latencia activa (s) |', '|---|---|---|---:|']
    for r in corridas:
        valor = f"{r['latencia_s']:.3f}" if r['estado'] == 'completada' else '—'
        lineas.append(f"| {r['corrida']} | {r['modalidad']} | {r['estado']} | {valor} |")
    lineas += ['', f"Máximo de las cinco: {'pendiente' if maximo is None else f'{maximo:.3f} s'}.",
               f"Umbral (sección 2.3): {UMBRAL_S} s.",
               'GPU objetivo informada por las cinco corridas: ' + ('sin comprobar' if gpu_objetivo is None else 'sí' if gpu_objetivo else 'no') + '.',
               'Contraste numérico: ' + ('pendiente' if maximo is None else 'cumple' if maximo <= UMBRAL_S else 'no cumple') + '.',
               '', 'La aceptación formal requiere verificar el hardware objetivo, la configuración y las condiciones '
               'de ejecución registradas. Una sesión de prueba no acredita la aceptación. El umbral fue definido para '
               'cinco minutos de audio; se informa la duración efectiva, sin extrapolar ni ajustar la latencia.', '',
               'Calidad: [evaluación independiente](calidad.md). No se infiere un veredicto global de la PoC.', '']
    (sesion / 'reporte.md').write_text('\n'.join(lineas), encoding='utf-8')
    return datos


def publicar(sesion, destino):
    """Prepara una copia revisable; no ejecuta Git ni modifica los artefactos originales."""
    if destino.is_relative_to(sesion):
        raise ValueError('La publicación debe quedar fuera de la sesión de trabajo.')
    if destino.exists():
        raise FileExistsError('El destino de publicación ya existe.')
    datos = reporte(sesion)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destino.parent) as temporal:
        base = Path(temporal) / 'publicacion'
        (base / 'muestra').mkdir(parents=True)
        for nombre in ('audio.wav', '01.wav', '02.wav', '03.wav', 'referencia.md', 'manifiesto.json'):
            shutil.copyfile(sesion / 'muestra' / nombre, base / 'muestra' / nombre)
        (base / 'corridas').mkdir()
        for r in datos['corridas']:
            nombre = f"{r['corrida']:02d}"
            origen = sesion / 'corridas' / nombre
            if not origen.exists():
                continue
            carpeta = base / 'corridas' / nombre
            carpeta.mkdir()
            if (origen / 'medicion.json').is_file():
                shutil.copyfile(origen / 'medicion.json', carpeta / 'medicion.json')
                for archivo in r.get('artefactos', {}):
                    shutil.copyfile(origen / archivo, carpeta / archivo)
        shutil.copyfile(sesion / 'calidad.md', base / 'calidad.md')
        reporte(base)
        base.rename(destino)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operacion', required=True)
    p = sub.add_parser('preparar')
    p.add_argument('sesion', type=Path)
    p.add_argument('--audio', required=True, type=Path)
    p.add_argument('--notas', required=True, type=Path)
    p.add_argument('--autor', required=True)
    p.add_argument('--tipo', choices=['prueba', 'formal'], required=True)
    p.add_argument('--equipo', required=True)
    permiso = p.add_mutually_exclusive_group(required=True)
    permiso.add_argument('--consentimiento', action='store_true')
    permiso.add_argument('--procedencia', type=Path, help='JSON de fuente externa autorizada')
    e = sub.add_parser('ejecutar')
    e.add_argument('sesion', type=Path)
    e.add_argument('--corrida', type=int, choices=range(1, 6))
    e.add_argument('--operador', required=True)
    e.add_argument('--condiciones', required=True)
    r = sub.add_parser('reporte')
    r.add_argument('sesion', type=Path)
    r.add_argument('--publicar', type=Path, help='crear una copia seleccionada para revisión antes de versionar')
    a = parser.parse_args(argv)
    sesion = a.sesion.resolve()
    if a.operacion == 'preparar':
        preparar(sesion, a.audio, a.notas, autor=a.autor, tipo=a.tipo, equipo=a.equipo, consentimiento=a.consentimiento, procedencia=a.procedencia)
    elif a.operacion == 'ejecutar':
        numeros = [a.corrida] if a.corrida else list(range(1, 6))
        if any((sesion / 'corridas' / f'{i:02d}').exists() for i in numeros):
            parser.error('Ya existe una corrida solicitada. Seleccioná explícitamente una corrida aún no iniciada.')
        for i in numeros:
            resultado = ejecutar(sesion, i, operador=a.operador, condiciones=a.condiciones)
            if resultado['estado'] != 'completada':
                return 1
    elif a.operacion == 'reporte':
        if a.publicar:
            publicar(sesion, a.publicar.resolve())
        else:
            reporte(sesion)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
