# api

Rutas HTTP:

- `GET /health`: confirma que FastAPI está disponible.
- `POST /api/v1/triage`: valida la entrada y usa Ollama cuando `provider=local`.

La ruta delega en el servicio y no contiene lógica del proveedor ni de la herramienta. OpenAPI documenta `429` para rate limit, `500` para matriz inválida, `502` para salidas o llamadas de herramienta rechazadas y `503` para proveedor no disponible.

Todas las respuestas llevan `X-Request-ID`; los errores previstos incluyen el mismo identificador en el cuerpo y no devuelven stack traces.

El proveedor `external` todavía no está configurado y devuelve `503` de forma
explícita hasta la Fase 5. Las pruebas de contrato inyectan el proveedor simulado;
las pruebas de Ollama usan `httpx.MockTransport` y no requieren un modelo real.
