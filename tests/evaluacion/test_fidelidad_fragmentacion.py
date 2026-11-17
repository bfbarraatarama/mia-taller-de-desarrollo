import hashlib
import json
from dataclasses import replace

import pytest

from evaluacion.fidelidad_minutas.fragmentacion import partir, serializar, deserializar
from src.minutas import ConfiguracionMinutas, generar_minuta
from src.minutas.entrada import leer_transcripcion
from src.minutas.experimento import Bloque, ExperimentoMinutas, Ocurrencia
from src.minutas.generacion import huella_experimento
from src.minutas.proveedores import LimiteModelo, RespuestaModelo


class Cliente:
    nombre = "simulado"
    proveedor = "ollama"

    def __init__(self):
        self.bloques = []

    def responder(self, instrucciones, datos, esquema):
        objeto = json.loads(datos)
        if "intervenciones" in objeto:
            bloque = objeto["intervenciones"]
            if len(bloque) > 4:
                raise LimiteModelo("límite simulado")
            self.bloques.append(bloque)
        return RespuestaModelo({"resumen": "Resumen sintético."})


def test_traza_real_con_recuperacion_y_plan_forzado(tmp_path):
    entrada = {"segments": [
        {"start": i * 2, "end": i * 2 + 1, "speaker": "A", "name": None,
         "text": f"Texto de intervención {i}.", "overlap": False, "ambiguous": False}
        for i in range(8)]}
    origen = tmp_path / "entrada.json"
    origen.write_text(json.dumps(entrada), encoding="utf-8")
    config = ConfiguracionMinutas(secciones=("resumen",))
    digest = hashlib.sha256(origen.read_bytes()).hexdigest()
    base = ExperimentoMinutas(digest, huella_experimento(config))
    cliente = Cliente()
    generar_minuta(origen, tmp_path / "base", configuracion=config, cliente=cliente, experimento=base)
    originales, _ = leer_transcripcion(origen)
    por_id = {i.id: i for i in originales}
    assert len(base.bloques) == 2
    for bloque, enviados in zip(base.bloques, cliente.bloques, strict=True):
        assert [por_id[o.id_intervencion].texto[o.inicio_texto:o.fin_texto] for o in bloque.ocurrencias] == [
            i["texto"] for i in enviados]
    assert deserializar(serializar(base.bloques)) == tuple(base.bloques)
    plan = partir(tuple(base.bloques))
    forzada = ExperimentoMinutas(digest, huella_experimento(config), tuple(base.bloques), plan)
    generar_minuta(origen, tmp_path / "forzada", configuracion=config, cliente=Cliente(), experimento=forzada)
    assert len(forzada.bloques) == 4
    assert {b.padre_id for b in forzada.bloques} == {b.bloque_id for b in plan}


def test_corte_imposible_y_traza_alterada():
    solo = Bloque("B1", (Ocurrencia("I1", 0, 100),))
    with pytest.raises(ValueError, match="equilibrado"):
        partir((solo,))
    bloque = Bloque("B1", (Ocurrencia("I1", 0, 4), Ocurrencia("I2", 0, 4)))
    datos = serializar((bloque,))
    datos[0]["caracteres_texto"] = 99
    with pytest.raises(ValueError, match="tamaño"):
        deserializar(datos)


def test_plan_forzado_rechaza_corte_distinto_y_baseline_duplicado():
    entrada = {"segments": [
        {"start": i * 2, "end": i * 2 + 1, "speaker": "A", "name": None,
         "text": "abcd", "overlap": False, "ambiguous": False}
        for i in range(5)]}
    intervenciones, _ = leer_transcripcion(entrada)
    padre = Bloque("B1", tuple(Ocurrencia(i.id, 0, len(i.texto)) for i in intervenciones))
    izquierda, derecha = partir((padre,))
    assert len(izquierda.ocurrencias) == 2  # 2/5 and 3/5 tie; the earlier cut wins.
    alternativo = (
        replace(izquierda, ocurrencias=padre.ocurrencias[:3]),
        replace(derecha, ocurrencias=padre.ocurrencias[3:]),
    )
    experimento = ExperimentoMinutas("entrada", "config", (padre,), alternativo)
    with pytest.raises(ValueError, match="corte equilibrado"):
        experimento.preparar(intervenciones, "entrada", "config", lambda _: True)
    with pytest.raises(ValueError, match="únicos"):
        partir((padre, padre))


def test_traza_preserva_offsets_de_fragmentos_repetidos(tmp_path):
    class LimiteTexto(Cliente):
        def responder(self, instrucciones, datos, esquema):
            objeto = json.loads(datos)
            if "intervenciones" in objeto:
                bloque = objeto["intervenciones"]
                if len(bloque) == 1 and len(bloque[0]["texto"]) > 15:
                    raise LimiteModelo("límite simulado")
                self.bloques.append(bloque)
            return RespuestaModelo({"resumen": "Resumen."})

    entrada = {"segments": [{"start": 0, "end": 1, "speaker": "A", "name": None,
                            "text": "repetido " * 8, "overlap": False, "ambiguous": False}]}
    origen = tmp_path / "entrada.json"
    origen.write_text(json.dumps(entrada), encoding="utf-8")
    config = ConfiguracionMinutas(secciones=("resumen",))
    traza = ExperimentoMinutas(hashlib.sha256(origen.read_bytes()).hexdigest(), huella_experimento(config))
    cliente = LimiteTexto()
    generar_minuta(origen, tmp_path / "base", configuracion=config, cliente=cliente, experimento=traza)
    original = leer_transcripcion(origen)[0][0].texto
    partes = [b.ocurrencias[0] for b in traza.bloques]
    assert "".join(original[o.inicio_texto:o.fin_texto] for o in partes) == original
    assert [original[o.inicio_texto:o.fin_texto] for o in partes] == [b[0]["texto"] for b in cliente.bloques]


def test_traza_con_contexto_superpuesto(tmp_path):
    class SinLimite(Cliente):
        def responder(self, instrucciones, datos, esquema):
            objeto = json.loads(datos)
            if "intervenciones" in objeto:
                self.bloques.append(objeto["intervenciones"])
            return RespuestaModelo({"resumen": "Resumen."})

    entrada = {"segments": [
        {"start": i * 2, "end": i * 2 + 1, "speaker": "A", "name": None,
         "text": f"{i} " + "texto " * 22, "overlap": False, "ambiguous": False}
        for i in range(20)]}
    origen = tmp_path / "entrada.json"
    origen.write_text(json.dumps(entrada), encoding="utf-8")
    config = ConfiguracionMinutas(secciones=("resumen",), max_caracteres_bloque=1000)
    traza = ExperimentoMinutas(hashlib.sha256(origen.read_bytes()).hexdigest(), huella_experimento(config))
    cliente = SinLimite()
    generar_minuta(origen, tmp_path / "base", configuracion=config, cliente=cliente, experimento=traza)
    assert len(traza.bloques) > 1
    for bloque, enviados in zip(traza.bloques, cliente.bloques, strict=True):
        assert [o.id_intervencion for o in bloque.ocurrencias] == [i["id"] for i in enviados]
    ids = [[o.id_intervencion for o in b.ocurrencias] for b in traza.bloques]
    assert any(set(a) & set(b) for a, b in zip(ids, ids[1:]))
