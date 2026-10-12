# Veredicto de viabilidad

**Documento 4 de 4 del [Hito 2](README.md)**

**Equipo:** Luisa, Bruno, Matías, Felipe.

**Datos sobre los que se decidió:** reales (OpenSLR 61, CORdeBA, Humyn LATAM,
AMI, ICSI, VoxConverse). Los códigos son celdas del
[notebook](notebooks/eda_viabilidad.ipynb).

---

## 1. Decisión

**Ajustar el alcance:** el producto es en castellano y se evalúa por módulo.

| Módulo | Veredicto | Con qué datos |
|---|---|---|
| Transcripción | Ajustar | Castellano rioplatense: lectura completa; espontáneo, después de alinear CORdeBA |
| Separación de hablantes | Seguir | AMI e ICSI (inglés): 91 reuniones que pyannote no vio |
| Minuta | Ajustar | AMI traducido al castellano (dataset derivado), con sus enlaces de evidencia |
| De punta a punta | Sin datos | 10 reuniones propias en castellano |

## 2. Fundamentos

- **Cada módulo tiene datos:** 15,0 h de audio rioplatense de 44 hablantes
  (`V1`), 700 sesiones con hablantes y tiempos (`V3`), 105 reuniones con
  minuta completa y el 90,5% de sus decisiones y acciones enlazadas a la
  transcripción (`M1`, `C4`).
- **El producto completo no tiene:** 0 reuniones en castellano con audio,
  transcripción, hablantes y minuta (`V5`), y 0 minutas en castellano (`R5`).
- **Pesó más `V5`:** ninguna fuente pública cubre el caso completo, pero lo
  que falta se puede producir.

## 3. Exposición al riesgo

Exposición = probabilidad × impacto, en horas de trabajo.

| Propiedad estimada | Riesgo (cifra) | Procedencia | Qué haría falta para medirla |
|---|---|---|---|
| Modalidad (`G2`) | El error medido en sala o en lectura no vale para videollamada: 0,6 × 12 h = **7,2 h** | 0 de 4 fuentes de videollamada (documentación) | Reuniones propias por videollamada |
| Cobertura de CORdeBA (`C1`) | El texto no se alinea solo con el audio: 0,4 × 15 h = **6,0 h** | Sin tiempos; 3 de 23 grabaciones bajo 100 palabras/min | Probar la alineación en 2 grabaciones |
| Traducción (`R5`) | La minuta sobre texto traducido no predice el resultado en castellano real: 0,5 × 10 h = **5,0 h** | 0 de 142 minutas en castellano | Comparar con las reuniones propias |
| Datos ya vistos (`L2`) | La minuta sobre AMI da mejor porque el modelo ya la vio: 0,7 × 6 h = **4,2 h** | Minutas públicas hace más de 15 años | Comparar con las reuniones propias |
| Edad (`R2`) | Transcribe peor a mayores de 50 y no se ve: 0,3 × 8 h = **2,4 h** | Mediana de 24 años (ficha de CORdeBA) | Common Voice 26, que trae edad |
| Error de la referencia (`F1`, `F3`) | Más de 2% de error en las transcripciones: 0,35 × 5 h = **1,8 h** | No medido; 20 de 28 filas de Humyn contradicen su ficha | Doble transcripción de 44 clips |

**Total: 26,6 h.** Riesgo del ajuste: no completar las 10 reuniones propias,
0,4 × 35 h = **14 h**.

## 4. Consecuencias de la decisión

| | Plan |
|---|---|
| Obtención y conjunto de evaluación | Un conjunto por módulo, congelado con su huella antes de ajustar nada. Transcripción: OpenSLR 61 partido por hablante, más CORdeBA y Humyn Argentina. Hablantes: las 91 reuniones de AMI e ICSI que pyannote no vio. Minuta: AMI partido por serie (`L4`). Punta a punta: 10 reuniones propias |
| Limpieza y transformaciones | Fuera: 78 clips repetidos, 12 turnos de duración cero, 47 marcadores `*NA*`, 1 audio ilegible, las filas de Humyn que no están en castellano. Texto normalizado (minúsculas, comillas, marcas de oralidad). CORdeBA se alinea con su audio. AMI se traduce al castellano (transcripción y minuta), marcado como sintético |
| Estructura final | Transcripción: audio + texto. Hablantes: audio + turnos (hablante, inicio, fin). Minuta: turnos + ítems (tipo, texto, citas). Cada fila con fuente, partición y origen (real o sintético) |

**Alcance nuevo:**

1. Castellano. Cada módulo se evalúa con su fuente; no hace falta un dataset
   que tenga todo.
2. La minuta se evalúa sobre AMI traducido, con verificaciones
   determinísticas, cobertura contra la referencia y un LLM como juez
   calibrado contra anotación humana (`M3`). Las citas se validan contra los
   enlaces de evidencia de AMI.
3. El producto completo se evalúa con 10 reuniones propias, anotadas igual
   que AMI (transcripción, hablantes, minuta y evidencias).

**Qué quedó afuera:** afirmar algo sobre reuniones reales en castellano antes
de tener las propias; hablantes de fuera de Buenos Aires; VoxConverse como
evaluación principal (pyannote entrenó con él).
