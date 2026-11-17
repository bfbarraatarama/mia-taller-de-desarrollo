import pytest

from evaluacion.fidelidad_minutas.metricas import comparar, metricas_juez


def test_metricas_incluyen_abstenciones_sin_convertirlas_en_no():
    filas = [{"recuperado_humano": "sí", "recuperado_juez": "incierto"},
             {"recuperado_humano": "no", "recuperado_juez": "no"},
             {"recuperado_humano": "", "recuperado_juez": "sí"}]
    resultado = metricas_juez(filas)
    assert resultado["exactitud"] == {"numerador": 1, "denominador": 2, "valor": 0.5}
    assert resultado["recall_si"]["valor"] == 0
    assert resultado["precision_si"]["valor"] is None
    assert resultado["sin_marca_humana"] == 1


def test_delta_solo_sobre_pares_evaluados():
    def fila(i, estado, etiqueta):
        return {"item_id": i, "tipo": "accion", "referencia": i, "estado": estado,
                "recuperado": etiqueta, "cita": "[]"}
    base = [fila("1", "evaluado", "sí"), fila("2", "incierto", "")]
    forzada = [fila("1", "evaluado", "no"), fila("2", "evaluado", "sí")]
    resultado = comparar(base, forzada)["total"]
    assert resultado["pares"] == 1 and resultado["excluidos"] == ["2"]
    assert resultado["delta_puntos_porcentuales"] == -100
    with pytest.raises(ValueError, match="mismos ítems"):
        comparar(base, forzada[:1])
