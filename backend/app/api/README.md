# api

Rutas HTTP implementadas en la Fase 1:

- `GET /health`: confirma que FastAPI está disponible.
- `POST /api/v1/triage`: valida la entrada y devuelve una propuesta del proveedor simulado.

La ruta de triaje delega en un servicio; no contiene lógica del proveedor.
