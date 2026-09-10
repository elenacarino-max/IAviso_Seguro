# Pruebas unitarias

Desde la raíz: `python -m pytest -q`. Se comprueban contratos, límites, resumen
de 10 palabras, JSON roto, enumeraciones inválidas, reparación, agotamiento,
errores de proveedor y herramienta, cobertura completa de la matriz,
configuración, logging sin contenido sensible y los adaptadores Ollama/Gemini con
transportes simulados. Las pruebas externas incluyen continuidad de llamadas de
función, tokens desconocidos, timeout, `429`, retry y backoff.
