# Contratos de triaje

Implementados en `triage.py`; vocabulario cerrado en `catalogs.py`.

- Entrada: `text` entre 1 y 4000 caracteres, `provider` obligatorio (`local` o `external`) y `location` opcional (nulo o entre 1 y 200 caracteres).
- Salida: `category`, `urgency`, `summary`, `department` y `justification` obligatorios.
- Se rechazan campos adicionales y conversiones implícitas de tipos.
- Resumen de exactamente 10 palabras y hasta 300 caracteres. Se normalizan espacios; cada palabra debe contener una letra o un número. La puntuación adjunta no añade palabras.
- Justificación entre 1 y 2000 caracteres.

El catálogo inicial tiene nueve categorías, cuatro urgencias y cuatro departamentos: prevención, mantenimiento, seguridad y limpieza. Las categorías no asignan automáticamente urgencia ni departamento. `otros` permite describir avisos no cubiertos sin inventar una categoría nueva.

`risk_matrix.py` añade contratos estrictos e inmutables para el documento versionado, cada regla, la consulta y la observación devuelta por la herramienta. La matriz debe cubrir las nueve categorías exactamente una vez, usar identificadores únicos y declarar que no es normativa.

Estos contratos validan la estructura, no la corrección profesional de una propuesta. Las decisiones humanas se implementarán después.
