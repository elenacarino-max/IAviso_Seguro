# Dashboard

Dashboard Streamlit conectado exclusivamente a FastAPI mediante
`IAvisoApiClient`. Incluye:

- alta de avisos con proveedor y ubicación;
- propuesta, justificación, modelo y métricas;
- bandeja para aprobar, modificar o rechazar;
- panel general de estado y urgencias;
- comparación local/externa con una entrada común.

Desde la raíz, arranca primero la API y después:

```powershell
python -m streamlit run frontend/app.py
```

`API_BASE_URL` permite cambiar la URL de FastAPI. Los errores se muestran con
mensajes seguros del contrato HTTP. La urgencia siempre aparece escrita y no
depende solo del color. El aviso sobre revisión profesional y protocolo de
emergencia permanece visible en todas las pantallas.
