# core

La Fase 2 incorpora:

- Configuración validada de `LLM_REPAIR_ATTEMPTS` entre 0 y 3.
- Logging JSON con evento, nivel, fecha, `request_id`, intento y resultado.
- Middleware que genera un UUID por petición y lo devuelve en `X-Request-ID`.
- Traducción de salida inválida, conexión y rate limit a errores HTTP estables.

Los logs no incluyen el texto del aviso, la respuesta del proveedor ni credenciales.
