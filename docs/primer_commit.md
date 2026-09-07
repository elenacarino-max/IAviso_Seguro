# Primer commit

La entrega contiene estructura, configuración de ejemplo y documentación. No incluye todavía una aplicación funcional.

Antes de publicar, revisar desde la raíz:

```powershell
git status --short
git add .
git diff --cached --stat
git diff --cached
```

Comprobar que no se incluyen credenciales, documentos originales, datos reales ni archivos personales. Después:

```powershell
git commit -m "chore: estructura inicial y documentación de IAviso Seguro"
git push -u origin main
```

Si el remoto ha cambiado desde la preparación, ejecutar `git fetch origin` y revisar sus ramas antes del push. No forzar la publicación sobre trabajo existente.
