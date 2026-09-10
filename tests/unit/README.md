# Pruebas unitarias

Desde la raíz: `python -m pytest -q`. Se comprueban contratos, límites, resumen
de 10 palabras, JSON roto, enumeraciones inválidas, reparación, agotamiento,
errores de proveedor y herramienta, cobertura completa de la matriz,
configuración, logging sin contenido sensible y los adaptadores Ollama/Gemini con
transportes simulados. Las pruebas externas incluyen continuidad de llamadas de
función, tokens desconocidos, timeout, `429`, retry y backoff.
También se validan los contratos de revisión y las transacciones SQLite con
aprobación, modificación, rechazo, auditoría y competencia entre revisores.
La fase de métricas añade cobertura de tokens, retries, costes conocidos y
desconocidos, dataset sintético y denominador de corrección humana.
