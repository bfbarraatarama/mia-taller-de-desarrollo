# Adquisición y verificación de fuentes

Este procedimiento recupera los originales necesarios para verificar los datos del Hito 2. No construye la muestra ni ejecuta el EDA.

## Requisitos

- Python 3.12 o posterior, `venv`, `pip` y acceso a Internet.
- Aceptación individual de las condiciones de las fuentes restringidas.
- Espacio disponible para los archivos originales y temporales.
- Ejecutar los comandos desde la raíz del repositorio.

Instalación del entorno en Linux o macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r hito-2/requirements-adquisicion.txt
```

En Windows (PowerShell):

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r hito-2/requirements-adquisicion.txt
```

Los comandos posteriores utilizan el intérprete del entorno virtual y no requieren su activación. Esta instalación mínima permite adquirir originales y ejecutar las pruebas de adquisición; **no** incluye las dependencias de `armar_muestra.py`, del notebook ni de sus pruebas. Para la suite completa debe instalarse también `requirements.txt`, según `README.md`.

## Credenciales

- **Mozilla Data Collective:** crear una credencial en *Account > Credentials*, después de aceptar los términos de Common Voice 26 Rioplatense. Variable requerida: `MDC_API_KEY`.
- **Hugging Face:** aceptar las condiciones de acceso de `talkbank/callhome`, crear un token de lectura con permiso para repositorios públicos restringidos. Variable requerida: `HF_TOKEN`.
- Las autorizaciones son personales. No compartir tokens ni datos restringidos sin permiso de la fuente.

En Bash, introducir las credenciales sin escribirlas en el historial:

```bash
read -rsp 'MDC_API_KEY: ' MDC_API_KEY; echo
export MDC_API_KEY
read -rsp 'HF_TOKEN: ' HF_TOKEN; echo
export HF_TOKEN
```

En PowerShell:

```powershell
$env:MDC_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'MDC_API_KEY' -AsSecureString)).Password
$env:HF_TOKEN = [System.Net.NetworkCredential]::new('', (Read-Host 'HF_TOKEN' -AsSecureString)).Password
```

Las variables duran únicamente en la sesión de terminal. No guardar credenciales en el repositorio ni incluirlas en capturas o registros compartidos. Si se usan archivos privados locales, ubicarlos fuera de la sincronización y del árbol de Git.

## Adquisición

Desde la raíz del repositorio, en Linux o macOS:

```bash
.venv/bin/python -I hito-2/scripts/descargar_fuentes.py anotaciones
.venv/bin/python -I hito-2/scripts/descargar_fuentes.py slr61 cordeba
.venv/bin/python -I hito-2/scripts/descargar_fuentes.py common_voice
.venv/bin/python -I hito-2/scripts/descargar_fuentes.py callhome
```

`callhome` es complementario y requiere acceso aprobado. `humyn` se conserva como fuente evaluada previamente, pero no forma parte del núcleo seleccionado. Para recuperar esa fuente, ejecutar el grupo `humyn` por separado.

**UBA Games (CONICET):** el inventario esperado está declarado en `fuentes.toml`, pero no se verificaron todos los enlaces individuales del repositorio CONICET. El comando `uba_games` sigue bloqueado para evitar enlaces ambiguos. No declarar adquirido el corpus completo.

**UBA Games (Figshare v2):** distribución diferenciada del estudio SIS, identificada por DOI `10.6084/m9.figshare.22647313.v2`. El repositorio registra por separado `phrases.rar` y `wavs.rar`, sus tamaños y MD5 publicados. El comando de adquisición reutiliza los originales locales si son verificables, fija sus SHA-256 en `fuentes.lock.json` y no sustituye la distribución original de CONICET.

```bash
.venv/bin/python -I hito-2/scripts/descargar_fuentes.py uba_games_figshare
.venv/bin/python -I hito-2/scripts/descargar_fuentes.py comprobar
```

La preparación se realiza desde el constructor general de muestras:

```bash
.venv/bin/python -I hito-2/scripts/armar_muestra.py uba_games_figshare
```

Este proceso requiere `libarchive` en el sistema operativo y las dependencias de `requirements.txt`. En Ubuntu, debe poder encontrarse `libarchive.so`. El archivo comprimido se lee sin extracción permanente: se preservan los 219 pares de tareas de las nueve sesiones originales disponibles en Figshare. El programa comprueba las referencias y el audio, conserva los intervalos de silencio y produce las tablas `grabaciones.csv`, `intervalos.parquet`, `hablantes.csv` y `extractos.csv`, junto con `procedencia.json`.

Se genera determinísticamente un extracto acústico por sesión cuando existe un par válido de pistas. La mezcla de canales se realiza con media aritmética sobre PCM de 16 bits; no se elimina el solapamiento temporal. Los FLAC derivados quedan excluidos del versionado mediante `.gitignore`.

El resultado de la normalización es evidencia estructural, no una decisión de viabilidad. Las transcripciones incluyen anotaciones no verbales cuya política de puntuación deberá establecerse antes de generar referencias RTTM definitivas. Los grupos se establecen por sesión para prevenir dependencias entre tareas de una misma conversación.

La publicación Figshare declara CC BY 4.0. Antes de redistribuir audio, transcripciones o derivados, verificar si las condiciones del corpus original imponen restricciones adicionales. No versionar los RAR originales. Los datos generados deben revisarse antes de incorporarlos al repositorio compartido.

Para reconstruir además el índice y los extractos de AMI e ICSI utilizados históricamente:

```bash
.venv/bin/python -I hito-2/scripts/descargar_fuentes.py audio
```

La adquisición puede tardar y ocupar varios gigabytes. Se recomienda ejecutar primero los grupos individuales, comprobarlos y continuar. Los originales y cachés auxiliares se guardan bajo `hito-2/.cache/`, ignorado por Git.

## Verificación y congelamiento

```bash
.venv/bin/python -I hito-2/scripts/descargar_fuentes.py comprobar

# Pruebas de adquisición (compatibles con el entorno mínimo de esta sección)
.venv/bin/python -m unittest discover -s hito-2/tests -p 'test_adquisicion.py' -v
.venv/bin/python -m unittest discover -s hito-2/tests -p 'test_descargar_fuentes.py' -v
```

Para ejecutar **todas** las pruebas, incluidas las de procesamiento y serialización de Parquet, instalar además `requirements.txt` y utilizar el comando de pruebas completas de `README.md`. No se omiten pruebas por falta de dependencias: se distinguen el entorno mínimo de adquisición y el entorno completo.

- `comprobar` verifica tamaño, SHA-256 y estructura ZIP de los archivos registrados; **no prueba completitud del corpus** ni calidad de etiquetas.
- Los hashes de los originales históricos se contrastan con `muestra/MANIFIESTO.json`. Una discrepancia detiene la adquisición; no cambiar el hash para forzar que pase.
- `fuentes.lock.json` registra hashes adquiridos, inventario y revisión de repositorios Hugging Face. Revisar y versionar el archivo **sólo después** de comprobar la adquisición, el inventario oficial y las restricciones de cada fuente.
- No versionar `.cache/`, claves, URLs firmadas temporales ni originales cuya redistribución no esté autorizada.
- Para verificar completitud, comparar el inventario remoto de cada revisión con sus archivos locales y después contrastar los registros y anotaciones originales con las tablas generadas. Esta segunda comprobación se realiza en la fase de normalización.
- No ejecutar `armar_muestra.py` ni actualizar los cuatro documentos del Hito 2 hasta terminar esas comprobaciones.

## Reproducción por el equipo

Cada integrante utiliza su propio entorno y credenciales autorizadas. Tras incorporar el `fuentes.lock.json` revisado al repositorio, el descargador debe reutilizar archivos correctos y rechazar versiones distintas. Si una fuente deja de estar accesible o cambia, documentar la incidencia; no reemplazar silenciosamente versiones ni mezclar conjuntos entre integrantes.

Las tablas históricas versionadas permiten inspeccionar el EDA anterior sin descargas. La ejecución **completa** del notebook actualizado requiere los TSV Common Voice, las cinco tablas normalizadas y la auditoría acústica local: por licencias y tamaño, esas entradas no se versionan. La ruta de reproducción completa y la inspección sin credenciales están diferenciadas en [`README.md`](README.md). Ningún integrante debe compartir originales restringidos ni tokens para facilitar la ejecución.