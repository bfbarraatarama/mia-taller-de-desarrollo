"""Tareas 3.1 a 3.3: selección determinista (requisito «Selección determinista»)."""

from __future__ import annotations

import random

import pytest

from evaluacion.modular.config import cargar_config
from evaluacion.modular.seleccion import (Clip, Reunion, SeleccionImposible, inventario_ami, inventario_common_voice,
                                          inventario_openslr, seleccionar_clips, seleccionar_reuniones,
                                          seleccionar_sesiones, sesiones_figshare)

SEMILLA = 20261010


def openslr() -> list[Clip]:
    clips = []
    for genero, prefijo, n in (("female", "arf", 4), ("male", "arm", 2)):
        for h in range(n):
            for c in range(3):
                clips.append(Clip("openslr", f"{prefijo}_{h:05d}_{c:011d}", f"{prefijo}_{h:05d}", genero,
                                  f"frase {h} {c}", f"{prefijo}_{h:05d}_{c:011d}.wav"))
    return clips


def common_voice() -> list[Clip]:
    clips = []
    for i, genero in enumerate(["male_masculine"] * 6 + ["female_feminine"] * 2 + [""] * 3):
        for c in range(2):
            clips.append(Clip("common_voice", f"common_voice_es_{i}{c}.mp3", f"cliente{i}", genero,
                              f"oración {i} {c}", f"es-Rioplatense/clips/common_voice_es_{i}{c}.mp3"))
    return clips


def test_clips_de_personas_distintas():
    elegidos = seleccionar_clips(openslr(), common_voice(), SEMILLA)
    assert [c.fuente for c in elegidos].count("openslr") == 3
    assert [c.fuente for c in elegidos].count("common_voice") == 2
    assert len({c.hablante for c in elegidos}) == 5
    generos = {c.genero.split("_")[0] for c in elegidos}
    assert generos == {"female", "male"}
    cv = [c for c in elegidos if c.fuente == "common_voice"]
    assert {c.genero for c in cv} == {"female_feminine", "male_masculine"}


def test_misma_semilla_misma_seleccion():
    a, b = openslr(), common_voice()
    primera = seleccionar_clips(a, b, SEMILLA)
    random.Random(1).shuffle(a)
    random.Random(2).shuffle(b)
    assert seleccionar_clips(a, b, SEMILLA) == primera  # el orden de lectura no cambia la selección
    otras = {tuple(seleccionar_clips(openslr(), common_voice(), s)) for s in range(10)}
    assert len(otras) > 1  # la semilla sí la cambia


def test_sesiones_excluidas():
    sesiones = ["S21", "S22", "S23", "S24", "S25", "S26", "S27", "S29", "S30"]
    elegidas, excluidas = seleccionar_sesiones(sesiones, SEMILLA)
    assert len(elegidas) == 3
    assert set(elegidas) <= {"S21", "S22", "S23", "S24", "S25"}
    assert set(excluidas) == {"S26", "S27", "S28", "S29", "S30"}
    assert "desarrollo" in excluidas["S26"]
    assert "incompleta" in excluidas["S27"]
    assert "no está" in excluidas["S28"]
    assert seleccionar_sesiones(list(reversed(sesiones)), SEMILLA)[0] == elegidas


def reuniones() -> list[Reunion]:
    datos = []
    for i, (serie, minutos, acciones) in enumerate([
            ("ES2002", 34, 2), ("ES2002", 33, 1), ("ES2003", 35, 3), ("ES2004", 12, 1), ("ES2005", 36, 0),
            ("IS1000", 31, 1), ("IS1001", 55, 2), ("TS3003", 30, 1), ("TS3004", 38, 4), ("TS3005", 37, 1)]):
        datos.append(Reunion(f"{serie}{'abcd'[i % 4]}", serie, minutos * 60.0, acciones))
    return datos


def test_reuniones_de_series_distintas_con_accion():
    elegidas = seleccionar_reuniones(reuniones(), SEMILLA)
    assert len(elegidas) == 3
    assert len({r.serie for r in elegidas}) == 3
    assert all(r.acciones >= 1 for r in elegidas)
    # ni la de 12 minutos ni la de 55 (fuera de los percentiles 25 a 75), ni la que no tiene acciones
    assert not {r.serie for r in elegidas} & {"ES2004", "IS1001", "ES2005"}


def test_reuniones_insuficientes():
    with pytest.raises(SeleccionImposible):
        seleccionar_reuniones([r for r in reuniones() if r.serie in ("ES2002", "ES2003")], SEMILLA)


# ---------- inventarios sobre los originales reales (se saltean si no están en la caché) ----------

def _cache():
    config = cargar_config()
    if not all((config.cache / o.clave).is_file() for o in config.originales.values()):
        pytest.skip("faltan originales en hito-2/.cache (ver `python -m evaluacion.modular preparar`)")
    return config.cache


def test_inventarios_reales():
    cache = _cache()
    slr = inventario_openslr(cache)
    assert len({c.hablante for c in slr}) == 44
    assert {c.genero for c in slr} == {"female", "male"}
    cv = inventario_common_voice(cache)
    assert len(cv) == 224 and all(c.ruta.startswith("es-Rioplatense/clips/") for c in cv)
    assert sesiones_figshare(cache) == ["S21", "S22", "S23", "S24", "S25", "S26", "S27", "S29", "S30"]
    ami = inventario_ami()
    assert len(ami) == 142 and sum(r.acciones >= 1 for r in ami) > 3
