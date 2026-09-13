# api

Rutas HTTP:

- `GET /health`: confirma que FastAPI está disponible y comunica por separado
  la salud de Ollama, Gemini y SQLite; las sondas de modelos no generan texto.
- `POST /api/v1/triage`: valida la entrada y selecciona Ollama con
  `provider=local` o Gemini con `provider=external`; persiste la propuesta como
  `pending_review` y adjunta la matriz y documentos preventivos consultados.
- `GET /api/v1/catalogs`: publica las categorías, urgencias y departamentos
  cerrados que aceptan los contratos Pydantic y los desplegables de React.
- `GET /api/v1/risk-matrix`: publica la matriz didáctica activa.
- `GET /api/v1/knowledge-base`: publica la versión y el inventario de fuentes
  RAG sin exponer los fragmentos completos.
- `GET /api/v1/notices`: devuelve una página de avisos con sus ejecuciones,
  propuestas y revisiones; admite `search`, `status`, `urgency`, `category`,
  `provider`, `closed`, `page` y `limit` como filtros tipados.
  `closed=true` alimenta el Registro y excluye pendientes antes de paginar.
- `GET /api/v1/notices/{notice_id}/audit-events`: devuelve cronológicamente los
  eventos persistidos de creación y revisión del aviso.
- `POST /api/v1/notices/{notice_id}/reviews`: aprueba, modifica o rechaza la
  propuesta pendiente usando control de versión optimista.
- `POST /api/v1/comparisons`: ejecuta concurrentemente la misma entrada en
  ambos proveedores, conserva el orden estable local/externo, devuelve
  resultados o errores individuales y no crea avisos duplicados.
- `POST /api/v1/comparisons/{comparison_id}/review`: guarda una única
  clasificación humana de referencia para contrastar los resultados de ambos
  proveedores.
- `GET /api/v1/metrics/summary`: agrega avisos y comparaciones persistidas por proveedor
  y devuelve flujo de revisión, latencia, intentos, reparaciones, validez JSON,
  tokens, coste, parámetros y acuerdo con la decisión humana.
- `POST /api/v1/evaluations`: ejecuta los 14 casos sintéticos etiquetados con
  ambos proveedores y devuelve exactitud por campo, validez JSON, latencia y
  coste medios sin crear avisos.

La ruta delega en el servicio y no contiene lógica del proveedor, la herramienta
ni la recuperación. OpenAPI documenta `429` para rate limit, `500` para matriz o
corpus inválidos, `502` para salidas o llamadas de herramienta rechazadas y
`503` para proveedor no disponible.

Todas las respuestas llevan `X-Request-ID`; los errores previstos incluyen el
mismo identificador en el cuerpo y no devuelven stack traces. Una revisión
inexistente produce `404`; una transición duplicada, obsoleta o sin cambio real
produce `409`. Una comparación inexistente también produce `404` y una segunda
referencia humana para la misma comparación produce `409` sin sobrescribir la
primera.

Sin `EXTERNAL_API_KEY`, el proveedor externo devuelve `503` antes de acceder a
la red. Las pruebas de contrato inyectan el proveedor simulado; las pruebas de
Ollama y Gemini usan `httpx.MockTransport` y no requieren modelos ni credenciales
reales.
