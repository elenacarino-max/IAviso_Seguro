# IAviso Seguro

Plataforma de triaje asistido para clasificar, priorizar y supervisar avisos de riesgos laborales.

## Estado

Primera entrega: estructura y diseño del proyecto. La API, los proveedores y el dashboard todavía no están implementados. No procesa avisos reales.

## Objetivo

Un trabajador describe una situación peligrosa. El sistema consulta una matriz de referencia, propone categoría, urgencia, resumen y departamento, y presenta la propuesta a un técnico para aprobarla, modificarla o rechazarla. La clasificación final requiere revisión humana.

El alcance académico adapta un enunciado de servicios urbanos a riesgos laborales; queda pendiente confirmar esta adaptación con el profesorado.

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

Las dependencias son una propuesta inicial; falta verificar su instalación conjunta y fijar las versiones resueltas. No hay comandos de arranque ni pruebas ejecutables todavía. Se añadirán junto con la primera implementación funcional.

## Documentación

- [Valoración y alcance](docs/analisis.md)
- [Arquitectura y contratos previstos](docs/arquitectura.md)
- [Requisitos y entregas](docs/plan.md)
- [Preparación del primer commit](docs/primer_commit.md)

Solo se publicarán ejemplos sintéticos. Las credenciales, bases de datos y registros de ejecución quedan excluidos del repositorio. Es un prototipo académico de apoyo a la revisión; no sustituye la evaluación profesional ni el protocolo de emergencias del centro.
