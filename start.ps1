<#
.SYNOPSIS
Arranca IAviso Seguro y sus servicios de desarrollo con un solo comando.

.EXAMPLE
.\start.ps1

.EXAMPLE
.\start.ps1 -NoBrowser

.PARAMETER NoBrowser
No abre automáticamente la interfaz en el navegador.

.PARAMETER SkipInstall
No crea ni sincroniza los entornos; requiere dependencias ya instaladas.

.PARAMETER SmokeTest
Comprueba el arranque y cierra inmediatamente los procesos de prueba.

.PARAMETER Help
Muestra esta ayuda sin preparar ni iniciar servicios.
#>

[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$SkipInstall,
    [switch]$SmokeTest,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$FrontendRoot = Join-Path $ProjectRoot "frontend-react"
$EnvPath = Join-Path $ProjectRoot ".env"
$EnvExamplePath = Join-Path $ProjectRoot ".env.example"
$LogRoot = Join-Path $ProjectRoot "data\local"
$FrontendUrl = "http://127.0.0.1:5173"
$OwnedProcesses = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()
$ProcessJob = [IntPtr]::Zero

function Write-Step {
    param([string]$Message)

    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-DotEnvValue {
    param(
        [string]$Name,
        [string]$Default
    )

    if (-not (Test-Path -LiteralPath $EnvPath)) {
        return $Default
    }

    $Prefix = "$Name="
    $Line = Get-Content -LiteralPath $EnvPath |
        Where-Object { $_.StartsWith($Prefix) } |
        Select-Object -First 1
    if ($null -eq $Line) {
        return $Default
    }

    $Value = $Line.Substring($Prefix.Length).Trim()
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $Default
    }
    return $Value
}

function Test-Endpoint {
    param([string]$Url)

    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Get-Sha256 {
    param([string]$Path)

    $Stream = [System.IO.File]::OpenRead($Path)
    $Hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        $Bytes = $Hasher.ComputeHash($Stream)
        return ([System.BitConverter]::ToString($Bytes)).Replace("-", "")
    }
    finally {
        $Hasher.Dispose()
        $Stream.Dispose()
    }
}

function Normalize-PathEnvironment {
    $Environment = [System.Environment]::GetEnvironmentVariables()
    $PathKeys = @(
        $Environment.Keys |
            Where-Object {
                [string]::Equals(
                    [string]$_,
                    "Path",
                    [System.StringComparison]::OrdinalIgnoreCase
                )
            }
    )
    if ($PathKeys.Count -le 1) {
        return
    }

    # PowerShell Core puede transmitir Path y PATH a Windows PowerShell. Su
    # Start-Process rechaza ese diccionario duplicado, por lo que se normaliza
    # después de localizar Python y Node y antes de crear procesos secundarios.
    $PathValue = [System.Environment]::GetEnvironmentVariable(
        "Path",
        [System.EnvironmentVariableTarget]::Process
    )
    foreach ($PathKey in $PathKeys) {
        [System.Environment]::SetEnvironmentVariable(
            [string]$PathKey,
            $null,
            [System.EnvironmentVariableTarget]::Process
        )
    }
    [System.Environment]::SetEnvironmentVariable(
        "Path",
        $PathValue,
        [System.EnvironmentVariableTarget]::Process
    )
}

function Wait-Endpoint {
    param(
        [string]$Url,
        [int]$TimeoutSeconds,
        [System.Diagnostics.Process]$Process
    )

    $Timer = [System.Diagnostics.Stopwatch]::StartNew()
    while ($Timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        if (($null -ne $Process) -and $Process.HasExited) {
            return $false
        }
        if (Test-Endpoint -Url $Url) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Show-LogTail {
    param([string[]]$Paths)

    foreach ($Path in $Paths) {
        if (Test-Path -LiteralPath $Path) {
            Write-Host ""
            Write-Host "--- $Path ---" -ForegroundColor Yellow
            Get-Content -LiteralPath $Path -Tail 30
        }
    }
}

function Initialize-ProcessJob {
    $Source = @"
using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;

public static class IAvisoProcessJob
{
    private const uint KillOnJobClose = 0x00002000;

    [StructLayout(LayoutKind.Sequential)]
    private struct BasicLimitInformation
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct IoCounters
    {
        public ulong ReadOperationCount;
        public ulong WriteOperationCount;
        public ulong OtherOperationCount;
        public ulong ReadTransferCount;
        public ulong WriteTransferCount;
        public ulong OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ExtendedLimitInformation
    {
        public BasicLimitInformation BasicLimitInformation;
        public IoCounters IoInfo;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryUsed;
        public UIntPtr PeakJobMemoryUsed;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr CreateJobObject(IntPtr securityAttributes, string name);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetInformationJobObject(
        IntPtr job,
        int informationClass,
        IntPtr information,
        uint informationLength
    );

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

    [DllImport("kernel32.dll")]
    private static extern bool CloseHandle(IntPtr handle);

    public static IntPtr Create()
    {
        IntPtr job = CreateJobObject(IntPtr.Zero, null);
        if (job == IntPtr.Zero)
            throw new Win32Exception(Marshal.GetLastWin32Error());

        ExtendedLimitInformation limits = new ExtendedLimitInformation();
        limits.BasicLimitInformation.LimitFlags = KillOnJobClose;
        int length = Marshal.SizeOf(typeof(ExtendedLimitInformation));
        IntPtr pointer = Marshal.AllocHGlobal(length);
        try
        {
            Marshal.StructureToPtr(limits, pointer, false);
            if (!SetInformationJobObject(job, 9, pointer, (uint)length))
                throw new Win32Exception(Marshal.GetLastWin32Error());
        }
        catch
        {
            CloseHandle(job);
            throw;
        }
        finally
        {
            Marshal.FreeHGlobal(pointer);
        }
        return job;
    }

    public static void Add(IntPtr job, int processId)
    {
        using (Process process = Process.GetProcessById(processId))
        {
            if (!AssignProcessToJobObject(job, process.Handle))
                throw new Win32Exception(Marshal.GetLastWin32Error());
        }
    }

    public static void Close(IntPtr job)
    {
        if (job != IntPtr.Zero)
            CloseHandle(job);
    }
}
"@

    Add-Type -TypeDefinition $Source -Language CSharp
    return [IAvisoProcessJob]::Create()
}

function Register-OwnedProcess {
    param([System.Diagnostics.Process]$Process)

    # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE hace que Windows cierre estos hijos
    # incluso si la consola desaparece antes de que PowerShell ejecute finally.
    [IAvisoProcessJob]::Add($ProcessJob, $Process.Id)
    $OwnedProcesses.Add($Process)
}

function Stop-OwnedProcess {
    param([System.Diagnostics.Process]$Process)

    if (($null -eq $Process) -or $Process.HasExited) {
        return
    }

    # npm y algunos servidores crean procesos hijo. taskkill /T limita el
    # cierre al árbol exacto que inició este script y no toca servicios previos.
    & taskkill.exe /PID $Process.Id /T /F 2>$null | Out-Null
}

function Resolve-PythonEnvironment {
    $VirtualPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $VirtualPython) {
        return $VirtualPython
    }
    if ($SkipInstall) {
        throw "No existe .venv. Ejecuta sin -SkipInstall para crearlo."
    }

    Write-Step "Creando el entorno virtual de Python"
    $Launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $Launcher) {
        & $Launcher.Source -3 -m venv (Join-Path $ProjectRoot ".venv") | Out-Host
    }
    else {
        $Launcher = Get-Command python -ErrorAction SilentlyContinue
        if ($null -eq $Launcher) {
            throw "No se encontro Python 3.11 o superior."
        }
        & $Launcher.Source -m venv (Join-Path $ProjectRoot ".venv") | Out-Host
    }
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo crear el entorno virtual."
    }
    return $VirtualPython
}

function Sync-BackendDependencies {
    param([string]$PythonPath)

    $RequirementsPath = Join-Path $ProjectRoot "requirements-dev.txt"
    $StampPath = Join-Path $ProjectRoot ".venv\.iaviso-requirements.sha256"
    $ExpectedHash = Get-Sha256 -Path $RequirementsPath
    $CurrentHash = if (Test-Path -LiteralPath $StampPath) {
        (Get-Content -LiteralPath $StampPath -Raw).Trim()
    }
    else {
        ""
    }

    # El sello evita reinstalar en cada arranque, pero detecta cambios reales
    # del archivo de dependencias.
    if ($SkipInstall -or ($ExpectedHash -eq $CurrentHash)) {
        return
    }

    Write-Step "Sincronizando dependencias de Python"
    & $PythonPath -m pip install -r $RequirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudieron instalar las dependencias de Python."
    }
    Set-Content -LiteralPath $StampPath -Value $ExpectedHash -NoNewline
}

function Sync-FrontendDependencies {
    $Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($null -eq $Npm) {
        throw "No se encontro Node.js/npm. Instala Node 22."
    }
    $Node = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($null -eq $Node) {
        throw "No se encontro el ejecutable de Node.js. Instala Node 22."
    }

    $LockPath = Join-Path $FrontendRoot "package-lock.json"
    $ModulesPath = Join-Path $FrontendRoot "node_modules"
    $StampPath = Join-Path $ModulesPath ".iaviso-package-lock.sha256"
    $ExpectedHash = Get-Sha256 -Path $LockPath
    $CurrentHash = if (Test-Path -LiteralPath $StampPath) {
        (Get-Content -LiteralPath $StampPath -Raw).Trim()
    }
    else {
        ""
    }

    if ($SkipInstall -and -not (Test-Path -LiteralPath $ModulesPath)) {
        throw "No existe node_modules. Ejecuta sin -SkipInstall para instalarlo."
    }
    if ($SkipInstall -or ((Test-Path -LiteralPath $ModulesPath) -and ($ExpectedHash -eq $CurrentHash))) {
        return [pscustomobject]@{
            NpmPath = $Npm.Source
            NodePath = $Node.Source
        }
    }

    Write-Step "Sincronizando dependencias de React"
    Push-Location $FrontendRoot
    try {
        # Out-Host conserva el progreso en pantalla sin mezclarlo con el valor
        # de retorno de la función (la ruta del ejecutable npm).
        & $Npm.Source ci | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "No se pudieron instalar las dependencias de React."
        }
        Set-Content -LiteralPath $StampPath -Value $ExpectedHash -NoNewline
    }
    finally {
        Pop-Location
    }
    return [pscustomobject]@{
        NpmPath = $Npm.Source
        NodePath = $Node.Source
    }
}

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Detailed
    return
}

if (-not (Test-Path -LiteralPath $EnvPath)) {
    Copy-Item -LiteralPath $EnvExamplePath -Destination $EnvPath
    Write-Host "Se ha creado .env desde .env.example." -ForegroundColor Green
}
New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null

$BackendOutLog = Join-Path $LogRoot "backend.out.log"
$BackendErrorLog = Join-Path $LogRoot "backend.error.log"
$FrontendOutLog = Join-Path $LogRoot "frontend.out.log"
$FrontendErrorLog = Join-Path $LogRoot "frontend.error.log"
$OllamaOutLog = Join-Path $LogRoot "ollama.out.log"
$OllamaErrorLog = Join-Path $LogRoot "ollama.error.log"

try {
    $PythonPath = Resolve-PythonEnvironment
    Sync-BackendDependencies -PythonPath $PythonPath
    $FrontendTools = Sync-FrontendDependencies
    Normalize-PathEnvironment
    $ProcessJob = Initialize-ProcessJob

    $ApiBaseUrl = (Get-DotEnvValue -Name "API_BASE_URL" -Default "http://127.0.0.1:8000").TrimEnd("/")
    $OllamaBaseUrl = (Get-DotEnvValue -Name "OLLAMA_BASE_URL" -Default "http://127.0.0.1:11434").TrimEnd("/")
    $LocalModel = Get-DotEnvValue -Name "LOCAL_MODEL" -Default "llama3.2:3b"
    $ApiUri = [Uri]$ApiBaseUrl

    $Ollama = Get-Command ollama.exe -ErrorAction SilentlyContinue
    $OllamaProcess = $null
    if (-not (Test-Endpoint -Url "$OllamaBaseUrl/api/tags")) {
        if ($null -eq $Ollama) {
            Write-Warning "Ollama no esta instalado. La app arrancara y mostrara el proveedor local como no disponible."
        }
        else {
            Write-Step "Iniciando Ollama"
            $OllamaProcess = Start-Process -FilePath $Ollama.Source -ArgumentList "serve" -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput $OllamaOutLog -RedirectStandardError $OllamaErrorLog -PassThru
            Register-OwnedProcess -Process $OllamaProcess
            if (-not (Wait-Endpoint -Url "$OllamaBaseUrl/api/tags" -TimeoutSeconds 20 -Process $OllamaProcess)) {
                Show-LogTail -Paths @($OllamaOutLog, $OllamaErrorLog)
                throw "Ollama no respondio en $OllamaBaseUrl."
            }
        }
    }

    if (Test-Endpoint -Url "$OllamaBaseUrl/api/tags") {
        $Models = Invoke-RestMethod -Uri "$OllamaBaseUrl/api/tags" -TimeoutSec 5
        $InstalledModels = @($Models.models | ForEach-Object { $_.name })
        if ($LocalModel -notin $InstalledModels) {
            if ($null -eq $Ollama) {
                Write-Warning "Falta el modelo $LocalModel y no se encontro el comando ollama para descargarlo."
            }
            else {
                Write-Step "Descargando el modelo $LocalModel (solo la primera vez)"
                & $Ollama.Source pull $LocalModel
                if ($LASTEXITCODE -ne 0) {
                    throw "No se pudo preparar el modelo $LocalModel."
                }
            }
        }
    }

    $BackendProcess = $null
    if (-not (Test-Endpoint -Url "$ApiBaseUrl/health")) {
        Write-Step "Iniciando FastAPI"
        $BackendArguments = @(
            "-m", "uvicorn", "backend.app.main:app",
            "--host", $ApiUri.Host,
            "--port", $ApiUri.Port.ToString()
        )
        $BackendProcess = Start-Process -FilePath $PythonPath -ArgumentList $BackendArguments -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput $BackendOutLog -RedirectStandardError $BackendErrorLog -PassThru
        Register-OwnedProcess -Process $BackendProcess
        if (-not (Wait-Endpoint -Url "$ApiBaseUrl/health" -TimeoutSeconds 45 -Process $BackendProcess)) {
            Show-LogTail -Paths @($BackendOutLog, $BackendErrorLog)
            throw "FastAPI no respondio en $ApiBaseUrl."
        }
    }
    else {
        Write-Host "FastAPI ya estaba disponible en $ApiBaseUrl." -ForegroundColor DarkGray
    }

    $FrontendProcess = $null
    if (-not (Test-Endpoint -Url $FrontendUrl)) {
        Write-Step "Iniciando React"
        $env:VITE_API_PROXY_TARGET = $ApiBaseUrl
        # Se inicia Vite directamente con Node. Así el PID observado es el
        # servidor real y Ctrl+C puede cerrarlo sin dejar un nieto de npm vivo.
        $ViteCli = Join-Path $FrontendRoot "node_modules\vite\bin\vite.js"
        $QuotedViteCli = '"' + $ViteCli + '"'
        $FrontendArguments = @(
            $QuotedViteCli,
            "--host", "127.0.0.1",
            "--port", "5173",
            "--strictPort"
        )
        $FrontendProcess = Start-Process -FilePath $FrontendTools.NodePath -ArgumentList $FrontendArguments -WorkingDirectory $FrontendRoot -WindowStyle Hidden -RedirectStandardOutput $FrontendOutLog -RedirectStandardError $FrontendErrorLog -PassThru
        Register-OwnedProcess -Process $FrontendProcess
        if (-not (Wait-Endpoint -Url $FrontendUrl -TimeoutSeconds 45 -Process $FrontendProcess)) {
            Show-LogTail -Paths @($FrontendOutLog, $FrontendErrorLog)
            throw "React no respondio en $FrontendUrl."
        }
    }
    else {
        Write-Host "React ya estaba disponible en $FrontendUrl." -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "IAviso Seguro esta listo." -ForegroundColor Green
    Write-Host "Aplicacion: $FrontendUrl"
    Write-Host "API:        $ApiBaseUrl"
    Write-Host "API docs:   $ApiBaseUrl/docs"
    Write-Host "Pulsa Ctrl+C para detener los procesos iniciados por este lanzador." -ForegroundColor DarkGray

    if ($SmokeTest) {
        Write-Host "Prueba de arranque completada; cerrando servicios de prueba." -ForegroundColor Green
        return
    }

    if (-not $NoBrowser) {
        Start-Process $FrontendUrl | Out-Null
    }

    while ($true) {
        Start-Sleep -Seconds 1
        if (($null -ne $BackendProcess) -and $BackendProcess.HasExited) {
            Show-LogTail -Paths @($BackendOutLog, $BackendErrorLog)
            throw "FastAPI se ha detenido inesperadamente."
        }
        if (($null -ne $FrontendProcess) -and $FrontendProcess.HasExited) {
            Show-LogTail -Paths @($FrontendOutLog, $FrontendErrorLog)
            throw "React se ha detenido inesperadamente."
        }
    }
}
finally {
    if ($OwnedProcesses.Count -gt 0) {
        Write-Step "Deteniendo los procesos iniciados"
    }
    if ($ProcessJob -ne [IntPtr]::Zero) {
        [IAvisoProcessJob]::Close($ProcessJob)
        $ProcessJob = [IntPtr]::Zero
    }
    for ($Index = $OwnedProcesses.Count - 1; $Index -ge 0; $Index--) {
        Stop-OwnedProcess -Process $OwnedProcesses[$Index]
    }
}
