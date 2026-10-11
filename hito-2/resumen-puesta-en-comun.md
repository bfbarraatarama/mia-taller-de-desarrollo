# Hito 2 en una página

**Equipo:** Luisa, Bruno, Matías, Felipe · **Alcance:** reuniones en inglés; transcribir y separar hablantes

## 1. Lo esencial

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
