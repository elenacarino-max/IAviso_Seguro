# Puesta en marcha de IAviso Seguro

Esta guía reúne la instalación, configuración, arranque y validación del
proyecto. Para conocer las pantallas y los recorridos de usuario, consulta la
[guía funcional](GUIA_FUNCIONAL.md). Para entender sus componentes internos,
consulta la [arquitectura e integraciones](ARQUITECTURA_E_INTEGRACIONES.md).

## Requisitos

- Windows con PowerShell para usar el lanzador incluido.
- Python 3.11 o superior.
- Node.js 20.19+ o 22.12+ para desarrollar la SPA.
- [Ollama](https://ollama.com/) y un modelo compatible con llamadas de
  herramienta para el proveedor local.
- Docker Desktop, solo si se prefiere el despliegue en contenedor.
- Una clave de Gemini, solo si se quiere utilizar el proveedor externo.

## Arranque recomendado

Desde la raíz del repositorio:

```powershell
.\start.ps1
```

También se puede ejecutar `start.bat` con doble clic. El lanzador:

- crea `.env` y `.venv` cuando faltan;
- sincroniza las dependencias cuando cambian los archivos de bloqueo;
- inicia Ollama y prepara el modelo configurado cuando es necesario;
- levanta FastAPI y la SPA de React;
- elige puertos locales libres si los configurados están ocupados;
- abre la aplicación en el navegador.

`Ctrl+C` detiene únicamente los procesos iniciados por el lanzador. Las opciones
`-NoBrowser` y `-SkipInstall` permiten omitir la apertura del navegador o la
instalación automática. Los diagnósticos se guardan en `data/local/*.log`, que
no se versiona.

## Instalación manual

### 1. Preparar Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Para reproducir exactamente el entorno validado se puede instalar
`requirements-lock.txt`. Ese archivo fue generado con Python 3.14 en Windows;
`requirements.txt` mantiene los rangos compatibles de las dependencias directas.

### 2. Preparar Ollama

El modelo es configurable. Este ejemplo coincide con la configuración inicial:

```powershell
ollama pull llama3.2:3b
ollama serve
```

Si Ollama ya se ejecuta como aplicación, no es necesario lanzar `ollama serve`.

La detección opcional de avisos similares usa un segundo modelo local. La
aplicación no lo descarga automáticamente:

```powershell
ollama pull nomic-embed-text
```

Después se habilita en `.env`:

```dotenv
EMBEDDING_ENABLED=true
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_THRESHOLD=0.78
EMBEDDING_TOP_K=3
EMBEDDING_TIMEOUT_SECONDS=10
```

Con `EMBEDDING_ENABLED=false`, el triaje continúa funcionando sin generar ni
consultar vectores.

### 3. Iniciar backend y frontend

En una terminal, desde la raíz:

```powershell
python -m uvicorn backend.app.main:app --reload
```

En otra terminal:

```powershell
cd frontend-react
npm install
npm run dev
```

La SPA se abre en `http://127.0.0.1:5173` y Vite redirige `/api` a
`http://127.0.0.1:8000`.

La interfaz Streamlit se conserva como respaldo académico:

```powershell
python -m streamlit run frontend/app.py
```

## Configuración

`.env.example` contiene todas las opciones documentadas. Las principales se
agrupan así:

| Área | Variables |
| --- | --- |
| Persistencia y RAG | `DATABASE_PATH`, `KNOWLEDGE_BASE_PATH`, `RAG_MAX_SOURCES` |
| Ollama | `OLLAMA_BASE_URL`, `LOCAL_MODEL`, `OLLAMA_TEMPERATURE`, `OLLAMA_TOP_P` |
| Similitud | `EMBEDDING_ENABLED`, `EMBEDDING_MODEL`, `EMBEDDING_THRESHOLD`, `EMBEDDING_TOP_K` |
| Gemini | `EXTERNAL_API_KEY`, `EXTERNAL_MODEL`, `EXTERNAL_TEMPERATURE`, `EXTERNAL_TOP_P` |
| Resiliencia | `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `LLM_REPAIR_ATTEMPTS` |

La clave externa permanece únicamente en el backend. Si falta, la API responde
con un error controlado y no redirige el aviso a otro proveedor.

## Docker

El contenedor compila React y sirve la SPA desde FastAPI. Con Ollama iniciado en
el equipo anfitrión:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

La aplicación queda disponible en `http://127.0.0.1:8000`. El contenedor accede
a Ollama mediante `host.docker.internal` y conserva SQLite en `data/local/`.
Para detenerlo:

```powershell
docker compose down
```

## Comprobaciones

### Backend

```powershell
python -m pytest -q
```

### Frontend

```powershell
cd frontend-react
npm test
npm run build
```

La integración continua repite estas validaciones con proveedores simulados;
no necesita secretos, Ollama ni modelos descargados.

### Salud y documentación HTTP

- Estado del sistema: `http://127.0.0.1:8000/health`
- OpenAPI interactiva: `http://127.0.0.1:8000/docs`
- Catálogos: `http://127.0.0.1:8000/api/v1/catalogs`

La lista completa de rutas, filtros y respuestas está en la
[documentación del API](../backend/app/api/README.md).

## Demos sintéticas

Estas demostraciones no requieren credenciales, Ollama ni datos reales:

```powershell
python -m scripts.run_demos --scenario main
python -m scripts.run_demos --scenario repair
python -m scripts.run_demos --scenario rate-limit
python -m scripts.run_demos --scenario all
```

- `main` crea, consulta y aprueba una propuesta mediante la API.
- `repair` muestra una salida JSON inválida y su reparación acotada.
- `rate-limit` simula un `429`, respeta `Retry-After` y se recupera sin conexiones
  ni esperas reales.

## Datos locales

Por defecto, SQLite se guarda en `data/local/iaviso.db`. En esa carpeta también
se crean logs y sellos del lanzador. Credenciales, bases locales y registros de
ejecución están excluidos del repositorio.
