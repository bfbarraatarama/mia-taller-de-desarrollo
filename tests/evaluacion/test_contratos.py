"""Tarea 5.1: contratos de los cuatro módulos desde lo guardado (requisitos «Contratos de los cuatro módulos»
y «Evaluación sin inferencia»)."""

from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path

from evaluacion.modular.__main__ import main
from evaluacion.modular.contratos import evaluar_contratos
from evaluacion.modular.muestra import construir_manifiesto
from src.minutas.entrada import leer_transcripcion

RAIZ = Path(__file__).resolve().parents[2]
SECCIONES = ["resumen", "temas", "decisiones", "problemas", "acciones"]


def wav(ruta: Path, segundos: float) -> str:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\0\0" * int(16000 * segundos))
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def escribir(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")


ASR = {"language": "es", "segments": [{"start": 0.1, "end": 0.9, "text": "hola",
                                       "words": [{"word": "hola", "start": 0.1, "end": 0.9}]}]}
DIAR = {"segments": [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]}
TRANS = {"segments": [{"start": 0.1, "end": 0.9, "speaker": "SPEAKER_00", "name": None, "text": "hola",
                       "overlap": False, "ambiguous": False}]}


def minuta(carpeta: Path, transcripcion: Path) -> None:
    [primera], _ = leer_transcripcion(transcripcion)
    elemento = {"texto": "Saludo.", "ids_intervenciones": [primera.id], "id_ancla": primera.id}
    escribir(carpeta / "minutes.json", {"resumen": "Se saludan.", "temas": [elemento], "decisiones": [],
                                        "problemas": [], "acciones": [{**elemento, "responsable": None,
                                                                       "plazo": None}]})
    escribir(carpeta / "ejecucion_minutas.json", {"secciones": SECCIONES})


def armar(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Muestra de 3 elementos (clip, tarea de Figshare, reunión de AMI) con todas sus salidas válidas."""
    datos, inferencia = tmp_path / "datos", tmp_path / "inferencia"
    elementos = [
        {"id": "clip-c1", "fuente": "openslr", "modulos": ["stt"],
         "archivos": {"clips/clip-c1/audio.wav": wav(datos / "clips/clip-c1/audio.wav", 1.0)}},
        {"id": "figshare-S22-01", "fuente": "figshare", "modulos": ["stt", "diarizacion", "asociacion", "minutas"],
         "archivos": {"figshare/S22/01/audio.wav": wav(datos / "figshare/S22/01/audio.wav", 1.0)}},
        {"id": "ami-r1", "fuente": "ami", "modulos": ["minutas"], "archivos": {}},
    ]
    escribir(datos / "ami/r1/transcription.json", TRANS)
    escribir(inferencia / "clip-c1/asr.json", ASR)
    fig = inferencia / "figshare-S22-01"
    escribir(fig / "asr.json", ASR)
    escribir(fig / "diarization.json", DIAR)
    escribir(fig / "transcription.json", TRANS)
    minuta(fig, fig / "transcription.json")
    minuta(inferencia / "ami-r1", datos / "ami/r1/transcription.json")
    manifiesto = tmp_path / "manifiesto.json"
    escribir(manifiesto, construir_manifiesto(20261010, {}, elementos, {}))
    return manifiesto, datos, inferencia


def test_todas_validas(tmp_path):
    reporte = evaluar_contratos(*armar(tmp_path))
    assert reporte["cumple"] is True
    assert {m: (r["validas"], r["total"]) for m, r in reporte["modulos"].items()} == {
        "stt": (2, 2), "diarizacion": (1, 1), "asociacion": (1, 1), "minutas": (2, 2)}
    assert all(r["porcentaje"] == 100.0 for r in reporte["modulos"].values())


def test_una_salida_fuera_de_contrato(tmp_path):
    manifiesto, datos, inferencia = armar(tmp_path)
    escribir(inferencia / "figshare-S22-01/diarization.json",
             {"segments": [{"start": 0.5, "end": 0.5, "speaker": "SPEAKER_00"}]})
    reporte = evaluar_contratos(manifiesto, datos, inferencia)
    assert reporte["cumple"] is False
    diar = reporte["modulos"]["diarizacion"]
    assert (diar["validas"], diar["total"]) == (0, 1)
    [violacion] = diar["violaciones"]
    assert violacion["archivo"] == "figshare-S22-01/diarization.json"
    assert "start" in violacion["regla"] and "end" in violacion["regla"]


def test_salida_faltante_no_es_violacion(tmp_path):
    manifiesto, datos, inferencia = armar(tmp_path)
    (inferencia / "clip-c1/asr.json").unlink()
    stt = evaluar_contratos(manifiesto, datos, inferencia)["modulos"]["stt"]
    assert stt["faltantes"] == ["clip-c1/asr.json"]
    assert stt["violaciones"] == []
    assert (stt["validas"], stt["total"]) == (1, 2)


def test_minuta_con_evidencia_inexistente(tmp_path):
    manifiesto, datos, inferencia = armar(tmp_path)
    ruta = inferencia / "ami-r1/minutes.json"
    datos_minuta = json.loads(ruta.read_text(encoding="utf-8"))
    datos_minuta["temas"][0]["ids_intervenciones"] = datos_minuta["temas"][0]["id_ancla"] = "x"
    datos_minuta["temas"][0]["ids_intervenciones"] = ["x"]
    escribir(ruta, datos_minuta)
    minutas = evaluar_contratos(manifiesto, datos, inferencia)["modulos"]["minutas"]
    assert (minutas["validas"], minutas["total"]) == (1, 2)
    assert minutas["violaciones"][0]["archivo"] == "ami-r1/minutes.json"


def test_evaluar_por_linea_de_comandos(tmp_path, capsys):
    manifiesto, datos, inferencia = armar(tmp_path)
    resultados = tmp_path / "resultados"
    config = tmp_path / "config.toml"
    config.write_text(
        (RAIZ / "evaluacion/modular/config.toml").read_text(encoding="utf-8")
        .replace('salida = "evaluacion/modular/datos"', f'salida = "{datos}"')
        .replace('manifiesto = "evaluacion/modular/muestra.manifest.json"', f'manifiesto = "{manifiesto}"')
        .replace('inferencia = "evaluacion/modular/inferencia"', f'inferencia = "{inferencia}"')
        .replace('resultados = "evaluacion/modular/resultados"', f'resultados = "{resultados}"')
        .replace('salidas = "evaluacion/modular/resultados/salidas"', f'salidas = "{tmp_path / "salidas"}"'),
        encoding="utf-8")
    assert main(["evaluar", "--config", str(config)]) == 0
    reporte = json.loads((resultados / "contratos.json").read_text(encoding="utf-8"))
    assert reporte["cumple"] is True and str(tmp_path) not in json.dumps(reporte)
    assert "4/4" in capsys.readouterr().out
    escribir(inferencia / "clip-c1/asr.json", {"language": "es", "segments": [{"start": 2, "end": 1}]})
    assert main(["evaluar", "--config", str(config)]) == 1
