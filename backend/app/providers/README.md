# providers

`TriageProvider` puede solicitar una `ToolCall` o devolver una salida JSON/diccionario. Tras la consulta, recibe una `RiskMatrixObservation`; si el servicio rechaza la respuesta final, también recibe un `RepairContext` acotado.

`ProviderConnectionError` y `ProviderRateLimitError` representan fallos esperados sin exponer detalles internos.

`MockTriageProvider` ejecuta de forma determinista el ciclo herramienta-respuesta para probar la integración. No clasifica texto ni llama a un LLM; toda salida se valida mediante `TriageResult`.

`OllamaTriageProvider` usa la API oficial `POST /api/chat` mediante `httpx`,
con `stream: false`. La primera llamada expone solo
`consultar_matriz_riesgos`; la segunda incorpora su observación y solicita JSON
estructurado. Timeout, URL, modelo, `temperature` y `top_p` proceden del entorno.
Los errores de transporte y HTTP se convierten en errores controlados sin devolver
el detalle interno de Ollama.

`GeminiTriageProvider` usa la API REST `generateContent` sin añadir un SDK. La
primera llamada fuerza exclusivamente `consultar_matriz_riesgos`; la segunda
devuelve a Gemini el contenido original de la llamada, incluidos `id` y
`thoughtSignature`, junto con la observación. La salida final se solicita como
JSON estructurado y vuelve al contrato común. Los fallos de transporte, `408`,
`429` y `5xx` transitorios usan retry y backoff exponencial acotados; los demás
errores HTTP no se reintentan. Las métricas de tokens ausentes se conservan como
desconocidas.

`ProviderRouter` garantiza la selección explícita: `local` usa Ollama y
`external` usa Gemini, sin fallback entre proveedores. Si falta la clave o el
modelo externo, se produce un `503` controlado antes de acceder a la red.

Prueba manual verificada el 8 de septiembre de 2026 con Ollama `0.33.3` y
`llama3.2:3b`. El modelo ocupó 2 GB en disco y 2,6 GB cargado con contexto 4096
en GPU en el equipo de prueba. Estas cifras no son requisitos mínimos. El modelo
pequeño necesitó una reparación para cumplir el resumen de diez palabras.

Referencias: [API Chat de Ollama](https://docs.ollama.com/api/chat),
[llamadas de herramienta](https://docs.ollama.com/capabilities/tool-calling) y
[salidas estructuradas](https://docs.ollama.com/capabilities/structured-outputs);
[function calling de Gemini](https://ai.google.dev/gemini-api/docs/function-calling)
y [salidas estructuradas de Gemini](https://ai.google.dev/gemini-api/docs/structured-output).
