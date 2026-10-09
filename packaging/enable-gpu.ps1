#Requires -Version 5.1
<#
.SYNOPSIS
    Enables CUDA (GPU) inference for an installed SovereignAI build.

.DESCRIPTION
    The installer ships a CPU-only torch runtime: a cu124 torch wheel adds
    ~3.2 GB of CUDA DLLs and NSIS corrupts installers over ~2 GB. This script
    replaces the bundled torch package with the CUDA build, so
    torch.cuda.is_available() becomes true and FullRAM/LayerStream use the GPU.

    Source order:
      1. -TorchSource <path to a site-packages containing a CUDA torch>
      2. a local dev venv (backend\.venv) when it already has a CUDA torch
      3. pip download of torch==2.5.1 (cu124) - requires network

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File enable-gpu.ps1
    powershell -ExecutionPolicy Bypass -File enable-gpu.ps1 -Target "D:\SovereignAI\build_exe\win-unpacked"
#>
[CmdletBinding()]
param(
    [string]$Target,
    [string]$TorchSource,
    [string]$TorchVersion = "2.5.1",
    [string]$CudaIndex = "https://download.pytorch.org/whl/cu124"
)

$ErrorActionPreference = "Stop"

function Find-InstallDir {
    param([string]$Explicit)
    if ($Explicit) {
        if (Test-Path -LiteralPath $Explicit) { return (Resolve-Path $Explicit).Path }
        throw "Target path not found: $Explicit"
    }
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\SovereignAI"),
        (Join-Path $env:ProgramFiles "SovereignAI"),
        (Join-Path $PSScriptRoot "..\win-unpacked")
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath (Join-Path $c "resources\backend")) { return (Resolve-Path $c).Path }
    }
    throw "Could not find an installed SovereignAI. Pass -Target <install dir>."
}

function Get-BundledTorchDir([string]$InstallDir) {
    $candidates = @(
        (Join-Path $InstallDir "resources\backend\_internal\torch"),
        (Join-Path $InstallDir "resources\backend\torch")
    )
    foreach ($c in $candidates) { if (Test-Path -LiteralPath $c) { return $c } }
    throw "Bundled torch not found under $InstallDir\resources\backend"
}

$installDir = Find-InstallDir -Explicit $Target
$torchDir = Get-BundledTorchDir -InstallDir $installDir
$python = Get-Command python -ErrorAction SilentlyContinue

if (Get-Process -Name "SovereignAI", "SovereignAIBackend" -ErrorAction SilentlyContinue) {
    throw "Close SovereignAI before enabling GPU support."
}

Write-Host "install dir : $installDir"
Write-Host "torch dir   : $torchDir"

$sourceRoot = $null
$tempRoot = $null
try {
    if ($TorchSource) {
        $sourceRoot = (Resolve-Path (Join-Path $TorchSource "torch")).Path
    } else {
        $devVenv = Join-Path $PSScriptRoot "..\..\backend\.venv\Lib\site-packages"
        if (Test-Path -LiteralPath (Join-Path $devVenv "torch")) { $sourceRoot = (Resolve-Path (Join-Path $devVenv "torch")).Path }
    }

    if ($sourceRoot) {
        $stage = Join-Path $sourceRoot "version.py"
        if (Test-Path -LiteralPath $stage) {
            $versionMatch = Select-String -Path $stage -Pattern "^cuda\s*=\s*'([^']*)'" | Select-Object -First 1
            $cuda = if ($versionMatch) { $versionMatch.Matches[0].Groups[1].Value } else { $null }
            if (-not $cuda -or $cuda -eq "None" -or $cuda -eq "") {
                throw "The bundled torch at $sourceRoot is CPU-only. Pass -TorchSource pointing at a CUDA torch, or remove -TorchSource to download one."
            }
            Write-Host "source      : $sourceRoot (cuda $cuda)"
        }
    } else {
        if (-not $python) { throw "No local CUDA torch found and 'python' is not on PATH to download one." }
        $tempRoot = Join-Path $env:TEMP "sovereign-gpu-$([guid]::NewGuid().ToString('N').Substring(0,8))"
        New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
        Write-Host "downloading : torch==$TorchVersion from $CudaIndex (about 2.5 GB)"
        & python -m pip download "torch==$TorchVersion" --index-url $CudaIndex --no-deps -d $tempRoot
        if ($LASTEXITCODE -ne 0) { throw "pip download failed." }
        $wheel = Get-ChildItem -LiteralPath $tempRoot -Filter "torch-*.whl" | Select-Object -First 1
        if (-not $wheel) { throw "No torch wheel was downloaded." }
        $expanded = Join-Path $tempRoot "expanded"
        Expand-Archive -LiteralPath $wheel.FullName -DestinationPath $expanded -Force
        $sourceRoot = Join-Path $expanded "torch"
        Write-Host "source      : $($wheel.Name)/torch"
    }

    $sourceDlls = Get-ChildItem -LiteralPath $sourceRoot -Recurse -Filter "*.dll" -ErrorAction SilentlyContinue
    if (-not $sourceDlls) { throw "No torch runtime found at $sourceRoot." }

    Write-Host "replacing bundled torch ..."
    Remove-Item -LiteralPath $torchDir -Recurse -Force
    Copy-Item -LiteralPath $sourceRoot -Destination $torchDir -Recurse -Force

    # transformers et al. read torch's version from installed distribution metadata
    $distInfo = Get-ChildItem -LiteralPath (Split-Path $sourceRoot -Parent) -Filter "torch-*.dist-info" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($distInfo) {
        $old = Get-ChildItem -LiteralPath (Split-Path $torchDir -Parent) -Filter "torch-*.dist-info" -ErrorAction SilentlyContinue
        foreach ($o in $old) { Remove-Item -LiteralPath $o.FullName -Recurse -Force }
        Copy-Item -LiteralPath $distInfo.FullName -Destination (Split-Path $torchDir -Parent) -Recurse -Force
    }

    $dlls = Get-ChildItem -LiteralPath (Join-Path $torchDir "lib") -Filter "*.dll" -ErrorAction SilentlyContinue
    $cudaDlls = $dlls | Where-Object { $_.Name -match "cud|nvrtc|nvjitlink|cublas" }
    $sizeMb = [math]::Round(((Get-ChildItem -LiteralPath $torchDir -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB), 1)
    Write-Host "done: $($dlls.Count) DLLs ($($cudaDlls.Count) CUDA), torch dir now $sizeMb MB" -ForegroundColor Green
    Write-Host "Launch SovereignAI; FullRAM/LayerStream will select the GPU when torch.cuda.is_available() is true."
}
finally {
    if ($tempRoot -and (Test-Path -LiteralPath $tempRoot)) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
