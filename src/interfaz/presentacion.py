"""Representaciones de lectura, sin alterar los artefactos ni depender de Qt."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
import json
import re

from ..asociacion.contrato import validar_transcripcion
from ..minutas.formato import TITULOS_SECCIONES

# umbral de presentación, no de asociación ni de detección de actividad vocal
PAUSA_MAX_MS = 1000


@dataclass(frozen=True)
class Bloque:
    inicio: float | None
    fin: float | None
    hablante: str | None
    nombre: str | None
    textos: tuple[str, ...]
    overlap: bool | None
    ambiguous: bool
    solapamiento_parcial: bool = False
    timing: str | None = None
    detectados: tuple[str, ...] | None = None


def agrupar_transcripcion(contenido: str) -> list[Bloque]:
    """Agrupa solamente vecinos inequívocos dentro de una pausa breve.

    La comprobación local del formato no sustituye la validación de vigencia
    del pipeline ni verifica el audio o las etiquetas contra la diarización.
    """
    datos = json.loads(contenido)
    filas = datos.get('segments') if isinstance(datos, dict) else None
    if not isinstance(filas, list):
        raise ValueError('La transcripción no contiene una lista de segmentos.')
    if any(isinstance(s, dict) and s.get('speaker') is not None
           and (not isinstance(s.get('speaker'), str) or not s['speaker'].strip()) for s in filas):
        raise ValueError('La etiqueta del hablante debe ser texto o nula.')
    etiquetas = {s.get('speaker') for s in filas if isinstance(s, dict)
                 and isinstance(s.get('speaker'), str)}
    etiquetas.update(d['speaker'] for s in filas if isinstance(s, dict) and isinstance(s.get('speakers_detected'), list)
                     for d in s['speakers_detected'] if isinstance(d, dict) and isinstance(d.get('speaker'), str))
    # sin acceso a la duración del audio en este adaptador de lectura
    errores = validar_transcripcion(datos, float('inf'), etiquetas)
    if errores:
        raise ValueError('\n'.join(errores))
    # Las intersecciones entre intervalos transcritos son distintas de la
    # marca overlap de la asociación (superposición de voces).
    fin_previo = -1.0
    cruzados = []
    for i, s in enumerate(filas):
        if s['start'] is None:
            cruzados.append(True)
            continue
        siguiente = filas[i + 1]['start'] if i + 1 < len(filas) else None
        cruzados.append(s['start'] < fin_previo or (siguiente is not None and siguiente < s['end']))
        fin_previo = max(fin_previo, s['end'])
    grupos = []
    for i, s in enumerate(filas):
        anterior = filas[i - 1] if i else None
        reunir = (anterior is not None and s['speaker'] is not None
                  and (s['speaker'], s['name']) == (anterior['speaker'], anterior['name'])
                  and not any((s['ambiguous'], anterior['ambiguous'], cruzados[i], cruzados[i - 1]))
                  and s.get('timing') == anterior.get('timing') in (None, 'word')
                  and s.get('speakers_detected') == anterior.get('speakers_detected')
                  and 0 <= round(s['start'] * 1000) - round(anterior['end'] * 1000) <= PAUSA_MAX_MS)
        if not reunir:
            grupos.append([])
        grupos[-1].append(s)

    bloques = []
    for grupo in grupos:
        primera, ultima = grupo[0], grupo[-1]
        solapados = sum(s['overlap'] is True for s in grupo)
        detectados = primera.get('speakers_detected')
        bloques.append(Bloque(primera['start'], ultima['end'], primera['speaker'], primera['name'],
                              tuple(s['text'] for s in grupo), None if primera['overlap'] is None else bool(solapados),
                              any(s['ambiguous'] for s in grupo), 0 < solapados < len(grupo), primera.get('timing'),
                              tuple(f"{d['name']} ({d['speaker']})" if d['name'] else d['speaker']
                                    for d in detectados) if detectados is not None else None))
    return bloques


def marca_tiempo(segundos: float) -> str:
    total, ms = divmod(round(segundos * 1000), 1000)
    horas, resto = divmod(total, 3600)
    minutos, segundos = divmod(resto, 60)
    return f'{horas:02d}:{minutos:02d}:{segundos:02d}.{ms:03d}'


def _literal(texto: str) -> str:
    return escape(texto).replace('\n', '<br>')


def _unir_textos(textos: tuple[str, ...]) -> str:
    """Insertar separadores de lectura sin modificar los fragmentos."""
    partes = [textos[0]]
    for anterior, siguiente in zip(textos, textos[1:]):
        espacio = '' if siguiente[0] in ',.;:!?%)]}' or anterior[-1] in '¿¡([{' else ' '
        partes.extend((espacio, siguiente))
    return ''.join(partes)


def transcripcion_html(contenido: str) -> str:
    bloques = agrupar_transcripcion(contenido)
    partes = ['<h1>Transcripción de la reunión</h1>',
              '<p>Vista agrupada para lectura. Consultá el original para los límites de cada fragmento.</p>']
    if any(b.timing is not None for b in bloques):
        partes.append('<p>Se conserva el orden de reconocimiento aunque no coincida con el temporal.</p>')
    if not bloques:
        partes.append('<p>No hay intervenciones transcritas.</p>')
    for b in bloques:
        hablante = b.hablante or 'Hablante no identificado'
        if b.nombre:
            hablante = f'{b.nombre} ({hablante})'
        marcas = []
        if b.overlap:
            marcas.append('solapamiento en parte de la intervención' if b.solapamiento_parcial else 'solapamiento')
        if b.ambiguous:
            marcas.append('atribución ambigua')
        detalle = ('Sin ubicación temporal verificable' if b.inicio is None else
                   f'{marca_tiempo(b.inicio)} – {marca_tiempo(b.fin)}')
        if b.timing == 'segment':
            marcas.append('resolución temporal por segmento')
        if b.detectados is not None and (b.ambiguous or b.overlap or len(b.detectados) != 1):
            marcas.append('hablantes detectados: ' + (', '.join(b.detectados) or 'ninguno'))
        if marcas:
            detalle += ' · ' + ' · '.join(marcas)
        partes.append(f'<p><b>{_literal(hablante)}</b><br>{_literal(detalle)}</p>')
        partes.append(f'<p>{_literal(_unir_textos(b.textos))}</p><hr>')
    return '\n'.join(partes)


# Invertir exclusivamente el escape que aplica src.minutas.formato._texto.
_ESCAPE = re.compile(r'\\([\\`*_{}\[\]<>])')
_RELOJ = r'\d{2,}:\d{2}(?::\d{2})?(?:\.\d{3})?'
_ITEM = re.compile(rf'^- \[({_RELOJ})(?:–{_RELOJ}, aprox\.)?\] ')


def minuta_html(contenido: str) -> str:
    """Renderiza el subconjunto de Markdown canónico: título, secciones y listas.

    No se interpreta HTML, enlaces, imágenes ni Markdown arbitrario del modelo.
    Los textos que no corresponden a la estructura conocida se muestran literalmente.
    """
    titulos = set(TITULOS_SECCIONES.values())
    partes = []
    seccion = None
    lista = False
    espera_resumen = False
    for i, linea in enumerate(contenido.splitlines()):
        if not linea.strip():
            continue
        if i == 0 and linea == '# Minuta de reunión':
            partes.append('<h1>Minuta de reunión</h1>')
            continue
        if not espera_resumen and linea.startswith('## ') and linea[3:] in titulos:
            if lista:
                partes.append('</ul>')
                lista = False
            seccion = linea[3:]
            espera_resumen = seccion == TITULOS_SECCIONES['resumen']
            partes.append(f'<h2>{_literal(seccion)}</h2>')
            continue
        if seccion in titulos - {TITULOS_SECCIONES['resumen']} and _ITEM.match(linea):
            if not lista:
                partes.append('<ul>')
                lista = True
            partes.append(f'<li>{_literal(_ESCAPE.sub(r"\1", linea[2:]))}</li>')
        else:
            if lista:
                partes.append('</ul>')
                lista = False
            partes.append(f'<p>{_literal(_ESCAPE.sub(r"\1", linea))}</p>')
            espera_resumen = False
    if lista:
        partes.append('</ul>')
    return '\n'.join(partes)
