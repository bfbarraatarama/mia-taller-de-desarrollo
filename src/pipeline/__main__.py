"""Puerta de terminal mínima y protocolo JSONL del trabajador GUI; no redefine la API."""
from __future__ import annotations

import argparse
import json
import signal
import sys
from pathlib import Path

from ..asociacion.etiquetado import Decision, Etiquetado
from ..minutas.contratos import SECCIONES_MINUTA
from ..minutas.generacion import ConfiguracionMinutas
from ..minutas.modelos import MODELO_PREDETERMINADO, listar_modelos
from ..rutas import DIRECTORIO_RESULTADOS_PREDETERMINADO
from . import SolicitudReunion, continuar_reunion, preparar_reunion, procesar_reunion, consultar_reunion
from .ejecucion import Cancelado


def _emisor(ev: dict) -> None:
    print(json.dumps(ev, ensure_ascii=False), flush=True)


def _terminar(_senal, _frame):
    raise Cancelado('Procesamiento interrumpido por el usuario.')


def _configuracion(datos: dict) -> ConfiguracionMinutas:
    datos = dict(datos)
    if 'secciones' in datos:
        datos['secciones'] = tuple(datos['secciones'])
    return ConfiguracionMinutas(**datos)


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
    inicio.add_argument('--modelo', choices=[m.clave for m in listar_modelos()], default=MODELO_PREDETERMINADO)
    inicio.add_argument('--secciones', default=','.join(SECCIONES_MINUTA))
    inicio.add_argument('--permitir-remoto', action='store_true')
    inicio.add_argument('--esperar-identificacion', action='store_true')
    continuar = sub.add_parser('continuar', help='Continuar desde fichas ya preparadas')
    continuar.add_argument('--reunion', type=Path, required=True)
    continuar.add_argument('--decision-json', help='JSON de Decision ("-" para leer stdin)')
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
            decision = Decision('escribir')
            if a.decision_json:
                contenido = sys.stdin.read() if a.decision_json == '-' else Path(a.decision_json).read_text()
                decision = _decision(json.loads(contenido))
            continuar_reunion(a.reunion, decision, emisor=_emisor)
        else:
            cfg = ConfiguracionMinutas(modelo=a.modelo, permitir_remoto=a.permitir_remoto,
                                      secciones=tuple(x.strip() for x in a.secciones.split(',')))
            solicitud = SolicitudReunion(fuentes=tuple(a.fuentes), salida=a.salida,
                modelo_stt=a.modelo_stt, dispositivo_stt=a.dispositivo_stt,
                dispositivo_diarizacion=a.dispositivo_diarizacion, num_speakers=a.num_speakers,
                minutas=cfg, identificacion='pausa' if a.esperar_identificacion else 'omitir')
            procesar_reunion(solicitud, emisor=_emisor)
    except Cancelado:
        return 130
    except (ValueError, OSError, RuntimeError, PermissionError, KeyError, TypeError) as error:
        print(f'{type(error).__name__}: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
