# Evaluación de asociación

El [README de asociación](../../docs/asociacion/README.md) describe los contratos y el ejemplo ideal. Desde la raíz del repositorio, con el entorno general instalado:

```bash
.venv/bin/python -m evaluacion.asociacion.ejemplo_ideal.generar
.venv/bin/python -m evaluacion.asociacion.stats_s26 evaluacion/diarizacion/resultados/hipotesis_S26
.venv/bin/python -m evaluacion.asociacion.tramos_solos evaluacion/diarizacion/resultados/hipotesis_S26
```

El generador requiere eSpeak NG y escribe en `evaluacion/asociacion/ejemplo_ideal/generado/` (local). Los dos análisis utilizan las hipótesis versionadas de diarización; no ejecutan el modelo. Las decisiones y mediciones originales se encuentran en [OpenSpec](../../docs/asociacion/openspec/changes/etapa-4-asociacion-etiquetado/).
