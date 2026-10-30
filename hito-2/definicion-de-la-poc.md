# Definición de la PoC - <equipo>

**Documento del [Hito 3](README.md) · en equipo · se entrega en el repo del equipo como `definicion-de-la-poc.md`, con el tag `hito-3`**

El documento tiene cuatro partes, que siguen las de un cambio en OpenSpec: la propuesta (por qué y hasta dónde; `proposal.md`), la spec (cómo se comporta el sistema y cuándo está terminado; `specs/`), el diseño (las decisiones de diseño y la arquitectura; `design.md`) y el plan (las tres semanas de construcción; `tasks.md`). Los datos y el plan del pipeline vienen del Hito 2; el código se escribe en el Módulo 4.

| # | Parte | Secciones | Cuándo se completan |
|---|---|---|---|
| 1 | Propuesta | 1.1 Overview; 1.2 Objetivo; 1.3 Fuera de alcance; 1.4 Riesgos | 1.1 y 1.2 en la Clase 5; 1.3 y 1.4 en la Clase 6 |
| 2 | Spec | 2.1 Escenarios; 2.2 User experience; 2.3 Criterios de aceptación | Clase 6 |
| 3 | Diseño | 3.1 Decisiones de diseño, un registro por decisión; 3.2 Arquitectura | El registro del modelo en la Clase 5; los demás y 3.2 en la Clase 6 |
| 4 | Plan | 4.1 Plan de construcción | Clase 6 |

**Extensión.** No más de 3.000 palabras.

**Agente de código.** Pueden usar cualquier agente disponible. En la materia recomendamos OpenSpec, que parte el documento en esos cuatro archivos, pero también pueden hacerlo completamente manual, en este archivo.

**Incógnitas.** Lo que el equipo no sepa o no pueda responder se escribe como **No sabemos**. Dejar una sección o una celda en blanco no distingue lo que no se sabe de lo que no se analizó.

## Historial de versiones

| Versión | Fecha | Qué cambió |
|---|---|---|
| 1, Hito 3 | | |

Si el documento vive en varios archivos, indicar acá dónde está cada parte.

---

## 1. Propuesta

### 1.1 Overview

Describe qué hace la PoC, para quién, y con qué datos cuenta para construirse (el veredicto del Hito 2, y si los datos son reales, sintéticos o los dos). La descripción va en un párrafo, y dice qué entra en este alcance y qué del producto queda afuera por ahora. Remite a los fundamentos del veredicto del Hito 2 con la cifra del EDA que sostiene ese alcance, sin reescribirlos; si el veredicto fue ajustar, dice el alcance nuevo.

- El producto es una aplicación ejectuada de manera local que transforma grabaciones de reuniones en minutas con los temas relevantes y acccionables pensado para organizaciones con terminologías complejas y e información confidencial.
- La PoC captura el micrófono y el audio del sistema (usuario y resto de los participantes), adapta el audio a un formato genérico, identifica quién hablo en cada momento, transcribe la reunión entera, y genera una minuta con temas importantes y acciones concretas.
- Contamos con los siguientes datos para evaluar cada uno de los módulos:
      1. Diarización: AMI, ICSI y VoxConverse. Las métricas de evaluación son DER y JER.
      2. Transcripción: OpenSLR, CORdeBA, Humyn y Common Voice. La métrica de evaluación WER y RTF.
      3. Minuta: AMI (previa traducción a español). Las métricas de evaluación son distancia coseno de los embeddings y un LLM as a judge.
- Para la PoC no vamos a utilizar los datos para optimizar hiperparámetros ni comparar modelos/pipelines, si no para tener una idea de su funcionamiento. 
- Queda por fuera:
1. el sistema de personalización de lenguaje/terminología específica
2. evaluación cualitativa de la minuta/rúbrica
3. especificaicones no funcionales (tiempos de inferencia)
4. adaptacion/evaluacion en bajos recursos de hardware

### 1.2 Objetivo

La PoC es un recorte arbitrario del producto con el objetivo de validar algún supuesto real del problema. Es una instancia de decisión (GO / NO GO). En esta sección detallar:

1. Qué supuesto(s) del producto pone a prueba la PoC y qué riesgos mitiga (revisar Módulo 1).
2. Qué resultado efectivamente valida el supuesto.
3. Qué decisión habilita el resultado: seguir con el producto, cambiar el enfoque o parar.

Que cada módulo por separado tenga un funcionamiento razonable (que las métricas de evaluación sean similares a las declaradas por las herramientas online).

### 1.3 Fuera de alcance

Lista lo que la PoC no construye, para que el recorte se decida ahora y no de apuro durante la construcción. Va un ítem por cada cosa, con su motivo, y al menos uno; entra lo que se resigna en las consecuencias de cada registro de decisión (3.1). Si cuesta llenarla, la pregunta que la destraba es cuál de las cosas que quieren hacer sacarían primero si perdieran una semana. El motivo está bien cuando dice por qué la PoC puede demostrar lo suyo sin esa pieza.

- Queda por fuera:
1. el sistema de personalización de lenguaje/terminología específica
2. evaluación cualitativa de la minuta/rúbrica
3. especificaicones no funcionales (tiempos de inferencia)
4. adaptacion/evaluacion en bajos recursos de hardware

### 1.4 Riesgos

Anticipa lo que puede impedir que la PoC funcione y deja decidido qué hacer si ocurre. Van los 2 o 3 más probables, entre los riesgos estimados del veredicto del Hito 2 que sigan abiertos y lo que se asume en las consecuencias de cada registro de decisión (3.1). Por cada riesgo, en un párrafo: cuál es, de dónde sale (el veredicto o la decisión técnica), la cifra del veredicto o el motivo por el que es probable, y el plan B, que tiene que ser algo que el equipo pueda ejecutar.

- Que el hardware de nuestra computadora no sea suficiente para soportar la aplicación
- Riesgo de filtración de la data sensible
- Reuniones en idiomas no soportados
- Que no entre en la ventana de contexto del LLM

---

## 2. Spec

### 2.1 Escenarios

Cuenta qué hace el sistema en el *happy path*, en 3 a 5 casos borde y cuando se equivoca. Cada escenario se escribe como en OpenSpec: un **Dado** (el estado de partida), un **Cuando** (lo que pasa) y un **Entonces** (lo que el sistema hace), con un **Y** por cada paso que sigue. La prueba es que un tercero pueda decir, con el escenario a la vista, si el sistema hizo lo que dice.

#### Happy path

El recorrido de un input típico de punta a punta sin que nada falle. Es un solo escenario, con tantos «Y» como pasos tenga.

- Dado
- Cuando
- Entonces
- Y

- Abrias la aplicación y pones a grabar
- Entras a la llamada
- Tenes la reunión
- Terminás la reunión
- Dejas de grabar
- Se procesa la reunión
- Se identifican los speakers
- Se crea la minuta en la carpeta por default


#### Casos borde

Un escenario por caso, numerado (2.1.1, 2.1.2, ...). Los casos borde salen de los límites conocidos del sistema y de los usos que se apartan del recorrido esperado. Cada uno cierra con una línea que diga qué le cuesta al usuario si sale mal; el que más le cuesta es el peor caso borde, y la *user experience* lo retoma.

##### 2.1.1

- Dado
- Cuando
- Entonces
- Le cuesta al usuario

- anglicismo
- personas con voces similares
- superposiciones
- demasiados hablantes (>30)
- vocabulario específico
- ruido: de micrófono, de ambiente

##### 2.1.2

#### Error del sistema

El escenario de cuando el sistema se equivoca o no puede responder. El «Entonces» dice qué hace el sistema para reconocer el límite y qué camino le deja al usuario para seguir.

- Dado
- Cuando
- Entonces
- Y

- La aplicación creashea durante la reunión.
- El audio se va guardando por chunks en un archivo, eso garantiza el procesamiento hasta el punto del crash + una forma fácil de indicar que n grabaciones son la misma reunion. 
- Perder la información desde que crashea hasta que reinicia y se pone a grabar.

- transcripciones erroneas
- error de diarización

### 2.2 User experience

Dice qué ve el usuario y qué control conserva sobre lo que hace el modelo, en esta interfaz y con este modelo. Cada punto es una decisión de diseño del equipo, y el último retoma el peor caso borde desde el lado del usuario. Se lee bien cuando alguien que no vio la demo puede decir qué hace el usuario en cada paso. En un párrafo por punto:

1. Interacción y control: cómo se interactúa con la PoC y qué control le queda al usuario sobre lo que hace el modelo.
2. Señal de confianza: cómo se le indica al usuario el grado de seguridad del sistema.
3. Corrección o aviso: si el usuario puede corregir la salida o avisar que está mal.
4. Peor caso borde: lo que ve el usuario en el peor caso borde de los escenarios y su camino para seguir.

- interfaz gráfica con los dispositivos de audio para poder seleccionarlos, carpeta de output, y botón de grabar y de frenar grabación
- botón de procesar reunión y botón de procesar múltiples grabaciones
- botón que abre el directorio de output

### 2.3 Criterios de aceptación

Define con qué números se decide que la PoC está terminada, y son los que se miden en el checkpoint de la semana 9. Cada criterio lleva su métrica, su umbral, el conjunto sobre el que se mide y cómo se chequea; el conjunto es el congelado en el veredicto, salvo que el criterio use otro. Un criterio está bien cuando un tercero puede chequearlo con un sí o un no, sin interpretar.

| Criterio | Métrica (qué cuenta como respuesta aceptable) | Umbral (uno por tipo de error, si un error cuesta más que el otro) | Conjunto de evaluación | Cómo se chequea |
|---|---|---|---|---|
| Calidad de la respuesta | | | | |
| Latencia (con el percentil) | | | | |
| Cobertura de los casos borde | | | | |
| Ventaja sobre el *baseline* (solo si lo que se construye no es el *baseline*) | | | | |

- Mismos criterios establecidos en hito-2

---

## 3. Diseño

### 3.1 Decisiones de diseño

Diseñar la PoC es tomar las decisiones que fijan qué se construye, antes de escribir código, y documentar cada una en un registro de decisión, en prosa, para que un lector externo pueda seguir el razonamiento y discutirlo con los mismos criterios. Hasta acá son hipótesis; si alguna alternativa se probó, se dice qué se probó y qué dio. Cada registro sigue la forma de un *Architecture Decision Record* (Nygard, 2011), en cuatro partes:

- **Contexto.** Qué pide el problema y con qué cuenta el equipo, en un párrafo, con los datos que dejó el veredicto del Hito 2 y las restricciones que hay (tiempo, costo, integración con algo existente).
- **Alternativas evaluadas.** Al menos dos, una por párrafo numerado. En cada una: qué es, qué la hacía atractiva, qué riesgos y costos tiene con lo que el equipo sabe hoy, y por qué se descartó o por qué sigue en pie. Las preguntas que guían cada argumento son qué queda demostrado si funciona, si entra en las tres semanas de construcción, qué puede impedir que funcione y cuánto cuesta.
- **Decisión.** Cuál de las alternativas se construye y qué la inclinó frente a las otras.
- **Consecuencias.** Qué se asume al elegirla y qué se resigna. Lo que se asume y puede fallar va a los riesgos (1.4); lo que se resigna va al fuera de alcance (1.3).

Las cinco decisiones de abajo las tiene toda PoC; si el proyecto tiene otra que importe, se agrega con la misma forma. La del modelo se escribe en la Clase 5; las demás, en la Clase 6.

- 

#### 3.1.1 El modelo

Qué hace el modelo (predecir una categoría o un número, o generar texto), de dónde sale (lo entrena el equipo, ajusta uno existente o llama uno de fundación por API) y con qué datos. Una de las alternativas es siempre la más simple que podría funcionar, el *baseline*, porque es la vara contra la que se mide lo demás.

- Contexto
- Alternativas evaluadas (3.1.1.1, 3.1.1.2, ...)
- Decisión
- Consecuencias

#### 3.1.2 Los datos

Qué entra al sistema y cómo se prepara, a partir del plan del pipeline del veredicto del Hito 2, diciendo qué de ese plan se mantiene y qué cambia para la PoC.

- Contexto
- Alternativas evaluadas
- Decisión
- Consecuencias

#### 3.1.3 Workflow o agente

Cómo se compone el sistema, que puede ser una llamada, un workflow con los pasos fijados por el equipo, o un agente en el que el modelo decide el camino.

- Contexto
- Alternativas evaluadas
- Decisión
- Consecuencias

#### 3.1.4 Construir o usar hecho

De cada pieza de la arquitectura (3.2), qué se construye y qué se usa hecho, con la API, el modelo preentrenado o la librería.

- Contexto
- Alternativas evaluadas
- Decisión
- Consecuencias

#### 3.1.5 Requerimientos no funcionales

Qué requerimientos priman y qué nivel fija la PoC para cada propiedad del sistema (confiable, escalable, mantenible). Lo que queda afuera a sabiendas pasa al fuera de alcance.

- Contexto
- Alternativas evaluadas
- Decisión
- Consecuencias

### 3.2 Arquitectura

Dice qué es cada una de las cinco piezas en este proyecto y cuáles se construyen y cuáles se usan hechas, según la decisión 3.1.4, que es lo que decide cuánto hay que construir en las tres semanas. El diagrama de las cinco piezas de punta a punta reemplaza al esquema de abajo; en Ingesta, Procesamiento y Evaluación se escribe solo lo que cambió respecto del veredicto del Hito 2, que ya trae el plan del pipeline. La sección está bien cuando la columna «Con qué» nombra la API, el modelo o la librería de cada pieza que se usa hecha.

```
[ingesta] -> [procesamiento] -> [modelo o agente] -> [interfaz]
                                       |
                                 [evaluación]
```

| Pieza | Qué es en este proyecto | Se construye o se usa hecha | Con qué (API, modelo preentrenado, librería) |
|---|---|---|---|
| Ingesta (la Obtención del plan del pipeline del veredicto) | | | |
| Procesamiento (la limpieza, las transformaciones y la estructura final del plan del pipeline del veredicto; completas si el veredicto fue pivotar) | | | |
| Modelo o agente | | | |
| Interfaz (la demo por donde la usa un tercero) | | | |
| Evaluación (contra los criterios de aceptación, sobre el conjunto de evaluación congelado del veredicto) | | | |

Herramientas del agente (si hay un agente):

---

## 4. Plan

### 4.1 Plan de construcción

Reparte las semanas 7, 8 y 9 del Módulo 4 en metas, cada una con su responsable y con lo que se muestra al cierre. El plan del pipeline y el conjunto de evaluación congelado son los del veredicto del Hito 2, y el *baseline* de punta a punta va en la semana 8. El docente lo lee como una prueba de que el trabajo entra en tres semanas con este equipo, y cada fila tiene que decir qué se va a poder demostrar.

| Semana | Meta | Qué se construye | Quién | Qué se muestra al cierre |
|---|---|---|---|---|
| 7, Workshop 1 | Datos listos | | | |
| 8, Workshop 2 | *Baseline* de punta a punta | | | |
| 9, Workshop 3 | Evaluación contra los criterios de aceptación | | | |

---

*Para el detalle de cada parte: [El alcance de la PoC](../../03-diseno-poc/conceptos/el-alcance-de-la-poc.md), [El enfoque técnico](../../03-diseno-poc/conceptos/el-enfoque-tecnico.md), [El *baseline*](../../03-diseno-poc/conceptos/el-baseline.md), [Workflows y agentes](../../03-diseno-poc/conceptos/workflows-y-agentes.md), [La experiencia frente al error](../../03-diseno-poc/conceptos/la-experiencia-frente-al-error.md) y [La definición de la PoC](../../03-diseno-poc/conceptos/la-definicion-de-la-poc.md).*
