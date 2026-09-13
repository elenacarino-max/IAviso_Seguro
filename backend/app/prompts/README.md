# prompts

Prompts versionados y separados por responsabilidad:

- `system.py`: límites, revisión humana, resistencia a instrucciones dentro del
  aviso, uso exclusivo de la evidencia recuperada y exclusión de atributos
  demográficos irrelevantes.
- `few_shot.py`: ejemplos sintéticos de selección de categoría.
- `tool_context.py`: única herramienta permitida y su esquema cerrado.
- `output_format.py`: formato final y esquema compatible derivado de Pydantic.
- `messages.py`: ensamblado que mantiene el aviso separado del resto del contexto.

La salida final siempre vuelve al parser estricto de `TriageResult`; el prompt y
la gramática de Ollama no reemplazan la validación de la aplicación.
La evidencia viaja dentro de la observación de herramienta. Los identificadores
visibles no forman parte de la salida generada: los adjunta el backend para que
una alucinación del modelo no pueda presentarse como fuente consultada.
