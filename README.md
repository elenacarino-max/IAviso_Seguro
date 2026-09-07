# IAviso Seguro

Plataforma de triaje asistido para clasificar, priorizar y supervisar avisos de riesgos laborales.

## Estado

Implementados los contratos Pydantic de entrada y salida y sus pruebas unitarias. La API, los proveedores y el dashboard todavía no están implementados. No procesa avisos reales.

## Objetivo

Un trabajador describe una situación peligrosa. El sistema consulta una matriz de referencia, propone categoría, urgencia, resumen y departamento, y presenta la propuesta a un técnico para aprobarla, modificarla o rechazarla. La clasificación final requiere revisión humana.

La adaptación del alcance académico de servicios urbanos a riesgos laborales está aprobada, según confirmación de la responsable del proyecto el 7 de septiembre de 2026.

## Arquitectura propuesta

- Backend: Python, FastAPI y validación estricta con Pydantic.
- Interfaz: Streamlit, comunicada exclusivamente con la API.
- Modelos: uno local mediante Ollama y uno externo mediante un adaptador independiente.
- Persistencia: SQLite para el prototipo, separando propuestas y decisiones finales.
- Evaluación: Pytest y casos sintéticos comunes a ambos proveedores.

## Estructura

```text
backend/app/
  api/           Rutas y respuestas HTTP
  core/          Configuración y observabilidad
  schemas/       Contratos de entrada y salida
  services/      Triaje, reintentos y revisión humana
  providers/     Adaptadores local y externo
  tools/         Consulta de la matriz de riesgos
  prompts/       Instrucciones y ejemplos versionados
  repositories/  Persistencia de avisos y decisiones
frontend/        Dashboard
config/          Configuración de dominio y matriz de referencia
data/           Ejemplos sintéticos y almacenamiento local
tests/          Pruebas unitarias, integración y respuestas simuladas
docs/           Análisis, arquitectura y plan de trabajo
```

## Preparación del entorno

Python 3.11 o superior. Desde la raíz, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Las dependencias son una propuesta inicial; falta verificar su instalación conjunta y fijar las versiones resueltas. Todavía no hay servidor ejecutable. Para comprobar los contratos desde la raíz:

```powershell
python -m pytest -q
```

## Documentación de trabajo

La carpeta `docs/` se conserva exclusivamente en local y está excluida del control de versiones. El README contiene la información pública necesaria para entender y ejecutar el proyecto; las decisiones internas, comparativas y notas de planificación permanecen en esa carpeta local.

Solo se publicarán ejemplos sintéticos. Las credenciales, bases de datos y registros de ejecución quedan excluidos del repositorio. Es un prototipo académico de apoyo a la revisión; no sustituye la evaluación profesional ni el protocolo de emergencias del centro.
