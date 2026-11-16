"""Medición de la ejecución vigente, separada de los checkpoints reutilizables."""
from __future__ import annotations

import math
from time import monotonic
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from copy import deepcopy

from .estado import DEPENDENCIAS

# El reloj monotónico de Python es común a los procesos del mismo arranque.
# Sin prueba de un arranque común solo se compara dentro de este intérprete.
try:
    DOMINIO_RELOJ = Path('/proc/sys/kernel/random/boot_id').read_text().strip() or str(uuid4())
except OSError:
    DOMINIO_RELOJ = str(uuid4())


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


class Medicion:
    def __init__(self, estado: dict, *, continuar: bool = False):
        self.inicio = monotonic()
        anterior = estado.get('tiempos')
        pausa = estado.get('estado') == 'esperando_identificacion' and continuar
        referencia = anterior.get('pausa') if isinstance(anterior, dict) else None
        latencia = anterior.get('latencia_activa_s') if isinstance(anterior, dict) else None
        recuperable = (pausa and isinstance(referencia, dict)
                       and isinstance(referencia.get('monotono_s'), (int, float))
                       and isinstance(latencia, (int, float)) and math.isfinite(latencia) and latencia >= 0
                       and isinstance(anterior.get('etapas'), dict)
                       and set(anterior['etapas']) == set(DEPENDENCIAS))
        if recuperable:
            self.datos = deepcopy(anterior)
            self.base = latencia
            self.datos.pop('pausa')
            comparable = referencia.get('dominio') == DOMINIO_RELOJ and self.inicio >= referencia['monotono_s']
            self.datos['espera_identificacion_s'] = (round(self.inicio - referencia['monotono_s'], 3)
                                                     if comparable else None)
            self.datos['identificacion_hasta_utc'] = ahora()
        else:
            self.base = 0.0
            self.datos = {'inicio_utc': ahora(), 'latencia_activa_s': 0.0,
                          'espera_identificacion_s': None if pausa else 0.0,
                          'etapas': {e: {'estado': 'no_ejecutada', 'tiempo_s': 0.0} for e in DEPENDENCIAS}}
            if pausa:  # Una pausa históricamente existente no permite reconstruir su latencia.
                self.datos['latencia_previa_desconocida'] = True
        self.datos['fin_utc'] = None
        self.datos['medicion_cerrada'] = False
        estado['tiempos'] = self.datos

    def etapa(self, nombre: str, estado: str, tiempo: float | None = None) -> None:
        self.datos['etapas'][nombre] = {'estado': estado, 'tiempo_s': tiempo}

    def actualizar(self) -> None:
        tramo = monotonic() - self.inicio
        self.datos['latencia_tramo_s'] = round(tramo, 3)
        self.datos['latencia_activa_s'] = (None if self.datos.get('latencia_previa_desconocida')
                                          else round(self.base + tramo, 3))

    def cerrar(self, *, pausa: bool = False) -> None:
        self.actualizar()
        if pausa:
            self.datos['pausa'] = {'dominio': DOMINIO_RELOJ, 'monotono_s': monotonic()}
            self.datos['identificacion_desde_utc'] = ahora()
            self.datos['espera_identificacion_s'] = None
        else:
            self.datos['fin_utc'] = ahora()
        self.datos['medicion_cerrada'] = not pausa
