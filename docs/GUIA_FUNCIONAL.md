# Guía funcional de IAviso Seguro

## Finalidad

IAviso Seguro es un prototipo académico para convertir una observación libre
sobre un riesgo laboral en una propuesta estructurada y revisable. La
inteligencia artificial no cierra avisos ni ejecuta actuaciones: propone y una
persona técnica decide.

El proyecto trabaja con datos sintéticos. No sustituye la evaluación PRL ni el
protocolo de emergencias.

## Perfiles y responsabilidades

| Perfil | Responsabilidad |
| --- | --- |
| Persona informante | Describe el peligro y, opcionalmente, su ubicación. |
| Modelo de IA | Propone categoría, urgencia, resumen, departamento y justificación. |
| Backend | Valida datos, consulta matriz y RAG, registra evidencia y persiste el resultado. |
| Persona técnica | Aprueba, corrige o rechaza la propuesta. |
| Responsable de evaluación | Consulta métricas, compara modelos y ejecuta el benchmark. |

## Recorrido principal

    Nuevo aviso
        ↓
    Selección de Ollama o Gemini
        ↓
    Matriz PRL + recuperación documental
        ↓
    Propuesta pendiente
        ↓
    Bandeja de revisión
        ↓
    Aprobación, corrección o rechazo
        ↓
    Registro de decisiones cerradas

1. La persona describe el aviso sin incluir datos personales.
2. Elige Ollama local o Gemini externo.
3. El backend valida la entrada y solicita una propuesta al proveedor elegido.
4. El modelo debe consultar la matriz de riesgos.
5. Tras validar la categoría, el backend recupera documentación preventiva
   relacionada y conserva las fuentes realmente utilizadas.
6. Pydantic comprueba el contrato de salida, incluido el resumen de exactamente
   diez palabras.
7. La propuesta se guarda en SQLite con estado pendiente.
8. Una persona técnica la aprueba, modifica o rechaza.
9. La decisión queda disponible en el Registro con su auditoría y destino final.

## Pantallas

### Nuevo aviso

Captura texto, ubicación opcional y motor. Ollama indica que los datos
permanecen en local; Gemini informa de que la petición se envía al proveedor.
El botón principal solo se activa cuando existe texto válido.

### Bandeja

Contiene únicamente propuestas pendientes. Permite buscar y filtrar, consultar
la propuesta original, su justificación, la matriz y la evidencia RAG. La
revisión admite tres decisiones:

- Aprobada: confirma sin cambios categoría, urgencia y departamento.
- Corregida: exige modificar al menos uno de esos tres campos.
- Rechazada: conserva la propuesta, pero no crea derivación departamental.

### Registro

Muestra exclusivamente avisos cerrados. Cada tarjeta indica estado y destino.
Al abrirla aparecen la observación original, la propuesta, la decisión humana,
la clasificación final, las fuentes consultadas y la línea temporal.

### Panel

Resume avisos y ejecuciones persistidas. Distingue propuestas aprobadas sin
cambios, correcciones y pendientes. Para cada proveedor presenta en el mismo
orden latencia, salidas reparadas, acuerdo con técnico, JSON válido, tokens y
coste.

Acuerdo con técnico significa aprobación sin cambios en un aviso o coincidencia
completa de categoría, urgencia y departamento en una comparación revisada.

### Matriz

Separa dos conceptos:

- La matriz PRL define reglas orientativas de clasificación y departamento.
- El RAG recupera documentación de apoyo después de validar la categoría.

La pantalla muestra también la versión y el inventario del corpus activo.

### Comparación

Ejecuta un único caso simultáneamente en Ollama y Gemini. No crea dos avisos.
Contrasta cada campo, latencia, reparaciones, tokens, coste y evidencia. Cuando
se registra una referencia humana, muestra por campo qué modelo coincide y su
porcentaje total.

### Benchmark

Ejecuta los mismos catorce casos sintéticos etiquetados en ambos proveedores y
mide exactitud por campo, validez JSON, latencia y coste. Es una evaluación del
proyecto, no una afirmación universal sobre qué modelo es mejor. Con Gemini
configurado puede generar consumo de API.

## Persistencia y trazabilidad

SQLite conserva el aviso, la propuesta original, proveedor y modelo, métricas,
evidencia, revisión, clasificación final y eventos de auditoría. La propuesta y
la decisión humana nunca se sobrescriben entre sí.

El MVP no envía todavía tarjetas a sistemas departamentales. Ese escalado debe
usar una cola transaccional y exclusivamente el departamento final validado.

## Puesta en marcha

Desde Windows, en la raíz del proyecto:

    .\start.bat

El lanzador prepara las dependencias, inicia los servicios disponibles, abre la
SPA y muestra los puertos seleccionados. Ctrl+C detiene solo los procesos que
el propio lanzador haya creado.
