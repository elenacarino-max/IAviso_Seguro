# IAviso Seguro

Plataforma de triaje asistido para clasificar, priorizar y supervisar avisos de riesgos laborales.

## Estado

Fase 3 completada: antes de emitir una propuesta, el proveedor debe consultar una matriz didáctica versionada mediante una herramienta con argumentos validados y un único paso permitido. La API conserva la validación y reparación acotada, los errores controlados, el `request_id` y los logs JSON trazables sin el texto del aviso. Los proveedores reales, la persistencia y el dashboard todavía no están implementados. No procesa avisos reales.

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

Las dependencias actuales se han instalado y probado conjuntamente en el entorno local; todavía falta fijar sus versiones resueltas para una entrega reproducible. Para ejecutar todas las pruebas desde la raíz:

```powershell
python -m pytest -q
```

Arrancar la API desde la raíz:

```powershell
python -m uvicorn backend.app.main:app --reload
```

Comprobarla en `http://127.0.0.1:8000/docs` o mediante:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/triage -ContentType 'application/json' -Body '{"text":"Hay agua en el pasillo.","provider":"local"}'
```

La matriz está en `config/risk_matrix.v1.json`, contiene una regla para cada una de las nueve categorías y se valida al consultarla. Su prioridad y departamento son recomendaciones didácticas para generar una propuesta revisable: no son normativa, no sustituyen la evaluación profesional y no deben interpretarse como una decisión operativa.

El ciclo de triaje admite exactamente una llamada a `consultar_matriz_riesgos`. La herramienta solo acepta la categoría cerrada del dominio; el texto del aviso se trata como datos y no puede seleccionar herramientas ni aportar argumentos adicionales. Los logs conservan nombre, argumentos validados, versión y regla aplicada, pero no el texto libre ni la salida completa del proveedor.

Cada respuesta incluye `X-Request-ID`. Los fallos previstos de proveedor, herramienta o matriz mantienen un cuerpo estable:

```json
{
  "error": {"code": "invalid_provider_output", "message": "El proveedor devolvió una respuesta inválida."},
  "request_id": "uuid-generado-por-el-servidor"
}
```

El número de reparaciones de contrato se configura con `LLM_REPAIR_ATTEMPTS` entre 0 y 3. Los reintentos de conexión y el backoff pertenecen a la futura integración del proveedor externo.


## Documentación de trabajo

La carpeta `docs/` se conserva exclusivamente en local y está excluida del control de versiones. El README contiene la información pública necesaria para entender y ejecutar el proyecto; las decisiones internas, comparativas y notas de planificación permanecen en esa carpeta local.

Solo se publicarán ejemplos sintéticos. Las credenciales, bases de datos y registros de ejecución quedan excluidos del repositorio. Es un prototipo académico de apoyo a la revisión; no sustituye la evaluación profesional ni el protocolo de emergencias del centro.
