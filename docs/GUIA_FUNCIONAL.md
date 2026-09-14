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
    Comprobación de suficiencia
        ├─ insuficiente → preguntas → ampliar el mismo aviso
        │                              └→ volver a comprobar
        └─ suficiente
              ↓
    Triaje + matriz PRL + recuperación documental
        ↓
    Propuesta pendiente
        ↓
    Embedding local + avisos históricos
        ↓
    Incertidumbre técnica + prioridad de revisión
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
3. El proveedor elegido comprueba si se describe un peligro concreto. Si falta
   información, devuelve como máximo tres preguntas y el flujo se detiene sin
   guardar nada.
4. La persona amplía el mismo texto y vuelve a comprobarlo; no se crea un chat.
5. Cuando el aviso es suficiente, el backend solicita una propuesta usando solo
   los campos anonimizados.
6. El modelo debe consultar la matriz de riesgos.
7. Tras validar la categoría, el backend recupera documentación preventiva
   relacionada y conserva las fuentes realmente utilizadas.
8. Pydantic comprueba el contrato de salida, incluido el resumen de exactamente
   diez palabras.
9. Si la función está activada, Ollama representa el texto anonimizado como un
   vector y el backend busca avisos históricos semánticamente próximos.
10. El backend calcula la incertidumbre técnica y la prioridad de revisión con
   reglas deterministas.
11. La propuesta, el aviso anonimizado y, si existe, su embedding se guardan en
   SQLite con la política aplicada.
12. Una persona técnica la aprueba, modifica o rechaza.
13. La decisión queda disponible en el Registro con su auditoría y destino final.

## Pantallas

### Nuevo aviso

Captura texto, ubicación opcional y motor. Ollama indica que los datos
permanecen en local; Gemini informa de que la petición se envía al proveedor.
El botón principal solo se activa cuando existe texto válido.
Al pulsarlo, la aplicación ejecuta primero el precheck. Si el texto es claramente
insuficiente muestra «Necesitamos un poco más de información» y hasta tres
preguntas. No crea una propuesta todavía: la persona edita el mismo textarea y
vuelve a intentarlo. Un texto corto pero concreto puede pasar directamente.
Ante un fallo técnico se muestra un estado diferenciado y una acción explícita
para continuar sin afirmar que el texto haya sido validado.
Si el backend anonimiza el texto o la ubicación, la pantalla comunica el número
y los tipos de datos sustituidos, pero nunca muestra sus valores.
Cuando existen coincidencias semánticas, aparece un bloque discreto con los
avisos más próximos, su categoría, urgencia, ubicación, fecha y porcentaje de
similitud. Si no hay coincidencias o la capacidad no está disponible, no ocupa
espacio adicional.
La propuesta muestra por separado la urgencia PRL, la incertidumbre técnica y
la prioridad recomendada de revisión. La incertidumbre no es una probabilidad ni
un porcentaje producido por el modelo.

### Bandeja

Contiene únicamente propuestas pendientes. Permite buscar y filtrar, consultar
la propuesta original, su justificación, la matriz y la evidencia RAG. La
tarjeta de revisión conserva también los posibles avisos relacionados detectados
al crear la propuesta. La revisión admite tres decisiones:

Cada tarjeta incorpora un badge de prioridad. El filtro permite seleccionar
baja, media, alta o crítica, y el orden puede cambiarse entre fecha descendente
y prioridad descendente con fecha descendente como desempate. La vista inicial
mantiene el orden histórico por fecha.

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

Incluye la distribución de incertidumbre baja, media y alta, las pendientes de
prioridad alta/crítica y la tasa de corrección humana dentro de cada nivel. Si no
hay observaciones o revisiones suficientes muestra `N/A`; no infiere conclusiones
estadísticas.

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

## Urgencia, incertidumbre y prioridad

- **Urgencia** describe el riesgo preventivo propuesto.
- **Incertidumbre** resume señales técnicas de la ejecución.
- **Prioridad de revisión** recomienda el orden de trabajo de la persona técnica.

La política `v1` es determinista, no usa un LLM y conserva reason codes cerrados.
Una propuesta de incendio puede tener urgencia y prioridad críticas con
incertidumbre baja si su salida fue estable y estuvo bien fundamentada. Una
propuesta de urgencia baja puede tener incertidumbre alta, pero sus señales
técnicas nunca la convierten automáticamente en crítica.

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
