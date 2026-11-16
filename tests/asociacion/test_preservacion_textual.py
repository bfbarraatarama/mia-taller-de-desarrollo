"""Regresiones de integridad textual y procedencia sin inferencias (issue #16)."""
import random

import pytest

from src.asociacion.asociacion import Turnos, armar_intervenciones, asociar
from src.asociacion.contrato import validar_asr, validar_transcripcion
from src.asociacion.etiquetado import ModeloFichas
from src.asociacion.fragmentos import _texto_fragmento
from src.asociacion.salida import escribir
from src.stt import build_asr, validate_asr_contract
from .conftest import crear_reunion, leer, palabras


def datos(texto, ws, inicio=0.0, fin=2.0):
    return {'language': 'es', 'segments': [dict(start=inicio, end=fin, text=texto, words=ws)]}


def asociacion(asr, turnos, duracion=5):
    normal, _ = validar_asr(asr, duracion)
    t = Turnos([dict(start=a, end=b, speaker=e) for a, b, e in turnos])
    intervenciones, _ = armar_intervenciones(normal, t)
    salida = {'segments': [i.a_dict() for i in intervenciones]}
    assert not validar_transcripcion(salida, duracion, t.etiquetas, asr=normal)
    return salida['segments']


def test_negacion_sin_marcas_validas(tmp_path):
    asr = build_asr(datos('No aprobar el cambio', palabras(('No', 0, 0), ('aprobar', .2, .8),
                     ('el', .8, 1.), ('cambio', 1., 1.8))))
    validate_asr_contract(asr, 2)
    carpeta = crear_reunion(tmp_path, 2, [(0, 2, 'A')], asr['segments'])
    a = asociar(carpeta)
    escribir(a)
    [fila] = leer(carpeta / 'transcription.json')['segments']
    assert fila == dict(start=0., end=2., speaker='A', name=None, text='No aprobar el cambio',
                        overlap=False, ambiguous=False, timing='segment',
                        speakers_detected=[dict(speaker='A', name=None)],
                        source=dict(segment=0, start=0, end=20))
    assert len(asr['segments'][0]['words']) == 3


@pytest.mark.parametrize('texto,ws', [
    ('No, no firmamos.', ['no', 'firmamos.']),
    ('No firmamos.', ['Sí', 'firmamos.']),
    ('No firmamos.', ['No', 'No', 'firmamos.']),
    ('abc', ['a', 'bc']),
    ('1,25', ['1', '25']),
    ('a b', ['ab']),
    ('No firmamos.', []),
])
def test_discordancias_sin_sustitucion_ni_duplicacion(texto, ws):
    asr = datos(texto, palabras(*[(w, .2+i*.2, .4+i*.2) for i, w in enumerate(ws)]))
    [fila] = asociacion(asr, [(0, 2, 'A')])
    assert fila['text'] == texto and fila['timing'] == 'segment'


def test_puntuacion_y_espacios_literales():
    asr = datos('  ¿Sí?  De\tacuerdo.  ', palabras(('¿', 0, .1), ('Sí', .1, .4), ('?', .4, .5),
                    ('De acuerdo.', .6, 1.5)))
    filas = asociacion(asr, [(0, .5, 'A'), (.5, 2, 'B')])
    assert [(f['text'], f['speaker'], f['timing']) for f in filas] == [
        ('¿Sí?', 'A', 'word'), ('De\tacuerdo.', 'B', 'word')]
    assert [(f['source']['start'], f['source']['end']) for f in filas] == [(2, 6), (8, 19)]


@pytest.mark.parametrize('turnos,speaker,overlap,detectados', [
    ([(0, 2, 'A')], 'A', False, ['A']),
    ([(0, 1, 'A'), (1, 2, 'B')], None, False, ['A', 'B']),
    ([(0, 2, 'A'), (.5, 1.5, 'B'), (1, 2, 'C')], None, True, ['A', 'B', 'C']),
    ([(0, 1, 'A')], None, False, ['A']),
    ([(0, 2, 'A'), (1.99, 2, 'B')], None, False, ['A', 'B']),
    ([], None, False, []),
])
def test_deteccion_no_equivale_a_atribucion(turnos, speaker, overlap, detectados):
    [fila] = asociacion(datos('No firmo.', palabras(('firmo.', .5, 1.))), turnos)
    assert fila['speaker'] == speaker
    assert fila['ambiguous'] is (speaker is None)
    assert fila['overlap'] is overlap
    assert [d['speaker'] for d in fila['speakers_detected']] == detectados


def test_etiquetado_de_detectados(tmp_path):
    asr = datos('No firmo.', palabras(('firmo.', .5, 1.)))
    carpeta = crear_reunion(tmp_path, 3, [(0, 2, 'A'), (.5, 1.5, 'B')], asr['segments'])
    a = asociar(carpeta)
    fichas = ModeloFichas(a)
    fichas.escribir_nombre('A', 'Lucía')
    fichas.escribir_nombre('B', 'Martín')
    escribir(a, fichas.confirmar().etiquetado)
    [f] = leer(carpeta / 'transcription.json')['segments']
    assert f['speaker'] is f['name'] is None
    assert f['speakers_detected'] == [dict(speaker='A', name='Lucía'), dict(speaker='B', name='Martín')]


def test_empate_y_hueco_local_no_se_diluyen():
    asr = datos('Yo no firmo.', palabras(('Yo', 0, 1), ('no', 1, 1.1), ('firmo.', 1.1, 2)))
    [f] = asociacion(asr, [(0, 2, 'A'), (1, 1.1, 'B')])
    assert (f['speaker'], f['overlap'], f['ambiguous']) == ('A', False, True)
    [f] = asociacion(asr, [(0, 1, 'A'), (1.1, 2, 'A')])
    assert (f['speaker'], f['overlap'], f['ambiguous']) == ('A', False, True)
    [f] = asociacion(datos('No.', palabras(('No.', 1, 1.1))), [(0, .99, 'A')])
    assert (f['speaker'], f['speakers_detected'], f['ambiguous']) == ('A', [], True)


def test_contradiccion_de_tiempos_no_invierte_texto():
    asr = datos('No firmo.', palabras(('No', 1.2, 1.5), ('firmo.', .1, .6)))
    [f] = asociacion(asr, [(0, 1, 'A'), (1, 2, 'B')])
    assert (f['text'], f['speaker'], f['timing']) == ('No firmo.', None, 'segment')
    asr['segments'].append(dict(start=0, end=.5, text='Primero.', words=palabras(('Primero.', 0, .5))))
    asr['segments'][0].update(start=1, end=2, text='Segundo.', words=palabras(('Segundo.', 1, 2)))
    fs = asociacion(asr, [(0, 1, 'A'), (1, 2, 'B')])
    assert [(f['text'], f['start']) for f in fs] == [('Segundo.', 1), ('Primero.', 0)]


@pytest.mark.parametrize('ws,inicio,fin,timing,intervalo', [
    ([('No', 4.2, 4.5), ('todavía.', 5.1, 5.2)], 4, 5.3, 'segment', (4, 5)),
    ([('No', 5.1, 5.2), ('todavía.', 5.2, 5.3)], 4, 5.4, 'segment', (4, 5)),
    ([('No', 5.1, 5.2), ('todavía.', 5.2, 5.3)], 5.1, 5.4, 'unknown', (None, None)),
    ([('No', 1, 1.2), ('todavía.', 1.2, 1.8)], 5.1, 5.4, 'word', (1, 1.8)),
    ([('No', 1, 1.2)], 3, 4, 'unknown', (None, None)),
    ([('No', 1, 1.2)], None, None, 'unknown', (None, None)),
])
def test_recortes_y_evidencia_contradictoria(ws, inicio, fin, timing, intervalo):
    [f] = asociacion(datos('No todavía.', palabras(*ws), inicio, fin), [(0, 5, 'A')])
    assert (f['text'], f['timing'], (f['start'], f['end'])) == ('No todavía.', timing, intervalo)
    if timing == 'unknown':
        assert f['speakers_detected'] is f['overlap'] is f['speaker'] is None
    if timing == 'segment':
        assert f['speaker'] is None and f['ambiguous']  # el intervalo perdido no respalda atribución


def test_fichas_no_presentan_segmento_parcial_como_texto_localizado():
    asr = datos('No firmo.', palabras(('firmo.', .5, 1.)))
    assert _texto_fragmento(asr, 0, 2000) == ('No firmo.', True)
    assert _texto_fragmento(asr, 400, 1200) == ('', True)
    assert _texto_fragmento(asr, 3000, 4000) == ('', False)


def test_invariante_en_combinaciones_deterministas():
    r = random.Random(16)
    tokens = ['No', 'no', '¿Sí?', 'presupuesto,', '1,25', 'Martín', 'firmamos.']
    turnos = [(0, 1, 'A'), (1, 2, 'B'), (1.1, 1.2, 'C')]
    for _ in range(150):
        n = r.randint(1, 7)
        ws = [r.choice(tokens) for _ in range(n)]
        texto = ws[0] + ''.join(r.choice([' ', '  ', '\t']) + w for w in ws[1:])
        tiempos = palabras(*[(w, i * .2, (i + 1) * .2) for i, w in enumerate(ws) if r.random() > .25])
        asr = datos(texto, tiempos)
        fs = asociacion(asr, turnos)
        assert fs == asociacion(asr, turnos)
        assert ''.join(f['text'].replace(' ', '').replace('\t', '') for f in fs) == texto.replace(' ', '').replace('\t', '')


@pytest.mark.parametrize('cambio', [
    lambda f: f.update(text='firmo.'),
    lambda f: f['source'].update(start=1),
    lambda f: f['source'].update(segment=3),
    lambda f: f.update(start=.1),
    lambda f: f.update(speakers_detected=[dict(speaker='B', name=None)]),
    lambda f: f.update(timing='unknown'),
    lambda f: f.update(speakers_detected=[dict(speaker='A', name=None)]*2),
    lambda f: f.pop('source'),
])
def test_validador_detecta_corrupcion_de_contrato(cambio):
    asr = datos('No firmo.', palabras(('No', 0, .4), ('firmo.', .4, 1)))
    normal, _ = validar_asr(asr, 5)
    fs = {'segments': asociacion(asr, [(0, 2, 'A')])}
    cambio(fs['segments'][0])
    assert validar_transcripcion(fs, 5, ('A',), asr=normal)


def test_rechaza_texto_vacio_con_palabras_y_intervalo_externo_invalido():
    with pytest.raises(ValueError):
        build_asr(datos('', palabras(('No', 0, .1))))
    asr = datos('No', palabras(('No', 0, .1)), None, .2)
    with pytest.raises(ValueError):
        validate_asr_contract(asr, 2)
