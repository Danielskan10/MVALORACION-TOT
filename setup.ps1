# =============================================================================
#  MVALORACION — Script de instalación automática (PowerShell)
#  Ejecutar desde la raíz del proyecto:
#      powershell -ExecutionPolicy Bypass -File setup.ps1
#
#  Compatible: Windows 10/11, Python 3.11+, entornos corporativos con proxy.
# =============================================================================
param(
    [string]$PythonExe    = "",          # ruta al python.exe si no está en PATH
    [string]$ProxyUrl     = "",          # ej: "http://proxy.empresa.com:8080"
    [string]$DataDir      = "",          # directorio de datos (por defecto: .\data)
    [string]$InfovalmerDir= "",          # ruta unidad J:\ o equivalente
    [int]   $Port         = 8000,
    [switch]$NoVenv,                     # instalar paquetes en python global
    [switch]$Force                       # reinstalar aunque ya exista el venv
)

Set-StrictMode -Off
$ErrorActionPreference = "Stop"

# ── Colores ──────────────────────────────────────────────────────────────────
function Write-Step($msg)  { Write-Host "`n  ► $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "    ✓ $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "    ⚠ $msg" -ForegroundColor Yellow }
function Write-Fail($msg)  { Write-Host "    ✗ $msg" -ForegroundColor Red; exit 1 }

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ROOT
Write-Host ""
Write-Host "  ╔══════════════════════════════════════╗" -ForegroundColor Blue
Write-Host "  ║   MVALORACION — Instalación v2.0     ║" -ForegroundColor Blue
Write-Host "  ╚══════════════════════════════════════╝" -ForegroundColor Blue

# ── 1. Detectar Python ───────────────────────────────────────────────────────
Write-Step "Buscando Python..."
if ($PythonExe -and (Test-Path $PythonExe)) {
    $py = $PythonExe
} else {
    $py = $null
    foreach ($candidate in @("python", "python3", "py")) {
        try {
            $ver = & $candidate --version 2>&1
            if ($ver -match "Python (\d+)\.(\d+)") {
                $maj = [int]$Matches[1]; $min = [int]$Matches[2]
                if ($maj -ge 3 -and $min -ge 10) { $py = $candidate; break }
            }
        } catch {}
    }
}
if (-not $py) { Write-Fail "Python 3.10+ no encontrado. Instala Python desde python.org o indica -PythonExe 'C:\...\python.exe'" }
$pyVer = (& $py --version 2>&1).Trim()
Write-Ok "$pyVer → $py"

# ── 2. Proxy ─────────────────────────────────────────────────────────────────
$pipProxy = @()
if ($ProxyUrl) {
    $pipProxy = @("--proxy", $ProxyUrl)
    $env:HTTPS_PROXY = $ProxyUrl
    $env:HTTP_PROXY  = $ProxyUrl
    Write-Ok "Proxy configurado: $ProxyUrl"
}

# ── 3. Entorno virtual ───────────────────────────────────────────────────────
Write-Step "Configurando entorno virtual..."
$venvDir = Join-Path $ROOT "venv"
if (-not $NoVenv) {
    if ($Force -and (Test-Path $venvDir)) {
        Remove-Item $venvDir -Recurse -Force
        Write-Warn "venv anterior eliminado (--Force)"
    }
    if (-not (Test-Path $venvDir)) {
        & $py -m venv $venvDir
        Write-Ok "venv creado en $venvDir"
    } else {
        Write-Ok "venv ya existe (usa -Force para recrear)"
    }
    $pip = Join-Path $venvDir "Scripts\pip.exe"
    $pyExe = Join-Path $venvDir "Scripts\python.exe"
} else {
    $pip = "pip"
    $pyExe = $py
    Write-Warn "Instalando en Python global (sin venv)"
}

# ── 4. Dependencias ──────────────────────────────────────────────────────────
Write-Step "Instalando dependencias Python..."
$pipArgs = @("install", "-r", (Join-Path $ROOT "requirements.txt"), "--upgrade") + $pipProxy
try {
    & $pip @pipArgs
    Write-Ok "Paquetes instalados"
} catch {
    Write-Warn "Error con pip. Intentando con --no-cache-dir..."
    $pipArgs += "--no-cache-dir"
    & $pip @pipArgs
}

# ── 5. Estructura de directorios ─────────────────────────────────────────────
Write-Step "Creando estructura de directorios..."
$dirs = @(
    (Join-Path $ROOT "data"),
    (Join-Path $ROOT "data\obs"),
    (Join-Path $ROOT "frontend"),
    (Join-Path $ROOT "logs")
)
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}
Write-Ok "Directorios listos"

# ── 6. config.yaml ───────────────────────────────────────────────────────────
Write-Step "Generando config.yaml..."
$cfgFile = Join-Path $ROOT "config.yaml"
if (-not (Test-Path $cfgFile)) {
    $dataDir = if ($DataDir) { $DataDir } else { Join-Path $ROOT "data" }
    $infovalmer = if ($InfovalmerDir) { $InfovalmerDir } else { "J:\\VALORACION\\VALORACION_ESPECIAL\\Bolsa\\INFOVALMER" }
    $cfgContent = @"
# MVALORACION — Configuración local
# Editar según rutas reales del entorno corporativo.
# Este archivo es ignorado por git (.gitignore).

# ── Rutas de datos ────────────────────────────────────────────────────────────
data_dir: "$($dataDir -replace '\\','\\')"

# Directorio raíz donde Infovalmer deposita los archivos diarios
# Estructura esperada: <infovalmer_dir>\<YYYYMMDD>\SP<mmddyy>.001, etc.
infovalmer_dir: "$($infovalmer -replace '\\','\\')"

# ── Archivos de referencia (catálogos) ───────────────────────────────────────
# Catálogo de especies: columnas LLAVE, TIPO  (sep ";", encoding latin-1)
ref_especies: "$($dataDir -replace '\\','\\')\Especies.csv"

# Referencia FCPE / Fondos de capital privado
ref_fcpe:      "$($dataDir -replace '\\','\\')\FCPE.xlsx"

# Referencia fondos fiduciaria
ref_fiduciaria: "$($dataDir -replace '\\','\\')\FIDUCIARIA0210.xlsx"

# Referencia fondos de inversión
ref_fondos:    "$($dataDir -replace '\\','\\')\FONDOS.xlsx"

# Referencia FCP
ref_fcp:       "$($dataDir -replace '\\','\\')\FCP.xlsx"

# ── Umbrales de alerta ────────────────────────────────────────────────────────
# Variación % de precio para disparar alerta (default 5%)
umbral_variacion_pct: 5.0

# Diferencia absoluta de causación para alerta (COP, default 1.0)
umbral_dif_causacion: 1.0

# ── Servidor ──────────────────────────────────────────────────────────────────
port: $Port
host: "0.0.0.0"

# ── Entorno corporativo ───────────────────────────────────────────────────────
# Proxy HTTP/HTTPS (dejar en blanco si no aplica)
proxy: ""

# Certificado SSL corporativo (ruta al .pem, o "false" para deshabilitar)
ssl_cert: ""
"@
    $cfgContent | Out-File -FilePath $cfgFile -Encoding utf8
    Write-Ok "config.yaml generado → $cfgFile"
} else {
    Write-Ok "config.yaml ya existe (no se sobreescribe)"
}

# ── 7. Lanzador MVALORACION.bat ──────────────────────────────────────────────
Write-Step "Creando lanzador MVALORACION.bat..."
$batFile = Join-Path $ROOT "MVALORACION.bat"
$batContent = @"
@echo off
chcp 65001 >nul
title MVALORACION
cd /d "%~dp0"
echo.
echo   Iniciando MVALORACION...
echo   Abre: http://localhost:$Port
echo.
"$pyExe" run.py
pause
"@
$batContent | Out-File -FilePath $batFile -Encoding ascii
Write-Ok "MVALORACION.bat creado"

# ── 8. Acceso directo en escritorio (opcional) ────────────────────────────────
Write-Step "Creando acceso directo en escritorio..."
try {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktop "MVALORACION.lnk"
    if (-not (Test-Path $shortcutPath)) {
        $wsh = New-Object -ComObject WScript.Shell
        $sc = $wsh.CreateShortcut($shortcutPath)
        $sc.TargetPath   = $batFile
        $sc.WorkingDirectory = $ROOT
        $sc.Description  = "MVALORACION — Control Operativo de Valoración"
        $sc.Save()
        Write-Ok "Acceso directo creado en $desktop"
    } else {
        Write-Ok "Acceso directo ya existe"
    }
} catch {
    Write-Warn "No se pudo crear acceso directo: $_"
}

# ── 9. Verificación final ────────────────────────────────────────────────────
Write-Step "Verificación de imports Python..."
$testScript = @"
import sys, pathlib
sys.path.insert(0, str(pathlib.Path('$($ROOT -replace "\\","\\\\")') / 'app'))
try:
    from routers import porfin, mitra, insumos
    from config import get_config
    import fastapi, uvicorn, pandas, numpy, openpyxl, yaml
    print('OK')
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
"@
$result = & $pyExe -c $testScript 2>&1
if ($result -match "OK") {
    Write-Ok "Todos los módulos importan correctamente"
} else {
    Write-Warn "Problema en imports: $result"
}

# ── Resumen ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║   ✓  INSTALACIÓN COMPLETA                           ║" -ForegroundColor Green
Write-Host "  ║                                                      ║" -ForegroundColor Green
Write-Host "  ║   Para iniciar:                                      ║" -ForegroundColor Green
Write-Host "  ║     Doble clic en MVALORACION.bat                   ║" -ForegroundColor Green
Write-Host "  ║     — o —                                            ║" -ForegroundColor Green
Write-Host "  ║     python run.py                                    ║" -ForegroundColor Green
Write-Host "  ║                                                      ║" -ForegroundColor Green
Write-Host "  ║   Configuración: edita config.yaml                  ║" -ForegroundColor Green
Write-Host "  ║   URL:  http://localhost:$Port                        ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
