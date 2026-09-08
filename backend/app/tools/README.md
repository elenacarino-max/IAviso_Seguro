# tools

`RiskMatrixTool` implementa la herramienta permitida `consultar_matriz_riesgos`.

- Carga de forma diferida `config/risk_matrix.v1.json`.
- Valida tanto el documento completo como el argumento `category`.
- Devuelve una observación tipada con versión, regla, condiciones y recomendación.
- Convierte argumentos o matrices inválidas en errores controlados.

El orquestador limita la ejecución a una sola consulta por triaje. Ningún texto del aviso se ejecuta como instrucción.
