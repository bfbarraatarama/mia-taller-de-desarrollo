"""Tipos para observar y repetir bloques de extracción en una evaluación."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .contratos import Intervencion
from .entrada import representar_intervenciones


@dataclass(frozen=True)
class Ocurrencia:
    id_intervencion: str
    inicio_texto: int
    fin_texto: int


@dataclass(frozen=True)
class Bloque:
    bloque_id: str
    ocurrencias: tuple[Ocurrencia, ...]
    padre_id: str | None = None
    lado: str | None = None


def partir(bloques: tuple[Bloque, ...]) -> tuple[Bloque, ...]:
    if not bloques or len({b.bloque_id for b in bloques}) != len(bloques):
        raise ValueError("La traza base no contiene bloques únicos.")
    resultado = []
    for bloque in bloques:
        ocurrencias = bloque.ocurrencias
        longitudes = [o.fin_texto - o.inicio_texto for o in ocurrencias]
        if not longitudes or any(n <= 0 for n in longitudes):
            raise ValueError(f"Bloque inválido: {bloque.bloque_id}.")
        total = sum(longitudes)
        candidatos = []
        izquierda = 0
        for i in range(1, len(ocurrencias)):
            izquierda += longitudes[i - 1]
            if (ocurrencias[i - 1].id_intervencion != ocurrencias[i].id_intervencion
                    and izquierda * 5 >= total * 2 and izquierda * 5 <= total * 3):
                candidatos.append((abs(2 * izquierda - total), i))
        if not candidatos:
            raise ValueError(f"No existe corte equilibrado para {bloque.bloque_id}.")
        _, corte = min(candidatos)
        for lado, parte in (("izquierda", ocurrencias[:corte]), ("derecha", ocurrencias[corte:])):
            resultado.append(Bloque(f"{bloque.bloque_id}-{lado}", parte, bloque.bloque_id, lado))
    return tuple(resultado)


@dataclass
class ExperimentoMinutas:
    """Instrumentación optativa; el plan se valida contra la traza base."""

    sha256_entrada: str
    sha256_configuracion: str
    baseline: tuple[Bloque, ...] | None = None
    plan: tuple[Bloque, ...] | None = None
    bloques: list[Bloque] = field(default_factory=list)
    _rangos: dict[int, Ocurrencia] = field(default_factory=dict, init=False, repr=False)

    def preparar(self, intervenciones: list[Intervencion], sha256_entrada: str, sha256_configuracion: str,
                 cabe: Callable[[str], bool]) -> list[list[Intervencion]] | None:
        if (self.sha256_entrada != sha256_entrada or self.sha256_configuracion != sha256_configuracion
                or self.bloques):
            raise ValueError("La traza no coincide con la entrada o configuración, o ya fue utilizada.")
        if self.plan is None:
            if self.baseline is not None:
                raise ValueError("No se admite un baseline sin plan forzado.")
            self._rangos = {id(i): Ocurrencia(i.id, 0, len(i.texto)) for i in intervenciones}
            return None

        if not self.baseline or len(self.plan) != 2 * len(self.baseline):
            raise ValueError("El plan debe contener dos hijos por bloque base.")
        esperados = partir(self.baseline)
        originales = {i.id: i for i in intervenciones}
        grupos = []
        for hijo, esperado in zip(self.plan, esperados, strict=True):
            if (hijo.padre_id, hijo.lado, hijo.ocurrencias) != (
                    esperado.padre_id, esperado.lado, esperado.ocurrencias):
                raise ValueError("El plan no preserva el corte equilibrado del bloque base.")
            grupo = []
            for o in hijo.ocurrencias:
                original = originales.get(o.id_intervencion)
                if (original is None or type(o.inicio_texto) is not int or type(o.fin_texto) is not int
                        or not 0 <= o.inicio_texto < o.fin_texto <= len(original.texto)):
                    raise ValueError("La ocurrencia no coincide con la transcripción.")
                fragmento = original.model_copy(update={"texto": original.texto[o.inicio_texto:o.fin_texto]})
                self._rangos[id(fragmento)] = o
                grupo.append(fragmento)
            if not cabe(representar_intervenciones(grupo)):
                raise ValueError("Un bloque forzado excede el presupuesto de extracción.")
            grupos.append(grupo)
        return grupos

    def registrar_fragmento(self, original: Intervencion, fragmento: Intervencion, inicio: int) -> None:
        anterior = self._rangos[id(original)]
        comienzo = anterior.inicio_texto + inicio
        self._rangos[id(fragmento)] = Ocurrencia(original.id, comienzo, comienzo + len(fragmento.texto))

    def registrar_bloque(self, grupo: list[Intervencion], padre: Bloque | None) -> None:
        self.bloques.append(Bloque(
            f"B{len(self.bloques) + 1:06d}", tuple(self._rangos[id(i)] for i in grupo),
            padre.bloque_id if padre else None, padre.lado if padre else None))
