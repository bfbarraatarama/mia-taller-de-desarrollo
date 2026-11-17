import csv
import zipfile

import pandas as pd
import pytest

from evaluacion.fidelidad_minutas.preparacion import preparar, seleccionar, verificar


class TraductorFalso:
    modelo = "simulado"
    revision = "fija"
    parametros = {"dispositivo": "cpu"}

    def traducir(self, textos):
        return textos


def test_preparar_seleccion_y_deteccion_de_alteraciones(tmp_path):
    fuente = tmp_path / "ami"
    fuente.mkdir()
    reuniones = [
        {"reunion": nombre, "duracion_s": duracion, "palabras": 2, "tiene_minuta": True}
        for nombre, duracion in (("A", 30), ("B", 50), ("C", 40), ("D", 10))]
    with (fuente / "reuniones.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=reuniones[0])
        w.writeheader()
        w.writerows(reuniones)
    pd.DataFrame([{"reunion": r["reunion"], "agente": "A", "inicio": 0.0, "fin": 2.0, "texto": "Texto."}
                  for r in reuniones]).to_parquet(fuente / "turnos.parquet")
    pd.DataFrame([{"reunion": r["reunion"], "tipo": "resumen", "orden": 1,
                   "item_id": f"{r['reunion']}-1", "texto": "Resumen."}
                  for r in reuniones]).to_parquet(fuente / "minutas.parquet")
    archivo = tmp_path / "ami.zip"
    with zipfile.ZipFile(archivo, "w") as z:
        z.writestr("corpusResources/meetings.xml", "".join(
            f'<meeting observation="{r["reunion"]}"><speaker nxt_agent="A" role="PM"/></meeting>'
            for r in reuniones))
    assert [r["reunion"] for r in seleccionar(fuente)] == ["B", "C", "A"]
    destino = tmp_path / "muestra"
    preparar(destino, carpeta_ami=fuente, traductor=TraductorFalso(), ami_zip=archivo)
    assert len(verificar(destino)["reuniones"]) == 3
    (destino / "ami/B/transcription.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="alterado"):
        verificar(destino)
