# Backend

API FastAPI ejecutable de IAviso Seguro. Centraliza contratos Pydantic,
proveedores Ollama/Gemini, matriz de riesgos, RAG local, persistencia SQLite,
revisión humana, métricas y benchmark.

Rutas de consulta principales:

- `GET /health`: salud de FastAPI, Ollama, Gemini y SQLite.
- `GET /api/v1/risk-matrix`: reglas de clasificación activas.
- `GET /api/v1/knowledge-base`: versión e inventario seguro del RAG.
- `GET /api/v1/notices`: tarjetas persistidas y revisiones.
- `GET /api/v1/metrics/summary`: métricas históricas.

El corpus RAG reside en
`../data/knowledge/prevention_docs.v1.json`. Actualmente se valida JSON
versionado; PDF y DOCX todavía necesitan un proceso de ingestión previo.

Desde la raíz, `start.bat` inicia el backend y la SPA. Para desarrollo manual:

```powershell
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```
