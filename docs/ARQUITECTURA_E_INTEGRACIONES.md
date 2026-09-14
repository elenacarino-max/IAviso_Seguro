# Arquitectura e integraciones de IAviso Seguro

## Visión general

La SPA React nunca accede directamente a modelos ni a SQLite. Toda operación
pasa por FastAPI, que aplica contratos Pydantic, orquesta el triaje, controla
las fuentes y persiste los resultados.

    Navegador
       │ HTTP / JSON
       ▼
    React + TypeScript
       │ /api/v1 y /health
       ▼
    FastAPI
       ├── Pydantic y catálogos cerrados
       ├── Privacidad determinista
       ├── Precheck de suficiencia
       ├── Servicio de triaje
       │    ├── Ollama local
       │    ├── Gemini externo
       │    ├── Matriz PRL versionada
       │    └── RAG local versionado
       ├── Similitud de avisos
       │    └── Embeddings locales de Ollama
       ├── Métricas y benchmark
       └── Repositorio SQLite

## Estructura del repositorio

| Ruta | Responsabilidad |
| --- | --- |
| frontend-react | SPA principal, cliente HTTP, tipos, componentes y estilos. |
| frontend | Interfaz Streamlit conservada como respaldo académico. |
| backend/app/api | Endpoints FastAPI y dependencias sustituibles. |
| backend/app/schemas | Contratos estrictos de entrada, salida y persistencia. |
| backend/app/services | Privacidad, triaje, recuperación, política de revisión, métricas, salud y evaluación. |
| backend/app/providers | Adaptadores de Ollama, Gemini y proveedor simulado. |
| backend/app/tools | Herramienta acotada de consulta de matriz. |
| backend/app/repositories | Persistencia y transacciones SQLite. |
| backend/app/prompts | Sistema, ejemplos, formato y contexto de herramienta. |
| config | Matriz de riesgos versionada. |
| data/knowledge | Corpus preventivo RAG versionado. |
| data/evaluation | Dataset sintético del benchmark. |
| tests | Pruebas unitarias e integración sin servicios reales. |
| .github/workflows | Integración continua de backend y frontend. |

## Secuencia de triaje

    React -> FastAPI: texto, ubicación, proveedor
    FastAPI -> Pydantic: validar entrada
    FastAPI -> Privacidad: sustituir PII en texto y ubicación libre
    FastAPI -> Proveedor seleccionado: comprobar suficiencia del texto limpio
    Proveedor -> FastAPI: suficiente o hasta tres preguntas
    FastAPI -> React: si falta información, detener sin persistir
    React -> FastAPI: volver a comprobar el mismo texto ampliado
    React -> FastAPI: iniciar el triaje con el texto ya suficiente
    FastAPI -> Privacidad: anonimizar de nuevo la petición de triaje
    FastAPI -> Proveedor: solicitar clasificación con campos anonimizados
    Proveedor -> FastAPI: llamada consultar_matriz_riesgos
    FastAPI -> Matriz: validar categoría y recuperar regla
    FastAPI -> RAG: recuperar fragmentos de la categoría
    FastAPI -> Proveedor: regla y evidencia
    Proveedor -> FastAPI: propuesta JSON
    FastAPI -> Pydantic: validar o reparar salida
    FastAPI -> Ollama embeddings: vectorizar solo el texto anonimizado
    FastAPI -> SQLite: recuperar vectores históricos del mismo modelo
    FastAPI -> Similitud: coseno, umbral, orden y top-k
    FastAPI -> UncertaintyService: telemetría, categoría y evidencia
    FastAPI -> ReviewPriorityService: urgencia, incertidumbre y recurrencia
    FastAPI -> SQLite: guardar propuesta, política v1, similitud y embedding
    FastAPI -> React: propuesta pendiente
    Técnico -> FastAPI: aprobar, corregir o rechazar
    FastAPI -> SQLite: guardar decisión y auditoría

Solo se permite una llamada a la herramienta de matriz. El texto libre se trata
como datos y no puede habilitar herramientas adicionales ni declarar las
fuentes visibles.

La dependencia `PrivacyService` se inyecta en las rutas de triaje y comparación.
Su ejecución precede al servicio de triaje, por lo que proveedores, matriz, RAG,
métricas y repositorio solo reciben los campos libres anonimizados. El servicio
usa patrones locales y checksum para correo, teléfono español, DNI/NIE e IBAN. Su
resultado no conserva coincidencias: solo texto limpio, indicador, recuento y
tipos detectados. Los nombres propios quedan fuera del MVP.

El precheck usa `InputAssessmentService`, el protocolo
`InputAssessmentProvider` y adaptadores específicos para Ollama y Gemini. No
reutiliza artificialmente `TriageService`: por ello no puede ejecutar llamadas
de herramienta, matriz, recuperación documental, reparaciones de triaje,
métricas o embeddings. `POST /api/v1/triage/precheck` no recibe un repositorio y
no crea `notice`, `triage_run` ni `audit_event`.

Su contrato cerrado admite solo `hazard`, `exposure`, `immediacy` y `context`
como aspectos ausentes. Un resultado suficiente exige listas vacías; uno
insuficiente exige entre una y tres preguntas seguras. Un error técnico se
representa con `available=false` y `sufficient=null`, se registra sin texto ni
respuesta del proveedor y deja la decisión de continuar a la persona usuaria.

`SimilarityService` se inyecta por separado y solo se ejecuta en el endpoint de
triaje una vez validada la propuesta. Recibe exclusivamente el texto y ubicación
del payload ya saneado. El proveedor de embeddings está detrás del protocolo
`EmbeddingProvider`, por lo que las pruebas usan dobles deterministas sin un
Ollama real. Un fallo de esta capacidad se captura antes de persistir el aviso y
no altera el éxito del triaje.

`UncertaintyService` y `ReviewPriorityService` son servicios puros sin acceso a
red, prompts ni modelos. El primero observa reparaciones, categoría genérica,
presencia de evidencia y retries de transporte. El segundo toma la urgencia como
base y aplica elevaciones acotadas por incertidumbre alta y recurrencia en la
misma ubicación. No leen el score de similitud como confianza.

SQLite conserva `uncertainty_json`, `review_priority_json` y
`review_policy_version` en `triage_runs`. La inicialización añade las columnas de
forma compatible; las ejecuciones antiguas permanecen en `NULL` y no se
recalculan. Los nuevos contratos se recuperan en bandeja, registro y respuesta
de revisión. Comparación y benchmark continúan fuera de esta política operativa.

### Política de revisión v1

| Cálculo | Regla |
| --- | --- |
| Incertidumbre baja | Ninguna señal técnica. |
| Incertidumbre media | Una señal técnica. |
| Incertidumbre alta | Dos o más señales, o múltiples reparaciones. |
| Prioridad base | Mismo nivel que la urgencia PRL. |
| Incertidumbre alta | Eleva un nivel, con tope alta. |
| Recurrencia misma zona | Eleva un nivel, con tope alta. |
| Recurrencia otra zona | Se registra, pero no eleva. |
| Urgencia crítica | Permanece crítica. |

Los reason codes de incertidumbre son `provider_output_repaired`,
`multiple_repairs`, `generic_category`, `incomplete_evidence` y `provider_retry`.
Los de prioridad son la urgencia base (`low_urgency`, `medium_urgency`,
`high_urgency`, `critical_urgency`) y, cuando proceda, `high_uncertainty`,
`recurrent_risk` o `recurrent_same_location`.

El estado técnico del precheck no se transmite a `/triage` en el contrato actual;
por eso `v1` no inventa ni persiste `precheck_unavailable`.

## Relaciones con servicios externos

| Servicio | Dirección | Datos intercambiados | Credencial | Comportamiento si falta |
| --- | --- | --- | --- | --- |
| Ollama | FastAPI hacia servidor local | Precheck y triaje sobre texto anonimizado; evidencia; opcionalmente embedding local | No | El precheck queda no disponible; triaje devuelve un error controlado; similitud falla abierta. |
| Gemini | FastAPI hacia API REST de Google | Precheck y triaje sobre texto anonimizado; evidencia y uso de tokens | Clave solo en backend | El precheck queda no disponible y el triaje devuelve 503. |
| SQLite | FastAPI hacia archivo local | Avisos anonimizados, propuestas, política versionada, revisiones, auditoría, comparaciones y métricas | No | La salud lo comunica y la escritura falla de forma controlada. |
| GitHub Actions | GitHub hacia el repositorio | Código y pruebas; no avisos de usuario | No para la CI actual | Backend y frontend se validan con mocks. |

El navegador no recibe claves ni llama directamente a Gemini u Ollama. Las
URLs, modelos, tiempos de espera, reintentos y muestreo se configuran mediante
variables de entorno del backend.

## Comparación y evaluación

La comparación anonimiza una vez y crea dos trabajadores concurrentes. Ambos
reciben la misma entrada limpia y comparten contrato, matriz y recuperación
documental. Cada ejecución
mantiene sus métricas y errores; el resultado conserva el orden Ollama/Gemini.

El benchmark usa un dataset independiente de los ejemplos del prompt. Ejecuta
catorce casos por proveedor y no crea avisos en la bandeja. La referencia humana
de una comparación se guarda una sola vez y permite calcular coincidencia real.
Ni comparación ni benchmark invocan el proveedor de embeddings o escriben en
`notice_embeddings`.

## Embeddings de recurrencia (no RAG)

`OllamaEmbeddingProvider` usa el endpoint local `/api/embed` y el modelo indicado
por `EMBEDDING_MODEL`. No descarga modelos ni contiene un nombre fijado en la
lógica. El operador debe ejecutar previamente, por ejemplo,
`ollama pull nomic-embed-text` y activar `EMBEDDING_ENABLED`.

El servicio consulta solo históricos del mismo modelo y descarta dimensiones
incompatibles. Calcula el coseno en Python, lo acota entre 0 y 1 para el contrato
público, filtra por `EMBEDDING_THRESHOLD`, ordena de forma descendente y limita
la respuesta a `EMBEDDING_TOP_K`. Este valor mide cercanía semántica: no es una
probabilidad, confianza del LLM ni prueba de que sea el mismo incidente.

La ubicación se normaliza con Unicode, espacios y mayúsculas/minúsculas para
producir `same_location`; no interviene en el embedding. Los fallos se registran
sin texto, PII ni vector y producen `similarity.available=false`.

SQLite es suficiente para el volumen pequeño del prototipo y permite auditar el
modelo y dimensión de cada vector sin incorporar FAISS, ChromaDB u otra
dependencia. Esta búsqueda entre avisos operativos es distinta del RAG: no
recupera documentación ni alimenta la propuesta del LLM.

## Matriz y RAG

La matriz activa reside en config/risk_matrix.v1.json y funciona como autoridad
orientativa de clasificación. El corpus RAG reside en
data/knowledge/prevention_docs.v1.json y aporta fragmentos preventivos después
de que la categoría haya sido validada.

El recuperador actual es local, determinista y léxico; no necesita base
vectorial ni servicio externo. Primero filtra por categoría y después puntúa
coincidencias. La API pública del corpus solo devuelve metadatos.

PDF y DOCX no se leen directamente. Una futura ingestión debe extraer texto,
fragmentarlo, asignar metadatos y categorías, validar cobertura y generar una
nueva versión del corpus. Copiar documentos a la carpeta no los indexa.

## Modelo de datos

Las tablas principales son:

- notices: observación y ubicación.
- triage_runs: propuesta original, proveedor, modelo, estado, métricas,
  incertidumbre, prioridad y versión de política.
- notice_embeddings: vector JSON, modelo, dimensión y fecha asociados al aviso;
  clave única por aviso/modelo.
- reviews: decisión humana y clasificación final.
- audit_events: transiciones y actor.
- comparisons y comparison_runs: ejecuciones paralelas sin duplicar avisos.
- comparison_reviews: referencia humana única.

Las revisiones usan versión esperada, transacción inmediata y restricción de
unicidad para impedir decisiones simultáneas o sobrescrituras.

## Despliegue y operación

En desarrollo, Vite sirve React y reenvía API y salud a FastAPI. El lanzador de
Windows elige puertos libres y gestiona únicamente sus propios procesos.

En Docker, una construcción multietapa compila React y FastAPI sirve el
resultado en el mismo origen. El volumen data/local conserva SQLite y Ollama se
alcanza en el host mediante host.docker.internal.

La salud comprueba FastAPI, modelo de Ollama, configuración de Gemini y una
consulta mínima de SQLite. Las sondas de modelo no generan contenido.

## Límites antes de un uso real

- Incorporar autenticación y roles para identificar revisores.
- Cifrar secretos y definir políticas de retención y datos personales.
- Ampliar la detección más allá del MVP; los nombres propios no se infieren.
- Sustituir el corpus sintético por documentación PRL validada y versionada.
- Añadir una outbox idempotente para integraciones departamentales.
- Revisar legalmente proveedores, transferencias de datos y trazabilidad.
- Implantar observabilidad, copias de seguridad y recuperación operativa.
