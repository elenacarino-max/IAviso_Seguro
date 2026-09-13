# Datos

- `examples/`: avisos sintéticos usados como ejemplos, no como referencia de
  evaluación.
- `evaluation/`: dataset etiquetado e independiente para el benchmark.
- `knowledge/`: corpus preventivo sintético y versionado utilizado por el RAG.
- `local/`: SQLite, logs y sellos del lanzador; se excluye de Git salvo su
  marcador vacío.

El corpus activo es JSON validado. PDF y DOCX requieren ingestión previa y no se
indexan automáticamente al copiarlos.
