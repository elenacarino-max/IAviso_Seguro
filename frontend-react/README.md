# Interfaz React de IAviso Seguro

SPA principal del proyecto, construida con React, TypeScript y Vite. FastAPI conserva toda la lógica de negocio y el frontend consume únicamente endpoints `/api/v1/...`. La interfaz Streamlit existente se mantiene como respaldo del requisito académico original.

## Desarrollo local

Con FastAPI disponible en `http://127.0.0.1:8000`:

```powershell
cd frontend-react
npm install
npm run dev
```

Vite abre `http://127.0.0.1:5173` y redirige `/api` al backend. Para usar otro destino:

```powershell
$env:VITE_API_PROXY_TARGET="http://127.0.0.1:9000"
npm run dev
```

## Validación

```powershell
npm test
npm run build
```

No se almacenan credenciales en el navegador. Las claves y la selección real de modelos continúan configurándose en el backend.

La barra lateral consume `GET /health` una vez al cargar y muestra FastAPI,
Ollama con su modelo, Gemini y SQLite. Un círculo vacío indica que el servicio no
está configurado; un estado de error se acompaña de texto y no depende solo del
color.

Cada propuesta representa `metrics.evidence` en una sección «Evidencia
consultada» con fuente, título, apartado, versión y extracto. La interfaz no
deduce referencias a partir de la justificación del modelo: muestra únicamente
las seleccionadas por el backend. Los dos formularios comparten el límite de
4000 caracteres del contrato de entrada.

La vista «Matriz» representa dos capas distintas: las reglas PRL proponen la
clasificación y el departamento, mientras que el bloque «RAG preventivo»
consulta `GET /api/v1/knowledge-base` para mostrar el corpus documental activo.
La bandeja rotula el departamento como «Destino propuesto» y conserva por
separado la clasificación final decidida durante la revisión humana. La pestaña
«Registro» consulta solo avisos cerrados y abre la misma ficha detallada en modo
consulta, incluyendo decisión, destino final, evidencia y auditoría.

El Panel denomina «Aprobadas sin cambios» exclusivamente a las propuestas
confirmadas sin corrección y muestra «Acuerdo con técnico» por proveedor. La
comparación de un caso representa la referencia humana en una tabla por campo
con el porcentaje de coincidencia de Ollama y Gemini.
