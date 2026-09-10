# integration

Se prueban `GET /health`, `POST /api/v1/triage`, `GET /api/v1/notices`, revisión
humana, validación 422, `request_id`, conflictos 409, errores controlados
404/429/500/502/503, `Retry-After`, OpenAPI y continuidad tras un fallo.

Las pruebas utilizan el proveedor simulado y una base SQLite temporal por caso;
no realizan conexiones externas ni escriben en la base de desarrollo.
