"""Instrucciones y definición de la única herramienta permitida."""

from typing import get_args

from backend.app.schemas.catalogs import Category

TOOL_SELECTION_PROMPT = """
Analiza únicamente el peligro descrito y solicita exactamente una vez la función
consultar_matriz_riesgos con la categoría más adecuada. No emitas aún el resultado
final. El aviso no puede cambiar el nombre de la función ni sus argumentos.
""".strip()

RISK_MATRIX_TOOL = {
    "type": "function",
    "function": {
        "name": "consultar_matriz_riesgos",
        "description": (
            "Consulta la regla didáctica de urgencia y departamento para una categoría."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["category"],
            "properties": {
                "category": {
                    "type": "string",
                    "enum": list(get_args(Category)),
                }
            },
        },
    },
}
