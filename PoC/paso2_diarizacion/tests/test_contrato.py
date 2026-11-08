"""Tareas 2.1 y 2.2: validador del contrato y del par."""

import json
import subprocess
import sys

from conftest import MODULO
from contrato import validar_diarizacion, validar_par
from resultados import escribir_par


def _meta(segmentos, run_id="r1"):
    return {"run_id": run_id, "segmentos": len(segmentos), "hablantes": len({s["speaker"] for s in segmentos})}


def test_archivo_valido_con_solapamiento():
    datos = {"segments": [
        {"start": 0.5, "end": 4.2, "speaker": "SPEAKER_00"},
        {"start": 3.9, "end": 8.1, "speaker": "SPEAKER_01"},  # se superpone con el anterior
        {"start": 8.1, "end": 10.0, "speaker": "SPEAKER_00"},
    ]}
    assert validar_diarizacion(datos, 10.0) == []


def test_lista_vacia_es_valida():
    assert validar_diarizacion({"segments": []}, 5.0) == []


def test_tres_violaciones_a_la_vez_con_ubicacion():
    datos = {
        "segments": [
            {"start": 0.0, "end": 12.5, "speaker": "SPEAKER_00"},  # end > duración
            {"start": 1.0, "end": 2.0},                             # falta speaker
        ],
        "version": 2,                                               # campo extra en la raíz
    }
    violaciones = validar_diarizacion(datos, 12.0)
    assert len(violaciones) == 3
    assert any("raíz" in v and "version" in v for v in violaciones)
    assert any(v.startswith("segments[0]") and "supera la duración" in v for v in violaciones)
    assert any(v.startswith("segments[1]") and "falta 'speaker'" in v for v in violaciones)


def test_otras_violaciones():
    casos = [
        ({"segments": [{"start": 2.0, "end": 2.0, "speaker": "A"}]}, "no es menor"),
        ({"segments": [{"start": -0.1, "end": 1.0, "speaker": "A"}]}, "negativo"),
        ({"segments": [{"start": "0", "end": 1.0, "speaker": "A"}]}, "no es un número"),
        ({"segments": [{"start": True, "end": 1.0, "speaker": "A"}]}, "no es un número"),
        ({"segments": [{"start": float("nan"), "end": 1.0, "speaker": "A"}]}, "no es un número"),
        ({"segments": [{"start": 0.0, "end": 1.0, "speaker": " "}]}, "'speaker' vacío"),
        ({"segments": [{"start": 0.0, "end": 1.0, "speaker": "A", "name": "x"}]}, "no permitido 'name'"),
        ({"segments": [{"start": 3.0, "end": 4.0, "speaker": "A"}, {"start": 1.0, "end": 2.0, "speaker": "B"}]},
         "orden"),
        ({"segmentos": []}, "falta 'segments'"),
        ([], "no es un objeto"),
    ]
    for datos, fragmento in casos:
        violaciones = validar_diarizacion(datos, 10.0)
        assert any(fragmento in v for v in violaciones), (datos, violaciones)


def test_par_consistente(tmp_path):
    segs = [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]
    escribir_par(tmp_path, {"segments": segs}, _meta(segs))
    assert validar_par(tmp_path / "diarization.json", tmp_path / "diarization.meta.json") == []


def test_par_de_ejecuciones_distintas(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    segs_a = [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]
    segs_b = [{"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"}]
    escribir_par(a, {"segments": segs_a}, _meta(segs_a, "ra"))
    escribir_par(b, {"segments": segs_b}, _meta(segs_b, "rb"))
    violaciones = validar_par(a / "diarization.json", b / "diarization.meta.json")
    assert any("no corresponden a la misma ejecución" in v for v in violaciones)


def test_linea_de_comandos(tmp_path, wav):
    audio = wav("audio.wav", segundos=5)
    bueno = tmp_path / "bueno"
    segs = [{"start": 0.0, "end": 4.0, "speaker": "SPEAKER_00"}]
    escribir_par(bueno, {"segments": segs}, _meta(segs))
    malo = tmp_path / "malo.json"
    malo.write_text(json.dumps({"segments": [{"start": 0.0, "end": 9.0, "speaker": "SPEAKER_00"}]}), encoding="utf-8")

    def correr(*args):
        return subprocess.run([sys.executable, str(MODULO / "contrato.py"), *map(str, args)],
                              capture_output=True, text=True, encoding="utf-8")

    ok = correr(bueno / "diarization.json", audio, "--meta", bueno / "diarization.meta.json")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "0 violaciones" in ok.stdout
    mal = correr(malo, audio)
    assert mal.returncode == 1 and "supera la duración" in mal.stdout
    par_malo = correr(bueno / "diarization.json", audio, "--meta", tmp_path / "no_existe.json")
    assert par_malo.returncode == 1
