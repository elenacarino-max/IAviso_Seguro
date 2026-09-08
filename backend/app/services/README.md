# services

`TriageService` procesa JSON o diccionarios, valida cada salida con `TriageResult` y solicita una reparación cuando el contrato falla. El límite configurable cuenta reparaciones adicionales: con el valor predeterminado 1 hay como máximo dos llamadas.

Cada intento registra solo metadatos técnicos. Si todos fallan, se lanza `InvalidProviderOutputError`; conexión y rate limit se propagan como errores conocidos para que la API los traduzca.

La revisión humana se implementará en su fase correspondiente.
