# Evaluación de la Etapa 2

Contiene la preparación del dataset de test de UBA Games (sesión S26, 25 grabaciones) y las métricas de calidad (DER y JER). Cada pieza corresponde al grupo 6 y a las tareas 7.x de [`../openspec/changes/etapa-2-diarizacion/tasks.md`](../openspec/changes/etapa-2-diarizacion/tasks.md).

- **Resultados y metodología:** [`EVALUACION_S26.md`](EVALUACION_S26.md).
- **Procedimiento de preparación:** en el README del módulo, sección "Dataset de test (Figshare, sesión S26)".

| Archivo | Estado | Qué hace |
|---|---|---|
| `rar7z.py` | ✅ tarea 6.1 | Localiza 7-Zip y lista los RAR (ruta, tamaño y CRC32) sin extraer. Rechaza rutas inseguras, compara los archivos de `extraidos/` con su entrada y calcula su SHA-256 |
| `preparar_figshare.py` | ✅ tareas 6.2 a 6.4, 6.7, 6.8 y 7.6 | Opciones de la línea de comandos:<br>· `--verificar-entradas`: verifica los RAR y los archivos extraídos.<br>· `--validar`: decide si cada grabación es válida o queda excluida; admite 1 cuadro de más al final en los WAV separados.<br>· `--inventario`: lista las etiquetas sin letras.<br>· `--preparar`: genera el mono `(L + R) // 2`, el RTTM, la cobertura y el manifiesto.<br>· `--verificar`: comprueba los derivados contra el manifiesto.<br>Todas aceptan `--seleccion 01 … 25` |
| `referencia.py` | ✅ tareas 6.5 y 6.6 | Arma la referencia RTTM a partir de las anotaciones:<br>· clasifica cada línea (`#`, texto con letras o etiqueta de la política);<br>· une los intervalos de un mismo canal y conserva el solapamiento entre canales;<br>· ajusta los fines dentro de la tolerancia.<br>También valida la referencia antes de calcular las métricas y calcula el indicador de cobertura |
| `der.py` | ✅ tareas 7.1 y 7.6 | DER estricto, DER con tolerancia NIST, JER con el error por hablante y componentes. Además calcula el acumulado ponderado, los estadísticos por grabación, la cantidad de hablantes, la cobertura NIST y el error con y sin solapamiento |
| `publicar_resultados.py` | ✅ | Copia los reportes de `tests/reportes/` y las hipótesis a `resultados/`, verificando SHA-256 y que no haya rutas absolutas |
| `politica_etiquetas.json` | versionado | `-?` y `?-` = `habla` (decisión del 08/11/2026) |
| `figshare_test.manifest.json` | versionado | `contenido`, que es determinista e incluye su `contenido_sha256`, y `ejecucion`, que varía. No incluye el texto de las anotaciones |
| `resultados/` | versionado | `calidad_S26.json`, `calidad_total.json` y `hipotesis_S26/<recording_id>.json` (las 25 salidas de la corrida principal) |
| `EVALUACION_S26.md` | versionado | Documentación de la evaluación de S26 |

Los derivados (WAV mono y RTTM) se escriben en `PoC/paso2_diarizacion/datos/figshare_test/S26/`, que git ignora.
