"""Ubicaciones de trabajo y evidencias de la evaluación de diarización."""

from pathlib import Path

DIRECTORIO = Path(__file__).resolve().parent
DATOS_BASE = DIRECTORIO / "datos" / "figshare_test"
REPORTES = DIRECTORIO / "reportes"
RESULTADOS = DIRECTORIO / "resultados"
MANIFIESTO = DIRECTORIO / "figshare_test.manifest.json"
