"""Puerta de terminal mínima y protocolo JSONL del trabajador GUI; no redefine la API."""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import signal
import sys
import wave
from pathlib import Path

from ..asociacion.etiquetado import Decision, Etiquetado
from ..asociacion.errores import AsociacionError
from ..minutas.generacion import ConfiguracionMinutas
from ..minutas.modelos import listar_modelos
from ..rutas import DIRECTORIO_RESULTADOS_PREDETERMINADO
from . import SolicitudReunion, continuar_reunion, preparar_reunion, procesar_reunion, consultar_reunion
from .ejecucion import Cancelado


def _emisor(ev: dict) -> None:
    print(json.dumps(ev, ensure_ascii=False), flush=True)


def _terminar(_senal, _frame):
    raise Cancelado('Procesamiento interrumpido por el usuario.')


def _opciones_minutas(p):
    p.add_argument('--modelo', choices=[m.clave for m in listar_modelos()])
    p.add_argument('--secciones')
    p.add_argument('--permitir-remoto', action='store_true')
    p.add_argument('--destino-autorizado', help=argparse.SUPPRESS)
    for clave, tipo in (('temperatura', float), ('max_tokens_salida', int),
                       ('reintentos_formato', int), ('num_ctx', int), ('max_caracteres_bloque', int)):
        p.add_argument('--' + clave.replace('_', '-'), type=tipo)


def _cambios_minutas(a) -> dict:
    cambios = {k: getattr(a, k) for k in ('modelo', 'temperatura', 'max_tokens_salida',
               'reintentos_formato', 'num_ctx', 'max_caracteres_bloque') if getattr(a, k) is not None}
    if a.secciones is not None:
        cambios['secciones'] = tuple(x.strip() for x in a.secciones.split(','))
    return dict(cambios, permitir_remoto=a.permitir_remoto, destino_autorizado=a.destino_autorizado)


def _decision(datos: dict) -> Decision:
    if datos.get('accion') != 'escribir':
        return Decision(datos.get('accion', 'cancelar'))
    etiquetado = datos.get('etiquetado')
    if etiquetado is None:
        return Decision('escribir')
    clips = {k: tuple(v) for k, v in etiquetado.get('clips', {}).items()}
    return Decision('escribir', Etiquetado(nombres=etiquetado['nombres'], clips=clips))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='PoC MIA104: ejecutar o continuar una reunión.')
    sub = p.add_subparsers(dest='accion', required=True)
    inicio = sub.add_parser('ejecutar', help='Procesar un audio o varios, en orden')
    inicio.add_argument('fuentes', nargs='+', type=Path)
    inicio.add_argument('--salida', type=Path, default=DIRECTORIO_RESULTADOS_PREDETERMINADO)
    inicio.add_argument('--modelo-stt', default='medium')
    inicio.add_argument('--dispositivo-stt', choices=['cpu', 'cuda'])
    inicio.add_argument('--dispositivo-diarizacion', choices=['auto', 'cpu', 'cuda'], default='auto')
    inicio.add_argument('--num-speakers', type=int)
    _opciones_minutas(inicio)
    inicio.add_argument('--esperar-identificacion', action='store_true')
    continuar = sub.add_parser('continuar', help='Continuar desde fichas ya preparadas')
    continuar.add_argument('--reunion', type=Path, required=True)
    continuar.add_argument('--decision-json', help='JSON de Decision ("-" para leer stdin)')
    continuar.add_argument('--huella-fichas', help=argparse.SUPPRESS)
    _opciones_minutas(continuar)
    consultar = sub.add_parser('estado')
    consultar.add_argument('--reunion', type=Path, required=True)
    a = p.parse_args(argv)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, _terminar)
    try:
        if a.accion == 'estado':
            print(json.dumps(consultar_reunion(a.reunion), ensure_ascii=False, indent=2))
            return 0
        if a.accion == 'continuar':
            decision = None
            if a.decision_json:
                contenido = sys.stdin.read() if a.decision_json == '-' else Path(a.decision_json).read_text()
                decision = _decision(json.loads(contenido))
            continuar_reunion(a.reunion, decision, cambios_minutas=_cambios_minutas(a),
                              emisor=_emisor, huella_fichas=a.huella_fichas)
        else:
            cfg = replace(ConfiguracionMinutas(), **_cambios_minutas(a))
            solicitud = SolicitudReunion(fuentes=tuple(a.fuentes), salida=a.salida,
                modelo_stt=a.modelo_stt, dispositivo_stt=a.dispositivo_stt,
                dispositivo_diarizacion=a.dispositivo_diarizacion, num_speakers=a.num_speakers,
                minutas=cfg, identificacion='pausa' if a.esperar_identificacion else 'omitir')
            procesar_reunion(solicitud, emisor=_emisor)
    except Cancelado:
        return 130
    except (ValueError, OSError, RuntimeError, KeyError, TypeError, AsociacionError, wave.Error, EOFError) as error:
        print(f'{type(error).__name__}: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
