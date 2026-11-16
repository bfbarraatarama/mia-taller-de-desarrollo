"""Protocolo integral con el workflow real y sustitución de inferencias y diálogo."""
import json
import shutil
import wave

import pytest

from evaluacion.integral import evaluar as ev
from src.asociacion.etiquetado import Decision, ModeloFichas
from tests.integracion.test_workflow import modelos_falsos

pytestmark = pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='Requiere FFmpeg')


def audio(ruta, muestras):
    # PCM determinista y no constante: detecta inversiones y omisiones de cortes.
    bloque = b''.join(i.to_bytes(2, 'little', signed=True) for i in range(-100, 101))
    with wave.open(str(ruta), 'wb') as w:
        w.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        bloques, resto = divmod(muestras, len(bloque) // 2)
        w.writeframes(bloque * bloques + bloque[:resto * 2])
    return ruta


@pytest.fixture
def fuentes(tmp_path):
    a = audio(tmp_path / 'original.wav', 300 * ev.FS + 2)
    n = tmp_path / 'notas.md'
    n.write_text('Notas sintéticas para comprobar el ejecutor, no evidencia semántica.', encoding='utf-8')
    return a, n


@pytest.fixture
def sesion(tmp_path, fuentes):
    s = tmp_path / 'sesion'
    ev.preparar(s, *fuentes, autor='Ana', tipo='prueba', equipo='Simulado', consentimiento=True)
    return s


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(ev, '_app', lambda: object())
    monkeypatch.setattr(ev, '_ollama', lambda destino: {'version': 'falsa', 'digest_qwen': 'falso', 'qwen_residente': False})
    monkeypatch.setattr(ev, '_entorno', lambda: {'gpu': 'simulada'})
    monkeypatch.setattr(ev, '_revision_diarizacion', lambda: None)
    monkeypatch.setenv('OLLAMA_HOST', 'http://127.0.0.1:11434')

    def dialogo(asociacion):
        modelo = ModeloFichas(asociacion)
        for ficha in modelo.fichas:
            modelo.escribir_nombre(ficha.etiqueta, 'Carla')
        return modelo.confirmar, True

    monkeypatch.setattr(ev, '_dialogo', dialogo)


def correr(sesion, numero):
    return ev.ejecutar(sesion, numero, operador='Bruno', condiciones='Simulación sin modelos reales')


def test_preparacion_congelada(sesion):
    m = ev.verificar_muestra(sesion)
    assert m['muestras'] == 300 * ev.FS + 2
    assert [p['fin_muestra'] for p in m['cortes']][-1] == m['muestras']
    assert ev.reporte(sesion)['maximo_s'] is None
    (sesion / 'muestra/referencia.md').write_text('cambiada')
    with pytest.raises(ValueError, match='congelada'):
        ev.verificar_muestra(sesion)


def test_rechaza_audio_corto_y_sin_consentimiento(tmp_path, fuentes):
    a = audio(tmp_path / 'corto.wav', 299 * ev.FS)
    salida = tmp_path / 'destino'
    with pytest.raises(ValueError, match='consentimiento'):
        ev.preparar(salida, a, fuentes[1], autor='Ana', tipo='prueba', equipo='simulado', consentimiento=False)
    with pytest.raises(ValueError, match='cinco minutos'):
        ev.preparar(salida, a, fuentes[1], autor='Ana', tipo='prueba', equipo='simulado', consentimiento=True)
    assert not salida.exists()


def test_corte_alterado(sesion):
    p = sesion / 'muestra/02.wav'
    with p.open('r+b') as f:
        f.seek(-2, 2)
        f.write(b'\xff\xff')
    with pytest.raises(ValueError, match='corte'):
        ev.verificar_muestra(sesion)


def test_cinco_corridas_y_publicacion(sesion, cliente, modelos_falsos, monkeypatch, tmp_path):
    from pathlib import Path
    from src.pipeline import ejecucion
    trabajador = ejecucion._trabajador

    def con_ruta_local(modulo, argumentos, *, emisor):
        resultado = trabajador(modulo, argumentos, emisor=emisor)
        if modulo == 'src.diarizacion.diarizar':
            directorio = Path(argumentos[argumentos.index('--salida') + 1])
            meta = directorio / 'diarization.meta.json'
            datos = ev.leer(meta)
            datos['audio']['ruta'] = str(directorio / 'audio.wav')
            ev.guardar(meta, datos)
        return resultado

    monkeypatch.setattr(ejecucion, '_trabajador', con_ruta_local)
    # El reloj del ejecutor se controla independientemente del del workflow.
    # Cada corrida llama a inicio, inicio de diálogo, fin del diálogo y fin del workflow.
    latencias = [20, 30, 1800, 50, 25]
    instantes = iter(t for i, latencia in enumerate(latencias)
                     for t in (i * 2000, i * 2000 + 10, i * 2000 + 40, i * 2000 + 30 + latencia))
    monkeypatch.setattr(ev, 'monotonic', lambda: next(instantes))
    for i in range(1, 6):
        r = correr(sesion, i)
        assert r['estado'] == 'completada'
        assert r['latencia_s'] == latencias[i - 1]
        assert r['identificacion']['tiempo_s'] == 30
        assert r['workflow']['sha256_audio'] == ev.verificar_muestra(sesion)['sha256_audio']
    assert set(modelos_falsos.values()) == {5}
    with pytest.raises(FileExistsError):
        correr(sesion, 1)
    r = ev.reporte(sesion)
    assert r['maximo_s'] == 1800 and r['cumple_umbral_latencia'] is True
    assert [c['modalidad'] for c in r['corridas']] == list(ev.MODALIDADES)
    assert set(modelos_falsos.values()) == {5}
    publica = tmp_path / 'publica'
    ev.publicar(sesion, publica)
    assert ev.reporte(publica) == r
    assert not (publica / 'corridas/01/audio.wav').exists()
    assert not (publica / 'corridas/01/workflow.json').exists()
    assert not (publica / 'corridas/01/ingesta.json').exists()
    assert not (publica / 'corridas/01/diarization.meta.json').exists()
    assert not (publica / 'corridas/01/transcription.meta.json').exists()
    assert str(sesion) not in (publica / 'corridas/01/medicion.json').read_text()
    # Comparación con p100 por encima del umbral, sin repetir inferencias.
    med = publica / 'corridas/03/medicion.json'
    registro = ev.leer(med)
    registro['tiempo_total_s'] += 1
    registro['latencia_s'] += 1
    ev.guardar(med, registro)
    assert ev.reporte(publica)['cumple_umbral_latencia'] is False
    (publica / 'corridas/01/minutes.md').write_text('alterada')
    with pytest.raises(ValueError, match='artefactos'):
        ev.reporte(publica)


def test_independencia_del_evaluador(sesion):
    with pytest.raises(ValueError, match='independiente'):
        ev.ejecutar(sesion, 1, operador=' ANA ', condiciones='prueba')
    assert not (sesion / 'corridas/01').exists()


def test_falla_conservada(sesion, cliente, modelos_falsos, monkeypatch):
    from src.pipeline import ejecucion

    def falla(*args, **kwargs):
        raise RuntimeError('Fallo simulado')

    monkeypatch.setattr(ejecucion, '_trabajador', falla)
    with pytest.raises(RuntimeError, match='simulado'):
        correr(sesion, 1)
    r = ev.reporte(sesion)
    assert r['corridas'][0]['estado'] == 'fallida'
    assert r['corridas'][0]['error_tipo'] == 'RuntimeError'
    assert r['maximo_s'] is None
    with pytest.raises(FileExistsError):
        correr(sesion, 1)


def test_cancelacion(sesion, cliente, modelos_falsos, monkeypatch):
    monkeypatch.setattr(ev, '_dialogo', lambda a: (lambda: Decision('cancelar'), True))
    r = correr(sesion, 1)
    assert r['estado'] == 'cancelada' and r['latencia_s'] is None
    assert modelos_falsos['src.minutas'] == 0
    assert ev.reporte(sesion)['maximo_s'] is None


def test_reporte_rechaza_reutilizacion(sesion, cliente, modelos_falsos):
    correr(sesion, 1)
    ruta = sesion / 'corridas/01/medicion.json'
    r = json.loads(ruta.read_text())
    r['workflow']['tiempos']['etapas']['transcribir']['estado'] = 'reutilizada'
    ruta.write_text(json.dumps(r))
    with pytest.raises(ValueError, match='reutilización'):
        ev.reporte(sesion)


def test_reporte_con_corrida_sin_cierre(sesion):
    carpeta = sesion / 'corridas/01'
    carpeta.mkdir()
    ev.guardar(carpeta / 'medicion.json', {'corrida': 1, 'modalidad': 'unico', 'estado': 'iniciada',
                                           'latencia_s': None, 'sha256_muestra': ev.sha256(sesion / 'muestra/manifiesto.json')})
    (carpeta / 'asr.json').write_text('{}')
    r = ev.reporte(sesion)
    assert r['corridas'][0]['estado'] == 'iniciada_sin_cierre'
    assert r['maximo_s'] is None


def test_procedencia_externa(tmp_path, fuentes):
    a = audio(tmp_path / 'fragmento.wav', 300 * ev.FS)
    p = tmp_path / 'procedencia.json'
    datos = {
        'titulo': 'Grabación sintética', 'url': 'https://example.org/video',
        'url_metadatos': 'https://example.org/api/video', 'licencia': 'CC0',
        'evidencia': 'Declaración de prueba', 'seleccion': 'Extracción de prueba',
        'sha256_original': 'a' * 64, 'sha256_fragmento': ev.sha256(a),
        'inicio_s': 100, 'fin_s': 400,
    }
    ev.guardar(p, datos)
    s = tmp_path / 'externa'
    kwargs = dict(autor='Ana', tipo='prueba', equipo='Simulado', procedencia=p)
    with pytest.raises(ValueError, match='no ambos'):
        ev.preparar(s, a, fuentes[1], consentimiento=True, **kwargs)
    for clave, valor in [('sha256_fragmento', 'b' * 64), ('fin_s', 401), ('licencia', '')]:
        ev.guardar(p, {**datos, clave: valor})
        with pytest.raises(ValueError, match='Procedencia externa'):
            ev.preparar(s, a, fuentes[1], **kwargs)
        assert not s.exists()
    ev.guardar(p, datos)
    m = ev.preparar(s, a, fuentes[1], **kwargs)
    assert m['consentimiento_declarado'] is False
    assert m['procedencia_externa'] == datos
    assert ev.verificar_muestra(s) == m
    destino = tmp_path / 'publicada'
    ev.publicar(s, destino)
    assert ev.verificar_muestra(destino) == m
    m['procedencia_externa']['sha256_fragmento'] = 'b' * 64
    ev.guardar(s / 'muestra/manifiesto.json', m)
    with pytest.raises(ValueError, match='Procedencia externa'):
        ev.verificar_muestra(s)
