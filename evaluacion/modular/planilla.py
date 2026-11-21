"""Planilla de minutas para marcado humano (requisito «Planilla de minutas», D10 y D17).

Por cada reunión de AMI: `<reunión>.csv` con un ítem de la minuta de referencia traducida por fila y la columna
`recuperado` vacía, y `<reunión>.minuta.md` con la minuta producida. Una planilla con marcas nunca se reescribe:
solo se resume. Si la minuta cambió y la planilla todavía no tiene marcas, se regenera.
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

COLUMNAS = ["reunion", "tipo", "item_id", "referencia", "referencia_original", "recuperado", "observaciones"]
SI, NO = {"sí", "si", "s"}, {"no", "n"}

LEEME = """# Planilla de minutas (evaluación modular, issue #13)

La marca una persona que **no** ejecutó la inferencia (D17), con el mismo criterio que la calidad de la respuesta
de la definición de la PoC (§2.3).

Para cada reunión:
1. Leer la minuta producida, `<reunión>.minuta.md`.
2. En `<reunión>.csv`, para cada ítem de la minuta de referencia (traducida automáticamente; el original en inglés
   está en `referencia_original`), escribir en `recuperado`:
   - `sí` si la minuta producida lo recupera, aunque sea con otras palabras;
   - `no` si no lo recupera.
   Una **acción** cuenta como recuperada solo si también coincide su responsable (en estas reuniones, el rol:
   «Diseñador industrial», «Gerente de proyecto»…; en IB4005 la referencia no nombra responsables).
3. `observaciones` es libre: dudas, ítems parcialmente recuperados, errores de la traducción.

No cambiar las otras columnas ni el orden de las filas. `python -m evaluacion.modular evaluar` resume lo marcado
sin modificar la planilla.
"""


class PlanillaInvalida(Exception):
    """Una planilla tiene valores que no son sí o no, o no corresponde a la referencia."""


def _escribir_planilla(ruta: Path, reunion: str, items: list[dict]) -> None:
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        for i in items:
            w.writerow({"reunion": reunion, "tipo": i["tipo"], "item_id": i["item_id"], "referencia": i["texto"],
                        "referencia_original": i["texto_original"], "recuperado": "", "observaciones": ""})


def _resumir(ruta: Path, items: list[dict]) -> dict:
    with open(ruta, encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    if [f["item_id"] for f in filas] != [i["item_id"] for i in items]:
        raise PlanillaInvalida(f"{ruta.name}: los ítems no coinciden con la minuta de referencia")
    por_tipo, invalidos = {}, []
    for fila in filas:
        valor = (fila.get("recuperado") or "").strip().lower()
        t = por_tipo.setdefault(fila["tipo"], {"items": 0, "marcados": 0, "recuperados": 0})
        t["items"] += 1
        if not valor:
            continue
        if valor not in SI | NO:
            invalidos.append(f"{fila['item_id']} ({fila['recuperado']!r})")
            continue
        t["marcados"] += 1
        t["recuperados"] += valor in SI
    if invalidos:
        raise PlanillaInvalida(f"{ruta.name}: valores que no son sí o no: " + ", ".join(invalidos))
    marcados = sum(t["marcados"] for t in por_tipo.values())
    return {"por_tipo": dict(sorted(por_tipo.items())), "items": len(filas), "marcados": marcados,
            "pendientes": len(filas) - marcados,
            "recuperados": sum(t["recuperados"] for t in por_tipo.values())}


def planillas_de_minutas(elementos: list[dict], datos: Path, inferencia: Path, carpeta: Path) -> dict:
    carpeta = Path(carpeta)
    reuniones, avisos, faltantes = {}, [], []
    for e in sorted(elementos, key=lambda e: e["id"]):
        if e["fuente"] != "ami":
            continue
        reunion = e.get("reunion") or e["id"].split("-", 1)[1]
        minuta = Path(inferencia) / e["id"] / "minutes.md"
        if not minuta.is_file():
            faltantes.append(f"{e['id']}/minutes.md")
            continue
        items = json.loads((Path(datos) / "ami" / reunion / "referencia_minuta.json")
                           .read_text(encoding="utf-8"))["items"]
        carpeta.mkdir(parents=True, exist_ok=True)
        if not (carpeta / "LEEME.md").is_file():
            (carpeta / "LEEME.md").write_text(LEEME, encoding="utf-8")
        planilla, copia = carpeta / f"{reunion}.csv", carpeta / f"{reunion}.minuta.md"
        if copia.is_file() and copia.read_bytes() != minuta.read_bytes():
            if planilla.is_file() and _resumir(planilla, items)["marcados"]:
                avisos.append(f"{reunion}: la minuta producida cambió después de generar la planilla; "
                              f"se conserva la copia marcada ({copia.name})")
            else:  # nadie marcó todavía: se regenera con la minuta vigente
                copia.unlink()
                planilla.unlink(missing_ok=True)
                avisos.append(f"{reunion}: la minuta producida cambió y la planilla no tenía marcas; se regeneró")
        if not copia.is_file():
            shutil.copyfile(minuta, copia)
        if not planilla.is_file():
            _escribir_planilla(planilla, reunion, items)
        reuniones[reunion] = _resumir(planilla, items)
    total = {"items": 0, "marcados": 0, "pendientes": 0, "recuperados": 0, "por_tipo": {}}
    for r in reuniones.values():
        for k in ("items", "marcados", "pendientes", "recuperados"):
            total[k] += r[k]
        for tipo, t in r["por_tipo"].items():
            acumulado = total["por_tipo"].setdefault(tipo, {"items": 0, "marcados": 0, "recuperados": 0})
            for k in acumulado:
                acumulado[k] += t[k]
    return {"criterio": "ítems de la minuta de referencia recuperados por la minuta producida, marcados por una "
                        "persona que no ejecutó la inferencia (§2.3, D17); sin umbral",
            "reuniones": reuniones, "total": total, "avisos": avisos, "faltantes": faltantes}
