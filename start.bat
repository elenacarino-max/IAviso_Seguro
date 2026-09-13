@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
set "IAVISO_EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %IAVISO_EXIT_CODE%
