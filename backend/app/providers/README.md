# providers

`TriageProvider` puede solicitar una `ToolCall` o devolver una salida JSON/diccionario. Tras la consulta, recibe una `RiskMatrixObservation`; si el servicio rechaza la respuesta final, también recibe un `RepairContext` acotado.

`ProviderConnectionError` y `ProviderRateLimitError` representan fallos esperados sin exponer detalles internos. La Fase 2 no reintenta conexiones ni límites de uso.

`MockTriageProvider` ejecuta de forma determinista el ciclo herramienta-respuesta para probar la integración. No clasifica texto ni llama a un LLM; toda salida se valida mediante `TriageResult`.

Ollama y el proveedor externo pertenecen a fases posteriores.
