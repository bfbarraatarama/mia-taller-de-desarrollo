"""Grupo 3: empates (D2), huecos (D3), marcas overlap y ambiguous (D5), entradas sin habla y cantidad de hablantes.

Los tests de D2 y D3 eligen etiquetas y largos de turno de modo que cada regla dé un resultado distinto al de
las reglas siguientes: si el código usara la regla equivocada, el test falla.
"""

from __future__ import annotations

import pytest

from asociacion import asociar
from asociar import main
from conftest import crear_reunion, leer, segmento
from contrato import validar_transcripcion
from errores import AsociacionError
from salida import escribir


def resumen(carpeta):
    return [(i.speaker, i.text) for i in asociar(carpeta).intervenciones]


# ---------- 3.1 D2: empates ----------


def test_empate_por_continuidad(tmp_path):
    """«mando» cae entera en los dos turnos; la palabra anterior es de SPEAKER_01.
    El turno más largo (SPEAKER_00) y la etiqueta menor (SPEAKER_00) darían otro resultado."""
    carpeta = crear_reunion(tmp_path, 7.0, [(0.0, 2.6, "SPEAKER_01"), (2.0, 6.0, "SPEAKER_00")],
                            [segmento(("Yo", 1.0, 1.5), ("mando", 2.1, 2.5), ("eso.", 3.0, 3.5))])
    a = asociar(carpeta)
    assert [(i.speaker, i.text) for i in a.intervenciones] == [("SPEAKER_01", "Yo mando"), ("SPEAKER_00", "eso.")]
    assert a.conteos["palabras_por_empate"] == 1


def test_empate_por_continuidad_entre_segmentos(tmp_path):
    """La palabra anterior se busca en todo asr.json, también en el segmento de Whisper anterior."""
    carpeta = crear_reunion(tmp_path, 7.0, [(0.0, 2.6, "SPEAKER_01"), (2.0, 6.0, "SPEAKER_00")],
                            [segmento(("Yo.", 1.0, 1.5)), segmento(("Mando.", 2.1, 2.5))])
    assert resumen(carpeta) == [("SPEAKER_01", "Yo."), ("SPEAKER_01", "Mando.")]


def test_empate_sin_palabra_anterior_gana_el_turno_mas_largo(tmp_path):
    """Primera palabra: no hay continuidad; gana SPEAKER_01 (turno de 6 s) aunque su etiqueta sea mayor."""
    carpeta = crear_reunion(tmp_path, 7.0, [(0.0, 6.0, "SPEAKER_01"), (2.0, 3.0, "SPEAKER_00")],
                            [segmento(("Mando.", 2.1, 2.5))])
    assert resumen(carpeta) == [("SPEAKER_01", "Mando.")]


def test_empate_con_turnos_iguales_gana_la_etiqueta_menor(tmp_path):
    carpeta = crear_reunion(tmp_path, 7.0, [(2.0, 3.0, "SPEAKER_01"), (2.0, 3.0, "SPEAKER_00")],
                            [segmento(("Mando.", 2.1, 2.5))])
    assert resumen(carpeta) == [("SPEAKER_00", "Mando.")]


# ---------- 3.1 D3: palabras en huecos ----------


@pytest.mark.parametrize("ini, fin, esperado", [
    (2.10, 2.40, "SPEAKER_00"),  # a 0,10 s de SPEAKER_00 y a 0,60 s de SPEAKER_01
    (2.25, 2.50, "SPEAKER_00"),  # exactamente 0,25 s: entra
    (2.251, 2.50, None),         # 0,251 s de SPEAKER_00 y 0,50 s de SPEAKER_01: queda sin hablante
    (2.60, 2.76, "SPEAKER_01"),  # a 0,24 s de SPEAKER_01
])
def test_palabra_en_hueco(tmp_path, ini, fin, esperado):
    carpeta = crear_reunion(tmp_path, 6.0, [(0.0, 2.0, "SPEAKER_00"), (3.0, 5.0, "SPEAKER_01")],
                            [segmento(("eh", ini, fin))])
    a = asociar(carpeta)
    assert [i.speaker for i in a.intervenciones] == [esperado]
    assert a.conteos["palabras_por_hueco"] == (esperado is not None)
    assert a.conteos["palabras_sin_hablante"] == (esperado is None)


def test_hueco_a_igual_distancia_sigue_la_continuidad(tmp_path):
    """«y» está a 0,10 s de los dos turnos; la anterior es de SPEAKER_00, aunque SPEAKER_01 tenga el turno más largo."""
    carpeta = crear_reunion(tmp_path, 6.0, [(0.0, 2.0, "SPEAKER_00"), (2.4, 5.0, "SPEAKER_01")],
                            [segmento(("Bien", 1.0, 1.5), ("y", 2.1, 2.3))])
    assert resumen(carpeta) == [("SPEAKER_00", "Bien y")]


# ---------- 3.2 D5: marcas ----------


def marcas(carpeta):
    return [(i.speaker, i.overlap, i.ambiguous) for i in asociar(carpeta).intervenciones]


def test_dos_personas_hablan_a_la_vez(tmp_path):
    carpeta = crear_reunion(tmp_path, 6.0, [(0.0, 5.0, "SPEAKER_00"), (2.0, 3.5, "SPEAKER_01")],
                            [segmento(("a", 0.5, 1.5), ("b", 1.5, 2.5), ("c", 2.5, 3.0), ("d", 3.0, 4.5))])
    [i] = asociar(carpeta).intervenciones
    assert i.overlap is True and i.text == "a b c d"


def test_interrupcion_breve(tmp_path):
    palabras = [(f"p{k}", 0.5 + k, 1.5 + k) for k in range(12)]  # intervención de 0,5 a 12,5 s
    carpeta = crear_reunion(tmp_path, 14.0, [(0.0, 13.0, "SPEAKER_00"), (5.0, 5.3, "SPEAKER_01")],
                            [segmento(*palabras)])
    assert marcas(carpeta) == [("SPEAKER_00", True, False)]


def test_roce_de_bordes(tmp_path):
    carpeta = crear_reunion(tmp_path, 5.0, [(0.0, 3.0, "SPEAKER_00"), (2.45, 4.0, "SPEAKER_01")],
                            [segmento(("hola", 0.5, 2.5))])
    assert marcas(carpeta) == [("SPEAKER_00", False, False)]


def test_segundo_hablante_en_el_30(tmp_path):
    """Intervención de 10,0 s (0,5 a 10,5); SPEAKER_01 cubre 1,5 + 1,5 = 3,0 s. «dos» y «cuatro» empatan (D2)."""
    carpeta = crear_reunion(tmp_path, 12.0,
                            [(0.0, 11.0, "SPEAKER_00"), (2.0, 3.5, "SPEAKER_01"), (6.0, 7.5, "SPEAKER_01")],
                            [segmento(("uno", 0.5, 2.0), ("dos", 2.0, 3.5), ("tres", 3.5, 6.0),
                                      ("cuatro", 6.0, 7.5), ("cinco", 7.5, 10.5))])
    assert marcas(carpeta) == [("SPEAKER_00", True, True)]


def test_texto_sin_respaldo_en_la_diarizacion(tmp_path):
    """Intervención de 2,0 s (1,0 a 3,0); SPEAKER_00 cubre 0,8 s. «dos» entra por D3 (a 0,2 s del turno)."""
    carpeta = crear_reunion(tmp_path, 5.0, [(0.0, 1.8, "SPEAKER_00")],
                            [segmento(("uno", 1.0, 2.0), ("dos", 2.0, 3.0))])
    assert marcas(carpeta) == [("SPEAKER_00", False, True)]


def test_valores_limite(tmp_path):
    """Intervención de 1,000 s: superposición de 0,200 s, SPEAKER_01 cubre 0,299 s (29,9 %), SPEAKER_00 0,500 s."""
    carpeta = crear_reunion(tmp_path, 3.0, [(1.0, 1.5, "SPEAKER_00"), (1.3, 1.599, "SPEAKER_01")],
                            [segmento(("palabra", 1.0, 2.0))])
    assert marcas(carpeta) == [("SPEAKER_00", True, False)]


def test_sin_hablante(tmp_path):
    carpeta = crear_reunion(tmp_path, 6.0, [(0.0, 1.0, "SPEAKER_00")], [segmento(("lejos", 3.0, 3.5))])
    assert marcas(carpeta) == [(None, False, True)]


def test_umbrales_en_los_metadatos(reunion):
    escribir(asociar(reunion))
    meta = leer(reunion / "transcription.meta.json")
    assert meta["umbrales"] == {"hueco_max_s": 0.25, "overlap_min_s": 0.2,
                                "segundo_hablante_min": 0.3, "propio_min": 0.5}
    assert {"palabras_por_empate", "palabras_por_hueco", "intervenciones_overlap",
            "intervenciones_ambiguous"} <= set(meta["conteos"])


# ---------- 3.3 entradas sin habla ----------


def test_sin_habla_transcrita(tmp_path, capsys):
    carpeta = crear_reunion(tmp_path, 5.0, [(0.0, 2.0, "SPEAKER_00")], [])
    with pytest.raises(AsociacionError) as e:
        asociar(carpeta)
    assert e.value.paso == "asr" and "sin habla transcrita" in e.value.mensaje
    assert main([str(carpeta)]) == 1
    assert "sin habla transcrita" in capsys.readouterr().err
    assert not (carpeta / "transcription.json").exists()
    assert "sin habla transcrita" in leer(carpeta / "transcription.error.json")["mensaje"]


def test_sin_habla_tras_el_recorte(tmp_path):
    """El único segmento empieza después del audio (dentro del margen de 1,0 s): se descarta y no queda habla."""
    carpeta = crear_reunion(tmp_path, 5.0, [(0.0, 2.0, "SPEAKER_00")], [segmento(("eco", 5.2, 5.6))])
    with pytest.raises(AsociacionError, match="sin habla transcrita"):
        asociar(carpeta)


def test_diarizacion_vacia_con_texto(tmp_path):
    carpeta = crear_reunion(tmp_path, 5.0, [], [segmento(("Hola", 0.5, 1.0), ("todos.", 1.0, 1.6)),
                                                segmento(("Arrancamos.", 2.0, 3.0))])
    a = asociar(carpeta)
    assert a.etiquetas == ()  # sin etiquetas, el etiquetado no tiene fichas que mostrar (grupo 5)
    assert [(i.speaker, i.name, i.ambiguous) for i in a.intervenciones] == [(None, None, True)] * 2
    assert " ".join(i.text for i in a.intervenciones) == "Hola todos. Arrancamos."
    escribir(a)
    assert validar_transcripcion(leer(carpeta / "transcription.json"), a.duracion, a.etiquetas) == []


# ---------- 3.4 cantidad de hablantes ----------


def test_seis_o_mas_hablantes(tmp_path):
    etiquetas = [f"SPEAKER_{k:02d}" for k in range(8)]
    turnos = [(1.0 + 2 * k, 2.5 + 2 * k, e) for k, e in enumerate(etiquetas)]
    segmentos = [segmento((f"Habla{k}.", 1.2 + 2 * k, 2.2 + 2 * k)) for k in range(8)]
    carpeta = crear_reunion(tmp_path, 20.0, turnos, segmentos)
    a = asociar(carpeta)
    assert a.etiquetas == tuple(etiquetas)  # una ficha por etiqueta en el etiquetado (grupo 5)
    escribir(a)
    datos = leer(carpeta / "transcription.json")
    assert [s["speaker"] for s in datos["segments"]] == etiquetas
