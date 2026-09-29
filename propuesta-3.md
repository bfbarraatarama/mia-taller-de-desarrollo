# AI Opportunity Canvas — HomeMatch AI

> **Integrantes:** Luisa, Bruno, Matías, Felipe.  
> **Caso:** HomeMatch AI — búsqueda de departamentos en alquiler en CABA  
> **Versión:** 1 · **Fecha:** 2026-09-28

---

## 1. Problema y contexto

### A quién le pasa

Alguien que está buscando alquilar un departamento en CABA — en proceso activo de búsqueda, con restricciones reales (presupuesto, barrio, ambientes) y preferencias subjetivas difíciles de expresar en filtros estructurados.

### Qué le pasa

> "Entro a ZonaProp, pongo precio y ambientes, y me aparecen 200 resultados. Los reviso uno por uno porque los filtros no capturan lo que me importa: quiero algo luminoso y tranquilo, cerca del trabajo aunque sea un poco más caro, con balcón pero podría resignarlo si la ubicación es mejor. Y encima mis preferencias van cambiando a medida que veo alternativas."

El problema no es solo encontrar publicaciones — es identificar cuáles vale la pena visitar sin revisar manualmente decenas de opciones. Las dimensiones:

- **Funcional:** tiempo y esfuerzo de revisión manual; incapacidad de los filtros de capturar trade-offs.
- **Social:** sensación de que otros "saben moverse" mejor en el mercado; dependencia de recomendaciones informales.
- **Emocional:** agotamiento, incertidumbre sobre si se tomó la mejor decisión, ansiedad por el tiempo que demanda la búsqueda.

### Cuánto le cuesta

El mercado de CABA procesa aproximadamente **50.000–52.000 nuevos contratos por año** (proxy del volumen de búsquedas activas). No se tiene el dato de cuántas publicaciones revisa en promedio cada buscador, ni cuánto tiempo destina — esa línea de base hay que medirla en el piloto.

### Evidencia

#### De confirmación

- Infobae (14/01/2025) reporta **12.500–13.000 contratos mensuales** en CABA, aproximadamente un tercio correspondiente a nuevos acuerdos. Confirma la escala del mercado y la existencia de un flujo continuo de buscadores activos. [1]
- La existencia de tres portales grandes con catálogos superpuestos (ZonaProp, Argenprop, MercadoLibre) es evidencia de que el problema de encontrar la propiedad adecuada no está resuelto por ninguno de ellos solo.
- RentIQ [2], AgonProp [3] y Zillow AI Mode [4] apuestan al mismo diagnóstico de forma independiente — confirma que el problema fue validado por equipos con recursos distintos.

#### De refutación

- Los portales existentes tienen alta tasa de uso sostenida, lo que podría indicar que el problema no duele lo suficiente como para cambiar de herramienta.
- No se tiene evidencia propia (entrevistas, observación) de cuánto tiempo pierde un buscador ni si lo vive como un problema grave. Hay que conseguirla antes de invertir más en la solución.

---

## 2. Stakeholders

### Roles

| Papel | Quién es | Qué necesita ver para decir que sí |
|---|---|---|
| Usuario | Persona que busca alquilar un departamento en CABA | Que las recomendaciones reflejen lo que describió, que le ahorre tiempo frente al portal tradicional |
| Influenciador | Pareja, familiar o compañero de cuarto que también vivirá en el departamento | Que el sistema considere las preferencias de todos, no solo de quien lo usa |
| Recomendador | Amigo o conocido con experiencia reciente en el mercado porteño | Que el sistema conozca el mercado real y no muestre propiedades fuera de precio o de barrio |
| Comprador | El mismo usuario (paga el alquiler) | Que el tiempo invertido en la búsqueda sea menor que con el método actual |
| Decisor | El mismo usuario | Que la decisión final siempre sea suya; que el sistema explique, no imponga |
| Saboteador | Portales inmobiliarios (pueden restringir scraping) / inmobiliarias (pueden perder consultas directas) | — |

### Evidencia

#### De confirmación

- En vivienda para uso propio, usuario, comprador y decisor suelen ser la misma persona o pareja — simplifica la dinámica de adopción.
- El saboteador más concreto es el portal inmobiliario: si restringe el scraping, el producto pierde su fuente de datos.

#### De refutación

- No se verificó si hay un perfil de buscador que delegue la búsqueda a una inmobiliaria (que actuaría como recomendador con mucho peso) — en ese caso la propuesta de valor se dirige al lugar equivocado.

---

## 3. Hipótesis de solución

### Descripción del producto

El usuario describe en lenguaje natural qué busca. HomeMatch interpreta la conversación, identifica **restricciones obligatorias** (presupuesto, ambientes, mascotas, zona excluida) y **preferencias** (luminosidad, balcón, cercanía al trabajo), lee las publicaciones disponibles, descarta las que violan alguna restricción, y rankea el resto. Devuelve un **Top 5** con explicación de por qué cada opción es compatible y qué trade-offs presenta. El usuario reacciona con feedback libre y el ranking se actualiza.

### Acción

El usuario ve un Top 5 personalizado con explicaciones y trade-offs en lugar de tener que revisar y comparar manualmente las publicaciones que devuelve un filtro.

### Predicción

Qué tan compatible es cada propiedad con las restricciones y preferencias del usuario, combinando atributos estructurados (precio, ambientes, ubicación) con similitud semántica entre las preferencias expresadas y el texto de la publicación.

### Juicio

- El umbral de restricciones duras (qué excluye y qué no) lo confirma el usuario antes del primer ranking.
- El parámetro α que balancea score estructurado y score semántico lo fija el equipo experimentalmente durante la PoC — no lo elige el usuario.
- Si HomeMatch infiere un cambio relevante en el perfil a partir del feedback, se lo muestra al usuario y espera confirmación antes de actualizar.

### Evidencia

#### De confirmación

- RentIQ (UC Berkeley, 2025) [2] combina conversación, extracción de preferencias, filtros estructurados y búsqueda semántica — confirma que la predicción propuesta es técnicamente realizable.
- Los embeddings de texto ya se usan para búsqueda semántica en propiedades en otros contextos (Zillow AI Mode [4]).

#### De refutación

- No se demostró aún que el ranking híbrido sea mejor que un filtro tradicional para este dominio — eso es precisamente lo que hay que medir en la PoC.
- Si el LLM interpreta mal una restricción obligatoria (por ejemplo, acepta una propiedad que no acepta mascotas), el error es grave. Ese riesgo no está cuantificado.

---

## 4. Alternativas y statu quo

### Qué hace hoy el usuario

Entra a ZonaProp, Argenprop o MercadoLibre. Aplica filtros por precio, barrio y ambientes. Revisa una a una las publicaciones resultantes. Guarda algunas en favoritos o en un grupo de WhatsApp. Vuelve a hacer lo mismo en otro portal. Compara manualmente y coordina visitas por su cuenta. El proceso se repite cada vez que actualiza sus preferencias.

### Qué otras soluciones existen o podrían aparecer

| Solución | Fortaleza | Limitación |
|---|---|---|
| ZonaProp / Argenprop / MercadoLibre | Gran volumen de publicaciones, filtros conocidos | No capturan preferencias subjetivas ni trade-offs; comparación manual |
| RentIQ (UC Berkeley) [2] | Conversación + semántica + reranking | No disponible en Argentina |
| AgonProp (Argentina) [3] | Búsqueda en lenguaje natural, asistente conversacional | Funcionalidad no verificada en profundidad |
| Zillow AI Mode [4] | Conversacional, con comparación de propiedades | Solo para mercado de EEUU |

### Por qué lo nuestro sería suficientemente mejor como para que alguien se mueva

Los portales actuales obligan al usuario a traducir sus necesidades a filtros y comparar manualmente. HomeMatch entiende preferencias subjetivas expresadas libremente, aprende del feedback durante la misma sesión, y explica los trade-offs de cada opción. La diferencia no es solo la interfaz conversacional — es que funciona como **asistente de decisión** que aprende de la interacción, no solo como buscador que filtra.

### Evidencia

#### De confirmación

- AgonProp [3] existe y opera en Argentina — confirma que hay demanda local para este tipo de herramienta.
- La persistencia de múltiples portales con catálogos superpuestos sugiere que ninguno resuelve bien el problema de encontrar la propiedad correcta, no solo mostrar publicaciones.

#### De refutación

- No se midió cuánto tiempo dedica hoy un buscador ni qué tan satisfecho queda con el proceso — sin esa línea de base, no se puede afirmar que HomeMatch sea "suficientemente mejor".
- El statu quo tiene cero fricción de adopción (ya está instalado, es gratis, lo conocen). Para que alguien cambie, la mejora tiene que ser perceptible desde el primer uso.

---

## 5. Hipótesis de datos

### Dataset

| Dato | Origen | ¿Público? | ¿Lo vimos? | ¿Sensibles? | Sesgo conocido | Comentarios |
|---|---|---|---|---|---|---|
| Listings (precio, barrio, ambientes, superficie, amenities, mascotas) | ZonaProp / Argenprop — scraping | Sí (web pública) | No | No | Pueden estar desactualizados o duplicados entre portales | Verificar TOS antes de implementar; empezar con un solo portal |
| Texto de las publicaciones (descripción libre) | Mismo origen | Sí | No | No | Calidad y extensión muy variables | Clave para embeddings; publicaciones breves pueden quedar mal representadas |
| Información geográfica (tiempo de viaje, transporte) | APIs de mapas (ej. Google Maps) | Parcialmente (requiere API key) | No | No | Tráfico estimado puede no reflejar horas pico reales | Feature adicional en el score; no crítica para la PoC |
| Preferencias del usuario | Conversación generada en sesión | N/A | N/A | Sí | — | No se persiste entre sesiones en la PoC; el usuario las re-expresa en cada uso |

### Evidencia

#### De confirmación

- Los portales mencionados publican sus listings en web abierta — el dato existe y en principio es accesible.

#### De refutación

- No se bajó ni inspeccionó ningún dataset todavía. Que el dato esté publicado no significa que tenga las columnas necesarias con valores completos — hay que abrirlo.
- Los TOS de los portales pueden prohibir el scraping automatizado. Eso no es un riesgo hipotético: es una restricción concreta que hay que verificar antes de construir.

---

## 6. Métrica de éxito

### Métrica de negocio

**Esfuerzo de búsqueda:** cantidad de publicaciones que el usuario debe revisar hasta encontrar 3 propiedades que visitaría. La hipótesis es que HomeMatch reduce esta cantidad frente a la búsqueda tradicional.

**Precision@5:** propiedades del Top 5 que el usuario visitaría / 5.

### Umbral — por debajo de esto, no vale la pena

Los umbrales cuantitativos se fijan después de medir el baseline con los primeros participantes del piloto. Establecerlos antes de tener evidencia del statu quo sería inventar un número. Lo que sí se puede decir: si HomeMatch no supera el baseline en esfuerzo de búsqueda Y en Precision@5, la hipótesis no se sostiene.

### Cómo se mediría dentro del trimestre

Test con aproximadamente **10 personas**. Cada participante resuelve la misma búsqueda de alquiler con:

- **A. Baseline:** portal inmobiliario + filtros tradicionales (ZonaProp).
- **B. HomeMatch:** conversación + recomendaciones personalizadas.

Se comparan: publicaciones revisadas hasta encontrar 3 candidatos, tiempo total, Precision@5, satisfacción (escala 1–5) y percepción de que las recomendaciones reflejan lo que buscaba.

### Métrica técnica que usaríamos como proxy

Thumbs up / thumbs down por recomendación individual — mide la relevancia percibida de cada propiedad en el momento.

### Qué se registra de cada uso

- Perfil de preferencias inferido (restricciones y preferencias identificadas).
- Cambios al perfil tras cada ronda de feedback.
- Score estructurado y semántico de cada propiedad en el ranking.
- Evaluación del usuario por propiedad (thumbs up / down).

### Evidencia

#### De confirmación

- La métrica de "publicaciones revisadas hasta encontrar 3 candidatos" es observable sin acceso al modelo: se puede medir con un contador en la UI o con un protocolo de pensamiento en voz alta.

#### De refutación

- No hay línea de base medida todavía. Sin saber cuántas publicaciones revisa hoy un buscador típico, el umbral de mejora no tiene referencia.

---

## 7. Riesgos éticos y de sesgo (preliminar)

**Calidad de servicio desigual:** el modelo semántico puede funcionar mejor para publicaciones bien redactadas (generalmente las de mayor precio o de inmobiliarias grandes), penalizando opciones más económicas o con descripciones breves. Habría que medir Precision@5 por rango de precio para detectarlo.

**Representación:** las publicaciones en los portales pueden sobre-representar ciertos barrios o rangos de precio. El sistema recomendaría lo que hay en el dataset, no necesariamente lo que está disponible en el mercado real.

**Interpersonal / privacidad:** las preferencias del usuario (presupuesto, zona deseada, composición del hogar, mascotas) son datos personales. En la PoC no se persisten entre sesiones; si el producto evoluciona a perfiles guardados, se requiere consentimiento explícito.

**Sesgo de confirmación en el feedback:** si el sistema aprende solo de lo que el usuario aprueba, puede quedarse en un óptimo local y dejar de mostrar opciones que el usuario no consideró pero podrían interesarle.

**Para qué no debería usarse:** el sistema no debe inferir características del arrendatario (capacidad de pago, composición familiar, origen) ni usarse para discriminar en la oferta disponible.

**Regulación:** el dominio de vivienda no está entre los de mayor riesgo regulatorio (crédito, empleo, salud), pero si el producto evoluciona a coordinar contactos con inmobiliarias o a comprometer visitas, entran en juego normas de protección al consumidor.

### Evidencia

#### De confirmación

- Sesgos similares están documentados en sistemas de recomendación de propiedades en mercados de EEUU (housing recommendation bias), donde los sistemas refuerzan tendencias de segregación existentes en los datos.

#### De refutación

- No se identificó regulación argentina específica que aplique a la PoC en su alcance actual (asistente de búsqueda, sin transacciones ni datos persistidos).

---

## Bitácora de revisiones

*Una línea por revisión. Qué cambió y qué evidencia lo motivó.*

| Fecha | Sección | Qué cambió | Qué lo motivó |
|---|---|---|---|
| 2026-09-28 | Todas | Adaptación de propuesta-3 al formato canvas | Primera versión |

---

## Referencias

[1] Infobae (14/01/2025). *Creció 200% la oferta de alquileres pero también la demanda: cuánto demora cerrar hoy una operación en CABA.*  
https://www.infobae.com/economia/2025/01/14/crecio-200-la-oferta-de-alquileres-pero-tambien-la-demanda-cuanto-demora-cerrar-hoy-una-operacion-en-caba/

[2] UC Berkeley School of Information (2025). *RentIQ: Your Smart AI Guide to Finding the Right Home.*  
https://www.ischool.berkeley.edu/projects/2025/rentiq-your-smart-ai-guide-finding-right-home

[3] AgonProp.  
https://agonprop.com/

[4] Zillow (2025). *Zillow Debuts AI Mode.*  
https://www.zillow.com/news/zillow-debuts-ai-mode/
