# Arquitectura prevista

Estado: diseño pendiente de implementación.

## Flujo

Dashboard → API → validación de entrada → servicio de triaje → proveedor → consulta de herramienta → validación de salida → propuesta pendiente → revisión humana → decisión final.

El backend será responsable de la lógica y de la base de datos. La interfaz consumirá la API; no accederá directamente a SQLite ni a los proveedores.

## Contratos

Entrada prevista: texto no vacío con longitud limitada, ubicación opcional y proveedor elegido de una lista permitida. Rechazar campos adicionales y tipos incorrectos.

Salida prevista: `category`, `urgency`, `summary`, `department` y `justification`. Categorías y departamentos serán enumeraciones configuradas; urgencias propuestas: `baja`, `media`, `alta`, `critica`. El resumen tendrá exactamente 10 palabras, contadas por separación de espacios tras normalizar espacios iniciales, finales y repetidos. La justificación será una explicación breve basada en el aviso y la regla consultada.

La respuesta de la API añadirá identificador de propuesta, estado, proveedor, modelo y métricas. Si el proveedor no informa tokens, registrar valor desconocido, nunca inventar cero. El coste local de infraestructura se distinguirá del coste de API. Las tarifas externas deberán guardar moneda, fuente y fecha.

## Herramientas y errores

La consulta de matriz recibirá argumentos validados y devolverá reglas identificables y versionadas. Un límite de pasos evitará bucles. El texto del aviso se tratará como datos, no como instrucciones para invocar acciones arbitrarias.

Separar errores de entrada, salida inválida del modelo, timeout y límite de peticiones. Prever corrección de salida inválida con un máximo de intentos y backoff para fallos transitorios. Contabilizar todos los intentos en las métricas de la petición.

## Persistencia y revisión

Tablas propuestas: `notices` para avisos, `triage_runs` para propuestas y métricas, `reviews` para decisión, cambios, motivo y revisor, y `audit_events` para transiciones con fecha UTC.

Una propuesta empieza en `pending_review` y pasa a `approved`, `modified` o `rejected`. La resolución operativa del aviso es un estado diferente y queda fuera del primer MVP. Conservar la propuesta original junto a la versión validada. Evitar revisiones duplicadas o concurrentes mediante transacciones y control de versión. La identificación fiable de revisores requerirá autenticación antes de cualquier uso compartido real.

## API propuesta

- `GET /health`: estado del servicio.
- `POST /api/v1/triage`: crear una propuesta pendiente.
- `GET /api/v1/notices`: consultar avisos y propuestas.
- `POST /api/v1/notices/{id}/reviews`: aprobar, modificar o rechazar.
- `POST /api/v1/comparisons`: evaluar el mismo texto con ambos proveedores sin duplicar el aviso final.

Estos endpoints todavía no existen.
