#Requires -Version 5.1
<#
.SYNOPSIS
    Prepares a self-contained, portable Windows x64 release of SovereignAI Edge.

.DESCRIPTION
    Stages a runnable portable bundle into build_zip\portable (default) from the
    Electron output in build_exe\win-unpacked. By default it first runs the
    canonical build_windows.ps1 (Next.js static export -> PyInstaller backend ->
    electron-builder --dir). Pass -SkipBuild to re-stage from an existing,
    verified build_exe\win-unpacked without rebuilding.

    The bundle carries its own runtimes (Electron 28 + a PyInstaller-frozen
    CPython backend), so end users need no Python, no Node and no admin rights.

    Writable state stays on the drive: the sibling data\ folder next to
    SovereignAI.exe is the app's portable-mode marker. The backend receives
    SOVEREIGN_DATA_ROOT=<root>\data and writes under data\workspace\...; Electron
    pins userData to data\electron and TEMP/HF_HOME under data\cache. No database
    is shipped -- it is created on first run so the folder stays portable.

    Nothing is deleted outside build_zip\. Source code, workspace\, releases\ and
    build_exe\ are never touched.

.EXAMPLE
    .\Script_portable.ps1
    .\Script_portable.ps1 -SkipBuild
    .\Script_portable.ps1 -Clean
    .\Script_portable.ps1 -Configuration Release -Architecture x64
#>
[CmdletBinding()]
param(
    [ValidateSet('Release', 'Debug')][string]$Configuration = 'Release',
    # Remove generated staging + reports first, then rebuild.
    [switch]$Clean,
    # Re-stage from an existing build_exe\win-unpacked instead of compiling.
    [switch]$SkipBuild,
    [ValidateSet('x64')][string]$Architecture = 'x64',
    # Must stay inside <repo>\build_zip.
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'scripts\portable_lib.ps1')

# --------------------------------------------------------------------------- #
# Paths (resolved from this script's location, never the shell's cwd)
# --------------------------------------------------------------------------- #
$Root = $PSScriptRoot
$BuildZip = Join-Path $Root 'build_zip'
$LogsDir = Join-Path $BuildZip 'logs'
$Unpacked = Join-Path $Root 'build_exe\win-unpacked'
$BuildScript = Join-Path $Root 'build_windows.ps1'
$AppName = 'SovereignAI Edge'
$PortableTop = 'SovereignAI-Portable-Windows-x64'

if (-not $OutputDirectory) { $OutputDirectory = Join-Path $BuildZip 'portable' }
$Stage = [System.IO.Path]::GetFullPath($OutputDirectory)
$AllowedRoot = [System.IO.Path]::GetFullPath($BuildZip)

function Get-RunStamp { (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') }

$report = New-Object System.Collections.Generic.List[string]
$startedUtc = Get-RunStamp

function Add-Report([string]$Line) { $report.Add($Line); Write-Host $Line }
function Fail([string]$Message) {
    Write-Log ERROR $Message
    # Overwrite any previous success report with an accurate FAILED one.
    $lines = @(
        'SovereignAI Edge - portable staging report',
        '==========================================',
        'status        : FAILED',
        "finished (UTC) : $((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))",
        "error         : $Message",
        "staging       : $Stage"
    )
    try { Write-TextFile -Path (Join-Path $BuildZip 'portable-report.txt') -Text (($lines -join [Environment]::NewLine) + [Environment]::NewLine) } catch { }
    Write-Host ''
    Write-Log ERROR "Build failed. Staging: $Stage"
    exit 1
}

try {
    Write-Host ''
    Write-Log INFO "Preparing portable release..."
    Write-Host "       repo   : $Root"
    Write-Log INFO "output : $Stage"
    Write-Host ''

    # ----------------------------------------------------------------------- #
    # 1. Parameter + repository validation
    # ----------------------------------------------------------------------- #
    if (-not $Stage.StartsWith($AllowedRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "OutputDirectory must be inside $AllowedRoot (got: $Stage)."
    }
    if ($Stage -eq $AllowedRoot) { throw "OutputDirectory must be a subfolder of $AllowedRoot, not the root itself." }

    Assert-Path -Path (Join-Path $Root 'electron\package.json') -What 'Electron package.json' -Kind Leaf
    Assert-Path -Path (Join-Path $Root 'backend\main.py') -What 'backend entry point' -Kind Leaf
    Assert-Path -Path (Join-Path $Root 'frontend\package.json') -What 'frontend package.json' -Kind Leaf
    if (-not $SkipBuild) { Assert-Path -Path $BuildScript -What 'build_windows.ps1' -Kind Leaf }
    Assert-Path -Path (Join-Path $Root 'scripts\portable_lib.ps1') -What 'portable_lib.ps1' -Kind Leaf

    # ----------------------------------------------------------------------- #
    # 2. Version (VERSION is the pipeline's authoritative source)
    # ----------------------------------------------------------------------- #
    $Version = Get-RepoVersion -RepoRoot $Root
    Write-Log INFO "version: $Version  configuration: $Configuration  architecture: $Architecture"

    # ----------------------------------------------------------------------- #
    # 3. Tools + disk space (before any expensive work)
    # ----------------------------------------------------------------------- #
    $requiredMb = 2400
    if (Test-Path -LiteralPath $Unpacked) { $requiredMb = [int](Get-PathSizeMb -Path $Unpacked) + 1200 }
    $freeMb = Get-FreeSpaceMb -Path $BuildZip
    if ($freeMb -ge 0 -and $freeMb -lt $requiredMb) {
        throw "Not enough free disk space: need ~$requiredMb MB, have $freeMb MB on the build_zip drive."
    }
    Write-Log INFO "disk space: $freeMb MB free (need ~$requiredMb MB)"

    if (-not $SkipBuild) {
        foreach ($tool in @('node', 'npm')) {
            if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Required build tool not found on PATH: $tool" }
        }
        $venvPython = Join-Path $Root 'backend\.venv-build\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $venvPython)) {
            throw "Build virtualenv missing: $venvPython (run build_windows.ps1 once, or pass -SkipBuild)."
        }
    }
    Write-Log OK "preflight complete"

    # ----------------------------------------------------------------------- #
    # 4. Build (reuse the canonical pipeline)
    # ----------------------------------------------------------------------- #
    New-Item -ItemType Directory -Force -Path $BuildZip, $LogsDir | Out-Null
    $buildLog = Join-Path $LogsDir ('portable-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')

    if ($SkipBuild) {
        Write-Log INFO "Skipping build (-SkipBuild): reusing existing build_exe\win-unpacked"
    } else {
        Write-Log BUILD "Compiling frontend + backend + Electron (build_windows.ps1)..."
        $buildOk = $true
        $buildErr = ''
        Push-Location $Root
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue' # native stderr must not terminate; exit code is the contract
        try {
            & $BuildScript -SkipInstallerTest 2>&1 | Tee-Object -FilePath $buildLog -Append | ForEach-Object { Write-Host $_ }
            if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
                $buildOk = $false; $buildErr = "build_windows.ps1 exited with code $LASTEXITCODE"
            }
            if ($buildOk -and -not (Select-String -LiteralPath $buildLog -SimpleMatch 'BUILD STATUS: SUCCESS' -Quiet)) {
                $buildOk = $false; $buildErr = 'build_windows.ps1 reported BUILD STATUS: FAILED'
            }
        } catch {
            $buildOk = $false; $buildErr = $_.Exception.Message
            $script:BuildFailed = $true
        } finally {
            $ErrorActionPreference = $prev
            Pop-Location
            if ($script:BuildFailed) { exit 1 }
        }
        if (-not $buildOk) { throw "Build step failed: $buildErr (log: $buildLog)" }
        Write-Log OK "build complete (log: $buildLog)"
    }

    # ----------------------------------------------------------------------- #
    # 5. Verify build inputs exist
    # ----------------------------------------------------------------------- #
    Assert-Path -Path $Unpacked -What 'Electron build output (build_exe\win-unpacked)' -Kind Container
    Assert-Path -Path (Join-Path $Unpacked 'SovereignAI.exe') -What 'Electron app executable'
    Assert-Path -Path (Join-Path $Unpacked 'resources\backend\SovereignAIBackend.exe') -What 'frozen backend executable'
    Assert-Path -Path (Join-Path $Unpacked 'resources\frontend\index.html') -What 'frontend static export'
    Write-Log VERIFY "build outputs present (win-unpacked: $(Get-PathSizeMb -Path $Unpacked) MB)"

    # ----------------------------------------------------------------------- #
    # 6. Fresh staging (never accumulates stale files)
    # ----------------------------------------------------------------------- #
    if ($Clean) {
        foreach ($extra in @('portable-report.txt', 'portable-build.json')) {
            $p = Join-Path $BuildZip $extra
            if (Test-Path -LiteralPath $p) { Remove-Item -Force -LiteralPath $p }
        }
        Write-Log INFO "-Clean: generated reports cleared"
    }
    Remove-GeneratedDir -Path $Stage -AllowedRoot $AllowedRoot -RepoRoot $Root
    New-Item -ItemType Directory -Force -Path $Stage | Out-Null
    Write-Log INFO "staging app files -> $Stage"

    Copy-Item -Path (Join-Path $Unpacked '*') -Destination $Stage -Recurse -Force

    # Source maps are dev artifacts: drop them (smaller bundle, no source exposure).
    $maps = @(Get-ChildItem -LiteralPath $Stage -Recurse -File -Filter '*.map' -ErrorAction SilentlyContinue)
    if ($maps.Count -gt 0) { $maps | Remove-Item -Force -ErrorAction SilentlyContinue; Write-Log INFO "stripped $($maps.Count) source map(s)" }

    # ----------------------------------------------------------------------- #
    # 7. Portable workshop storage (the app's real data layout)
    # ----------------------------------------------------------------------- #
    Write-Log DATA "Configuring portable workshop storage..."
    foreach ($rel in @(Get-PortableRequiredDirs)) {
        New-Item -ItemType Directory -Force -Path (Join-Path $Stage $rel) | Out-Null
    }
    $dataNote = @"
SovereignAI Edge - portable data folder
=======================================
This folder is the portable-mode marker: while it exists next to
SovereignAI.exe, every writable path stays on this drive.

  workspace\database\   settings DB (sovereign_settings.db) + app DB (sovereign.db)
  workspace\models\     model weights you download or import (none are bundled)
  workspace\plugins\    user plugins + custom model catalogs
  workspace\logs\       backend + app logs
  workspace\sessions\   chat session snapshots
  cache\                temp work files and the HuggingFace cache
  electron\             Electron userData (window state, cache)
  config\, share\       redirected XDG config/data roots

No database is shipped - it is created here on first launch. Move the whole
folder (or the whole drive) to another machine and your data comes with it.
Do not rename this folder; the app looks for "data" next to the executable.
"@
    Write-TextFile -Path (Join-Path $Stage 'data\README.txt') -Text $dataNote

    # ----------------------------------------------------------------------- #
    # 8. Brand logo (shipped flat next to the exe, so the portable bundle
    #    carries the official logo as an inspectable file; the exe itself is
    #    stamped with it -- see electron\assets\make_icon.py)
    # ----------------------------------------------------------------------- #
    $logoSource = Get-LogoPng -RepoRoot $Root
    if (-not $logoSource) {
        throw "No logo PNG in $Root - expected sovereignai.png (or sovereign.png). The portable bundle ships it as sovereignai.png."
    }
    Copy-Item -LiteralPath $logoSource -Destination (Join-Path $Stage 'sovereignai.png') -Force
    Write-Log DATA "logo: $(Split-Path -Leaf $logoSource) -> sovereignai.png"

    # ----------------------------------------------------------------------- #
    # 9. Licenses / third-party notices
    # ----------------------------------------------------------------------- #
    $repoLicenses = Join-Path $Root 'LICENSES'
    if (Test-Path -LiteralPath $repoLicenses -PathType Container) {
        Copy-Item -LiteralPath $repoLicenses -Destination (Join-Path $Stage 'LICENSES') -Recurse -Force
    } else {
        New-Item -ItemType Directory -Force -Path (Join-Path $Stage 'LICENSES') | Out-Null
    }

    # ----------------------------------------------------------------------- #
    # 10. Launcher + end-user README
    # ----------------------------------------------------------------------- #
    Write-Log DATA "Writing portable launcher..."
    $launcher = @"
@echo off
rem Launch SovereignAI Edge from this folder. Portable: no install, no admin.
rem Portable mode is automatic -- the data\ folder next to the exe is the
rem marker, and the Electron shell starts the local backend then opens the UI.
setlocal
set "HERE=%~dp0"
if not exist "%HERE%SovereignAI.exe" (
  echo [ERROR] SovereignAI.exe not found next to this launcher: %HERE%
  echo         Extract the whole archive, then run this file from the folder.
  pause
  exit /b 1
)
"%HERE%SovereignAI.exe" %*
exit /b %errorlevel%
"@
    Write-TextFile -Path (Join-Path $Stage 'SovereignAI.bat') -Text $launcher -NoBom

    $readmeSrc = Join-Path $Root 'packaging\README_PORTABLE.txt'
    Assert-Path -Path $readmeSrc -What 'packaging\README_PORTABLE.txt'
    Copy-Item -LiteralPath $readmeSrc -Destination (Join-Path $Stage 'README_PORTABLE.txt') -Force
    Write-Log OK "launcher + README_PORTABLE.txt written"

    # ----------------------------------------------------------------------- #
    # 11. Validation (structure, secrets, hardcoded repo path)
    # ----------------------------------------------------------------------- #
    Write-Log VERIFY "Checking packaged runtime..."
    $problems = New-Object System.Collections.Generic.List[string]
    foreach ($p in @(Test-PortableBundle -Path $Stage)) { $problems.Add($p) }
    foreach ($p in @(Test-SecretArtifacts -Path $Stage)) { $problems.Add("secret: $p") }

    $leakage = Test-BundlePathLeakage -Path $Stage -RepoRoot $Root
    foreach ($p in @($leakage.Hard)) { $problems.Add("hardcoded repository path in packaged file: $p") }

    if ($problems.Count -gt 0) {
        foreach ($p in $problems) { Write-Log ERROR $p }
        throw "$($problems.Count) validation check(s) failed."
    }
    Write-Log OK "bundle contract OK (files, data dirs, no shipped DB, no secrets, no repo paths)"

    if (@($leakage.Soft).Count -gt 0) {
        Write-Log WARN "$(@($leakage.Soft).Count) text file(s) contain a Windows drive path (reported, not fatal)"
    }

    # Windows MAX_PATH: the frozen transformers runtime holds deep example paths,
    # so the extraction root has a hard length budget. Report it instead of
    # letting an unzip fail halfway on a deep temp path.
    $top = Get-PortableTopName -Version $Version
    $maxRel = 0
    $worstRel = ''
    foreach ($f in (Get-ChildItem -LiteralPath $Stage -Recurse -File -Force)) {
        $rel = $f.FullName.Substring($Stage.Length).TrimStart('\')
        if ($rel.Length -gt $maxRel) { $maxRel = $rel.Length; $worstRel = $rel }
    }
    $rootBudget = 259 - ($top.Length + 1 + $maxRel)
    if ($rootBudget -lt 80) {
        Write-Log WARN "long paths: keep the extraction folder under $rootBudget chars (Windows MAX_PATH). Longest: $worstRel"
    }

    # ----------------------------------------------------------------------- #
    # 12. Reports
    # ----------------------------------------------------------------------- #
    $sizeMb = Get-PathSizeMb -Path $Stage
    $fileCount = (Get-ChildItem -LiteralPath $Stage -Recurse -File -Force | Measure-Object).Count
    $finishedUtc = Get-RunStamp

    Write-Host ''
    Add-Report "SovereignAI Edge - portable staging report"
    Add-Report "=========================================="
    Add-Report "app            : $AppName"
    Add-Report "version        : $Version"
    Add-Report "configuration  : $Configuration"
    Add-Report "platform       : windows $Architecture"
    Add-Report "started (UTC)  : $startedUtc"
    Add-Report "finished (UTC) : $finishedUtc"
    Add-Report "build          : $(if ($SkipBuild) { 'skipped (-SkipBuild); reused build_exe\win-unpacked' } else { 'build_windows.ps1 (frontend + PyInstaller backend + electron --dir)' })"
    Add-Report "staging        : $Stage"
    Add-Report "staging size   : $sizeMb MB ($fileCount files)"
    Add-Report "portable data  : data\ (workspace\..., cache\, electron\) - created on this drive"
    Add-Report "launcher       : SovereignAI.bat -> SovereignAI.exe (Electron shell)"
    Add-Report "logo           : sovereignai.png (next to the exe); exe icon stamped from it"
    Add-Report "longest path   : $maxRel chars; extract into a folder under $rootBudget chars (Windows MAX_PATH)"
    Add-Report "bundled        : Electron 28 runtime, frozen CPython backend, Next.js static export"
    Add-Report "not bundled    : model weights, GPU/CUDA torch, cloud API keys"
    Add-Report "checks         : bundle contract PASS, secret scan PASS, repo-path scan PASS"
    if (@($leakage.Soft).Count -gt 0) { Add-Report "warnings       : $(@($leakage.Soft).Count) text file(s) with a Windows drive path" }
    Add-Report ""
    Add-Report "status         : OK"

    Write-TextFile -Path (Join-Path $BuildZip 'portable-report.txt') -Text (($report -join [Environment]::NewLine) + [Environment]::NewLine)

    $meta = [ordered]@{
        app           = $AppName
        version       = $Version
        configuration = $Configuration
        os            = 'windows'
        arch          = $Architecture
        started_utc   = $startedUtc
        finished_utc  = $finishedUtc
        staging       = $Stage
        staging_mb    = $sizeMb
        files         = $fileCount
        longest_path  = $maxRel
        extract_root_budget = $rootBudget
        build         = if ($SkipBuild) { 'reused' } else { 'built' }
        portable_data = 'data'
        status        = 'ok'
    }
    Write-TextFile -Path (Join-Path $BuildZip 'portable-build.json') -Text ($meta | ConvertTo-Json)

    Write-Host ''
    Write-Log OK "Portable release prepared: $Stage ($sizeMb MB)"
    Write-Log INFO "Next: .\Script_zip.ps1 -SkipBuild   (or just .\Script_zip.ps1)"
    exit 0
} catch {
    Fail $_.Exception.Message
}
