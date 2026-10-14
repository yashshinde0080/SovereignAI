#Requires -Version 5.1
<#
.SYNOPSIS
    Builds the portable Windows x64 release of SovereignAI Edge.

.DESCRIPTION
    Produces releases/windows/x64/SovereignAI-Windows-x64-Portable.zip from the
    Electron "unpacked" app (electron-builder --dir output in build_exe/win-unpacked).

    By default it first runs the canonical build_windows.ps1 (frontend -> PyInstaller
    backend -> electron --dir). Pass -Reuse to skip the build and assemble from an
    existing build_exe/win-unpacked (useful when the backend can't be rebuilt on this
    Python, or for re-packaging only).

    The portable bundle keeps the app's real layout: the Electron app + resources/
    (backend + frontend) at the top level, next to a data/ marker directory that
    switches the app into portable mode (all writable state stays on the drive).

    No network and no publishing: this only writes inside the repo's releases/.

.EXAMPLE
    .\scripts\build-release.ps1                 # full build + package
    .\scripts\build-release.ps1 -Reuse          # package existing win-unpacked
    .\scripts\build-release.ps1 -Reuse -Force   # overwrite an existing artifact
#>
[CmdletBinding()]
param(
    [ValidateSet('windows')][string]$Platform = 'windows',
    [ValidateSet('x64')][string]$Arch = 'x64',
    [string]$Version = '',
    # Assemble from an existing build_exe/win-unpacked instead of rebuilding.
    [switch]$Reuse,
    # Overwrite an existing zip in releases/ (refused by default).
    [switch]$Force,
    [switch]$SkipChecks
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Guard against an inherited/polluted PSModulePath (see build_windows.ps1):
# without this, Get-FileHash & friends fail to auto-load in PowerShell 5.1.
$env:PSModulePath = (@(
        (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'WindowsPowerShell\Modules'),
        (Join-Path $env:ProgramFiles 'WindowsPowerShell\Modules'),
        (Join-Path $PSHOME 'Modules')
    ) | Where-Object { Test-Path -LiteralPath $_ }) -join ';'
Import-Module Microsoft.PowerShell.Utility -ErrorAction SilentlyContinue

# Shared helpers -- Get-LogoPng resolves the official logo in the repo root.
. (Join-Path $PSScriptRoot 'portable_lib.ps1')

# --------------------------------------------------------------------------- #
$Root        = Split-Path -Parent $PSScriptRoot
$Releases    = Join-Path $Root 'releases'
$PlatformDir = Join-Path $Releases "$Platform\$Arch"
$Unpacked    = Join-Path $Root 'build_exe\win-unpacked'
$Lib         = Join-Path $PSScriptRoot 'release_lib.py'
$StageRoot   = Join-Path $Releases '.stage'
$BundleName  = 'SovereignAI-Windows-x64-Portable'
$Stage       = Join-Path $StageRoot $BundleName
$ZipOut      = Join-Path $PlatformDir 'SovereignAI-Windows-x64-Portable.zip'
$AppName     = 'SovereignAI Edge'

function Assert-File([string]$Path, [string]$What) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$What not found: $Path" }
}
function Get-SizeMb([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return 0 }
    $item = Get-Item -LiteralPath $Path
    if ($item.PSIsContainer) {
        $bytes = (Get-ChildItem -LiteralPath $Path -Recurse -File | Measure-Object -Property Length -Sum).Sum
    } else { $bytes = $item.Length }
    return [math]::Round($bytes / 1MB, 1)
}
function Invoke-Lib([string[]]$LibArgs) {
    & python $Lib @LibArgs
    if ($LASTEXITCODE -ne 0) { throw "release_lib.py $($LibArgs -join ' ') failed (exit $LASTEXITCODE)" }
}

Write-Host ''
Write-Host 'SovereignAI portable release (Windows x64)' -ForegroundColor Cyan
Write-Host "  root   : $Root"
Write-Host "  output : $PlatformDir"
Write-Host ''

# ---- version ------------------------------------------------------------- #
if (-not $Version) {
    $vfile = Join-Path $Root 'VERSION'
    if (Test-Path -LiteralPath $vfile) { $Version = (Get-Content -LiteralPath $vfile -Raw).Trim() }
}
if (-not $Version) { $Version = '0.0.0-dev' }
if ($Version -notmatch '^[0-9A-Za-z._-]+$') { throw "Unsafe version string: '$Version'" }

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'python is required (for release_lib.py and zipping).' }

# ---- 1. build (or reuse) ------------------------------------------------- #
if (-not $Reuse) {
    Assert-File (Join-Path $Root 'build_windows.ps1') 'build_windows.ps1'
    Write-Host '-- running build_windows.ps1 (frontend + PyInstaller backend + electron --dir)'
    & (Join-Path $Root 'build_windows.ps1') -SkipInstallerTest
    if ($LASTEXITCODE -ne 0) { throw "build_windows.ps1 failed (exit $LASTEXITCODE)" }
} else {
    Write-Host '-- reusing existing build_exe/win-unpacked (-Reuse)'
}

Assert-File (Join-Path $Unpacked 'SovereignAI.exe') 'Electron app (build_exe/win-unpacked/SovereignAI.exe)'
Assert-File (Join-Path $Unpacked 'resources\backend\SovereignAIBackend.exe') 'Packaged backend'
Assert-File (Join-Path $Unpacked 'resources\frontend\index.html') 'Frontend static export'

if ((Test-Path -LiteralPath $ZipOut) -and -not $Force) {
    throw "Artifact already exists: $ZipOut (pass -Force to overwrite)."
}

# ---- 2. stage the bundle ------------------------------------------------- #
Write-Host '-- staging portable bundle'
if (Test-Path -LiteralPath $StageRoot) { Remove-Item -Recurse -Force -LiteralPath $StageRoot }
New-Item -ItemType Directory -Force -Path $Stage, $PlatformDir | Out-Null

Copy-Item -Path (Join-Path $Unpacked '*') -Destination $Stage -Recurse -Force

# Strip JS source maps (dev artifacts; smaller bundle, no source exposure).
Get-ChildItem -LiteralPath (Join-Path $Stage 'resources\frontend') -Recurse -File -Filter '*.map' -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

# Portable marker + writable-state dirs (main.js: data/ sibling => portable mode).
foreach ($d in @('data\models', 'data\plugins', 'data\cache')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Stage $d) | Out-Null
}
Set-Content -LiteralPath (Join-Path $Stage 'data\models\README.txt') -Encoding ASCII -Value @"
Download or import models into this folder. No models are bundled.
Kept on the drive so the package stays portable and license-clean.
"@

# Licenses (project) + Electron/Chromium licenses already ship next to the exe.
if (Test-Path -LiteralPath (Join-Path $Root 'LICENSES')) {
    Copy-Item -LiteralPath (Join-Path $Root 'LICENSES') -Destination (Join-Path $Stage 'LICENSES') -Recurse -Force
} else {
    New-Item -ItemType Directory -Force -Path (Join-Path $Stage 'LICENSES') | Out-Null
}
Assert-File (Join-Path $Stage 'LICENSE.electron.txt') 'Electron license (from electron-builder)'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README_PORTABLE.txt') -Destination (Join-Path $Stage 'README_PORTABLE.txt') -Force

# Official logo, flat next to the exe. The exe itself already carries it as its
# icon (electron/assets/make_icon.py -> rcedit / electron-builder).
$logo = Get-LogoPng -RepoRoot $Root
if (-not $logo) {
    throw "No logo PNG in $Root - expected sovereignai.png (or sovereign.png). The bundle ships it as sovereignai.png."
}
Copy-Item -LiteralPath $logo -Destination (Join-Path $Stage 'sovereignai.png') -Force
Write-Host "   logo: $(Split-Path -Leaf $logo) -> sovereignai.png"

# ---- 3. launch scripts (paths relative to their own location) ------------ #
Set-Content -LiteralPath (Join-Path $Stage 'Launch-SovereignAI.bat') -Encoding ASCII -Value @"
@echo off
rem Launch SovereignAI Edge from this folder (portable; no install).
setlocal
set "HERE=%~dp0"
if not exist "%HERE%SovereignAI.exe" (
  echo [ERROR] SovereignAI.exe not found next to this launcher.
  pause
  exit /b 1
)
"%HERE%SovereignAI.exe" %*
exit /b %errorlevel%
"@

Set-Content -LiteralPath (Join-Path $Stage 'Launch-SovereignAI.ps1') -Encoding ASCII -Value @"
# Launch SovereignAI Edge from this folder (portable; no install).
`$here = Split-Path -Parent `$MyInvocation.MyCommand.Path
`$exe = Join-Path `$here 'SovereignAI.exe'
if (-not (Test-Path -LiteralPath `$exe)) {
    Write-Error "SovereignAI.exe not found next to this launcher (`$here)"
    exit 1
}
`$p = Start-Process -FilePath `$exe -WorkingDirectory `$here -PassThru
`$p.WaitForExit()
exit `$p.ExitCode
"@

# ---- 4. structural checks ------------------------------------------------ #
if (-not $SkipChecks) {
    Write-Host '-- checks'
    Assert-File (Join-Path $Stage 'SovereignAI.exe') 'Staged app exe'
    Assert-File (Join-Path $Stage 'sovereignai.png') 'Staged logo'
    Assert-File (Join-Path $Stage 'Launch-SovereignAI.bat') 'Launch .bat'
    Assert-File (Join-Path $Stage 'Launch-SovereignAI.ps1') 'Launch .ps1'
    Assert-File (Join-Path $Stage 'resources\backend\SovereignAIBackend.exe') 'Staged backend'
    Assert-File (Join-Path $Stage 'resources\frontend\index.html') 'Staged frontend'
    foreach ($d in @('data', 'data\models', 'data\plugins', 'data\cache')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Stage $d) -PathType Container)) { throw "Missing portable dir: $d" }
    }
    $shippedDb = Get-ChildItem -LiteralPath $Stage -Recurse -File -Filter 'sovereign*.db*' -ErrorAction SilentlyContinue
    if ($shippedDb) { throw "A sovereign DB was staged (should be created on first run): $($shippedDb[0].FullName)" }
    $absolute = Select-String -Path (Join-Path $Stage 'Launch-SovereignAI.bat'), (Join-Path $Stage 'Launch-SovereignAI.ps1') `
        -Pattern '[A-Za-z]:\\' -ErrorAction SilentlyContinue
    if ($absolute) { throw "Absolute host path in a launcher: $($absolute[0].Line)" }
    Write-Host '   ok: exe + logo + launchers + resources/ + data/ present, no shipped DB, no absolute paths'
}

# ---- 5. zip -------------------------------------------------------------- #
Write-Host "== zipping -> $ZipOut"
Invoke-Lib @('zip', $Stage, $ZipOut)
$zipMb = Get-SizeMb $ZipOut
$hash = (Get-FileHash -LiteralPath $ZipOut -Algorithm SHA256).Hash.ToLower()

# ---- 6. per-artifact metadata -------------------------------------------- #
$builtAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$nodeVer = 'n/a'
if (Get-Command node -ErrorAction SilentlyContinue) { $nodeVer = (& node --version) -join '' }
$gitRev = 'unknown'
if (Get-Command git -ErrorAction SilentlyContinue) { $gitRev = (& git -C $Root rev-parse --short HEAD) -join '' }
$backendMb = Get-SizeMb (Join-Path $Stage 'resources\backend')

$buildInfo = @"
SovereignAI Edge - Windows x64 Portable
=======================================
app        : $AppName
version    : $Version
platform   : windows x64
artifact   : SovereignAI-Windows-x64-Portable.zip
format     : zip (deflate)
built (UTC): $builtAt
built on   : $([Environment]::OSVersion.VersionString)
node       : $nodeVer
zip size   : $zipMb MB
sha256     : $hash
extracted  : $([math]::Round((Get-ChildItem -LiteralPath $Stage -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB, 1)) MB

Included runtimes / assets
  - Electron 28 runtime (Chromium + Node), bundled in the app.
  - CPython runtime frozen with PyInstaller -> resources/backend/SovereignAIBackend.exe ($backendMb MB, CPU torch).
  - Next.js static export      -> resources/frontend/ (served over app://).

External prerequisites
  - None to launch. No admin rights, no separate Python/Node install.
  - GPU (CUDA) inference is optional and NOT bundled (CPU torch). See build_windows.ps1 extras.
  - No models are bundled. Download/import into data/models after first run (needs network).

Offline support
  - Full UI + local inference: offline.
  - Cloud providers + model downloads: need network + your own keys.

Portable mode
  - The data/ folder next to the exe switches the app into portable mode:
    userData, TEMP/TMP, HF_HOME, XDG_* and SOVEREIGN_DATA_ROOT all live under data/.
  - Everything writable stays on the drive; nothing is installed system-wide.

Verification
  - sha256sum -c SHA256SUMS.txt            (macOS/Linux, from releases/)
  - certutil -hashfile SovereignAI-Windows-x64-Portable.zip SHA256   (Windows)
"@
Set-Content -LiteralPath (Join-Path $PlatformDir 'BUILD-INFO.txt') -Encoding UTF8 -Value $buildInfo

$buildJson = [ordered]@{
    app                = $AppName
    version            = $Version
    os                 = $Platform
    arch               = $Arch
    artifact           = 'SovereignAI-Windows-x64-Portable.zip'
    format             = 'zip'
    built_at           = $builtAt
    built_on           = [Environment]::OSVersion.VersionString
    git                = $gitRev
    portable           = $true
    offline            = $true
    runtimes           = @('Electron 28', 'CPython (PyInstaller onedir)', 'Next.js static export')
    external_prereqs   = @()
    bundled_models     = $false
    status             = 'built'
}
$buildJson | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PlatformDir 'build.json') -Encoding UTF8

# ---- 7. finalize manifest + checksums ------------------------------------ #
Write-Host '-- finalize MANIFEST.json + SHA256SUMS.txt'
Invoke-Lib @('finalize', $Releases, $AppName, $Version)

Remove-Item -Recurse -Force -LiteralPath $StageRoot -ErrorAction SilentlyContinue

Write-Host ''
Write-Host 'RELEASE: OK' -ForegroundColor Green
Write-Host "  artifact : $ZipOut ($zipMb MB)"
Write-Host "  sha256   : $hash"
