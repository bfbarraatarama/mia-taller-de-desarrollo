# Pipeline de procesamiento de audio y generación de minutas

## Objetivo

Desarrollar un pipeline modular que permita grabar reuniones, identificar hablantes, transcribir el audio, nombrar a cada hablante y generar automáticamente una minuta estructurada en formato Markdown, siguiendo los campos definidos a partir del corpus AMI.

Cada etapa debe contar con un contrato de entrada y salida que permita su desarrollo, integración y validación de manera independiente. Las etapas 2 y 3 procesan el mismo `audio.wav` por separado y no dependen entre sí (decisión 3.1.3 de la [definición de la PoC](definicion-de-la-poc.md)).

```
                          ┌─ 2. Diarización ─▶ diarization.json ─┐
1. Grabación ─▶ audio.wav ┤                                      ├─▶ 4. Asociación y etiquetado ─▶ transcription.json ─▶ 5. Minuta ─▶ minutes.md
                          └─ 3. STT ─────────▶ asr.json ─────────┘        (el usuario nombra a cada hablante)
```

| Etapa | Responsable |
|---|---|
| 1. Grabación y normalización | _a completar_ |
| 2. Diarización | Luisa |
| 3. STT | Felipe |
| 4. Asociación y etiquetado de hablantes | Matías |
| 5. Minuta | Bruno |

---

## Entorno común

| Qué | Valor |
|---|---|
| Máquina de referencia | RTX 3050 Laptop, 6 GB de VRAM, 31 GB de RAM |
| Python | 3.12 para las etapas 2, 3 y 5 (PyTorch, pyannote y Whisper todavía no son confiables en 3.14); las etapas 1 y 4 corren también en 3.14 |
| FFmpeg | Lo usan las etapas 1, 2 y 3. Fedora: `sudo dnf install ffmpeg` · Ubuntu: `sudo apt install ffmpeg` · Windows: `winget install Gyan.FFmpeg` · macOS: `brew install ffmpeg` |
| Entornos | Uno para la interfaz (etapas 1 y 4) y otro compartido por las etapas 2 y 3 (comparten PyTorch, unos 3 GB). La etapa 5 solo necesita Python y Ollama |
| Memoria de la GPU | Diarización, Whisper `medium` (unos 5 GB) y `qwen2.5:7b` (4,7 GB) no entran juntos: **cada etapa libera la GPU al terminar** y se ejecutan en secuencia |

---

## Etapa 1. Grabación y normalización de audio

**Responsable:** _a completar_

**Objetivo:** Capturar el audio de una reunión mediante una interfaz y generar un archivo WAV normalizado.

### Contrato de entrada
- Fuente de audio: micrófono y audio del sistema, o uno o varios archivos cargados en orden.
- Parámetros de grabación.

### Contrato de salida
- `audio.wav`: archivo de audio normalizado. Si se cargaron varios archivos, se unen en orden en un solo `audio.wav`.
- Formato recomendado: WAV, PCM 16 bits, mono, 16 kHz.

### Contrato entre etapas 1 → 2 y 1 → 3
- Archivo `audio.wav` normalizado.

### Herramientas

| Herramienta | Versión | Para qué | Instalación |
|---|---|---|---|
| sounddevice (PortAudio) | ≥ 0.5 | Capturar micrófono y audio del sistema | `pip install sounddevice` |
| soundfile (libsndfile) | ≥ 0.12 | Escribir el WAV mientras se graba | `pip install soundfile` |
| NumPy | ≥ 1.26 | Mezclar las fuentes a mono | `pip install numpy` |
| SciPy | ≥ 1.13 | Remuestrear de 48 kHz a 16 kHz (`scipy.signal.resample_poly(x, 1, 3)`) | `pip install scipy` |
| PySide6 (Qt) | ≥ 6.8 | Interfaz: elegir dispositivos y carpeta, grabar, detener | `pip install pyside6-essentials` |
| FFmpeg | sistema | Normalizar y unir archivos cargados | ver Entorno común |
| Audio del sistema | — | Linux: fuente *monitor* de PipeWire o PulseAudio · Windows: loopback WASAPI o cable virtual (VB-Cable) · macOS: BlackHole | según el sistema |

**Normalizar un archivo existente:**

```bash
ffmpeg -i entrada.mp3 -vn -ac 1 -ar 16000 -c:a pcm_s16le audio.wav
```

**Requisitos de la definición de la PoC:**
- Escribir el WAV **mientras se graba** (cola entre el *callback* de sounddevice y un hilo que escribe con `soundfile.SoundFile`): ante un cierre forzado se pierden 5 s o menos, y la grabación queda marcada como interrumpida para ofrecerla al reiniciar (2.1, error del sistema).
- Conservar las pistas originales (micrófono y sistema) antes de mezclarlas a mono.

**Para probar sola:** comprobar con `soundfile.info("audio.wav")` que da 16 000 Hz, 1 canal y `PCM_16`.

---

## Etapa 2. Diarización de hablantes

**Responsable:** Luisa

**Objetivo:** Identificar los intervalos temporales correspondientes a cada hablante y asignar un identificador único.

### Contrato de entrada
- `audio.wav`: archivo generado en la etapa 1.
- Token de Hugging Face para acceder al modelo de diarización.

### Contrato de salida
- `diarization.json`: archivo con los segmentos temporales y el identificador de cada hablante. Los segmentos de hablantes distintos pueden superponerse.

**Estructura del JSON:**

```json
{
  "segments": [
    {
      "start": 0.5,
      "end": 4.2,
      "speaker": "SPEAKER_00"
    },
    {
      "start": 4.5,
      "end": 8.1,
      "speaker": "SPEAKER_01"
    }
  ]
}
```

### Contrato entre etapas 2 → 4
- Archivo `diarization.json`.

### Herramientas

| Herramienta | Versión | Para qué | Instalación |
|---|---|---|---|
| PyTorch + torchaudio | 2.8.0, CUDA 12.8 | Correr el modelo en la GPU | `pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128` |
| pyannote.audio | ≥ 4.0 | Pipeline de diarización | `pip install "pyannote.audio>=4.0"` |
| Modelo `pyannote/speaker-diarization-community-1` | — | Quién habla y cuándo | Aceptar las condiciones en [huggingface.co/pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) |
| Token de Hugging Face (`hf` CLI) | viene con pyannote | Descargar el modelo | Crear un token de lectura en [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) y correr `hf auth login` (o exportar `HF_TOKEN`) |
| FFmpeg | sistema | pyannote 4 lo usa para leer el audio | ver Entorno común |

**Uso mínimo:**

```python
import os, json, torch
from pyannote.audio import Pipeline

p = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1", token=os.environ.get("HF_TOKEN"))
p.to(torch.device("cuda"))
out = p("audio.wav")
segments = [{"start": round(t.start, 3), "end": round(t.end, 3), "speaker": s}
            for t, s in out.speaker_diarization]
json.dump({"segments": segments}, open("diarization.json", "w"), indent=2)
del p; torch.cuda.empty_cache()   # liberar la GPU para la etapa 3
```

`out.speaker_diarization` conserva el habla superpuesta, que la etapa 4 necesita para marcarla.

**Conjunto de evaluación (2.3):** las 3 sesiones de Figshare de la muestra congelada. Contrato: cada segmento con hablante, `start < end` y `end` ≤ duración del audio.

**Para probar sola:** cualquier WAV de 16 kHz mono con dos o más voces.

---

## Etapa 3. Reconocimiento automático del habla (STT)

**Responsable:** Felipe

**Objetivo:** Convertir el audio en texto con marcas temporales por segmento y por palabra. No usa la diarización: la asociación con hablantes es la etapa 4.

### Contrato de entrada
- `audio.wav`: archivo de audio normalizado.

### Contrato de salida
- `asr.json`: transcripción con tiempos por segmento y por palabra.

**Estructura del JSON:**

```json
{
  "language": "es",
  "segments": [
    {
      "start": 0.5,
      "end": 4.2,
      "text": "Vamos a revisar los resultados.",
      "words": [
        {"word": "Vamos", "start": 0.5, "end": 0.8},
        {"word": "a", "start": 0.8, "end": 0.9}
      ]
    }
  ]
}
```

### Contrato entre etapas 3 → 4
- Archivo `asr.json`.

### Herramientas

| Herramienta | Versión | Para qué | Instalación |
|---|---|---|---|
| PyTorch | 2.8.0, CUDA 12.8 | Igual que la etapa 2 (mismo entorno) | ver etapa 2 |
| openai-whisper | última | Transcripción en castellano con marcas temporales por palabra | `pip install openai-whisper` |
| Modelo Whisper `medium` | — | Unos 5 GB de VRAM; 1,5 GB de descarga | Se baja solo en el primer `load_model("medium")` |
| FFmpeg | sistema | Whisper lo usa para leer el audio | ver Entorno común |

**Uso mínimo:**

```python
import json, whisper, torch

m = whisper.load_model("medium", device="cuda")
r = m.transcribe("audio.wav", language="es", word_timestamps=True)
asr = {"language": "es", "segments": [
    {"start": s["start"], "end": s["end"], "text": s["text"].strip(),
     "words": [{"word": w["word"].strip(), "start": w["start"], "end": w["end"]} for w in s["words"]]}
    for s in r["segments"]]}
json.dump(asr, open("asr.json", "w"), ensure_ascii=False, indent=2)
del m; torch.cuda.empty_cache()   # liberar la GPU
```

Se transcribe **el audio completo una vez**. No conviene cortarlo por segmento de diarización: Whisper pierde contexto y tiende a inventar texto en fragmentos cortos.

**Plan B de memoria (riesgo 1.4.1):** Whisper `small` (unos 2 GB) o `device="cpu"`, registrando el cambio.

**Conjunto de evaluación (2.3):** los 5 clips de OpenSLR y Common Voice de la muestra congelada. Contrato: segmentos con texto y tiempos.

**Para probar sola:** cualquier audio corto propio en castellano.

---

## Etapa 4. Asociación y etiquetado de hablantes

**Responsable:** Matías

**Objetivo:** Unir la diarización con la transcripción y, mediante una interfaz, que el usuario escuche un fragmento de cada hablante, lea su texto y escriba su nombre, para que la transcripción y la minuta queden con nombres reales.

### Contrato de entrada
- `audio.wav`: archivo de audio normalizado.
- `diarization.json`: archivo generado en la etapa 2.
- `asr.json`: archivo generado en la etapa 3.

### Contrato de salida
- `speakers.json`: nombre que el usuario le dio a cada etiqueta y el fragmento que escuchó.
- `transcription.json`: transcripción estructurada con tiempos, texto, hablante, nombre y marcas de confianza.

**Estructura de `speakers.json`:**

```json
{
  "SPEAKER_00": {"name": "Luisa", "clip_start": 12.3, "clip_end": 24.8},
  "SPEAKER_01": {"name": null, "clip_start": 40.1, "clip_end": 49.6}
}
```

**Estructura de `transcription.json`:**

```json
{
  "segments": [
    {
      "start": 0.5,
      "end": 4.2,
      "speaker": "SPEAKER_00",
      "name": "Luisa",
      "text": "Vamos a revisar los resultados.",
      "overlap": false,
      "ambiguous": false
    },
    {
      "start": 4.5,
      "end": 8.1,
      "speaker": "SPEAKER_01",
      "name": null,
      "text": "Estoy de acuerdo con la propuesta.",
      "overlap": false,
      "ambiguous": false
    }
  ]
}
```

### Contrato entre etapas 4 → 5
- Archivo `transcription.json` con la transcripción completa, los hablantes con su nombre (o `null`) y las marcas de confianza.

### Cómo funciona

1. **Asociación.** A cada palabra de `asr.json` se le asigna el hablante de `diarization.json` que más se le superpone en el tiempo. Las palabras seguidas del mismo hablante forman una intervención. Se asocia por palabra porque Whisper corta los segmentos por pausas, no por cambio de hablante.
2. **Marcas de confianza (2.2, punto 2).**
   - `overlap`: la intervención tiene 0,2 s o más en un tramo con dos o más hablantes.
   - `ambiguous`: ningún turno la cubre, o un segundo hablante cubre el 30 % o más de su duración.
3. **Fragmento por hablante.** Se elige el tramo más largo en que esa persona habla sola, recortado a 15 s; si no tiene ninguno de al menos 5 s, se usa el más largo que haya. Su texto son las palabras de `asr.json` que caen dentro del tramo.
4. **Interfaz de etiquetado (2.2, punto 5).** Al terminar las etapas 2 y 3, el procesamiento se detiene y muestra una ficha por hablante, ordenadas por tiempo de habla:

   ```
   ┌───────────────────────────────────────────────────────────┐
   │ SPEAKER_00 · habla 6 min 12 s                             │
   │ [▶ Reproducir]  [Otro fragmento]                          │
   │ "Bueno, arrancamos con el tema del presupuesto que..."    │
   │ Nombre: [ Luisa                    ]                      │
   ├───────────────────────────────────────────────────────────┤
   │ SPEAKER_01 · habla 3 min 40 s                             │
   │ ...                                                       │
   └───────────────────────────────────────────────────────────┘
                                       [Confirmar y seguir]
   ```

   - **Otro fragmento:** muestra el siguiente tramo más largo, por si no se reconoce la voz.
   - **Nombre vacío:** queda `null` y se usa la etiqueta.
   - **Mismo nombre en dos etiquetas:** se tratan como una persona (caso 2.1.2: la diarización separó a alguien en dos).
   - **Confirmar:** escribe `speakers.json` y `transcription.json`, y sigue con la etapa 5.
5. **Sin interfaz** (línea de comandos): el etiquetado se saltea, `name` queda en `null` y no se escribe `speakers.json`.
6. **Latencia (2.3):** el tiempo que el usuario tarda en etiquetar no se cuenta.

### Herramientas

| Herramienta | Versión | Para qué | Instalación |
|---|---|---|---|
| Python (sin bibliotecas extra) | 3.12 o 3.14 | Asociación y marcas de confianza | — |
| soundfile + NumPy | ≥ 0.12 / ≥ 1.26 | Recortar el fragmento de `audio.wav` | `pip install soundfile numpy` |
| sounddevice | ≥ 0.5 | Reproducir el fragmento (`sd.play(x, 16000)`) | `pip install sounddevice` |
| PySide6 (Qt) | ≥ 6.8 | Fichas de hablantes dentro de la GUI de la etapa 1 | `pip install pyside6-essentials` |

No usa la GPU.

**Conjunto de evaluación (2.3):** las salidas de las etapas 2 y 3 sobre las 3 sesiones de Figshare de la muestra congelada. Contrato: cada intervención con etiqueta, nombre o `null`, texto, tiempos y marcas de confianza.

**Para probar sola:** un audio corto propio con un `diarization.json` y un `asr.json` escritos a mano.

---

## Etapa 5. Generación de minuta estructurada

**Responsable:** Bruno

**Objetivo:** Procesar la transcripción estructurada y generar una minuta de reunión en formato Markdown, utilizando los campos definidos a partir del corpus AMI.

### Contrato de entrada
- `transcription.json`: archivo generado en la etapa 4.

### Contrato de salida
- `minutes.md`: archivo Markdown con la minuta estructurada.

### Campos propuestos
- Información general de la reunión.
- Resumen de la reunión.
- Temas tratados.
- Decisiones tomadas.
- Acciones o tareas identificadas.
- Responsables.
- Referencias temporales a la transcripción.

La estructura definitiva deberá ajustarse a los campos del esquema AMI seleccionado. En la muestra del Hito 2 ([`minutas.parquet`](../hito-2/muestra/ami/minutas.parquet)), los ítems de AMI son de cuatro tipos: `resumen`, `decision`, `problema` y `accion`.

### Herramientas

| Herramienta | Versión | Para qué | Instalación |
|---|---|---|---|
| Ollama | ≥ 0.5 (salida con esquema JSON) | Servidor local del LLM | Linux: `curl -fsSL https://ollama.com/install.sh \| sh` · Windows y macOS: [ollama.com/download](https://ollama.com/download) |
| Modelo `qwen2.5:7b` | Q4_K_M, 4,7 GB | Generar la minuta en castellano | `ollama pull qwen2.5:7b` |
| Cliente `ollama` para Python | última | Llamar al modelo (o HTTP directo a `http://localhost:11434/api/chat`) | `pip install ollama` |
| Python (sin bibliotecas extra) | — | Pasar la respuesta JSON a `minutes.md` | — |

**Uso mínimo:**

```python
import json, ollama

texto = "\n".join(f"[{s['start']:.1f}] {s['name'] or s['speaker']}: {s['text']}"
                  for s in json.load(open("transcription.json"))["segments"])
r = ollama.chat(model="qwen2.5:7b",
                messages=[{"role": "system", "content": PROMPT},
                          {"role": "user", "content": texto}],
                format=ESQUEMA_JSON,                      # esquema de la minuta
                options={"temperature": 0, "seed": 0, "num_ctx": 16384})
minuta = json.loads(r["message"]["content"])              # después se escribe minutes.md
```

**Requisitos:**
- **Fijar `num_ctx`.** El valor por defecto de Ollama es mucho menor que el contexto de Qwen2.5 (32 768 tokens), y lo que no entra se descarta sin aviso. Si la transcripción no entra ni con el máximo, se procesa por fragmentos y se consolida (caso 2.1.5).
- Pedir la respuesta con un **esquema JSON** (`format`) y armar `minutes.md` desde ese JSON: así se puede validar que estén todas las secciones.
- La minuta tiene temas, decisiones y acciones; cada acción con su **responsable por nombre** (campo `name`, o la etiqueta si es `null`).
- Cada decisión y acción cita la marca temporal (`start`) de la intervención que la respalda (2.2).
- **Ninguna acción inventada** (2.3).

**Plan B de memoria:** `qwen2.5:3b` (1,9 GB).

**Conjunto de evaluación (2.3):** las 3 reuniones de AMI traducidas de la muestra congelada. Contrato: secciones de temas, decisiones y acciones.

**Para probar sola:** `ollama serve` corriendo y un `transcription.json` escrito a mano con 2 temas y 1 acción.

---

## Resumen de contratos entre etapas

| Etapa | Responsable | Entrada | Salida | Herramientas |
|---|---|---|---|---|
| 1. Grabación | _a completar_ | Interfaz de grabación o archivos en orden | `audio.wav` | sounddevice, soundfile, NumPy, SciPy, PySide6, FFmpeg |
| 2. Diarización | Luisa | `audio.wav` + token Hugging Face | `diarization.json` | PyTorch, pyannote.audio 4 con `speaker-diarization-community-1`, FFmpeg |
| 3. STT | Felipe | `audio.wav` | `asr.json` | PyTorch, openai-whisper `medium`, FFmpeg |
| 4. Asociación y etiquetado | Matías | `audio.wav` + `diarization.json` + `asr.json` + nombres del usuario | `speakers.json` + `transcription.json` | Python, soundfile, NumPy, sounddevice, PySide6 |
| 5. Minuta | Bruno | `transcription.json` | `minutes.md` | Ollama con `qwen2.5:7b` |

## Criterios generales de integración

1. Cada etapa debe implementarse como un módulo independiente.
2. Los contratos de entrada y salida deben mantenerse estables.
3. Los archivos JSON deben respetar la estructura definida.
4. Los campos `start` y `end` deben expresarse en segundos desde el inicio de la grabación.
5. Los identificadores `speaker` deben mantenerse consistentes entre diarización, `speakers.json` y transcripción.
6. Cada etapa debe validar sus entradas antes de iniciar el procesamiento.
7. Los módulos deben permitir pruebas independientes mediante archivos de ejemplo.
8. La salida de una etapa debe poder utilizarse directamente como entrada de la siguiente, sin transformaciones manuales.
9. Las etapas que usan la GPU (2, 3 y 5) la liberan al terminar.

## Resultado esperado

El pipeline debe permitir transformar una grabación de audio en una minuta estructurada mediante el siguiente flujo:

`Interfaz de grabación → audio.wav → diarization.json + asr.json → etiquetado de hablantes → transcription.json → minutes.md`
