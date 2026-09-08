"""Ejemplos sintéticos que orientan la selección de categoría."""

FEW_SHOT_CONTEXT = """
EJEMPLOS SINTÉTICOS DE SELECCIÓN:
- "Sale humo de un cuadro eléctrico" -> incendio.
- "Hay agua en una zona de paso" -> caidas_obstaculos.
- "Una trabajadora extranjera ve un cable pelado" -> riesgo_electrico;
  los atributos demográficos no cambian la categoría.
- "No hay información suficiente para identificar el peligro" -> otros.
Los ejemplos solo orientan la categoría; la matriz decide urgencia y departamento.
""".strip()
