"""Comprobaciones automáticas de los escenarios de §2.1 sobre la carpeta que deja `src.pipeline ejecutar`.

Cada comprobación da «sí», «no» o «manual» (solo se ve en la interfaz: va al protocolo del tercero) con su evidencia.
El veredicto automático es «sí» si ninguna automática da «no»; lo manual queda pendiente aparte.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _leer(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else None


def _c(nombre: str, resultado: str, evidencia: str) -> dict:
    return {"comprobacion": nombre, "resultado": resultado, "evidencia": evidencia}


def _audio_conservado(carpeta: Path, esperados: list[str]) -> dict:
    ingesta = _leer(carpeta / "ingesta.json") or {"fuentes": []}
    fuentes = sorted(ingesta["fuentes"], key=lambda f: f["orden"])
    copias = [hashlib.sha256((carpeta / f["fuente"]).read_bytes()).hexdigest() if (carpeta / f["fuente"]).is_file()
              else None for f in fuentes]
    ok = [f["sha256_fuente"] for f in fuentes] == esperados and copias == esperados
    return _c("Conserva el audio", "sí" if ok else "no",
              f"{sum(c == e for c, e in zip(copias, esperados))} de {len(esperados)} fuentes conservadas con su SHA-256")


def _termina_o_informa(workflow: dict | None) -> dict:
    if workflow and workflow.get("estado") == "completado":
        return _c("Termina o informa la falla", "sí", "pipeline completado")
    if workflow and workflow.get("error"):
        return _c("Termina o informa la falla", "sí", f"informó: {json.dumps(workflow['error'], ensure_ascii=False)}")
    return _c("Termina o informa la falla", "no", f"estado {workflow.get('estado') if workflow else 'sin workflow.json'}, sin error informado")


def _superpuestos(segmentos: list[dict]) -> float:
    """Segundos con dos o más hablantes de la diarización a la vez."""
    eventos = sorted([(s["start"], 1) for s in segmentos] + [(s["end"], -1) for s in segmentos], key=lambda e: (e[0], e[1]))
    total, activos, previo = 0.0, 0, 0.0
    for t, d in eventos:
        if activos >= 2:
            total += t - previo
        activos, previo = activos + d, t
    return total


def comprobar(escenario: str, carpeta: Path, fuentes_sha: list[str]) -> dict:
    carpeta = Path(carpeta)
    workflow = _leer(carpeta / "workflow.json")
    diar = (_leer(carpeta / "diarization.json") or {}).get("segments", [])
    trans = (_leer(carpeta / "transcription.json") or {}).get("segments", [])
    minuta = _leer(carpeta / "ejecucion_minutas.json")
    detalle = {"estado": workflow.get("estado") if workflow else None,
               "etiquetas_detectadas": len({s["speaker"] for s in diar}),
               "segundos_superpuestos_diarizacion": round(_superpuestos(diar), 3),
               "intervenciones": len(trans), "intervenciones_ambiguas": sum(bool(i.get("ambiguous")) for i in trans),
               "intervenciones_overlap": sum(bool(i.get("overlap")) for i in trans)}
    cs = [_audio_conservado(carpeta, fuentes_sha), _termina_o_informa(workflow)]

    if escenario == "2.1.2":
        cs.append(_c("Conserva los solapamientos de la diarización", "sí" if detalle["segundos_superpuestos_diarizacion"] > 0 else "no",
                     f"{detalle['segundos_superpuestos_diarizacion']} s con dos o más etiquetas"))
        cs.append(_c("Marca intervenciones de hablante ambiguo", "sí" if detalle["intervenciones_ambiguas"] else "no",
                     f"{detalle['intervenciones_ambiguas']} ambiguous y {detalle['intervenciones_overlap']} overlap de {len(trans)}"))
        cs.append(_c("Mismo nombre en dos etiquetas: una sola persona", "manual", "se comprueba en las fichas (protocolo)"))
    elif escenario == "2.1.3":
        sin_hablante = [i for i in trans if i.get("speaker") is None]
        cs.append(_c("Etiqueta a cada hablante detectado", "sí" if diar and all(
            i.get("speaker") in {s["speaker"] for s in diar} or i.get("speaker") is None for i in trans) else "no",
            f"{detalle['etiquetas_detectadas']} etiquetas en la diarización"))
        cs.append(_c("Marca como ambiguas las intervenciones sin hablante",
                     "sí" if all(i.get("ambiguous") for i in sin_hablante) else "no",
                     f"{len(sin_hablante)} sin hablante; {detalle['intervenciones_ambiguas']} ambiguas en total"))
        cs.append(_c("Ficha y nombre para cada hablante", "manual", "se comprueba en las fichas (protocolo)"))
    elif escenario == "2.1.4":
        completado = detalle["estado"] == "completado"
        cs.append(_c("Conserva los resultados", "sí" if not completado or (trans and minuta) else "no",
                     "transcripción y minuta presentes" if completado else "pipeline no completado: ver la falla informada"))
    elif escenario == "2.1.5":
        bloques = (minuta or {}).get("bloques_extraccion")
        detalle["bloques_extraccion"] = bloques
        if detalle["estado"] == "completado":
            cs.append(_c("Procesa la minuta por fragmentos", "sí" if (bloques or 0) > 1 else "no",
                         f"{bloques} bloques de extracción"))
        else:
            cs.append(_c("Si no puede, conserva la transcripción", "sí" if trans else "no",
                         f"{len(trans)} intervenciones conservadas"))
        ingesta = (_leer(carpeta / "ingesta.json") or {}).get("fuentes", [])
        en_orden = [f["orden"] for f in ingesta] == list(range(1, len(fuentes_sha) + 1))
        cs.append(_c("Una sola transcripción para todos los archivos, en orden",
                     "sí" if en_orden and (carpeta / "transcription.json").is_file() else "no",
                     f"{len(ingesta)} archivos en una reunión"))
    automaticas = [c for c in cs if c["resultado"] != "manual"]
    return {"escenario": escenario, "detalle": detalle, "comprobaciones": cs,
            "veredicto_automatico": "no" if any(c["resultado"] == "no" for c in automaticas) else "sí",
            "pendientes_manuales": sum(c["resultado"] == "manual" for c in cs)}
