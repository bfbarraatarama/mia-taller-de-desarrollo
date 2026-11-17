"""Métricas puras para comparaciones y evaluación del juez."""

from __future__ import annotations

from collections import Counter


def proporcion(numerador: int, denominador: int) -> dict:
    return {"numerador": numerador, "denominador": denominador,
            "valor": numerador / denominador if denominador else None}


def metricas_juez(filas: list[dict]) -> dict:
    etiquetas = ("sí", "no", "incierto", "no_evaluable")
    validas = [f for f in filas if f["recuperado_humano"] in ("sí", "no")]
    tabla = {h: {p: 0 for p in etiquetas} for h in ("sí", "no")}
    for fila in validas:
        tabla[fila["recuperado_humano"]][fila["recuperado_juez"]] += 1
    tp = tabla["sí"]["sí"]
    precision = proporcion(tp, tabla["sí"]["sí"] + tabla["no"]["sí"])
    recall = proporcion(tp, sum(tabla["sí"].values()))
    p, r = precision["valor"], recall["valor"]
    f1 = None if p is None or r is None else (2 * p * r / (p + r) if p + r else 0.0)
    return {"total": len(filas), "sin_marca_humana": len(filas) - len(validas),
            "confusion": tabla, "exactitud": proporcion(tp + tabla["no"]["no"], len(validas)),
            "precision_si": precision, "recall_si": recall, "f1_si": f1,
            "abstenciones": sum(tabla[h][p] for h in tabla for p in ("incierto", "no_evaluable")),
            "desacuerdos": [f for f in validas if f["recuperado_humano"] != f["recuperado_juez"]]}


def recall(filas: list[dict]) -> dict:
    estados = Counter(f["estado"] for f in filas)
    evaluados = [f for f in filas if f["estado"] == "evaluado"]
    return {"total": len(filas), "estados": dict(sorted(estados.items())),
            "recall": proporcion(sum(f["recuperado"] == "sí" for f in evaluados), len(evaluados))}


def comparar(base: list[dict], forzada: list[dict]) -> dict:
    b = {f["item_id"]: f for f in base}
    f = {fila["item_id"]: fila for fila in forzada}
    if len(b) != len(base) or len(f) != len(forzada) or b.keys() != f.keys():
        raise ValueError("Las condiciones deben contener los mismos ítems únicos.")
    if any(b[i]["tipo"] != f[i]["tipo"] or b[i]["referencia"] != f[i]["referencia"] for i in b):
        raise ValueError("Las referencias de ambas condiciones no coinciden.")
    if any(x["estado"] == "error" for x in base + forzada):
        raise ValueError("No se calcula recall con juicios incompletos.")

    def grupo(ids: list[str]) -> dict:
        bs, fs = [b[i] for i in ids], [f[i] for i in ids]
        pares = [i for i in ids if b[i]["estado"] == f[i]["estado"] == "evaluado"]
        rb = proporcion(sum(b[i]["recuperado"] == "sí" for i in pares), len(pares))
        rf = proporcion(sum(f[i]["recuperado"] == "sí" for i in pares), len(pares))
        return {"baseline": recall(bs), "forzada": recall(fs), "pares": len(pares),
                "baseline_pareada": rb, "forzada_pareada": rf,
                "delta_puntos_porcentuales": 100 * (rf["valor"] - rb["valor"]) if pares else None,
                "excluidos": [i for i in ids if i not in pares],
                "transiciones": [{"item_id": i, "baseline": b[i]["recuperado"],
                                  "forzada": f[i]["recuperado"], "cita_baseline": b[i]["cita"],
                                  "cita_forzada": f[i]["cita"]} for i in pares]}
    ids = sorted(b)
    return {"total": grupo(ids), "tipos": {tipo: grupo([i for i in ids if b[i]["tipo"] == tipo])
            for tipo in sorted({v["tipo"] for v in b.values()})}}
