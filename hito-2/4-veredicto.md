# Veredicto de viabilidad

**Documento 4 de 4 del [Hito 2](README.md)**

**Equipo:** Luisa, Bruno, Matías, Felipe.

**Datos sobre los que se decidió:** reales (AMI, ICSI, VoxConverse). Los
códigos son celdas del [notebook](notebooks/eda_viabilidad.ipynb).

---

## 1. Decisión

**Ajustar el alcance.**

## 2. Fundamentos

- **Volumen, completitud y corrección cumplen:** 171,6 h transcriptas de 250
  hablantes (`V1`), 222 reuniones completas (`V5`), audio disponible para las
  246 (`K3`).
- **Vigencia no cumple:** 0% del material es posterior a 2015 (`G1`) y
  ninguna fuente es de videollamada (`G2`).
- **Pesó más la vigencia:** los datos sostienen la evaluación sobre reuniones
  presenciales; sobre videollamada hay que medir con datos propios.

## 3. Exposición al riesgo

Exposición = probabilidad × impacto, en horas de trabajo.

| Propiedad estimada | Riesgo (cifra) | Procedencia | Qué haría falta para medirla |
|---|---|---|---|
| Modalidad (`G2`) | El error medido en sala no vale para videollamada: 0,6 × 12 h = **7,2 h** | 0 de 3 fuentes de videollamada (documentación) | 5 reuniones propias por videollamada |
| Datos ya vistos por Whisper (`L2`) | El error de transcripción sale mejor que en uso real: 0,5 × 4 h = **2,0 h** | Whisper no publica sus datos; AMI e ICSI son públicos hace más de 15 años | Comparar con las reuniones propias |
| Error de la referencia (`F3`) | Más de 2% de error en la transcripción de referencia: 0,2 × 5 h = **1,0 h** | No medido; los tiempos sí coinciden con el audio (AUC 0,89, `F1`) | Doble transcripción de los 24 extractos |

**Total: 10,2 h.**

## 4. Consecuencias de la decisión

| | Plan |
|---|---|
| Obtención y conjunto de evaluación | Evaluación: **91 reuniones** que pyannote no vio (16 de AMI + 75 de ICSI). Ajuste de parámetros: las 18 de AMI de su parte de ajuste. Partición por serie y por hablante (`L4`). Audio: 19,8 GB, con las URL de `reuniones.csv`. La lista se congela con su huella antes de ajustar nada |
| Limpieza y transformaciones | Se descartan 2 turnos de duración cero, los turnos sin palabras y la lectura de dígitos. Texto en minúsculas y sin puntuación. Audio a 16 kHz mono (ya lo está, salvo 1 archivo estéreo) |
| Estructura final | Por reunión: audio, turnos (hablante, inicio, fin, texto) y partición |

**Alcance nuevo:**

1. Inglés; transcribir y separar hablantes.
2. Métricas: error por palabra, error de diarización y el error combinado
   (palabra + hablante), sobre las 91 reuniones.
3. La minuta se evalúa solo con AMI (142 reuniones, partidas por serie) con
   verificaciones determinísticas, cobertura contra la referencia con
   embeddings y un LLM como juez calibrado contra anotación humana. El LLM
   generador se define después. Se planea validar las citas (posiblemente por
   coincidencia exacta de texto); aún no.
4. Los resultados valen para reuniones presenciales con micrófono cercano.
   La videollamada se mide aparte, con 5 reuniones propias.

**Qué quedó afuera:** castellano; VoxConverse como
evaluación principal (pyannote entrenó con él y no tiene transcripción).
