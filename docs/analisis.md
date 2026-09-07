# Valoración del proyecto

## Conclusión

La propuesta ofrece un caso de uso coherente para el ejercicio: transforma texto libre en una propuesta estructurada y revisable. La matriz de riesgos da una finalidad concreta a la consulta de herramientas y la revisión humana permite contrastar el resultado. En esta revisión no existía código local y el remoto no anunciaba referencias; se evalúa el diseño, no una aplicación operativa.

## Documentos de partida

Se han contrastado la propuesta de triaje laboral del documento de análisis y el enunciado del Proyecto I del Módulo V. Se utilizan como material de referencia para delimitar el trabajo. Sus ejemplos y sugerencias no equivalen a funcionalidades implementadas. Los originales no se incorporan al repositorio.

## Puntos fuertes

- Flujo fácil de demostrar con avisos sintéticos y decisiones humanas.
- Categoría, urgencia y departamento permiten validar contratos cerrados.
- La misma colección de avisos permite comparar los dos proveedores.
- SQLite y una interfaz sencilla mantienen razonable el alcance individual.

## Aspectos que deben resolverse

1. Confirmar con el profesorado la adaptación desde servicios urbanos a riesgos laborales.
2. Limitar el MVP: un centro, aviso por texto, una propuesta y una revisión. Dejar fuera planes comerciales, multicliente, notificaciones e instalación corporativa.
3. Definir categorías y reglas antes de escribir los prompts. No inferir automáticamente una urgencia solo a partir de la categoría.
4. Exigir exactamente 10 palabras en el resumen; los ejemplos narrativos de la propuesta no constituyen un contrato válido.
5. Ejecutar realmente la consulta a la matriz. Mencionarla en el prompt no demuestra un ciclo de herramientas.
6. Mostrar una justificación breve sustentada en evidencias y registrar herramienta, argumentos y resultado. Contrastar con el docente cómo satisfacer la exigencia de explicación intermedia del enunciado con el modelo elegido.
7. Separar el borrador pendiente del registro validado: guardar una propuesta no significa aprobarla ni resolver el peligro.
8. Acotar reintentos, tiempos de espera y corrección de JSON para que un fallo del proveedor termine en un error controlado.
9. Medir calidad con etiquetas de referencia, además de coste y latencia; una respuesta JSON válida puede clasificar mal.

## Alcance recomendado

Construir primero un recorrido completo con proveedor simulado: enviar aviso, obtener propuesta, revisarla y conservar ambas versiones. Después integrar el proveedor local, el externo y la comparación. Las matrices y etiquetas iniciales serán didácticas, pendientes de validación profesional; no se presentan como normativa ni como una evaluación de riesgos acreditada.

La ejecución local reduce envíos externos, pero por sí sola no garantiza privacidad. Utilizar únicamente datos sintéticos durante el desarrollo y evitar textos completos o credenciales en los registros técnicos.
