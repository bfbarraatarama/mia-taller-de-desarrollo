# Veredicto de viabilidad

**MIA104 · Hito 2 · Luisa, Bruno, Matías y Felipe.** Evidencia: [`EDA`](2-eda-de-viabilidad.md), [`notebook`](notebooks/eda_viabilidad.ipynb) y [`niveles a priori`](niveles-a-priori.md).

## Decisión: ajustar el alcance

**Continuar con la evaluación por módulo; no considerar aún viable la evaluación integral en castellano.** La validez estructural no implica que todas las referencias sean puntuables.

## Fundamentos

- **Transcripción:** 5.739 clips de OpenSLR (44 voces) y 10.393 de Common Voice. C5 cumple (97,5 % de clips con género, edad y acento); R3 no (46,4 % de horas espontáneas en fuentes históricas). F3 permanece sin medir.
- **Hablantes:** 700 sesiones históricas; Figshare aporta nueve sesiones, no 219. En CALLHOME, 159/3.168 segmentos de 15 audios inspeccionados exceden la duración del audio (dos registros). K2 no cumple; la muestra no permite extrapolar esta tasa.
- **Minuta e integral:** AMI tiene 105 reuniones con minuta completa, todas en inglés; solo el 3,5 % de las horas con minuta son de reuniones reales (M2). **V5 = 0**, frente a diez reuniones integrales requeridas en castellano.

## Riesgos y procedencia

| Riesgo | Evidencia del EDA | Qué falta medir o conseguir |
|---|---|---|
| Dominio y volumen integral | G2: **0** fuentes de videollamada; V5: **0/10** reuniones integrales | Grabar y anotar diez reuniones propias consentidas |
| Contaminación | L2: **154/171** AMI figuran en entrenamiento/ajuste de una configuración de pyannote | Auditar la versión y el entrenamiento de cada modelo candidato |
| Referencias | CALLHOME: **2/15** audios con exceso temporal; F3 y M3 sin medir | Filtrar intervalos no puntuables, doble transcripción y calibrar el juez |
| Representatividad | G1: **53,6–92,8 %** estimado desde fichas; R2 sin medición por persona | Obtener fechas de captación y edades por hablante |

Las cifras de CALLHOME son muestrales; las de G1 son estimaciones documentadas, no mediciones directas. No se asignan probabilidades de fracaso sin sustento.

## Plan básico del procesamiento

- **Obtención:** fijar originales, permisos y hashes; particionar por colaborador, serie o sesión comprobada; no inventar grupos CALLHOME.
- **Transformaciones:** comprobar audio y tiempos; preservar originales, silencio y solapamientos; excluir con trazabilidad tramos inválidos y distinguir traducciones sintéticas.
- **Estructura:** conjuntos separados de ASR, diarización y minuta, más diez reuniones propias con audio, transcripción, hablantes y minuta para la evaluación integral.

**Nuevo alcance:** evaluación modular; la evaluación integral queda como trabajo futuro hasta reunir referencias válidas.
