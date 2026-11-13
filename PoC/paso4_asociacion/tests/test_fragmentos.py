"""Grupo 4: fragmento por hablante (D6). Tramos solos, candidatos, semilla, recorte, respaldos y texto."""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

import pytest

from asociacion import Turnos, asociar
from conftest import MODULO, crear_reunion, leer, segmento
from fragmentos import fragmentos, tramos_solos
from salida import escribir


def reunion_con(tmp_path, duracion, turnos, segmentos=None):
    """Reunión con los turnos dados; asr.json con una palabra si no se indica otra cosa (hace falta habla)."""
    return crear_reunion(tmp_path / "reunion", duracion, turnos, segmentos or [segmento(("hola", 0.0, 0.3))])


def tiempos(fragmento):
    return fragmento.start, fragmento.end


def separados_por(etiqueta, otra, largos, pausa=1.0):
    """Turnos de `etiqueta` con los largos dados, separados por turnos de `otra` de `pausa` s que los tocan."""
    turnos, t = [], 0.0
    for largo in largos:
        turnos.append((t, t + largo, etiqueta))
        turnos.append((t + largo, t + largo + pausa, otra))
        t += largo + pausa
    return turnos, t


# ---------- 4.1 tramos solos, candidatos, semilla y permutación ----------


def test_tramos_solos():
    """Lo que se superpone con otra voz no cuenta; los turnos de la misma etiqueta que se tocan se unen."""
    t = Turnos([{"start": 0.0, "end": 2.0, "speaker": "A"}, {"start": 1.5, "end": 3.0, "speaker": "B"},
                {"start": 2.0, "end": 4.0, "speaker": "A"}, {"start": 5.0, "end": 6.0, "speaker": "C"},
                {"start": 5.5, "end": 5.8, "speaker": "D"}])
    assert tramos_solos(t) == {"A": [(0, 1500), (3000, 4000)], "B": [], "C": [(5000, 5500), (5800, 6000)],
                               "D": []}


def test_candidatos_de_al_menos_la_media(tmp_path):
    """Tramos solos de 2, 4, 6, 8 y 30 s (media 10 s): solo el de 30 s (24 a 54 s), recortado a 31,5 a 46,5 s."""
    turnos, fin = separados_por("SPEAKER_00", "SPEAKER_01", [2, 4, 6, 8, 30])
    f = fragmentos(asociar(reunion_con(tmp_path, fin, turnos)))["SPEAKER_00"]
    assert [tiempos(x) for x in f.secuencia] == [(31.5, 46.5)]
    assert f.origen == "candidatos" and not f.secuencia[0].superpuesto


def test_minimo_de_5_s(tmp_path):
    """Tramos de 3 y 4 s: la media es 3,5 s, pero el mínimo es 5 s, así que no hay candidatos (respaldo 1)."""
    turnos, fin = separados_por("SPEAKER_00", "SPEAKER_01", [3, 4])
    f = fragmentos(asociar(reunion_con(tmp_path, fin, turnos)))["SPEAKER_00"]
    assert f.origen == "tramo_solo_mas_largo" and [tiempos(x) for x in f.secuencia] == [(4.0, 8.0)]


def test_misma_entrada_mismo_fragmento(tmp_path):
    turnos, fin = separados_por("SPEAKER_00", "SPEAKER_01", [6, 7, 8, 9, 10, 6, 7, 8])
    carpeta = reunion_con(tmp_path, fin, turnos)
    primera = fragmentos(asociar(carpeta))["SPEAKER_00"].secuencia
    segunda = fragmentos(asociar(carpeta))["SPEAKER_00"].secuencia
    assert primera == segunda and len(primera) == 4  # media 7,625 s: candidatos 8, 9, 10 y 8 s


def test_misma_secuencia_en_otro_proceso(tmp_path):
    """La permutación no depende de la semilla de hash de Python (PYTHONHASHSEED) ni del proceso."""
    turnos, fin = separados_por("SPEAKER_00", "SPEAKER_01", [6, 7, 8, 9, 10, 6, 7, 8])
    carpeta = reunion_con(tmp_path, fin, turnos)
    codigo = ("import sys; sys.path.insert(0, sys.argv[1]); from asociacion import asociar; "
              "from fragmentos import fragmentos; "
              "print([(x.start, x.end) for x in fragmentos(asociar(sys.argv[2]))['SPEAKER_00'].secuencia])")
    salidas = {subprocess.run([sys.executable, "-c", codigo, str(MODULO), str(carpeta)], capture_output=True,
                              text=True, check=True, env={**os.environ, "PYTHONHASHSEED": h}).stdout
               for h in ("1", "2")}
    assert len(salidas) == 1


def test_otro_fragmento_sin_repetir(tmp_path):
    """3 candidatos de 6 s: los 3 aparecen una vez cada uno y después vuelve a empezar."""
    turnos, fin = separados_por("SPEAKER_00", "SPEAKER_01", [6, 6, 6])
    f = fragmentos(asociar(reunion_con(tmp_path, fin, turnos)))["SPEAKER_00"]
    vistos = [tiempos(f.en(i)) for i in range(3)]
    assert sorted(vistos) == [(0.0, 6.0), (7.0, 13.0), (14.0, 20.0)]
    assert tiempos(f.en(3)) == vistos[0]


def test_semilla_en_los_metadatos(tmp_path):
    turnos, fin = separados_por("SPEAKER_00", "SPEAKER_01", [6, 6])
    carpeta = reunion_con(tmp_path, fin, turnos)
    escribir(asociar(carpeta))
    meta = leer(carpeta / "transcription.meta.json")
    assert meta["semilla_fragmentos"] == int(meta["sha256"]["diarization.json"][:16], 16)


# ---------- 4.2 recorte central y respaldos ----------


def test_tramo_de_mas_de_15_s(tmp_path):
    carpeta = reunion_con(tmp_path, 80.0, [(40.0, 70.0, "SPEAKER_00")])
    f = fragmentos(asociar(carpeta))["SPEAKER_00"]
    assert [tiempos(x) for x in f.secuencia] == [(47.5, 62.5)]


def test_sin_tramo_de_5_s(tmp_path):
    turnos, fin = separados_por("SPEAKER_01", "SPEAKER_00", [1.2, 2.8, 3.5])
    f = fragmentos(asociar(reunion_con(tmp_path, fin, turnos)))["SPEAKER_01"]
    assert f.origen == "tramo_solo_mas_largo"
    assert [tiempos(x) for x in f.secuencia] == [(6.0, 9.5)] and not f.secuencia[0].superpuesto


def test_nunca_habla_solo(tmp_path):
    carpeta = reunion_con(tmp_path, 25.0, [(0.0, 20.0, "SPEAKER_00"), (2.0, 4.0, "SPEAKER_01"),
                                           (6.0, 9.0, "SPEAKER_01")])
    f = fragmentos(asociar(carpeta))["SPEAKER_01"]
    assert f.origen == "turno_mas_largo"
    assert [tiempos(x) for x in f.secuencia] == [(6.0, 9.0)] and f.secuencia[0].superpuesto


def test_turno_de_respaldo_de_mas_de_15_s(tmp_path):
    carpeta = reunion_con(tmp_path, 60.0, [(0.0, 50.0, "SPEAKER_00"), (10.0, 40.0, "SPEAKER_01")])
    f = fragmentos(asociar(carpeta))["SPEAKER_01"]
    assert [tiempos(x) for x in f.secuencia] == [(17.5, 32.5)] and f.secuencia[0].superpuesto


# ---------- 4.3 texto del fragmento ----------


def test_texto_por_punto_medio(tmp_path):
    """Fragmento de 47,5 a 62,5 s. Entra la palabra con punto medio en 47,5; quedan afuera la de 47,4 y la de
    62,5 aunque se superpongan con el fragmento."""
    segmentos = [segmento(("antes", 47.0, 47.8), ("borde", 47.3, 47.7), ("dentro", 50.0, 51.0)),
                 segmento(("despues", 62.3, 62.7))]
    carpeta = reunion_con(tmp_path, 80.0, [(40.0, 70.0, "SPEAKER_00")], segmentos)
    assert fragmentos(asociar(carpeta))["SPEAKER_00"].secuencia[0].texto == "borde dentro"


def test_segmento_sin_palabras_en_el_fragmento(tmp_path):
    carpeta = reunion_con(tmp_path, 10.0, [(0.0, 9.0, "SPEAKER_00")], [])
    (carpeta / "asr.json").write_text(json.dumps({"language": "es", "segments": [
        {"start": 1.0, "end": 2.0, "text": " mmm ", "words": []}]}), encoding="utf-8")
    assert fragmentos(asociar(carpeta))["SPEAKER_00"].secuencia[0].texto == "mmm"


def test_diarizacion_vacia_sin_fragmentos(tmp_path):
    assert fragmentos(asociar(reunion_con(tmp_path, 5.0, []))) == {}


# ---------- datos de la Etapa 2 ----------


def _hipotesis_s26() -> Path:
    raiz = Path(os.environ.get("ETAPA2_DIR", MODULO.parent / "paso2_diarizacion"))
    return raiz / "evaluacion/resultados/hipotesis_S26"


@pytest.mark.skipif(not _hipotesis_s26().is_dir(), reason="faltan las hipótesis de S26 de la Etapa 2 (PR #8)")
def test_tramos_solos_coinciden_con_la_medicion_de_s26():
    """design.md, D6: 49 hablantes, 16 sin tramo solo, media por hablante con mediana 1,99 s (0,92 a 4,30 s)."""
    medias, sin_tramo, total = [], 0, 0
    for archivo in sorted(_hipotesis_s26().glob("*.json")):
        solos = tramos_solos(Turnos(json.loads(archivo.read_text(encoding="utf-8"))["segments"]))
        for tramos in solos.values():
            total += 1
            if tramos:
                medias.append(statistics.mean(f - i for i, f in tramos) / 1000)
            else:
                sin_tramo += 1
    assert (total, sin_tramo) == (49, 16)
    assert (round(statistics.median(medias), 2), round(min(medias), 2), round(max(medias), 2)) == (1.99, 0.92, 4.30)
