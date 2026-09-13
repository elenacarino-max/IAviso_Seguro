# Arquitectura e integraciones de IAviso Seguro

## Visión general

La SPA React nunca accede directamente a modelos ni a SQLite. Toda operación
pasa por FastAPI, que aplica contratos Pydantic, orquesta el triaje, controla
las fuentes y persiste los resultados.

    Navegador
       │ HTTP / JSON
       ▼
    React + TypeScript
       │ /api/v1 y /health
       ▼
    FastAPI
       ├── Pydantic y catálogos cerrados
       ├── Servicio de triaje
       │    ├── Ollama local
       │    ├── Gemini externo
       │    ├── Matriz PRL versionada
       │    └── RAG local versionado
       ├── Métricas y benchmark
       └── Repositorio SQLite

## Estructura del repositorio

| Ruta | Responsabilidad |
| --- | --- |
| frontend-react | SPA principal, cliente HTTP, tipos, componentes y estilos. |
| frontend | Interfaz Streamlit conservada como respaldo académico. |
| backend/app/api | Endpoints FastAPI y dependencias sustituibles. |
| backend/app/schemas | Contratos estrictos de entrada, salida y persistencia. |
| backend/app/services | Triaje, recuperación, métricas, salud y evaluación. |
| backend/app/providers | Adaptadores de Ollama, Gemini y proveedor simulado. |
| backend/app/tools | Herramienta acotada de consulta de matriz. |
| backend/app/repositories | Persistencia y transacciones SQLite. |
| backend/app/prompts | Sistema, ejemplos, formato y contexto de herramienta. |
| config | Matriz de riesgos versionada. |
| data/knowledge | Corpus preventivo RAG versionado. |
| data/evaluation | Dataset sintético del benchmark. |
| tests | Pruebas unitarias e integración sin servicios reales. |
| .github/workflows | Integración continua de backend y frontend. |

## Secuencia de triaje

    React -> FastAPI: texto, ubicación, proveedor
    FastAPI -> Pydantic: validar entrada
    FastAPI -> Proveedor: solicitar clasificación
    Proveedor -> FastAPI: llamada consultar_matriz_riesgos
    FastAPI -> Matriz: validar categoría y recuperar regla
    FastAPI -> RAG: recuperar fragmentos de la categoría
    FastAPI -> Proveedor: regla y evidencia
    Proveedor -> FastAPI: propuesta JSON
    FastAPI -> Pydantic: validar o reparar salida
    FastAPI -> SQLite: guardar propuesta, métricas y evidencia
    FastAPI -> React: propuesta pendiente
    Técnico -> FastAPI: aprobar, corregir o rechazar
    FastAPI -> SQLite: guardar decisión y auditoría

Solo se permite una llamada a la herramienta de matriz. El texto libre se trata
como datos y no puede habilitar herramientas adicionales ni declarar las
fuentes visibles.

## Relaciones con servicios externos

| Servicio | Dirección | Datos intercambiados | Credencial | Comportamiento si falta |
| --- | --- | --- | --- | --- |
| Ollama | FastAPI hacia servidor local | Prompt, aviso y evidencia; respuesta del modelo | No | El proveedor local devuelve un error controlado. |
| Gemini | FastAPI hacia API REST de Google | Prompt, aviso y evidencia; respuesta y uso de tokens | Clave solo en backend | Devuelve 503 antes de intentar la red. |
| SQLite | FastAPI hacia archivo local | Avisos, propuestas, revisiones, auditoría, comparaciones y métricas | No | La salud lo comunica y la escritura falla de forma controlada. |
| GitHub Actions | GitHub hacia el repositorio | Código y pruebas; no avisos de usuario | No para la CI actual | Backend y frontend se validan con mocks. |

El navegador no recibe claves ni llama directamente a Gemini u Ollama. Las
URLs, modelos, tiempos de espera, reintentos y muestreo se configuran mediante
variables de entorno del backend.

## Comparación y evaluación

La comparación crea dos trabajadores concurrentes. Ambos reciben la misma
entrada y comparten contrato, matriz y recuperación documental. Cada ejecución
mantiene sus métricas y errores; el resultado conserva el orden Ollama/Gemini.

El benchmark usa un dataset independiente de los ejemplos del prompt. Ejecuta
catorce casos por proveedor y no crea avisos en la bandeja. La referencia humana
de una comparación se guarda una sola vez y permite calcular coincidencia real.

## Matriz y RAG

La matriz activa reside en config/risk_matrix.v1.json y funciona como autoridad
orientativa de clasificación. El corpus RAG reside en
data/knowledge/prevention_docs.v1.json y aporta fragmentos preventivos después
de que la categoría haya sido validada.

El recuperador actual es local, determinista y léxico; no necesita base
vectorial ni servicio externo. Primero filtra por categoría y después puntúa
coincidencias. La API pública del corpus solo devuelve metadatos.

PDF y DOCX no se leen directamente. Una futura ingestión debe extraer texto,
fragmentarlo, asignar metadatos y categorías, validar cobertura y generar una
nueva versión del corpus. Copiar documentos a la carpeta no los indexa.

## Modelo de datos

Las tablas principales son:

- notices: observación y ubicación.
- triage_runs: propuesta original, proveedor, modelo, estado y métricas.
- reviews: decisión humana y clasificación final.
- audit_events: transiciones y actor.
- comparisons y comparison_runs: ejecuciones paralelas sin duplicar avisos.
- comparison_reviews: referencia humana única.

Las revisiones usan versión esperada, transacción inmediata y restricción de
unicidad para impedir decisiones simultáneas o sobrescrituras.

## Despliegue y operación

En desarrollo, Vite sirve React y reenvía API y salud a FastAPI. El lanzador de
Windows elige puertos libres y gestiona únicamente sus propios procesos.

En Docker, una construcción multietapa compila React y FastAPI sirve el
resultado en el mismo origen. El volumen data/local conserva SQLite y Ollama se
alcanza en el host mediante host.docker.internal.

La salud comprueba FastAPI, modelo de Ollama, configuración de Gemini y una
consulta mínima de SQLite. Las sondas de modelo no generan contenido.

## Límites antes de un uso real

- Incorporar autenticación y roles para identificar revisores.
- Cifrar secretos y definir políticas de retención y datos personales.
- Sustituir el corpus sintético por documentación PRL validada y versionada.
- Añadir una outbox idempotente para integraciones departamentales.
- Revisar legalmente proveedores, transferencias de datos y trazabilidad.
- Implantar observabilidad, copias de seguridad y recuperación operativa.
