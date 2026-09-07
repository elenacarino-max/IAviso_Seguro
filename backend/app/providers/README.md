# providers

`TriageProvider` define el contrato mínimo intercambiable. `MockTriageProvider` completa el flujo de la Fase 1 con una respuesta sintética determinista.

El mock no clasifica riesgos ni llama a un LLM. Su salida siempre se valida mediante `TriageResult`.

Ollama y el proveedor externo pertenecen a fases posteriores.
