# repositories

`SQLiteNoticeRepository` crea y consulta avisos, ejecuciones de triaje,
revisiones, eventos de auditoría y comparaciones independientes. La ruta del archivo procede de
`DATABASE_PATH`.

La creación de aviso, propuesta `pending_review` y evento inicial es atómica. La
revisión usa `BEGIN IMMEDIATE`, estado y `expected_version` para que solo una
transición concurrente pueda ganar; además, `reviews.triage_run_id` es único. Se
conservan por separado la propuesta original y la clasificación final. Un
rechazo no tiene clasificación final aceptada.

Cada ejecución conserva sus métricas como JSON validado. Las comparaciones se
guardan en tablas propias y no escriben en `notices`; una migración aditiva
incorpora `metrics_json` a bases creadas por versiones anteriores.

Los tests usan archivos temporales y ejercitan aprobación, modificación,
rechazo, duplicados, versiones obsoletas y dos revisores concurrentes.
