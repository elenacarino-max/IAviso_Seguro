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
    Anonimización local
        ↓
    Matriz PRL + recuperación documental
        ↓
    Propuesta pendiente
        ↓
    Embedding local + avisos históricos
        ↓
    Bandeja de revisión
        ↓
    Aprobación, corrección o rechazo
        ↓
    Registro de decisiones cerradas

1. La persona describe el aviso, evita incluir datos personales y elige Ollama
   local o Gemini externo.
2. El backend valida la entrada y sustituye PII conocida por marcadores sin
   conservar sus valores.
3. El backend solicita una propuesta al proveedor elegido usando solo el texto
   anonimizado.
4. El modelo debe consultar la matriz de riesgos.
5. Tras validar la categoría, el backend recupera documentación preventiva
   relacionada y conserva las fuentes realmente utilizadas.
6. Pydantic comprueba el contrato de salida, incluido el resumen de exactamente
   diez palabras.
7. Si la función está activada, Ollama representa el texto anonimizado como un
   vector y el backend busca avisos históricos semánticamente próximos.
8. La propuesta, el aviso anonimizado y, si existe, su embedding se guardan en
   SQLite con estado pendiente.
9. Una persona técnica la aprueba, modifica o rechaza.
10. La decisión queda disponible en el Registro con su auditoría y destino final.

## Pantallas

### Nuevo aviso

Captura texto, ubicación opcional y motor. Ollama indica que los datos
permanecen en local; Gemini informa de que la petición se envía al proveedor.
El botón principal solo se activa cuando existe texto válido.
Si el backend anonimiza el texto o la ubicación, la pantalla comunica el número
y los tipos de datos sustituidos, pero nunca muestra sus valores.
Cuando existen coincidencias semánticas, aparece un bloque discreto con los
avisos más próximos, su categoría, urgencia, ubicación, fecha y porcentaje de
similitud. Si no hay coincidencias o la capacidad no está disponible, no ocupa
espacio adicional.

### Bandeja

Contiene únicamente propuestas pendientes. Permite buscar y filtrar, consultar
la propuesta original, su justificación, la matriz y la evidencia RAG. La
tarjeta de revisión conserva también los posibles avisos relacionados detectados
al crear la propuesta. La
revisión admite tres decisiones:

- Aprobada: confirma sin cambios categoría, urgencia y departamento.
- Corregida: exige modificar al menos uno de esos tres campos.
- Rechazada: conserva la propuesta, pero no crea derivación departamental.

### Registro

Muestra exclusivamente avisos cerrados. Cada tarjeta indica estado y destino.
Al abrirla aparecen la observación anonimizada persistida, la propuesta, la
decisión humana, la clasificación final, las fuentes consultadas y la línea
temporal.

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

SQLite conserva el aviso ya anonimizado, la propuesta original, proveedor y
modelo, métricas, evidencia, revisión, clasificación final y eventos de
auditoría. Si la recurrencia está activada, conserva además un único embedding
por aviso y modelo, su dimensión y el resultado de similitud mostrado durante la
revisión. La propuesta y la decisión humana nunca se sobrescriben entre sí.

## Privacidad del MVP

El filtro se ejecuta en FastAPI antes de matriz, RAG, Ollama, Gemini y SQLite.
Detecta correos electrónicos, teléfonos españoles, DNI/NIE e IBAN y utiliza los
marcadores `[EMAIL]`, `[PHONE]`, `[DNI_NIE]` e `[IBAN]`. Los valores encontrados
no forman parte del resultado interno, la respuesta, las métricas ni los logs.

No detecta automáticamente nombres propios. La recomendación funcional sigue
siendo no introducir nombres ni otros datos personales; el filtro reduce una
exposición accidental, pero no garantiza que cualquier PII posible sea
reconocida.

## Detección de recurrencia

Esta función opcional compara el significado del nuevo aviso con avisos reales
anteriores. Los embeddings se generan localmente mediante Ollama y siempre a
partir del texto que ya ha pasado por `PrivacyService`. No se usa Gemini ni se
envía el vector a un servicio externo.

El porcentaje mostrado es el coseno entre dos vectores, acotado para la interfaz:
indica similitud semántica, no confianza, probabilidad ni identidad del incidente.
La coincidencia de ubicación es solo una señal visual adicional tras normalizar
mayúsculas y espacios. El umbral y el número máximo de resultados son
configurables.

Para el MVP los vectores viven en SQLite por su bajo volumen y trazabilidad. Esta
función no es RAG: busca avisos posiblemente recurrentes, mientras el RAG busca
fragmentos de documentación preventiva. Comparación y benchmark no crean
embeddings. Si Ollama o el modelo de embeddings fallan, el alta continúa sin
mostrar el bloque de relacionados.

El MVP no envía todavía tarjetas a sistemas departamentales. Ese escalado debe
usar una cola transaccional y exclusivamente el departamento final validado.

## Puesta en marcha

Desde Windows, en la raíz del proyecto:

    .\start.bat

El lanzador prepara las dependencias, inicia los servicios disponibles, abre la
SPA y muestra los puertos seleccionados. Ctrl+C detiene solo los procesos que
el propio lanzador haya creado.
