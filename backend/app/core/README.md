# core

Las Fases 2 y 3 incorporan:

- Configuración validada de `LLM_REPAIR_ATTEMPTS` entre 0 y 3.
- Logging JSON con evento, nivel, fecha, `request_id`, intento y resultado; para herramientas añade nombre, argumentos validados, versión de matriz y regla aplicada.
- Middleware que genera un UUID por petición y lo devuelve en `X-Request-ID`.
- Traducción de fallos esperados de proveedor, herramienta y matriz a errores HTTP estables.

Los logs no incluyen el texto del aviso, la respuesta del proveedor ni credenciales.
