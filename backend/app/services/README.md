# services

`TriageService` orquesta un ciclo acotado: exige una consulta previa a `consultar_matriz_riesgos`, entrega la observación al proveedor y valida la salida final con `TriageResult`.

Solo se permite una llamada de herramienta. Se rechazan herramientas desconocidas, argumentos fuera de contrato, matrices inválidas, una segunda consulta y resultados cuya categoría contradiga la observación. Las salidas inválidas admiten las mismas reparaciones configurables de la Fase 2.

Cada intento y ejecución registra solo metadatos técnicos trazables. Los errores esperados se propagan para que la API los traduzca sin exponer detalles internos.

Tras un triaje válido, la API delega la creación de la propuesta y las
transiciones humanas al repositorio transaccional. La propuesta original nunca
se reemplaza por la clasificación revisada.
