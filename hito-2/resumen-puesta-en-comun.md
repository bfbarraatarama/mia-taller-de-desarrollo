# Hito 2 en una página

**Equipo:** Luisa, Bruno, Matías, Felipe · **Alcance:** reuniones en inglés; transcribir y separar hablantes

## 1. Qué hicimos y cómo

El objetivo del hito fue responder una pregunta: ¿existen datos públicos que permitan evaluar un sistema que transcribe reuniones y separa hablantes?

**Paso 1 — Buscar y obtener las fuentes** · [1-mapa-de-fuentes.md](1-mapa-de-fuentes.md)
Listamos todas las fuentes candidatas, evaluamos disponibilidad, licencia y volumen, y descartamos las que no cubrían el alcance (castellano, portugués, sin relación con las dos etapas). Quedaron tres fuentes públicas: AMI, ICSI y VoxConverse. 

**Paso 2 — Fijar los niveles antes de medir** · [niveles-a-priori.md](niveles-a-priori.md)
Antes de abrir los datos escribimos los 23 umbrales mínimos que el producto necesita cubrir: horas, completitud, corrección, vigencia, representatividad y confiabilidad. Los niveles de minuta (M1–M3) se agregaron después de ver qué anotaciones trae AMI, pero antes de correr ninguna medición.

**Paso 3 — Armar la muestra** · [`scripts/armar_muestra.py`](scripts/armar_muestra.py)
No trabajamos sobre los datos crudos directamente. Un script descargó las fuentes y construyó una muestra estructurada: tablas en CSV y Parquet con reuniones, hablantes, turnos y minutas, más 24 extractos de audio de 30 segundos. Esa muestra es lo que está en [`muestra/`](muestra/) y lo que se puede reproducir sin descargar los 26 GB de audio completo.

**Paso 4 — Correr el EDA** · [notebooks/eda_viabilidad.ipynb](notebooks/eda_viabilidad.ipynb)
El notebook midió cada uno de los 23 niveles celda por celda. También buscó exposición a leakage: columnas que el modelo no debería ver, reuniones que pyannote ya usó para entrenarse y hablantes repetidos entre particiones. Los resultados quedaron guardados en [`resultados_eda.csv`](../resultados_eda.csv) y [`resultados_leakage.csv`](../resultados_leakage.csv), y se generaron 4 gráficos en [`figuras/`](figuras/).

**Paso 5 — Documentar los datos** · [3-datasheet.md](3-datasheet.md)
Completamos la datasheet abreviada: qué representa cada tabla, qué falta, qué errores hay, cómo se recolectó y para qué no deberían usarse los datos.

**Paso 6 — Decidir** · [4-veredicto.md](4-veredicto.md)
Con los resultados del EDA tomamos una decisión explícita: ajustar el alcance. No descartamos los datos sino que acotamos qué se puede concluir con ellos. Las consecuencias concretas quedaron escritas en el veredicto.

---

## 2. Lo esencial

23 niveles: 15 se cumplen, 4 no, 2 en parte, 2 pendientes.

| Propiedad | Número |
|---|---|
| Volumen | 171,6 h transcriptas, 250 hablantes, 222 reuniones completas |
| Completitud | 100% de los audios con transcripción y hablantes |
| Corrección | 246 de 246 audios disponibles; 0 duplicados; 2 turnos inválidos |
| Vigencia | **0% posterior a 2015; 0 fuentes de videollamada** |
| Representatividad | 57,8% de las horas son reuniones reales; mujeres: 37,2% (AMI) y 21,1% (ICSI) del habla |
| Confiabilidad | Los tiempos anotados coinciden con el audio (AUC 0,89) |
| *Leakage* | pyannote entrenó con 154 de las 171 reuniones de AMI. Quedan 91 no vistas |

**Veredicto: ajustar el alcance.**

1. **Obtención:** evaluación sobre 91 reuniones (16 AMI + 75 ICSI), partidas por serie y hablante.
2. **Limpieza:** fuera turnos inválidos, turnos sin palabras y lectura de dígitos; texto normalizado.
3. **Estructura:** por reunión, audio + turnos (hablante, inicio, fin, texto).

## 2. La decisión que tomamos, y qué descartamos

- Solo inglés, solo transcribir y separar hablantes.
- Evaluar sobre las 91 reuniones que pyannote no vio.
- Descartado: fuentes en castellano; VoxConverse como evaluación principal.

## 3. Nuestro mayor riesgo

Los datos son de sala, de 2001–2005. El error en videollamada puede ser
distinto, y solo se mide con reuniones propias.

## 4. Qué necesitamos del docente

- Si 5 reuniones propias alcanzan para medir la brecha con videollamada.
