"""Instrucciones exclusivas del contrato de salida."""

from backend.app.schemas import TriageResult

OUTPUT_FORMAT_PROMPT = """
Devuelve exclusivamente un objeto JSON válido que cumpla el esquema adjunto.
No añadas Markdown ni campos adicionales. La categoría debe coincidir exactamente
con la consultada. Usa la urgencia y el departamento de la matriz. El resumen debe
tener exactamente diez palabras. La justificación debe citar la versión y la regla
de la matriz y recordar que la propuesta requiere revisión profesional.
Ejemplo de resumen de diez palabras:
"Humo visible requiere aislar zona y activar revisión profesional inmediata."
""".strip()


def ollama_output_schema() -> dict[str, object]:
    """Deriva el subconjunto de JSON Schema aceptado por la gramática de Ollama."""

    source = TriageResult.model_json_schema()
    properties = {
        name: {
            key: value
            for key, value in definition.items()
            if key in {"type", "enum"}
        }
        for name, definition in source["properties"].items()
    }
    return {
        "type": "object",
        "properties": properties,
        "required": source["required"],
    }
