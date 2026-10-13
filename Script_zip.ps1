#Requires -Version 5.1
<#
.SYNOPSIS
    Packages the portable staging directory into a versioned, verified Windows ZIP.

.DESCRIPTION
    Produces build_zip\SovereignAI-Portable-Windows-x64-v<version>.zip from the
    portable staging directory prepared by Script_portable.ps1, plus
    build_zip\SHA256SUMS.txt and build_zip\build-report.txt.

    Unless -SkipBuild is given, Script_portable.ps1 runs first. The archive holds
    a single top-level folder (SovereignAI-Portable-Windows-x64-v<version>) -- no
    nested "portable" directory -- and preserves empty data directories so the
    bundle is portable out of the box.

    Zip creation reuses the project's Python stdlib helper (scripts\release_lib.py),
    the same one scripts\build-release.ps1 uses; it writes explicit directory
    entries, which .NET Compress-Archive does not reliably do.

    An existing artifact is never overwritten silently: without -Force a
    collision-safe, timestamped name is produced instead. Nothing outside
    build_zip\ is written or removed.

.EXAMPLE
    .\Script_zip.ps1
    .\Script_zip.ps1 -SkipBuild
    .\Script_zip.ps1 -Force
    .\Script_zip.ps1 -Clean -Configuration Release
#>
[CmdletBinding()]
param(
    [ValidateSet('Release', 'Debug')][string]$Configuration = 'Release',
    # Clear generated staging/reports and rebuild from scratch.
    [switch]$Clean,
    # Do not rebuild: package the existing, verified staging directory.
    [switch]$SkipBuild,
    [ValidateSet('x64')][string]$Architecture = 'x64',
    # Overwrite an existing ZIP of the same version.
    [switch]$Force,
    # Must stay inside <repo>\build_zip.
    [string]$OutputDirectory = '',
    [string]$PortableDirectory = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'scripts\portable_lib.ps1')

# --------------------------------------------------------------------------- #
# Paths (resolved from this script's location, never the shell's cwd)
# --------------------------------------------------------------------------- #
$Root = $PSScriptRoot
$BuildZip = Join-Path $Root 'build_zip'
$PortableScript = Join-Path $Root 'Script_portable.ps1'
$Lib = Join-Path $Root 'scripts\release_lib.py'
$AppName = 'SovereignAI Edge'

if (-not $OutputDirectory) { $OutputDirectory = $BuildZip }
if (-not $PortableDirectory) { $PortableDirectory = Join-Path $BuildZip 'portable' }
$OutputDir = [System.IO.Path]::GetFullPath($OutputDirectory)
$Stage = [System.IO.Path]::GetFullPath($PortableDirectory)
$AllowedRoot = [System.IO.Path]::GetFullPath($BuildZip)

$validation = New-Object System.Collections.Generic.List[string]
$report = New-Object System.Collections.Generic.List[string]
function Add-Report([string]$Line) { $report.Add($Line); Write-Host $Line }
function Check([string]$Name, [bool]$Passed, [string]$Detail) {
    $tag = if ($Passed) { 'PASS' } else { 'FAIL' }
    $validation.Add("[$tag] $Name :: $Detail")
    if (-not $Passed) { Write-Log ERROR "$Name :: $Detail" } else { Write-Log VERIFY "$Name :: $Detail" }
}
function Fail([string]$Message) {
    Write-Log ERROR $Message
    # Overwrite any previous success report with an accurate FAILED one, so a
    # failed run never leaves a stale "status: OK" behind.
    $lines = @(
        'SovereignAI Edge - portable ZIP build report',
        '===========================================',
        'status        : FAILED',
        "build time    : $((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))",
        "error         : $Message",
        'zip path      : (not produced)',
        'report        : build_zip\build-report.txt'
    )
    if ($validation.Count -gt 0) {
        $lines += 'validation:'
        foreach ($v in $validation) { $lines += "  $v" }
    }
    try { Write-TextFile -Path (Join-Path $BuildZip 'build-report.txt') -Text (($lines -join [Environment]::NewLine) + [Environment]::NewLine) } catch { }
    Write-Host ''
    Write-Log ERROR "Packaging failed. See build_zip\build-report.txt"
    exit 1
}

try {
    Write-Host ''
    Write-Log INFO "Creating portable ZIP release..."
    Write-Host "       repo   : $Root"
    Write-Log INFO "output : $OutputDir"
    Write-Host ''

    # ----------------------------------------------------------------------- #
    # 1. Validation
    # ----------------------------------------------------------------------- #
    if (-not $OutputDir.StartsWith($AllowedRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase) -and
        $OutputDir -ne $AllowedRoot) {
        throw "OutputDirectory must be inside $AllowedRoot (got: $OutputDir)."
    }
    Assert-Path -Path $PortableScript -What 'Script_portable.ps1'
    Assert-Path -Path $Lib -What 'scripts\release_lib.py'
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw 'python is required on the build machine to create the archive (scripts\release_lib.py).'
    }
    $Version = Get-RepoVersion -RepoRoot $Root

    # ----------------------------------------------------------------------- #
    # 2. Build / stage
    # ----------------------------------------------------------------------- #
    if ($SkipBuild) {
        Write-Log INFO "Skipping build (-SkipBuild): packaging existing staging"
        if ($Clean) {
            foreach ($extra in @('build-report.txt', 'SHA256SUMS.txt', 'portable-report.txt', 'portable-build.json')) {
                $p = Join-Path $BuildZip $extra
                if (Test-Path -LiteralPath $p) { Remove-Item -Force -LiteralPath $p }
            }
            Write-Log INFO "-Clean: generated reports/checksums cleared"
        }
    } else {
        Write-Log BUILD "Preparing portable staging (Script_portable.ps1)..."
        $portableArgs = @('-Configuration', $Configuration, '-Architecture', $Architecture)
        if ($Clean) { $portableArgs += '-Clean' }
        & $PortableScript @portableArgs
        if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Script_portable.ps1 exited with code $LASTEXITCODE" }
    }

    # ----------------------------------------------------------------------- #
    # 3. The staging directory must be a complete portable application
    # ----------------------------------------------------------------------- #
    $bundleProblems = @(Test-PortableBundle -Path $Stage)
    if ($bundleProblems.Count -gt 0) {
        foreach ($p in $bundleProblems) { Write-Log ERROR "  $p" }
        throw "Staging is not a complete portable application ($($bundleProblems.Count) problem(s)). Run .\Script_portable.ps1 first."
    }
    Check 'staging-complete' $true "staging at $Stage is a complete portable app"

    # ----------------------------------------------------------------------- #
    # 4. Target filename (never overwrite silently)
    # ----------------------------------------------------------------------- #
    $artBase = Get-PortableTopName -Version $Version
    $zipPath = Join-Path $OutputDir "$artBase.zip"
    if ((Test-Path -LiteralPath $zipPath) -and -not $Force) {
        $collision = "$artBase-" + (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss') + '.zip'
        Write-Log WARN "Artifact already exists: $(Split-Path -Leaf $zipPath)"
        Write-Log WARN "Writing a collision-safe name instead: $collision (use -Force to overwrite)"
        $zipPath = Join-Path $OutputDir $collision
    } elseif ((Test-Path -LiteralPath $zipPath) -and $Force) {
        Write-Log WARN "Overwriting existing artifact (-Force): $(Split-Path -Leaf $zipPath)"
    }
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

    # ----------------------------------------------------------------------- #
    # 5. Create the archive (single top-level folder, no nested "portable")
    # ----------------------------------------------------------------------- #
    Write-Log ZIP "Creating archive..."
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & python $Lib zip $Stage $zipPath --top $artBase
        $zipCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    if ($zipCode -ne 0) { throw "release_lib.py zip failed (exit $zipCode)" }
    Assert-Path -Path $zipPath -What 'created archive'
    $zipMb = Get-PathSizeMb -Path $zipPath
    Write-Log OK "archive written: $zipPath ($zipMb MB)"

    # ----------------------------------------------------------------------- #
    # 6. Checksum
    # ----------------------------------------------------------------------- #
    $hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $relZip = Split-Path -Leaf $zipPath
    Write-TextFile -Path (Join-Path $BuildZip 'SHA256SUMS.txt') -Text ("$hash  $relZip" + "`n") -NoBom
    Write-Log OK "sha256: $hash"

    # ----------------------------------------------------------------------- #
    # 7. Verify the archive can be opened and holds what we expect
    # ----------------------------------------------------------------------- #
    Write-Log VERIFY "Verifying archive contents..."
    $expected = @(
        "$artBase/SovereignAI.exe",
        "$artBase/SovereignAI.bat",
        "$artBase/README_PORTABLE.txt",
        "$artBase/resources/backend/SovereignAIBackend.exe",
        "$artBase/resources/frontend/index.html",
        "$artBase/data/",
        "$artBase/data/workspace/database/",
        "$artBase/data/cache/"
    )
    $names = @()
    try {
        $archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
        try { $names = @($archive.Entries | ForEach-Object { $_.FullName }) } finally { $archive.Dispose() }
    } catch {
        throw "Archive could not be opened: $($_.Exception.Message)"
    }

    $missing = @($expected | Where-Object { $names -notcontains $_ })
    Check 'archive-opens' $true "$($names.Count) entries"
    Check 'archive-contents' ($missing.Count -eq 0) $(if ($missing.Count -eq 0) { "all $($expected.Count) expected entries present" } else { "missing: $($missing -join ', ')" })
    if ($missing.Count -gt 0) { throw "Archive is missing expected entries." }

    $nested = @($names | Where-Object { $_ -like "$artBase/portable/*" })
    Check 'no-nested-portable' ($nested.Count -eq 0) 'archive has no nested portable\ directory'

    $leaked = @($names | Where-Object { $_ -match '(^|/)(\.git/|node_modules/|\.env)' -or $_ -like '*.map' })
    Check 'exclusions-clean' ($leaked.Count -eq 0) $(if ($leaked.Count -eq 0) { 'no git/node_modules/.env/source-map entries' } else { "unexpected entries: $($leaked[0])" })
    if ($leaked.Count -gt 0) { throw "Archive contains excluded development artifacts." }

    # Checksum matches the file on disk (the value we wrote above).
    $verifyHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Check 'sha256-matches' ($verifyHash -eq $hash) $hash

    # ----------------------------------------------------------------------- #
    # 8. Build report
    # ----------------------------------------------------------------------- #
    $builtAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    Add-Report "SovereignAI Edge - portable ZIP build report"
    Add-Report "==========================================="
    Add-Report "app           : $AppName"
    Add-Report "version       : $Version"
    Add-Report "configuration : $Configuration"
    Add-Report "platform      : windows $Architecture"
    Add-Report "build time    : $builtAt"
    Add-Report "zip path      : $zipPath"
    Add-Report "zip size      : $zipMb MB"
    Add-Report "sha256        : $hash"
    Add-Report "staging       : $Stage ($(Test-Path -LiteralPath $Stage))"
    Add-Report "portable data : data\ (workspace\..., cache\, electron\)"
    Add-Report "bundled       : Electron 28, frozen CPython backend, Next.js static export"
    Add-Report "external deps : none to launch (no Python/Node install, no admin)"
    Add-Report "not bundled   : model weights, GPU/CUDA torch, cloud API keys"
    Add-Report ""
    Add-Report "validation:"
    foreach ($v in $validation) { Add-Report "  $v" }
    Add-Report ""
    Add-Report "status        : OK"

    Write-TextFile -Path (Join-Path $BuildZip 'build-report.txt') -Text (($report -join [Environment]::NewLine) + [Environment]::NewLine)

    Write-Host ''
    Write-Log OK "Portable release validated."
    Write-Host "       zip    : $zipPath"
    Write-Host "       sha256 : $hash"
    Write-Host "       report : $(Join-Path $BuildZip 'build-report.txt')"
    exit 0
} catch {
    Fail $_.Exception.Message
}
