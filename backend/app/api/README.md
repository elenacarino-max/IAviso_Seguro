# api

Rutas HTTP:

- `GET /health`: confirma que FastAPI está disponible.
- `POST /api/v1/triage`: valida la entrada y devuelve una propuesta del proveedor simulado.

La ruta delega en el servicio y no contiene lógica del proveedor ni de la herramienta. OpenAPI documenta `429` para rate limit, `500` para matriz inválida, `502` para salidas o llamadas de herramienta rechazadas y `503` para proveedor no disponible.

Todas las respuestas llevan `X-Request-ID`; los errores previstos incluyen el mismo identificador en el cuerpo y no devuelven stack traces.
