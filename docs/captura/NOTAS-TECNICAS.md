# Captura · notas técnicas

Detalle de [`README.md`](README.md): escritura a prueba de cortes, pruebas del reporte, mediciones y problema conocido de eco.

## Escritura a prueba de cortes

| Referencia | Mecanismo |
|---|---|
| OBS (MKV, Hybrid MP4) | Contenedor legible hasta el último fragmento escrito; al terminar se "finaliza" ([KB Hybrid MP4](https://obsproject.com/kb/hybrid-mp4), [blog](https://obsproject.com/blog/obs-studio-hybrid-mp4)) |
| WAV (este script) | libsndfile `SFC_SET_UPDATE_HEADER_AUTO` reescribe la cabecera tras cada escritura ([doc](https://libsndfile.github.io/libsndfile/command.html)); `fsync` cada 5 s |

| `kill -9` a mitad de grabación | `wave` (Python) | soundfile | ffprobe | Datos en disco |
|---|---|---|---|---|
| WAV sin actualizar cabecera (3,4 s) | error: cabecera sin `data` | 3,4 s | 3,4 s | 3,4 s |
| Cabecera actualizada cada 1 s (3,4 s) | 3,0 s | 3,0 s | 3,0 s | 3,4 s |
| Cabecera automática (3,4 s) | 3,4 s | 3,4 s | 3,4 s | 3,4 s |
| `captura.py`, corte a ~5,5 s de grabación | 5,5 s | 5,5 s | 5,5 s | 5,5 s |
| `captura.py`, corte a ~112 s de grabación | 112,0 s | 112,0 s | 112,0 s | 112,0 s |

| Medición | Valor |
|---|---|
| Costo de la cabecera automática | 13,1 µs vs 12,8 µs por bloque |
| Remuestreo por bloques vs señal entera (48; 44,1; 22,05; 8 kHz, 7 s de ruido) | diferencia máxima 0,0 |

`kill -9` no pierde lo ya escrito (queda en la caché del sistema operativo); ante un corte de luz se pierden como máximo los últimos 5 s (`SYNC_SEG`).

## Pruebas del reporte

| Prueba | Criterio |
|---|---|
| Ambas fuentes registran señal | RMS > −60 dBFS (`--umbral-silencio`) |
| Sin pérdidas | 0 overflows y \|duración reloj − duración muestras\| ≤ 0,05 s + 0,1 % |
| Sin desincronización | Mismo stream, o deriva entre fuentes ≤ misma tolerancia |
| Salida procesable | `AAAA_MM_DD_HH_MM_SS.wav` mono, 16 kHz, PCM 16 |
| Tono capturado (`--tono`) | Tono de 1 kHz detectado en la pista del sistema entre −0,1 y +0,5 s del envío, con continuidad ≥ 0,98 (fracción de muestras no nulas en la pista del sistema) |

Los primeros 0,5 s de cada stream se descartan (conexión de puertos); sus overflows se informan en `overflows_calentamiento_descartado`.

## Resultado en este equipo (29/10/2026, Fedora 43, PipeWire, PortAudio 19.7)

| Corrida | Dispositivos | fs (Hz) | Overflows | Faltante (s) | Desfase (s) | Tono enviado → detectado (s) | Continuidad | Pruebas |
|---|---|---|---|---|---|---|---|---|
| CLI automático, 4 s | JACK "Audio Interno" can. 0–1 / 2–3 | 48 000 / 48 000 | 0 | 0,000 | 0 (mismo stream) | 1,086 → 1,03 | 1,0 | 5/5 |
| CLI manual, 4 s | ALSA `pipewire` / JACK can. 2–3 | 44 100 / 48 000 | 0 | −0,017 / −0,016 | 0,0017 | 1,051 → 1,03 | 1,0 | 5/5 |
| Interfaz automático, 8 s | Igual que CLI automático | 48 000 / 48 000 | 0 | 0,001 | 0 | — | — | 5/5 |
| Interfaz manual, 8 s | Igual que CLI manual | 44 100 / 48 000 | 0 | −0,001 | — | — | — | 5/5 |

| Variante de lectura (PortAudio 19.7, JACK) | Bloqueo del GIL | Overflows | Huecos en tono de 0,5 s |
|---|---|---|---|
| Callback (la usada) | 0 ms | 0 | 0 |
| Callback | ~85 ms cada 0,2 s | 15 en 4 s | — |
| Lectura bloqueante, bloque 1024 | 0 ms | 0 | 23 huecos de 512 muestras |

## Problema conocido: el audio del sistema entra por el micrófono (no resuelto)

Con parlantes, la voz de los participantes remotos sale por los parlantes y el micrófono la vuelve a captar. En `YYYY_MM_DD_HH_MM_SS.wav` esa voz queda dos veces: directa (pista sistema) y como eco atenuado y retrasado (pista mic). Con auriculares no debería ocurrir (no medido).

| Medido (29/10/2026, parlantes internos de la notebook) | Valor |
|---|---|
| Corridas con tono en que el micrófono captó el tono | 2 (reportes no conservados; salida registrada en la sesión) |
| Retardo mic vs. sistema en esas corridas | 0,06 s (1,11 vs. 1,05 s; 1,09 vs. 1,03 s) |
| Reportes conservados con tono (`retardo_mic_vs_sistema_s`) | 9, ninguno con detección en el micrófono |

| No medido | Por qué importa |
|---|---|
| Nivel del eco respecto de la pista sistema (dB) | Define si afecta a diarización y ASR |
| Efecto en pyannote (DER/JER) | El eco en la pista mic puede atribuir voz remota al hablante local o sumar un hablante |
| Efecto en ASR (WER) | Copia retrasada 60 ms superpuesta a la voz original |

El detector del tono exige 100 ms seguidos con más de la mitad de la energía en 900–1100 Hz: un eco débil o con ruido del ambiente puede no detectarse aunque exista.

### Soluciones rápidas (sin implementar)

| # | Solución | Esfuerzo | Qué resuelve | Limitación | Requiere pistas separadas |
|---|---|---|---|---|---|
| 1 | Auriculares en la máquina que graba | Nulo | Elimina la causa | No aplica a salas con parlante compartido | No |
| 2 | Cancelación de eco de PipeWire (`libpipewire-module-echo-cancel`, WebRTC) | Archivo de configuración, sin código | Saca el eco del micrófono antes de grabar | Solo Linux; la app de la reunión tiene que sonar por "Echo Cancellation Sink"; no verificado que la detección automática tome los nodos virtuales; efecto sobre la voz local no medido | No |
| 3 | Atenuar el micrófono mientras suena el sistema (*ducking*) | ~20 líneas en `Mezclador` | Quita el eco cuando hablan los remotos | Corta la voz local cuando hablan los dos a la vez, justo los solapamientos que tiene que resolver la diarización | No |
| 4 | Cancelación de eco offline con la pista sistema como referencia (`speexdsp` o `webrtc-audio-processing` de PyPI) | Script de post-proceso | Saca el eco de la pista mic; repetible y ajustable | Bindings no probados (ambos instalables en este Python 3.14); necesita retardo mic–sistema estable | Sí |
| 5 | Atribución por canal dominante: por segmento de pyannote, comparar energía mic vs. sistema y transcribir desde la pista dominante | Script sobre la salida de pyannote | El eco llega atenuado: el segmento se asigna al lado correcto y el ASR no ve la copia | No limpia la mezcla; no medido con habla simultánea | Sí |

| Verificado en este equipo | Resultado |
|---|---|
| `libpipewire-module-echo-cancel.so` | Instalado (PipeWire 1.4.11), no cargado |
| `webrtc-audio-processing` (sistema) | 1.3-9.fc43 instalado |
| `speexdsp`, `webrtc-audio-processing`, `pyaec` (PyPI) | Resuelven para el `.venv` (`uv pip install --dry-run`) |

Configuración de la opción 2, según la [documentación de PipeWire](https://docs.pipewire.org/page_module_echo_cancel.html), en `~/.config/pipewire/pipewire.conf.d/echo-cancel.conf` (método por defecto `aec/libspa-aec-webrtc`); después elegir "Echo Cancellation Source" y "Echo Cancellation Sink" como entrada y salida por defecto:

```
context.modules = [
  { name = libpipewire-module-echo-cancel
    args = {
      capture.props  = { node.name = "Echo Cancellation Capture" }
      source.props   = { node.name = "Echo Cancellation Source" }
      sink.props     = { node.name = "Echo Cancellation Sink" }
      playback.props = { node.name = "Echo Cancellation Playback" }
    }
  }
]
```

Orden sugerido para probar, de menor a mayor esfuerzo: 1 → 2 → 5 → 4. La 3 es la más barata de programar, pero degrada los solapamientos.

### Procesar las dos pistas por separado

Para tratar el eco hace falta conservar las pistas mic y sistema separadas: la pista sistema sirve de referencia para cancelarlo y cada pista identifica de qué lado está el hablante (mic = local, sistema = remotos). Hoy `captura.py` escribe solo la mezcla, así que esa separación se pierde. Recuperarla implica cambiar la salida, decisión que queda abierta:

| Opción | Archivo | Compatibilidad con pyannote |
|---|---|---|
| WAV estéreo | canal 0 = mic, canal 1 = sistema | pyannote trabaja sobre una sola señal: hay que elegir o mezclar el canal antes (comportamiento con estéreo no verificado) |
| Dos WAV mono + mezcla | `…_mic.wav`, `…_sistema.wav`, `….wav` | Directa con la mezcla; las pistas quedan para eco y atribución |
