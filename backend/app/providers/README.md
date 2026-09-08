# providers

`TriageProvider` acepta salidas JSON o diccionarios y recibe un `RepairContext` cuando el servicio rechaza una respuesta. El contexto contiene la salida inválida y tipos de error Pydantic para que un adaptador futuro pueda pedir una corrección.

`ProviderConnectionError` y `ProviderRateLimitError` representan fallos esperados sin exponer detalles internos. La Fase 2 no reintenta conexiones ni límites de uso.

`MockTriageProvider` continúa devolviendo una respuesta sintética determinista. No clasifica riesgos ni llama a un LLM; toda salida se valida mediante `TriageResult`.

Ollama y el proveedor externo pertenecen a fases posteriores.
