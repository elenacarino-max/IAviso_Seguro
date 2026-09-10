# repositories

`SQLiteNoticeRepository` crea y consulta cuatro entidades: avisos, ejecuciones de
triaje, revisiones y eventos de auditoría. La ruta del archivo procede de
`DATABASE_PATH`.

La creación de aviso, propuesta `pending_review` y evento inicial es atómica. La
revisión usa `BEGIN IMMEDIATE`, estado y `expected_version` para que solo una
transición concurrente pueda ganar; además, `reviews.triage_run_id` es único. Se
conservan por separado la propuesta original y la clasificación final. Un
rechazo no tiene clasificación final aceptada.

Los tests usan archivos temporales y ejercitan aprobación, modificación,
rechazo, duplicados, versiones obsoletas y dos revisores concurrentes.
