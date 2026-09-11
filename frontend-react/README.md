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
