# HomeMatch AI — Product Canvas

> **Alcance de la PoC:** búsqueda de departamentos en alquiler en CABA.

## 1. Problema / necesidad

Buscar un departamento para alquilar requiere revisar muchas publicaciones distribuidas entre distintos portales, con información heterogénea y difícil de comparar.

Los buscadores tradicionales permiten filtrar variables explícitas —precio, barrio, ambientes, superficie—, pero no capturan preferencias expresadas de forma natural, por ejemplo:

- “quiero algo luminoso y tranquilo”;
- “prefiero estar cerca del trabajo aunque sea un poco más caro”;
- “quiero balcón, pero podría resignarlo por una mejor ubicación”.

Además, las preferencias pueden cambiar a medida que la persona ve alternativas. El problema no es solamente **encontrar publicaciones**, sino **identificar cuáles vale la pena visitar sin revisar manualmente decenas de opciones**.

**Pregunta de producto**

> ¿Podemos reducir el esfuerzo de búsqueda y ayudar al usuario a encontrar mejores candidatos para visitar para comprender sus preferencias y comparar propiedades?

---

## 2. Usuario / stakeholders

### Usuario principal
Personas que buscan alquilar un departamento en CABA. (Restringido a CABA en fase inica)

### Mercado potencial inicial
Como referencia de magnitud, una nota de Infobae de enero de 2025 reporta aproximadamente **12.500–13.000 contratos de alquiler mensuales en CABA**. Cerca de un tercio correspondería a nuevos acuerdos.

Esto equivale a aproximadamente **50.000–52.000 nuevos contratos por año**, que se utilizarán como **proxy inicial del flujo anual del mercado potencial**, no como cantidad directa de usuarios.

---

## 3. Soluciones actuales / alternativas

### Portales inmobiliarios tradicionales
ZonaProp, Argenprop y Mercado Libre permiten buscar mediante filtros estructurados.

**Fortaleza:** gran cantidad de publicaciones y filtros simples.  
**Limitación:** el usuario debe traducir sus necesidades a filtros y comparar manualmente las alternativas.

### Soluciones con IA similares

**RentIQ — UC Berkeley**  
Asistente de búsqueda de vivienda que combina conversación, extracción de preferencias, filtros estructurados, búsqueda semántica y reranking.

**AgonProp — Argentina**  
Plataforma inmobiliaria con búsqueda mediante lenguaje natural, asistente conversacional y herramientas de comparación.

**Zillow AI Mode**  
Experiencia conversacional para buscar y comparar propiedades a partir de preferencias expresadas en lenguaje natural.

---

## 4. Hipótesis de solución

La persona cuenta qué busca con sus propias palabras. El sistema identifica qué es excluyente y qué es deseable, lee todos los avisos disponibles (incluida la descripción), descarta los que violan algo excluyente y ordena el resto. Muestra 5 opciones con el motivo de cada una y lo que sacrifica. La persona reacciona ("este me gusta, pero el balcón me importa más de lo que dije") y el orden se ajusta.

Si la solucion puede:

1. comprender necesidades expresadas libremente por el usuario;
2. distinguir restricciones obligatorias de preferencias;
3. combinar información estructurada y semántica de las propiedades;
4. aprender del feedback durante la búsqueda;
5. explicar por qué recomienda cada alternativa;

entonces el usuario podrá **encontrar propiedades que consideraría visitar revisando menos publicaciones que con una búsqueda tradicional**.

### Oportunidad 
No limitarse a “buscar con lenguaje natural”, sino funcionar como un **asistente de decisión** que aprende de la interacción, reordena alternativas y explica los trade-offs.

---

## 5. Propuesta de valor

> **HomeMatch AI ayuda a encontrar departamentos para alquilar en CABA que se ajusten a las necesidades y preferencias reales del usuario, reduciendo el esfuerzo de revisar y comparar publicaciones.**

El objetivo no es reemplazar la decisión humana. HomeMatch **prioriza, compara y explica**; el usuario decide qué propiedad visitar.

---

## 6. Solución propuesta

### Experiencia del usuario

**Conversación → perfil de búsqueda → candidatos → ranking personalizado → explicación → feedback → nuevo ranking**

El usuario describe libremente qué busca.

Ejemplo:

> “Busco un dos ambientes, hasta $X, que acepte mascotas. Trabajo en Microcentro y no quisiera viajar más de 35 minutos. Prefiero algo luminoso y con balcón.”

HomeMatch interpreta la conversación y construye un perfil.

### Restricciones obligatorias
Ejemplos:
- presupuesto máximo;
- cantidad mínima de ambientes;
- mascotas;
- ubicación excluida/incluida.

Las propiedades que no cumplen estas condiciones se eliminan.

### Preferencias
Ejemplos:
- balcón;
- luminosidad;
- tranquilidad;
- cercanía al trabajo;
- espacios verdes;
- transporte.

Estas variables participan del ranking pero no necesariamente eliminan una propiedad.

### Resultado
HomeMatch devuelve un **Top 5 personalizado**, indicando:

- por qué cada propiedad es compatible;
- qué preferencias cumple;
- qué compromisos o trade-offs presenta;
- link a la publicación original.

---

## 7. Inteligencia Artificial

### LLM
Se utiliza para:

- interpretar la conversación;
- extraer restricciones y preferencias;
- detectar información faltante o ambigua;
- interpretar el feedback;
- generar explicaciones de las recomendaciones.

Los cambios importantes inferidos por el LLM deben ser confirmados por el usuario.

### Embeddings / búsqueda semántica
Permiten relacionar preferencias subjetivas con el texto de las publicaciones.

Ejemplo:

> “quiero un departamento luminoso”

puede relacionarse semánticamente con descripciones como:

> “gran entrada de luz natural”, “ventanales amplios”, “orientación abierta”.

### Ranking híbrido

**Score final = α × Score estructurado + (1 − α) × Score semántico**

El ranking combina:

- cumplimiento de preferencias cuantificables;
- similitud semántica;
- restricciones duras aplicadas previamente.

El parámetro **α** se determinará experimentalmente durante la PoC.

---

## 8. Datos / inputs

### Publicaciones inmobiliarias
Obtenidas mediante scraping de uno o más portales.

Variables posibles:

- precio;
- expensas;
- barrio / ubicación;
- ambientes;
- superficie;
- amenities;
- acepta mascotas;
- descripción;
- URL de la publicación.

### Texto de las publicaciones
Utilizado para extracción de características y embeddings.

### Información geográfica
Variables simples de contexto:

- tiempo estimado de viaje;
- transporte;
- cercanía a espacios verdes o servicios.

### Información del usuario
Obtenida durante la conversación:

- restricciones;
- preferencias;
- prioridades;
- feedback sobre recomendaciones.

### Alcance de datos de la PoC
Para validar la hipótesis **no es necesario integrar todos los portales**. Si el scraping multiportal aumenta demasiado el alcance, la PoC puede realizarse inicialmente con una única fuente.

---

## 9. Feedback / aprendizaje durante la búsqueda

Después de recibir recomendaciones, el usuario puede expresar:

> “Me gustaron estos, pero me doy cuenta de que el balcón es más importante de lo que pensaba.”

o:

> “50 minutos de viaje es demasiado.”

El LLM interpreta el feedback y propone una modificación del perfil.

**Feedback → propuesta de cambio → confirmación → actualización del perfil → nuevo ranking**

La PoC no requiere entrenar nuevamente un modelo con cada interacción.

---

## 10. Output

El producto entrega:

### Top 5 de propiedades recomendadas

Para cada propiedad:

- nivel de compatibilidad;
- principales razones de recomendación;
- preferencias que cumple;
- trade-offs;
- acceso a la publicación original.

Ejemplo:

> **Opción A**  
> Cumple presupuesto, acepta mascotas y reduce el viaje al trabajo a 28 min. Tiene balcón y buena coincidencia con tu preferencia por luminosidad. Como trade-off, tiene menor superficie que otras alternativas.

---

## 11. Interacción humano–IA

La IA **asiste**, pero no toma la decisión final.

**Usuario**
- define necesidades;
- confirma restricciones importantes;
- evalúa recomendaciones;
- proporciona feedback;
- decide qué propiedad visitar;
- autoriza cualquier contacto externo.

**IA**
- interpreta;
- estructura preferencias;
- filtra;
- rankea;
- explica;
- adapta recomendaciones.

Si HomeMatch prepara un mensaje para una inmobiliaria o agente, **el envío requiere confirmación explícita del usuario**.

---

## 12. Métricas de éxito

La PoC se comparará contra una **búsqueda tradicional con filtros**.

### KPI principal — Thumbs up

Cada recomendación recibida por el usuario puede ser evaluada con un "thumbs up" si le resulta relevante o con un "thumbs down" si no lo es.

### KPI principal — Precision@5

**Precision@5 = propiedades del Top 5 que el usuario visitaría / 5**

Mide la relevancia de las primeras recomendaciones.

### KPI principal — esfuerzo de búsqueda

**Cantidad de publicaciones que el usuario debe revisar hasta encontrar 3 propiedades que visitaría.**

La hipótesis es que HomeMatch reduzca esta cantidad frente a la búsqueda tradicional.

### Métricas secundarias

- tiempo hasta encontrar 3 candidatos;
- satisfacción del usuario;
- percepción de que las recomendaciones reflejan lo que buscaba (escala 1–5).

### Criterio de éxito

HomeMatch deberá **superar el baseline de búsqueda tradicional** en las métricas principales.

Los umbrales cuantitativos definitivos se fijarán después de un primer piloto, evitando establecer valores arbitrarios sin evidencia.

---

## 13. Validación

### Prueba con usuarios

Realizar una prueba pequeña con aproximadamente **10 personas**.

Cada participante deberá resolver una búsqueda de alquiler utilizando:

**A. Baseline:** portal inmobiliario + filtros tradicionales.  
**B. HomeMatch:** conversación + recomendaciones personalizadas.

Se compararán:

- relevancia del Top 5;
- cantidad de publicaciones revisadas;
- tiempo de búsqueda;
- satisfacción.

---

## 14. Riesgos y limitaciones

### Scraping
Los portales pueden modificar su estructura o limitar el acceso automatizado.
Además, el scraping puede no estar permitido por los términos de uso de los portales.

**Mitigación:** comenzar con un portal y ampliar solamente si el tiempo lo permite + verificar los términos de uso de cada portal antes de implementar scraping.

### Calidad de datos
Puede haber publicaciones incompletas, desactualizadas o duplicadas.

**Mitigación:** normalización, validaciones y deduplicación básica.

### Interpretación del LLM
El modelo puede interpretar incorrectamente una preferencia.

**Mitigación:** mostrar el perfil inferido y pedir confirmación ante cambios relevantes.

### Calidad del ranking
Un score alto no garantiza que la propiedad sea realmente atractiva para el usuario.

**Mitigación:** validación con usuarios y comparación contra baseline.

### Alcance
El proyecto debe poder implementarse dentro de aproximadamente dentro del dictado de la materia

**Mitigación:** priorizar el recomendador y la experiencia conversacional; multiportal, automatización de contactos y funcionalidades avanzadas quedan como evolución.

---

## 15. MVP / alcance de la PoC

### Incluido
- CABA.
- Departamentos en alquiler.
- Una fuente inmobiliaria como mínimo.
- Scraping de publicaciones reales.
- Interfaz conversacional.
- Extracción de preferencias con LLM.
- Hard filters.
- Score estructurado.
- Embeddings.
- Ranking híbrido.
- Top 5 explicado.
- Feedback y reranking.
- Evaluación contra baseline.

### Fuera del MVP
- Análisis de imágenes.
- Negociación automática.
- Reserva autónoma de visitas.
- Aprendizaje colaborativo entre usuarios.
- Integración obligatoria con todos los portales.
- Entrenamiento de un LLM propio.

---

## 16. Evolución posible

Una vez validada la PoC:

- incorporar múltiples portales;
- detectar publicaciones duplicadas entre plataformas;
- mejorar información de movilidad y contexto;
- incorporar alertas de nuevas propiedades compatibles;
- preparar contacto con inmobiliarias;
- coordinar visitas con autorización del usuario;
- aprender preferencias longitudinales;
- incorporar información adicional sobre barrios.

---

## Síntesis del Canvas

| Bloque | HomeMatch AI |
|---|---|
| **Problema** | Buscar alquiler requiere revisar y comparar muchas publicaciones; los filtros tradicionales no representan bien preferencias subjetivas y trade-offs. |
| **Usuario** | Personas que buscan alquilar departamentos en CABA. |
| **Alternativas** | Portales tradicionales; RentIQ; AgonProp; Zillow AI Mode. |
| **Hipótesis** | Comprender preferencias + ranking personalizado + feedback permitirá encontrar mejores candidatos revisando menos publicaciones. |
| **Valor** | Mejores candidatos para visitar con menor esfuerzo de búsqueda. |
| **Solución** | Asistente conversacional con recomendador híbrido y feedback iterativo. |
| **Datos** | Listings reales, texto, ubicación/contexto y preferencias del usuario. |
| **IA** | LLM + embeddings + scoring/ranking híbrido. |
| **Output** | Top 5 explicado con cumplimiento de preferencias y trade-offs. |
| **Humano–IA** | La IA recomienda y explica; el usuario confirma preferencias y toma la decisión. |
| **Éxito** | Precision@5 + publicaciones revisadas hasta encontrar 3 candidatos + tiempo/satisfacción. |
| **Validación** | 10 usuarios; comparación HomeMatch vs. búsqueda tradicional. |
| **Riesgos** | Scraping, calidad de datos, errores del LLM, ranking y alcance. |
| **MVP** | CABA + alquiler + ≥1 portal + conversación + ranking + feedback. |

---

## Referencias

- Infobae (14/01/2025), mercado de alquileres en CABA:  
  https://www.infobae.com/economia/2025/01/14/crecio-200-la-oferta-de-alquileres-pero-tambien-la-demanda-cuanto-demora-cerrar-hoy-una-operacion-en-caba/

- RentIQ — UC Berkeley School of Information:  
  https://www.ischool.berkeley.edu/projects/2025/rentiq-your-smart-ai-guide-finding-right-home

- AgonProp:  
  https://agonprop.com/

- Zillow AI Mode:  
  https://www.zillow.com/news/zillow-debuts-ai-mode/
