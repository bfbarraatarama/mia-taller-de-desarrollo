"""Tarea 5.2: inferencia sobre la muestra verificada (requisito «Inferencia sobre la muestra verificada»)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluacion.modular.config import cargar_config
from evaluacion.modular.inferencia import ARCHIVOS_ESPERADOS, MuestraAlterada, inferir
from tests.evaluacion.test_contratos import armar

RAIZ = Path(__file__).resolve().parents[2]


class EjecutorFalso:
    """Registra cada comando y escribe los archivos que dejaría el módulo real."""

    def __init__(self):
        self.comandos = []

    def __call__(self, comando: list[str], carpeta: Path, fuente: str) -> int:
        self.comandos.append(comando)
        carpeta.mkdir(parents=True, exist_ok=True)
        for nombre in ARCHIVOS_ESPERADOS[fuente]:
            (carpeta / nombre).write_text("{}", encoding="utf-8")
        return 0


def config_en(tmp_path):
    manifiesto, datos, _ = armar(tmp_path)
    inferencia = tmp_path / "inferencia-nueva"
    ruta = tmp_path / "config.toml"
    ruta.write_text(
        (RAIZ / "evaluacion/modular/config.toml").read_text(encoding="utf-8")
        .replace('salida = "evaluacion/modular/datos"', f'salida = "{datos.as_posix()}"')
        .replace('manifiesto = "evaluacion/modular/muestra.manifest.json"', f'manifiesto = "{manifiesto.as_posix()}"')
        .replace('inferencia = "evaluacion/modular/inferencia"', f'inferencia = "{inferencia.as_posix()}"'),
        encoding="utf-8")
    return cargar_config(ruta)


def test_comandos_por_fuente(tmp_path):
    config, falso = config_en(tmp_path), EjecutorFalso()
    resumen = inferir(config, ejecutar=falso)
    assert resumen == {"ejecutados": 3, "reutilizados": 0}
    por_modulo = {c[2]: c for c in falso.comandos}
    assert set(por_modulo) == {"src.stt", "src.pipeline", "src.minutas"}
    pipeline = por_modulo["src.pipeline"]
    assert pipeline[3] == "ejecutar" and Path(pipeline[4]).as_posix().endswith("figshare/S22/01/audio.wav")
    assert pipeline[pipeline.index("--modelo") + 1] == "qwen2.5-7b"
    assert pipeline[pipeline.index("--secciones") + 1] == "resumen,temas,decisiones,problemas,acciones"
    assert por_modulo["src.stt"][por_modulo["src.stt"].index("--model") + 1] == "medium"
    assert Path(por_modulo["src.minutas"][por_modulo["src.minutas"].index("--entrada") + 1]).as_posix().endswith(
        "ami/r1/transcription.json")
    registro = json.loads((config.inferencia / "figshare-S22-01" / "inferencia.json").read_text(encoding="utf-8"))
    assert registro["codigo"] == 0 and registro["configuracion"]["modelo_stt"] == "medium"
    assert str(tmp_path) not in json.dumps(registro)  # sin rutas de la máquina


def test_muestra_alterada(tmp_path):
    config, falso = config_en(tmp_path), EjecutorFalso()
    (config.salida / "clips/clip-c1/audio.wav").write_bytes(b"otro audio")
    try:
        inferir(config, ejecutar=falso)
    except MuestraAlterada as e:
        assert "clips/clip-c1/audio.wav" in str(e)
    else:
        raise AssertionError("debía fallar")
    assert falso.comandos == []  # no se cargó ningún modelo


def test_reutilizacion(tmp_path):
    config, falso = config_en(tmp_path), EjecutorFalso()
    inferir(config, ejecutar=falso)
    salidas = {p: p.stat().st_mtime_ns for p in config.inferencia.rglob("*") if p.is_file()}
    segundo = EjecutorFalso()
    assert inferir(config, ejecutar=segundo) == {"ejecutados": 0, "reutilizados": 3}
    assert segundo.comandos == []
    assert {p: p.stat().st_mtime_ns for p in config.inferencia.rglob("*") if p.is_file()} == salidas


def test_rehacer_y_salida_incompleta(tmp_path):
    config = config_en(tmp_path)
    inferir(config, ejecutar=EjecutorFalso())
    (config.inferencia / "clip-c1" / "asr.json").unlink()  # quedó incompleta: se vuelve a correr
    otro = EjecutorFalso()
    assert inferir(config, ejecutar=otro) == {"ejecutados": 1, "reutilizados": 2}
    assert inferir(config, ejecutar=EjecutorFalso(), rehacer=True) == {"ejecutados": 3, "reutilizados": 0}


def test_fallo_de_un_modulo_no_se_reutiliza(tmp_path):
    config = config_en(tmp_path)

    def falla(comando, carpeta, fuente):
        return 1

    resumen = inferir(config, ejecutar=falla)
    assert resumen["ejecutados"] == 3 and resumen["fallidos"] == ["ami-r1", "clip-c1", "figshare-S22-01"]
    assert inferir(config, ejecutar=EjecutorFalso()) == {"ejecutados": 3, "reutilizados": 0}
