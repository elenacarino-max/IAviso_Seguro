# IAviso Seguro

[![CI](https://github.com/elenacarino-max/IAviso_Seguro/actions/workflows/ci.yml/badge.svg)](https://github.com/elenacarino-max/IAviso_Seguro/actions/workflows/ci.yml)

Plataforma de triaje asistido para registrar, clasificar y revisar avisos
sintéticos de riesgos laborales. Un modelo propone categoría, urgencia, resumen
y departamento apoyándose en una matriz PRL y evidencia documental; una persona
técnica conserva siempre la decisión final.

> Proyecto académico y demostrativo. No sustituye una evaluación profesional ni
> el protocolo de emergencias y no está preparado para procesar avisos reales.

## Qué permite

- Crear avisos con Ollama local o Gemini externo mediante el mismo contrato.
- Revisar, corregir o rechazar propuestas con control de versión y auditoría.
- Consultar en el Registro las decisiones cerradas y su departamento final.
- Comparar ambos proveedores en paralelo sobre exactamente el mismo caso.
- Ejecutar un benchmark sintético y consultar métricas históricas por modelo.
- Ver la regla de matriz y las fuentes RAG realmente consultadas.
- Supervisar FastAPI, Ollama, Gemini y SQLite desde la barra lateral.
- Anonimizar PII conocida antes de consultar modelos o guardar el aviso.
- Detectar posibles riesgos recurrentes mediante embeddings locales de avisos
  ya anonimizados.
- Enviar directamente a triaje los avisos breves que cumplan el contrato básico,
  sin un paso previo de preguntas aclaratorias.
- Calcular una incertidumbre técnica y una prioridad de revisión deterministas,
  versionadas y separadas de la urgencia preventiva.

Las propuestas, revisiones, evidencias y métricas se conservan en SQLite.
GitHub Actions ejecuta las pruebas de backend y frontend y compila la SPA en
cada `push` y `pull_request`.

## Documentación

- [Guía funcional](docs/GUIA_FUNCIONAL.md): pantallas, usuarios y recorridos.
- [Arquitectura e integraciones](docs/ARQUITECTURA_E_INTEGRACIONES.md):
  componentes, flujo de datos y relación con servicios externos.

## Arquitectura implementada

- Backend: Python, FastAPI y validación estricta con Pydantic.
- Interfaz principal: React, TypeScript y Vite, comunicada exclusivamente con la API.
- Interfaz de respaldo: Streamlit, conservada para el requisito académico original.
- Modelos: uno local mediante Ollama y uno externo mediante un adaptador independiente.
- Persistencia: SQLite para el prototipo, separando propuestas y decisiones finales.
- Evaluación: Pytest y casos sintéticos comunes a ambos proveedores.

## Estructura

```text
backend/app/
  api/           Rutas y respuestas HTTP
  core/          Configuración y observabilidad
  schemas/       Contratos de entrada y salida
  services/      Privacidad, triaje, recuperación, telemetría y evaluación
  providers/     Adaptadores local y externo
  tools/         Consulta de la matriz de riesgos
  prompts/       Instrucciones y ejemplos versionados
  repositories/  Persistencia de avisos y decisiones
frontend-react/  SPA principal React/TypeScript
frontend/        Dashboard Streamlit de respaldo y cliente HTTP
config/          Configuración de dominio y matriz de referencia
data/           Ejemplos, corpus preventivo, evaluación y almacenamiento local
.github/        Integración continua de backend y frontend
tests/          Pruebas unitarias, integración y respuestas simuladas
docs/           Análisis, arquitectura y plan de trabajo
```

## Preparación del entorno

### Arranque con un solo comando

En Windows, desde la raíz del proyecto:

```powershell
.\start.ps1
```

También se puede ejecutar `start.bat` con doble clic. El lanzador crea `.env`
y `.venv` si faltan, sincroniza dependencias cuando cambian sus archivos de
bloqueo, inicia Ollama, prepara el modelo configurado, levanta FastAPI y React y
abre la aplicación. Al pulsar `Ctrl+C` detiene únicamente los procesos que él
haya iniciado. Las opciones `-NoBrowser` y `-SkipInstall` permiten omitir la
apertura del navegador o la instalación automática.
Si los puertos configurados contienen una versión antigua u otro servicio, el
lanzador elige puertos locales libres y muestra las direcciones utilizadas.
Los diagnósticos de arranque quedan en `data/local/*.log`, que no se versiona.

Python 3.11 o superior. Desde la raíz, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Para reproducir exactamente el entorno validado de cierre se puede sustituir la
instalación anterior por `python -m pip install -r requirements-lock.txt`. El
lock fue generado con Python 3.14 en Windows; `requirements.txt` mantiene los
rangos compatibles de las dependencias directas realmente usadas.

Antes de arrancar la API, inicia Ollama y prepara un modelo con llamadas de
herramienta. El modelo es configurable; este ejemplo coincide con la prueba manual:

```powershell
ollama pull llama3.2:3b
# En otra terminal, solo si Ollama no se inició como aplicación:
ollama serve
```

La detección opcional de avisos similares usa un modelo distinto, también local.
La aplicación no lo descarga automáticamente. Para habilitarla, prepáralo de
forma explícita y ajusta `.env`:

```powershell
ollama pull nomic-embed-text
```

```dotenv
EMBEDDING_ENABLED=true
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_THRESHOLD=0.78
EMBEDDING_TOP_K=3
EMBEDDING_TIMEOUT_SECONDS=10
```

`nomic-embed-text` es el valor de ejemplo, no un nombre fijado en la lógica.
Con `EMBEDDING_ENABLED=false` el triaje funciona sin generar ni consultar
vectores.

Las dependencias están fijadas en `requirements-lock.txt` y se han instalado y
probado conjuntamente en un entorno limpio. Para ejecutar todas las pruebas desde
la raíz:

```powershell
python -m pytest -q
```

Arrancar la API desde la raíz:

```powershell
python -m uvicorn backend.app.main:app --reload
```

En otra terminal, instalar y arrancar la interfaz principal (Node 20.19+ o
22.12+):

```powershell
cd frontend-react
npm install
npm run dev
```

La interfaz abre en `http://127.0.0.1:5173` y Vite redirige `/api` a
`http://127.0.0.1:8000`. Para validar el frontend: `npm test` y
`npm run build`.

### Integración continua

El workflow `.github/workflows/ci.yml` se ejecuta en cada envío y propuesta de
cambio. Instala dependencias desde los archivos bloqueados de cada entorno y
ejecuta dos trabajos independientes:

- Backend (Python 3.12): `python -m pytest -q`.
- Frontend (Node 22): `npm ci`, `npm test` y `npm run build`.

Las pruebas sustituyen Ollama y Gemini por dobles locales, por lo que GitHub
Actions no necesita secretos, modelos descargados ni acceso a los proveedores.

### Despliegue reproducible con Docker

El contenedor construye React y lo sirve desde la misma aplicación FastAPI. Con
Ollama iniciado en el equipo y un modelo preparado:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

El dashboard completo queda disponible en `http://127.0.0.1:8000`. Dentro del
contenedor, Ollama se consulta mediante `host.docker.internal`; para habilitar
Gemini debe definirse `EXTERNAL_API_KEY` en `.env`. La base SQLite se conserva
en `data/local/`. Para detener el despliegue: `docker compose down`.

El dashboard Streamlit se conserva como fallback y puede arrancarse desde la raíz:

```powershell
python -m streamlit run frontend/app.py
```

Comprobarla en `http://127.0.0.1:8000/docs` o mediante:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/catalogs
Invoke-RestMethod http://127.0.0.1:8000/api/v1/risk-matrix
Invoke-RestMethod http://127.0.0.1:8000/api/v1/knowledge-base
Invoke-RestMethod http://127.0.0.1:8000/api/v1/metrics/summary
$proposal = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/triage -ContentType 'application/json' -Body '{"text":"Hay agua en el pasillo.","provider":"local"}'
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/notices?status=pending_review&urgency=alta&provider=local&page=1&limit=20'
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/notices/$($proposal.notice_id)/audit-events"
$review = @{decision='approved'; reviewer='Tecnica demo'; comment='Caso sintetico revisado.'; expected_version=$proposal.version} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/notices/$($proposal.notice_id)/reviews" -ContentType 'application/json' -Body $review
$comparison = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/comparisons -ContentType 'application/json' -Body '{"text":"Hay humo junto a una salida.","location":"Zona demo"}'
$comparisonReview = @{category='incendio'; urgency='critica'; department='seguridad'; reviewer='Tecnica demo'; comment='Referencia humana verificada.'} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/comparisons/$($comparison.comparison_id)/review" -ContentType 'application/json' -Body $comparisonReview
$evaluation = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/evaluations
# Requiere EXTERNAL_API_KEY en .env:
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/triage -ContentType 'application/json' -Body '{"text":"Hay humo junto a una salida.","provider":"external"}'
```

Persistencia:

- `DATABASE_PATH`: archivo SQLite local; por defecto `data/local/iaviso.db`.
- Toda propuesta nueva empieza en `pending_review` con versión `0`.
- La revisión exige `expected_version`; una revisión duplicada o concurrente
  devuelve `409` y no sobrescribe la decisión ganadora.
- `approved` confirma la clasificación, `modified` exige al menos un cambio en
  categoría, urgencia o departamento y `rejected` no crea una clasificación
  final aceptada.

Recuperación documental:

- `KNOWLEDGE_BASE_PATH`: corpus JSON local y versionado; por defecto
  `data/knowledge/prevention_docs.v1.json`.
- `RAG_MAX_SOURCES`: número de fragmentos recuperados, entre 1 y 5; por defecto 2.
- El corpus incluido es sintético, didáctico y no normativo. No requiere una
  base vectorial ni un servicio externo.

Variables del proveedor local:

- `OLLAMA_BASE_URL`: URL del servidor local.
- `LOCAL_MODEL`: nombre del modelo instalado; no está fijado en el código.
- `LLM_TIMEOUT_SECONDS`: tiempo máximo de cada llamada.
- `OLLAMA_TEMPERATURE` y `OLLAMA_TOP_P`: parámetros de muestreo validados.

Variables de similitud semántica:

- `EMBEDDING_ENABLED`: activa la capacidad opcional; por defecto está desactivada.
- `EMBEDDING_MODEL`: modelo local de Ollama preparado manualmente.
- `EMBEDDING_THRESHOLD`: coseno mínimo para considerar un aviso relacionado,
  entre 0 y 1.
- `EMBEDDING_TOP_K`: máximo de coincidencias devueltas, entre 1 y 10.
- `EMBEDDING_TIMEOUT_SECONDS`: límite independiente para generar el vector.

Variables del proveedor externo:

- `EXTERNAL_API_BASE_URL`: base de la API REST de Gemini.
- `EXTERNAL_API_KEY`: secreto obligatorio para usar `provider=external`.
- `EXTERNAL_MODEL`: modelo de Gemini; por defecto `gemini-3.5-flash-lite`.
- `EXTERNAL_TEMPERATURE` y `EXTERNAL_TOP_P`: parámetros de muestreo validados.
- `LLM_MAX_RETRIES`: reintentos de transporte, `429` y HTTP transitorios.
- `LLM_RETRY_BASE_SECONDS` y `LLM_RETRY_MAX_SECONDS`: backoff exponencial y
  límite máximo de espera.
- `EXTERNAL_PRICE_MODEL`, tarifas por millón de tokens, moneda, fuente y fecha:
  referencia versionada para calcular el coste solo cuando coincide el modelo.

Si falta la clave externa, la API responde `503` sin intentar una conexión. Un
aviso nunca se redirige implícitamente a otro proveedor.

`GET /health` devuelve una lista ordenada para FastAPI, Ollama, Gemini, SQLite,
matriz PRL, corpus RAG y embeddings. Ollama se consulta una sola vez mediante
`/api/tags`, distinguiendo el modelo generativo del modelo de embeddings; Gemini
solo consulta metadatos cuando existe clave. La matriz y el corpus se cargan con
sus schemas estrictos y SQLite ejecuta una consulta mínima. Embeddings
desactivados se muestran como `disabled`, sin degradar el sistema. El estado
global es `ok` cuando SQLite, matriz, RAG y al menos un proveedor LLM están
disponibles y ninguna capacidad configurada está caída; en caso contrario es
`degraded`. Las sondas no procesan avisos ni
generan texto o vectores y mantienen el límite de
`HEALTH_CHECK_TIMEOUT_SECONDS` (2 segundos por defecto). El endpoint conserva
HTTP 200 y comunica cada incidencia de forma segura en el cuerpo.

## Prompts, herramienta y seguridad

Antes de que `POST /api/v1/triage` o `POST /api/v1/comparisons` invoquen el
servicio de triaje, un filtro local y determinista anonimiza el texto del aviso
y la ubicación libre opcional. El MVP cubre correos electrónicos, teléfonos
españoles, DNI/NIE e IBAN válidos y los sustituye por `[EMAIL]`, `[PHONE]`,
`[DNI_NIE]` e `[IBAN]`. No utiliza
Gemini, Ollama ni ninguna API externa para detectar estos datos.

Solo los campos anonimizados llegan a proveedores, matriz, recuperación RAG,
métricas y SQLite. Los valores detectados no se conservan, no se devuelven y no
se incorporan a logs. Los errores de validación tampoco reflejan el contenido
original de los campos enviados. La respuesta incluye únicamente un resumen seguro:

```json
{
  "privacy": {
    "redacted": true,
    "redaction_count": 2,
    "redaction_types": ["EMAIL", "DNI_NIE"]
  }
}
```

Este filtro no intenta reconocer nombres propios: hacerlo mediante heurísticas
simples produciría falsos positivos y falsas garantías. Por eso la interfaz
mantiene la recomendación de no introducir nombres ni ningún dato personal. La
anonimización es una defensa adicional del MVP, no una solución legal completa
de prevención de pérdida de datos.

## Avisos similares y posibles riesgos recurrentes

Después de crear correctamente la propuesta de un aviso real, el backend puede
generar con Ollama un embedding del **texto ya anonimizado**. Un embedding es una
representación numérica que permite comparar proximidad semántica. El servicio
recupera únicamente vectores históricos del mismo modelo y dimensión, calcula
el coseno de forma determinista, aplica `EMBEDDING_THRESHOLD`, ordena de mayor a
menor y devuelve como máximo `EMBEDDING_TOP_K` resultados. La ubicación se
normaliza solo para marcar una coincidencia adicional; no se geocodifica ni
forma parte del vector.

El `score` público se acota entre 0 y 1 para facilitar su lectura. Expresa
**similitud semántica**, no probabilidad, confianza del modelo ni confirmación de
que dos avisos describan el mismo incidente. La interfaz solo muestra el bloque
«Posibles avisos relacionados» cuando existen coincidencias, tanto al crear la
propuesta como durante la revisión.

Los vectores se guardan de forma explícita en SQLite junto con el modelo y sus
dimensiones. Para el volumen del MVP esto ofrece trazabilidad y evita añadir una
base vectorial como FAISS o ChromaDB. La clave compuesta aviso/modelo impide
duplicados. Comparaciones y benchmark no generan embeddings porque son casos de
evaluación, no avisos operativos.

La capacidad es complementaria y falla abierta: si Ollama no está disponible,
falta el modelo o el vector es inválido, el aviso y su propuesta se conservan
con `similarity.available=false`. Los logs del fallo incluyen metadatos técnicos
seguros, nunca el texto, la PII ni el vector completo.

Esta funcionalidad **no es RAG**. Usa embeddings para encontrar reincidencias
en avisos históricos; el RAG descrito a continuación recupera documentación
preventiva para fundamentar una propuesta.

## Incertidumbre y prioridad de revisión

El backend aplica la política determinista `v1` después de obtener una propuesta
válida, su evidencia y la similitud histórica. Son tres conceptos distintos:

- **Urgencia PRL**: gravedad y rapidez preventiva propuesta para el riesgo.
- **Incertidumbre técnica**: señales observables que aconsejan extremar la
  comprobación de la salida de IA.
- **Prioridad de revisión**: orden recomendado para que una persona técnica
  atienda la bandeja.

No existe un porcentaje de confianza generado por el LLM. `UncertaintyService`
devuelve `low` cuando no hay señales; `medium` ante una señal; y `high` ante dos
o más señales o varias reparaciones. Las señales cerradas son: salida reparada,
varias reparaciones, categoría `otros`, evidencia incompleta y retry técnico del
proveedor. Un retry se detecta cuando los intentos superan las dos llamadas
lógicas normales —herramienta y salida— más las reparaciones realizadas.

`ReviewPriorityService` parte de la urgencia: baja, media, alta o crítica. La
incertidumbre alta y una recurrencia en la misma ubicación elevan cada una un
nivel, con tope `high`; por tanto, ninguna señal técnica o similitud puede crear
por sí sola una prioridad crítica. La recurrencia en otra ubicación queda como
razón auditable, pero no eleva el nivel. Una urgencia crítica nunca se reduce.

```json
{
  "uncertainty": {
    "level": "medium",
    "reasons": ["provider_output_repaired"]
  },
  "review_priority": {
    "level": "high",
    "reasons": ["high_urgency", "recurrent_same_location"]
  },
  "review_policy_version": "v1"
}
```

Los tres campos se guardan con la ejecución. `GET /api/v1/notices` admite
`review_priority=low|medium|high|critical` y
`order=newest|review_priority`; el orden predeterminado continúa siendo el más
reciente. Las filas creadas antes de esta política conservan valores nulos: no se
recalculan con reglas nuevas sin versionado.

## Panorama preventivo por zonas

`GET /api/v1/metrics/preventive?window_days=30` agrega avisos históricos sin
LLM ni base analítica adicional. Admite exclusivamente `7`, `30`, `90` y `all`.
Las ventanas se aplican sobre la fecha de alta del aviso en UTC; la serie se
agrupa por día para 7/30 días, por semana para 90 días y por mes para todo el
histórico.

La fuente de verdad es humana: una aprobación utiliza su clasificación final
confirmada y una modificación utiliza categoría, urgencia y departamento
corregidos. Los rechazados se cuentan aparte y no alimentan rankings. Las
propuestas pendientes aparecen únicamente como carga operativa, desglosadas por
`review_priority`, y nunca se mezclan con categorías o urgencias confirmadas.

Las zonas se normalizan con Unicode NFKC, compactación de espacios y
mayúsculas/minúsculas. No existe fuzzy matching: `Almacén` y ` ALMACÉN ` se
agrupan, pero `Almacén norte` y `Almacén` continúan separados. Los avisos sin
ubicación forman el grupo explícito «Sin ubicación». No hay coordenadas,
geocodificación ni mapa físico.

Un **foco preventivo** es una combinación exacta zona + categoría con al menos
dos avisos confirmados. Describe concentración observada, no causalidad,
peligrosidad estadística ni predicción. Con menos de tres avisos confirmados la
interfaz advierte que no existen datos suficientes para identificar tendencias.
No se realiza forecasting y los datos sintéticos de demostración no representan
una empresa real.

La matriz está en `config/risk_matrix.v1.json`, contiene una regla para cada una de las nueve categorías y se valida al consultarla. Su prioridad y departamento son recomendaciones didácticas para generar una propuesta revisable: no son normativa, no sustituyen la evaluación profesional y no deben interpretarse como una decisión operativa.

La SPA consulta esa misma versión mediante `GET /api/v1/risk-matrix` y muestra
sus reglas, niveles de urgencia, departamentos y evidencia. La ubicación se
mantiene como contexto libre opcional porque no existe un catálogo canónico de
zonas en el alcance acordado.

El ciclo de triaje admite exactamente una llamada a `consultar_matriz_riesgos`. La herramienta solo acepta la categoría cerrada del dominio; el texto del aviso se trata como datos y no puede seleccionar herramientas ni aportar argumentos adicionales. La matriz no es solo contexto: el backend verifica que la categoría, la urgencia y el departamento finales coincidan con la observación realmente consultada, y cualquier contradicción consume un intento de reparación. Los prompts separan sistema, ejemplos sintéticos, aviso, contexto de herramienta y formato. Indican que se ignoren atributos demográficos irrelevantes. Los logs conservan nombre, argumentos validados, versión y regla aplicada, pero no el texto libre ni la salida completa del proveedor.

Cada respuesta incluye `X-Request-ID`. Los fallos previstos de proveedor,
herramienta, matriz, persistencia o transición mantienen un cuerpo estable:

```json
{
  "error": {"code": "invalid_provider_output", "message": "El proveedor devolvió una respuesta inválida."},
  "request_id": "uuid-generado-por-el-servidor"
}
```

## RAG y evidencia consultada

El triaje sigue este flujo acotado:

```text
aviso → anonimización → triaje → matriz PRL → recuperación documental
      → LLM → contrato Pydantic
      → embedding → similitud → incertidumbre → prioridad de revisión
      → persistencia → revisión humana
```

Después de que la herramienta valida una categoría cerrada, el recuperador
descarta primero los documentos de otras categorías y ordena los restantes por
coincidencia léxica ponderada. Ese orden es determinista y usa el identificador
de fuente para resolver empates. La observación enviada al proveedor contiene
la regla y los fragmentos seleccionados, pero la respuesta estructurada del LLM
no puede declarar fuentes: `ExecutionMetrics.evidence` la construye el backend y
la conserva junto a cada ejecución.

Esta separación evita que una instrucción incluida en el aviso fuerce otra
categoría, invente una referencia o haga aparecer una fuente no consultada. Si
el corpus falta o incumple su contrato, la API devuelve el error estable
`invalid_knowledge_base`; no continúa con evidencia incompleta. El resumen de la
propuesta mantiene sin cambios la validación de exactamente diez palabras.

El corpus activo se aloja localmente en
`data/knowledge/prevention_docs.v1.json`. La API
`GET /api/v1/knowledge-base` publica su versión e inventario de fuentes sin
exponer los fragmentos completos. La pantalla Matriz muestra ambos niveles:
la matriz decide la clasificación orientativa y el RAG aporta documentación de
apoyo después de validar la categoría.

No existe todavía una carga directa de PDF o DOCX. Para añadir esos formatos hay
que implementar una ingestión que extraiga texto, lo divida en fragmentos,
asigne identificador, título, apartado, categorías y palabras clave, valide el
resultado y genere una nueva versión del JSON. Copiar un archivo a la carpeta no
hace que el sistema lo consulte automáticamente.

## Métricas y resiliencia

El número de reparaciones de contrato se configura con `LLM_REPAIR_ATTEMPTS`
entre 0 y 3. Los reintentos externos son independientes de esas reparaciones:
solo cubren fallos transitorios y quedan limitados por la configuración anterior.

`POST /api/v1/comparisons` envía el caso a Ollama y Gemini mediante dos
trabajadores concurrentes. La respuesta conserva siempre el orden estable
`local`, `external`; cada resultado mantiene su propia telemetría y error, y
la escritura SQLite se realiza una sola vez cuando ambos han terminado.

Las métricas nunca convierten un dato ausente en cero. El coste de API local es
`0`, mientras que su coste computacional queda como `null` porque depende del
equipo y no se mide. El coste externo queda como `null` si faltan tokens o la
tarifa no corresponde exactamente al modelo usado. El conjunto
`data/evaluation/avisos.v1.json` está separado de los ejemplos few-shot y cubre
las nueve categorías, ambigüedad, información insuficiente y variantes
demográficas. Sus resultados son académicos, no una referencia profesional.

`GET /api/v1/metrics/summary` agrega las ejecuciones persistidas de avisos y
comparaciones. Para cada proveedor devuelve modelos y parámetros observados, latencia,
intentos, reparaciones, éxito, validez JSON, tokens, coste y acuerdo con la
revisión humana. Este último indicador es la proporción de propuestas aprobadas
sin cambios entre las revisadas; en una comparación exige coincidencia en los
tres campos con su referencia humana. Una corrección, rechazo, discrepancia o
ejecución fallida cuentan como desacuerdo cuando existe referencia. Los campos
sin observaciones permanecen en `null`; la validez JSON, los tokens y el coste
se acompañan de su número de observaciones.

El «benchmark» es una prueba comparativa controlada: ejecuta los mismos 14 casos
sintéticos etiquetados con Ollama y Gemini y contrasta exactitud de categoría,
urgencia y departamento, validez JSON, latencia y coste. Sirve para comparar
estos proveedores dentro del proyecto; no demuestra cuál es el mejor modelo
para cualquier tarea. La calidad se calcula exclusivamente sobre ejecuciones
evaluables; los fallos técnicos se muestran por separado y nunca se interpretan
como una exactitud del 0 %.

SQLite ya conserva la tarjeta operativa completa: texto y ubicación del aviso,
propuesta del agente, departamento propuesto, métricas y evidencia, decisión
humana y clasificación final. La bandeja identifica el destino propuesto y la
pestaña «Registro» reúne los avisos cerrados con su decisión, destino final,
evidencia y auditoría. Un
despliegue que envíe tarjetas a sistemas departamentales debería añadir una cola
de salida transaccional y usar exclusivamente el departamento final validado;
el envío externo sigue fuera del MVP.

La SPA React ofrece alta de avisos, bandeja profesional, revisión
aprobada/modificada/rechazada, matriz de referencia, panel de evaluación y comparación
entre proveedores. La bandeja consulta al servidor con búsqueda y filtros de estado,
urgencia, categoría y motor, y pagina los resultados. El detalle muestra una línea
temporal que combina la recepción y propuesta con los eventos persistidos de auditoría;
los avisos ya revisados pueden reabrirse en modo lectura para consultar responsable,
transición y cambios de clasificación. El panel consume el resumen histórico del backend y permite
contrastar rendimiento, robustez, coste y acuerdo humano de Ollama y Gemini. La
comparación de un caso destaca coincidencias por campo, el modelo más rápido,
las reparaciones y el coste; después permite registrar una única clasificación
humana y muestra cuántos campos acertó cada proveedor. Las comparaciones de
latencia, coste y resultados solo se realizan entre ejecuciones válidas; un
proveedor no disponible no se considera ganador por sus valores parciales o
nulos. La vista comparativa también
permite ejecutar bajo demanda el dataset
sintético completo: cada proveedor procesa los mismos 14 casos y se muestran la
exactitud de categoría, urgencia y departamento, la tasa de JSON válido, la
latencia media y el coste medio. Cada propuesta muestra la justificación generada, una traza
auditable de acción, regla y evidencia, además de las fuentes recuperadas y el
JSON estructurado. Esta vista
explica el resultado verificable del modelo; no almacena ni expone razonamiento
interno privado.
La urgencia se presenta siempre con texto explícito además del color. Los
errores de API se convierten en mensajes seguros y todas las pantallas mantienen
visible el recordatorio de revisión profesional y protocolo de emergencia.
Los formularios de alta y comparación comparten el mismo límite de 4000
caracteres que el contrato Pydantic del backend.

## Demos sintéticas

Las demos no necesitan credenciales, Ollama ni datos reales:

```powershell
python -m scripts.run_demos --scenario main
python -m scripts.run_demos --scenario repair
python -m scripts.run_demos --scenario rate-limit
# Ejecutar las tres:
python -m scripts.run_demos --scenario all
```

`main` crea, consulta y aprueba humanamente una propuesta mediante la API;
`repair` muestra una salida JSON inválida y su única reparación; `rate-limit`
simula un `429`, respeta `Retry-After` y se recupera sin realizar esperas ni
conexiones reales.

## Ética y límites

- Los textos, matrices y datasets incluidos son sintéticos y didácticos.
- La urgencia no cambia por atributos demográficos irrelevantes; el dataset
  contiene pares que solo varían la edad y conservan la etiqueta esperada.
- Un resultado del modelo siempre es una propuesta pendiente de validación
  humana, no una decisión operativa ni una evaluación preventiva acreditada.
- Ante un peligro inmediato debe aplicarse el protocolo de emergencia del
  centro; la aplicación no sustituye ese protocolo.
- No se versionan credenciales, bases locales, logs ni la documentación interna
  de `docs/`.

### Prueba manual local verificada

El 8 de septiembre de 2026 se verificó el flujo completo con Ollama `0.33.3` y
`llama3.2:3b`: selección de `incendio`, consulta de `RM-INCE-001`, reparación
acotada y resultado válido. En el equipo de prueba, el modelo ocupa 2 GB en disco
y Ollama mostró 2,6 GB cargados, contexto 4096 y ejecución 100 % GPU. Son medidas
observadas, no requisitos mínimos; el consumo y la latencia dependen del hardware.

Limitaciones conocidas: un modelo pequeño puede necesitar la reparación configurada;
Ollama 0.33.3 no acepta algunas restricciones de longitud al generar su gramática, por
lo que recibe un esquema compatible derivado de Pydantic y el servicio aplica después
el contrato completo. No se envían datos reales y la propuesta nunca sustituye la
revisión profesional.


## Documentación de trabajo


Solo se publicarán ejemplos sintéticos. Las credenciales, bases de datos y registros de ejecución quedan excluidos del repositorio. Es un prototipo académico de apoyo a la revisión; no sustituye la evaluación profesional ni el protocolo de emergencias del centro.
