# Requisitos y plan de entregas

Todos los requisitos funcionales están pendientes. Esta entrega solo aporta estructura y documentación.

| Requisito del ejercicio | Ubicación prevista | Evidencia de aceptación |
| --- | --- | --- |
| FastAPI y entrada estricta | backend/app/api, schemas | Petición válida y rechazo de tipos o campos inválidos |
| Salida estructurada | schemas, services | Enumeraciones y resumen de exactamente 10 palabras |
| Corrección ante salida inválida | services | JSON defectuoso se corrige o produce error controlado |
| Modelo local y externo | providers | Mismo contrato para ambos adaptadores |
| ReAct y explicación | tools, prompts | Consulta ejecutada, resultado y justificación visible |
| Ejemplos y mitigación de sesgos | prompts | Few-shot y exclusión de atributos demográficos de la urgencia |
| Dashboard conectado | frontend | JSON, explicación y revisión desde la API |
| Comparación | services, frontend | Coste, latencia y calidad con las mismas entradas |
| Tokens y límites de proveedor | core, providers | Métricas por intento, timeout y retry/backoff acotado |
| Pruebas con mocks | tests | Al menos tres tests; incluir entrada válida y salida alucinada |
| Instalación y demo | README.md | Arranque reproducible y flujo completo |

## Secuencia para dos semanas

1. Contratos, catálogos y API mínima con proveedor simulado.
2. Pruebas de entrada válida, JSON inválido, resumen incorrecto y fallo del proveedor.
3. Matriz didáctica, consulta de herramientas y modelo local.
4. Adaptador externo, métricas y límites de reintentos.
5. Persistencia, revisión humana y dashboard.
6. Evaluación comparativa, instrucciones reproducibles y demo.

## Evaluación propuesta

Construir casos sintéticos con etiquetas revisadas para todas las categorías y urgencias, incluyendo textos ambiguos y datos insuficientes. Separar ejemplos del prompt y conjunto de evaluación. Medir acierto por campo, errores de formato, correcciones humanas, latencia y coste. Incluir pares equivalentes con variaciones demográficas para comprobar que la urgencia no cambia por esos atributos. No publicar resultados hasta ejecutar la evaluación.
