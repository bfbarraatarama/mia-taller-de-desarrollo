"""Tarea 4.2: manifiesto verificable (requisitos «Manifiesto verificable» y «Selección determinista»)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evaluacion.modular.__main__ import main
from evaluacion.modular.muestra import construir_manifiesto, verificar_muestra

RAIZ = Path(__file__).resolve().parents[2]


def sha(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def muestra_chica(datos: Path) -> dict:
    """Dos elementos ya preparados en `datos` y su manifiesto."""
    (datos / "clips" / "c1").mkdir(parents=True)
    (datos / "clips" / "c1" / "audio.wav").write_bytes(b"audio uno")
    (datos / "ami" / "r1").mkdir(parents=True)
    (datos / "ami" / "r1" / "transcription.json").write_bytes(b'{"segments": []}')
    elementos = [
        {"id": "ami-r1", "fuente": "ami", "modulos": ["minutas"],
         "archivos": {"ami/r1/transcription.json": sha(b'{"segments": []}')}},
        {"id": "clip-c1", "fuente": "openslr", "modulos": ["stt"],
         "archivos": {"clips/c1/audio.wav": sha(b"audio uno")}},
    ]
    return construir_manifiesto(20261010, {"ami": "abc"}, elementos, {"S26": "desarrollo"})


def escribir(ruta: Path, manifiesto: dict) -> Path:
    ruta.write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta


def test_misma_semilla_misma_muestra(tmp_path):
    a = muestra_chica(tmp_path / "a")
    b = muestra_chica(tmp_path / "b")
    assert a["contenido"] == b["contenido"]
    assert a["contenido_sha256"] == b["contenido_sha256"]
    # el orden en que se arman los elementos no cambia el contenido
    invertido = construir_manifiesto(20261010, {"ami": "abc"}, list(reversed(a["contenido"]["elementos"])),
                                     {"S26": "desarrollo"})
    assert invertido["contenido_sha256"] == a["contenido_sha256"]
    otra_semilla = construir_manifiesto(7, {"ami": "abc"}, a["contenido"]["elementos"], {"S26": "desarrollo"})
    assert otra_semilla["contenido_sha256"] != a["contenido_sha256"]


def test_muestra_intacta(tmp_path):
    datos = tmp_path / "datos"
    ruta = escribir(tmp_path / "manifiesto.json", muestra_chica(datos))
    antes = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in datos.rglob("*") if p.is_file()}
    assert verificar_muestra(ruta, datos) == []
    assert {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in datos.rglob("*") if p.is_file()} == antes


def test_archivo_alterado(tmp_path):
    datos = tmp_path / "datos"
    ruta = escribir(tmp_path / "manifiesto.json", muestra_chica(datos))
    (datos / "clips" / "c1" / "audio.wav").write_bytes(b"audio cambiado")
    problemas = verificar_muestra(ruta, datos)
    assert len(problemas) == 1
    assert "clips/c1/audio.wav" in problemas[0]
    assert sha(b"audio uno") in problemas[0] and sha(b"audio cambiado") in problemas[0]


def test_archivo_faltante(tmp_path):
    datos = tmp_path / "datos"
    ruta = escribir(tmp_path / "manifiesto.json", muestra_chica(datos))
    (datos / "ami" / "r1" / "transcription.json").unlink()
    assert ["ami/r1/transcription.json" in p and "falta" in p for p in verificar_muestra(ruta, datos)] == [True]


def test_manifiesto_editado_a_mano(tmp_path):
    datos = tmp_path / "datos"
    manifiesto = muestra_chica(datos)
    manifiesto["contenido"]["semilla"] = 1  # cambia el contenido sin recalcular su hash
    problemas = verificar_muestra(escribir(tmp_path / "manifiesto.json", manifiesto), datos)
    assert any("contenido_sha256" in p for p in problemas)


def _config(tmp_path, datos: Path, manifiesto: Path) -> Path:
    config = tmp_path / "config.toml"
    config.write_text(
        (RAIZ / "evaluacion/modular/config.toml").read_text(encoding="utf-8")
        .replace('salida = "evaluacion/modular/datos"', f'salida = "{datos}"')
        .replace('manifiesto = "evaluacion/modular/muestra.manifest.json"', f'manifiesto = "{manifiesto}"'),
        encoding="utf-8")
    return config


def test_verificar_por_linea_de_comandos(tmp_path, capsys):
    datos = tmp_path / "datos"
    ruta = escribir(tmp_path / "manifiesto.json", muestra_chica(datos))
    config = _config(tmp_path, datos, ruta)
    assert main(["preparar", "--verificar", "--config", str(config)]) == 0
    (datos / "clips" / "c1" / "audio.wav").write_bytes(b"otro")
    assert main(["preparar", "--verificar", "--config", str(config)]) == 1
    assert "clips/c1/audio.wav" in capsys.readouterr().err
