"""Contratos de extremo a extremo de la preservación textual, sin modelos reales."""
import json

import pytest

from src.asociacion.asociacion import asociar
from src.asociacion.etiquetado import ModeloFichas
from src.asociacion.salida import escribir
from src.interfaz.presentacion import agrupar_transcripcion, minuta_html, transcripcion_html
from src.minutas.contratos import modelo_minuta, validar_evidencias
from src.minutas.entrada import leer_transcripcion
from src.minutas.generacion import ConfiguracionMinutas, generar_minuta
from src.minutas.proveedores import RespuestaModelo
from src.stt import build_asr
from tests.asociacion.conftest import crear_reunion, palabras


class Cliente:
    proveedor = 'ollama'
    nombre = 'simulado'

    def __init__(self):
        self.llamadas = []

    def responder(self, instrucciones, datos, esquema):
        filas = json.loads(datos)['intervenciones']
        self.llamadas.append((instrucciones, filas))
        return RespuestaModelo({'decisiones': [{'texto': 'No se aprobó el cambio.',
                                'ids_intervenciones': [filas[0]['id']], 'id_ancla': filas[0]['id']}]})


def entrada(tmp_path):
    asr = build_asr({'segments': [
        {'start': None, 'end': None, 'text': 'Texto ilocalizable.', 'words': []},
        {'start': .125, 'end': .875, 'text': 'No aprobar el cambio.', 'words': palabras(
            ('No', .125, .125), ('aprobar', .2, .5), ('el', .5, .6), ('cambio.', .6, .8))},
        {'start': 1., 'end': 2., 'text': 'Se revisó.', 'words': palabras(('Se', 1, 1.3), ('revisó.', 1.3, 2))},
    ]})
    carpeta = crear_reunion(tmp_path, 3, [(0, 2, 'A'), (.2, .8, 'B')], asr['segments'])
    a = asociar(carpeta)
    fichas = ModeloFichas(a)
    fichas.escribir_nombre('A', 'Lucía')
    fichas.escribir_nombre('B', 'Martín')
    return escribir(a, fichas.confirmar().etiquetado)


def test_de_stt_a_minutas_y_visores(tmp_path):
    ruta = entrada(tmp_path)
    cliente = Cliente()
    config = ConfiguracionMinutas(secciones=('decisiones',))
    resultado = generar_minuta(ruta, tmp_path, configuracion=config, cliente=cliente)
    [(prompt, filas)] = cliente.llamadas
    assert [f['id'] for f in filas] == ['I000002', 'I000003']
    assert [f['texto'] for f in filas] == ['No aprobar el cambio.', 'Se revisó.']
    assert filas[0]['hablante'] is None and filas[0]['ambiguo']
    assert filas[0]['resolucion_temporal'] == 'segmento'
    assert filas[0]['hablantes_detectados'] == [{'hablante': 'A', 'nombre': 'Lucía'},
                                                {'hablante': 'B', 'nombre': 'Martín'}]
    assert 'actividad vocal, no autores' in prompt
    md = resultado.markdown.read_text(encoding='utf-8')
    assert '[00:00.125–00:00.875, aprox.]' in md
    assert 'falta de ubicación temporal (una intervención)' in md
    assert '<li>' in minuta_html(md)
    meta = json.loads(resultado.manifiesto.read_text(encoding='utf-8'))
    assert (meta['intervenciones'], meta['intervenciones_sin_ubicacion_excluidas']) == (2, 1)
    contenido = ruta.read_text(encoding='utf-8')
    html = transcripcion_html(contenido)
    for texto in ('Texto ilocalizable.', 'Sin ubicación temporal verificable', 'No aprobar el cambio.',
                  'resolución temporal por segmento', 'Lucía (A)', 'Martín (B)', 'atribución ambigua'):
        assert texto in html
    assert len(agrupar_transcripcion(contenido)) == 3
    intervenciones, _ = leer_transcripcion(ruta)
    invalida = modelo_minuta(('decisiones',)).model_validate({'decisiones': [dict(
        texto='Falsa evidencia', ids_intervenciones=['I000001'], id_ancla='I000001')]})
    with pytest.raises(ValueError, match='referencias inexistentes'):
        validar_evidencias(invalida, intervenciones)


def test_todo_ilocalizable_no_llama_al_modelo(tmp_path):
    carpeta = crear_reunion(tmp_path, 3, [], [{'start': None, 'end': None, 'text': 'No firmo.', 'words': []}])
    ruta = escribir(asociar(carpeta))
    cliente = Cliente()
    with pytest.raises(ValueError, match='No existe evidencia temporal utilizable'):
        generar_minuta(ruta, tmp_path, cliente=cliente)
    assert cliente.llamadas == [] and ruta.exists()
    assert 'No firmo.' in transcripcion_html(ruta.read_text())
    assert not (tmp_path / 'minutes.md').exists()


def test_orden_de_reconocimiento_se_conserva_en_consumidores(tmp_path):
    carpeta = crear_reunion(tmp_path, 3, [(0, 3, 'A')], [
        dict(start=1, end=2, text='Primero reconocido.', words=palabras(('Primero reconocido.', 1, 2))),
        dict(start=0, end=.9, text='Segundo reconocido.', words=palabras(('Segundo reconocido.', 0, .9))),
    ])
    ruta = escribir(asociar(carpeta))
    fs, _ = leer_transcripcion(ruta)
    assert [(f.inicio, f.texto) for f in fs] == [(1, 'Primero reconocido.'), (0, 'Segundo reconocido.')]
    html = transcripcion_html(ruta.read_text())
    assert html.index('Primero reconocido.') < html.index('Segundo reconocido.')


def test_no_agrupar_bloques_con_distinta_evidencia(tmp_path):
    ruta = entrada(tmp_path)
    filas = json.loads(ruta.read_text())['segments']
    assert len(agrupar_transcripcion(json.dumps({'segments': filas[1:]}))) == 2
