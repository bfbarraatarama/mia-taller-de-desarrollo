"""Pruebas de la representación determinista, sin Qt ni inferencia."""
import json
from html.parser import HTMLParser

import pytest

from src.interfaz.presentacion import (agrupar_transcripcion, marca_tiempo, minuta_html,
                                           transcripcion_html)
from src.minutas.formato import a_markdown
from src.minutas.contratos import modelo_minuta, Intervencion


def fila(inicio, fin, texto='texto', **cambios):
    return dict(start=inicio, end=fin, speaker='SPEAKER_00', name='Ana', text=texto,
                overlap=False, ambiguous=False) | cambios


def datos(*filas):
    return json.dumps({'segments': list(filas)}, ensure_ascii=False)


def test_agrupa_sin_reformular_y_conserva_limites():
    original = datos(fila(0, 1, 'Una oración'), fila(1.25, 2, 'que continúa'),
                     fila(3, 4, 'y termina.'))
    b, = agrupar_transcripcion(original)
    assert (b.inicio, b.fin, b.hablante, b.nombre, b.textos) == (
        0, 4, 'SPEAKER_00', 'Ana', ('Una oración', 'que continúa', 'y termina.'))
    assert 'Una oración que continúa y termina.' in transcripcion_html(original)
    assert json.loads(original)['segments'][0]['text'] == 'Una oración'


@pytest.mark.parametrize('cambio', [dict(speaker='SPEAKER_01'), dict(name='Otra'),
                                      dict(ambiguous=True), dict(overlap=True, ambiguous=True), dict(speaker=None, name=None)])
def test_no_agrupa_ante_cambio_o_incertidumbre(cambio):
    assert len(agrupar_transcripcion(datos(fila(0, 1), fila(1, 2, **cambio)))) == 2
    assert len(agrupar_transcripcion(datos(fila(0, 1, **cambio), fila(1, 2)))) == 2


@pytest.mark.parametrize('marcas', [(True, False, False), (False, True, False),
                                    (False, False, True), (True, True, True)])
def test_agrupa_solapamiento_no_ambiguo_y_conserva_marcas(marcas):
    original = datos(*(fila(i, i + 1, t, overlap=m) for i, (t, m) in
                       enumerate(zip(('Una', 'misma', 'intervención.'), marcas))))
    bloque, = agrupar_transcripcion(original)
    assert bloque.textos == ('Una', 'misma', 'intervención.')
    assert (bloque.inicio, bloque.fin) == (0, 3)
    assert bloque.overlap and not bloque.ambiguous
    assert bloque.solapamiento_parcial == (not all(marcas))
    html = transcripcion_html(original)
    assert 'Una misma intervención.' in html
    assert 'solapamiento' in html
    assert ('solapamiento en parte de la intervención' in html) == (not all(marcas))
    assert [s['overlap'] for s in json.loads(original)['segments']] == list(marcas)


def test_secuencia_observada_con_solapamientos_y_pausas_breves():
    original = datos(fila(0, 3, 'Primera parte', name=None, overlap=True),
                     fila(3.9, 6.24, 'de una', name=None, overlap=True),
                     fila(6.24, 21.26, 'intervención', name=None),
                     fila(21.78, 27.78, 'larga.', name=None, overlap=True),
                     fila(28, 29, 'Otra voz.', name=None, speaker='SPEAKER_01'))
    primero, segundo = agrupar_transcripcion(original)
    assert (primero.inicio, primero.fin, primero.hablante) == (0, 27.78, 'SPEAKER_00')
    assert primero.overlap and primero.solapamiento_parcial
    assert segundo.hablante == 'SPEAKER_01' and not segundo.overlap
    html = transcripcion_html(original)
    assert '00:00:27.780' in html and 'Primera parte de una intervención larga.' in html


def test_solapamiento_no_elimina_barreras_temporales_o_de_atribucion():
    casos = [fila(0.9, 2, overlap=True), fila(2.001, 3, overlap=True),
             fila(1, 2, overlap=True, ambiguous=True), fila(1, 2, overlap=True, speaker='SPEAKER_01')]
    for posterior in casos:
        assert len(agrupar_transcripcion(datos(fila(0, 1, overlap=True), posterior))) == 2


def test_pausas_limite_y_hablante_sin_nombre():
    f = lambda i, j: fila(i, j, name=None)
    assert len(agrupar_transcripcion(datos(f(0, 1), f(2, 3)))) == 1
    assert len(agrupar_transcripcion(datos(f(0, 1), f(2.001, 3)))) == 2


def test_no_agrupa_etiquetas_desconocidas_ni_salta_hablantes():
    f = lambda i, j: fila(i, j, speaker=None, name=None, ambiguous=True)
    assert len(agrupar_transcripcion(datos(f(0, 1), f(1, 2)))) == 2
    assert len(agrupar_transcripcion(datos(fila(0, 1), fila(1, 2, speaker='SPEAKER_01'), fila(2, 3)))) == 3


def test_no_agrupa_intersecciones_aunque_no_haya_marcas():
    assert len(agrupar_transcripcion(datos(fila(0, 2), fila(1, 3), fila(3, 4)))) == 3
    assert len(agrupar_transcripcion(datos(fila(0, 5, speaker='SPEAKER_01'),
                                              fila(1, 2), fila(2, 3)))) == 3


def test_marcas_e_identidades_visibles():
    html = transcripcion_html(datos(fila(0, 1, overlap=True, ambiguous=True),
                                     fila(1, 2, speaker=None, name=None, ambiguous=True)))
    for texto in ('Ana (SPEAKER_00)', 'solapamiento', 'atribución ambigua', 'Hablante no identificado'):
        assert texto in html
    assert marca_tiempo(3661.125) == '01:01:01.125'


@pytest.mark.parametrize('contenido', ['[]', '{}', '{', datos(fila(1, 0)), datos(fila(1, 2), fila(0, 1)),
                                        datos(fila(0, 1, speaker=[])), datos(fila(0, 1, speaker="")), datos(fila(0, 1, overlap=1))])
def test_rechaza_transcripcion_invalida(contenido):
    with pytest.raises(ValueError):
        agrupar_transcripcion(contenido)


def test_transcripcion_vacia():
    assert agrupar_transcripcion(datos()) == []
    assert 'No hay intervenciones' in transcripcion_html(datos())


class InspeccionHTML(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.textos = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, attrs))

    def handle_data(self, texto):
        self.textos.append(texto)


def comprobar_html(html, ataque):
    p = InspeccionHTML(html)
    assert all(tag in {'h1', 'h2', 'p', 'b', 'br', 'hr', 'ul', 'li'} and not attrs for tag, attrs in p.tags)
    assert ataque in ''.join(p.textos)
    return p


@pytest.mark.parametrize('ataque', ['<img src="file:///etc/passwd">', '<a href="https://ejemplo.com">link</a>',
                                   '![x](https://ejemplo.com/x)', '<script>alert(1)</script>',
                                   'a & b <> [x] `texto` \\ *c*'])
def test_transcripcion_no_interpreta_contenido(ataque):
    html = transcripcion_html(datos(fila(0, 1, ataque, name=ataque)))
    comprobar_html(html, ataque)


@pytest.mark.parametrize('texto', ['<img src="https://ejemplo.com/x">', '![x](file:///tmp/x)',
                                  '<a href="https://ejemplo.com">enlace</a>', 'a & b <> [x] `texto` \\ *c*',
                                  '## Temas tratados', '- [00:01] texto'])
def test_minuta_usa_contrato_real_y_escape_reversible(texto):
    esquema = modelo_minuta(('resumen',))
    minuta = esquema.model_validate({'resumen': texto})
    original = a_markdown(minuta, [])
    p = comprobar_html(minuta_html(original), texto)
    assert sum(t == 'h2' for t, _ in p.tags) == 1


def test_minuta_listas_y_secciones_seleccionadas():
    contenido = ('# Minuta de reunión\n\n## Decisiones\n\n- [00:01] una\n- [00:02] dos\n\n'
                 '## Acciones pendientes\n\n- [01:01:11] una acción — Responsable: Ana\n')
    html = minuta_html(contenido)
    assert html.count('<ul>') == html.count('</ul>') == 2
    assert html.count('<li>') == 3
    assert '<h2>Decisiones</h2>' in html and '<h2>Acciones pendientes</h2>' in html
    assert '<h2>Resumen</h2>' not in html and '[01:01:11]' in html


def test_union_de_puntuacion_sin_cambiar_fragmentos():
    original = datos(fila(0, 1, '¿'), fila(1, 2, 'Cómo estás'), fila(2, 3, '?'), fila(3, 4, 'Bien.'))
    assert agrupar_transcripcion(original)[0].textos == ('¿', 'Cómo estás', '?', 'Bien.')
    assert '¿Cómo estás? Bien.' in transcripcion_html(original)


def test_minuta_con_acciones_reales_y_texto_no_confiable():
    intervenciones = [Intervencion(id='I000001', inicio=3661, fin=3662, hablante='SPEAKER_00',
                                  nombre='Ana', texto='texto', superposicion=False, ambiguo=False)]
    ataque = '<img src="file:///tmp/no-leer">'
    base = {'texto': ataque, 'id_ancla': 'I000001', 'ids_intervenciones': ['I000001']}
    minuta = modelo_minuta(('decisiones', 'acciones', 'problemas')).model_validate({
        'decisiones': [base], 'acciones': [base | {'responsable': ataque, 'plazo': 'mañana'}], 'problemas': []})
    html = minuta_html(a_markdown(minuta, intervenciones))
    p = comprobar_html(html, ataque)
    assert ''.join(p.textos).count(ataque) == 3
    assert '[01:01:01]' in html and 'No se identificaron elementos.' in html
    assert 'plazo: mañana' in html
    assert 'Resumen' not in html
