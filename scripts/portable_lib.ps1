#Requires -Version 5.1
<#
    Shared helpers for the SovereignAI portable release scripts.

    Dot-source this file from Script_portable.ps1 / Script_zip.ps1 (both live in
    the repo root); do not run it directly.

    Everything here is Windows PowerShell 5.1 compatible (no PS7-only syntax).
#>

# Windows PowerShell 5.1 fails to auto-load its own cmdlets (Get-FileHash and
# friends) when the shell inherited PowerShell 7's or a POSIX PSModulePath.
# Pin the standard 5.1 module directories before anything else (same guard as
# build_windows.ps1 / scripts\build-release.ps1).
$env:PSModulePath = (@(
        (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'WindowsPowerShell\Modules'),
        (Join-Path $env:ProgramFiles 'WindowsPowerShell\Modules'),
        (Join-Path $PSHOME 'Modules')
    ) | Where-Object { Test-Path -LiteralPath $_ }) -join ';'
Import-Module Microsoft.PowerShell.Utility -ErrorAction SilentlyContinue
Add-Type -AssemblyName System.IO.Compression -ErrorAction SilentlyContinue
Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
function Write-Log {
    param(
        [Parameter(Mandatory)][ValidateSet('INFO', 'BUILD', 'DATA', 'VERIFY', 'ZIP', 'OK', 'WARN', 'ERROR')][string]$Level,
        [Parameter(Mandatory)][string]$Message
    )
    $color = switch ($Level) {
        'BUILD' { 'Cyan' }
        'DATA' { 'Magenta' }
        'VERIFY' { 'DarkCyan' }
        'ZIP' { 'Blue' }
        'OK' { 'Green' }
        'WARN' { 'Yellow' }
        'ERROR' { 'Red' }
        default { 'Gray' }
    }
    Write-Host ("[{0}] {1}" -f $Level, $Message) -ForegroundColor $color
}

function Write-TextFile {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Text,
        # LF + no BOM, so `sha256sum -c` can read the checksum file on unix.
        [switch]$NoBom
    )
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $utf8Bom = New-Object System.Text.UTF8Encoding($true)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    if ($NoBom) { [System.IO.File]::WriteAllText($Path, $Text, $utf8NoBom) }
    else { [System.IO.File]::WriteAllText($Path, $Text, $utf8Bom) }
}

# --------------------------------------------------------------------------- #
# Validation / measurement
# --------------------------------------------------------------------------- #
function Assert-Path {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$What,
        [ValidateSet('Leaf', 'Container')][string]$Kind = 'Leaf'
    )
    if (-not (Test-Path -LiteralPath $Path -PathType $Kind)) {
        throw "$What not found ($Kind): $Path"
    }
}

function Get-RepoVersion {
    param([Parameter(Mandatory)][string]$RepoRoot)
    $vf = Join-Path $RepoRoot 'VERSION'
    Assert-Path -Path $vf -What 'VERSION file'
    $v = (Get-Content -LiteralPath $vf -Raw).Trim()
    if (-not $v) { throw "VERSION file is empty: $vf" }
    if ($v -notmatch '^[0-9]+\.[0-9]+\.[0-9]+([-.+][0-9A-Za-z.-]+)?$') {
        throw "VERSION is not a valid version string: '$v' ($vf)"
    }
    return $v
}

function Get-PathSizeMb {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return 0 }
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.PSIsContainer) {
        $bytes = (Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum
        if (-not $bytes) { return 0 }
        return [math]::Round($bytes / 1MB, 1)
    }
    return [math]::Round($item.Length / 1MB, 1)
}

function Get-FreeSpaceMb {
    param([Parameter(Mandatory)][string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    while ($full -and -not (Test-Path -LiteralPath $full)) {
        $parent = Split-Path -Parent $full
        if (-not $parent -or $parent -eq $full) { break }
        $full = $parent
    }
    $drive = [System.IO.Path]::GetPathRoot($full)
    try { $d = New-Object System.IO.DriveInfo($drive) }
    catch { return -1 }
    return [math]::Round($d.AvailableFreeSpace / 1MB, 1)
}

# --------------------------------------------------------------------------- #
# Guarded cleanup (staging only -- never source, user data, or releases)
# --------------------------------------------------------------------------- #
function Remove-GeneratedDir {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$AllowedRoot,
        [Parameter(Mandatory)][string]$RepoRoot
    )
    $full = [System.IO.Path]::GetFullPath($Path)
    $allowed = [System.IO.Path]::GetFullPath($AllowedRoot)
    $repo = [System.IO.Path]::GetFullPath($RepoRoot)
    $sep = [System.IO.Path]::DirectorySeparatorChar

    if ($full -eq $allowed) { return } # the output root itself is never deleted
    if (-not $full.StartsWith($allowed + $sep, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to delete '$full' - outside the allowed output root '$allowed'."
    }
    if ($full -eq $repo) { throw "Refusing to delete the repository root: $full" }
    if ($full -eq [System.IO.Path]::GetPathRoot($full)) { throw "Refusing to delete a drive root: $full" }
    foreach ($protected in @('workspace', 'workshop', 'releases', 'build_exe', 'releases', 'backend', 'frontend', 'electron', '.git', 'scripts', 'packaging')) {
        if ($full -eq (Join-Path $repo $protected)) { throw "Refusing to delete protected path: $full" }
    }
    $leaf = Split-Path -Leaf $full
    if ($leaf -in @('workspace', 'workshop', 'releases', 'build_exe', '.git')) {
        throw "Refusing to delete a '$leaf' directory: $full"
    }
    if (Test-Path -LiteralPath $full) {
        Write-Log INFO "Removing generated output: $full"
        Remove-Item -Recurse -Force -LiteralPath $full
    }
}

# --------------------------------------------------------------------------- #
# Security / release hygiene scans
# --------------------------------------------------------------------------- #
function Test-SecretArtifacts {
    param([Parameter(Mandatory)][string]$Path)
    $problems = New-Object System.Collections.Generic.List[string]
    if (-not (Test-Path -LiteralPath $Path)) { return $problems }

    $exact = @('.env', 'id_rsa', 'id_ed25519', 'credentials.json', 'secrets.json',
        'cloud_providers.db', '.npmrc', '.netrc')
    Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $n = $_.Name.ToLowerInvariant()
        $p = $_.FullName.ToLowerInvariant()
        if ($exact -contains $n) { $problems.Add("credential file: $($_.FullName)"); return }
        if ($n.StartsWith('.env')) { $problems.Add("env file: $($_.FullName)"); return }
        if ($n.EndsWith('.env')) { $problems.Add("env file: $($_.FullName)"); return }
        if ($n.StartsWith('id_rsa') -or $n.StartsWith('id_ed25519')) { $problems.Add("private key: $($_.FullName)"); return }
        if ($n.EndsWith('.pfx') -or $n.EndsWith('.p12') -or $n.EndsWith('.key')) { $problems.Add("key material: $($_.FullName)"); return }
        if ($n -like 'sovereign*.db*') { $problems.Add("shipped database: $($_.FullName)"); return }
        # *.pem is usually a CA bundle (certifi) -- only flag ones that are not.
        if ($n.EndsWith('.pem') -and $p -notmatch '[\\/]certifi[\\/]' -and $n -ne 'cacert.pem') {
            $problems.Add("certificate/key file: $($_.FullName)")
        }
    }
    return $problems
}

function Test-BundlePathLeakage {
    <#
        Returns a hashtable: @{ Hard = [string[]]; Soft = [string[]] }.

        Hard = the build machine's repo path appears inside a packaged file
               (criterion: the app must not depend on D:\SovereignAI).
        Soft = a Windows drive path appears in a small text file (reported, not
               fatal -- minified vendor JS may legitimately contain one).

        The frozen runtime (resources\backend\_internal, ~850 MB of CPython +
        torch) is skipped; it is not on the launch path.
    #>
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$RepoRoot
    )
    $hard = New-Object System.Collections.Generic.List[string]
    $soft = New-Object System.Collections.Generic.List[string]
    $needle = $RepoRoot.TrimEnd('\', '/')
    $skipDir = 'resources' + [System.IO.Path]::DirectorySeparatorChar + 'backend' + [System.IO.Path]::DirectorySeparatorChar + '_internal'
    $textExt = @('.txt', '.json', '.html', '.js', '.bat', '.cmd', '.ps1', '.md', '.ini', '.cfg', '.yml', '.yaml', '.css', '.mjs')
    $maxBytes = 16MB

    $files = Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notlike "*$skipDir*" }

    foreach ($f in $files) {
        $found = $false
        try {
            $fs = [System.IO.File]::OpenRead($f.FullName)
            try {
                $len = [int][math]::Min($fs.Length, $maxBytes)
                if ($len -le 0) { continue }
                $buf = New-Object byte[] $len
                [void]$fs.Read($buf, 0, $len)
            } finally { $fs.Dispose() }

            $ascii = [System.Text.Encoding]::ASCII.GetString($buf)
            $uni = [System.Text.Encoding]::Unicode.GetString($buf)
            if ($ascii.IndexOf($needle, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -or
                $uni.IndexOf($needle, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                $hard.Add($f.FullName)
                $found = $true
            }
            if (-not $found -and $textExt -contains $f.Extension.ToLowerInvariant()) {
                if ($ascii -match '[A-Za-z]:\\[A-Za-z0-9_. -]+\\') { $soft.Add($f.FullName) }
            }
        } catch {
            Write-Log WARN "Could not scan $($f.FullName): $($_.Exception.Message)"
        }
    }
    return @{ Hard = $hard; Soft = $soft }
}

function Test-LauncherHygiene {
    <# A launcher must reference the exe by name and hold no absolute host path. #>
    param([Parameter(Mandatory)][string]$Path)
    $problems = New-Object System.Collections.Generic.List[string]
    $text = Get-Content -LiteralPath $Path -Raw
    if ($text -notmatch 'SovereignAI\.exe') { $problems.Add("$([IO.Path]::GetFileName($Path)) does not reference SovereignAI.exe") }
    if ($text -match '[A-Za-z]:\\') { $problems.Add("$([IO.Path]::GetFileName($Path)) contains an absolute drive path") }
    if ($text -match 'D:\\SovereignAI') { $problems.Add("$([IO.Path]::GetFileName($Path)) hardcodes the repository path") }
    return $problems
}

# --------------------------------------------------------------------------- #
# Portable bundle contract (the app's real layout, not a generic template)
# --------------------------------------------------------------------------- #
function Get-PortableTopName {
    <# Single source of truth for the ZIP's top-level folder (and the report).
       Keep it short: the frozen transformers runtime holds deep paths, and the
       whole chain must fit Windows' 260-char MAX_PATH after extraction. #>
    param([Parameter(Mandatory)][string]$Version)
    "SovereignAI-Portable-Windows-x64-v$Version"
}

function Get-PortableRequiredFiles {
    @(
        'SovereignAI.exe',
        'SovereignAI.bat',
        'README_PORTABLE.txt',
        'resources\backend\SovereignAIBackend.exe',
        'resources\frontend\index.html'
    )
}

function Get-PortableRequiredDirs {
    # Written by the app at runtime under SOVEREIGN_DATA_ROOT (= <root>\data).
    # Only directories the app actually uses -- see electron\main.js + backend\app\config.py.
    @(
        'data',
        'data\electron',
        'data\cache\temp',
        'data\cache\hf',
        'data\config',
        'data\share',
        'data\workspace',
        'data\workspace\models',
        'data\workspace\plugins',
        'data\workspace\database',
        'data\workspace\logs',
        'data\workspace\sessions'
    )
}

function Test-PortableBundle {
    <# Returns [string[]] of problems (empty array = a complete portable bundle). #>
    param([Parameter(Mandatory)][string]$Path)

    $problems = New-Object System.Collections.Generic.List[string]
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        $problems.Add("staging directory missing: $Path")
        return $problems
    }

    foreach ($rel in @(Get-PortableRequiredFiles)) {
        if (-not (Test-Path -LiteralPath (Join-Path $Path $rel) -PathType Leaf)) {
            $problems.Add("missing required file: $rel")
        }
    }
    foreach ($rel in @(Get-PortableRequiredDirs)) {
        if (-not (Test-Path -LiteralPath (Join-Path $Path $rel) -PathType Container)) {
            $problems.Add("missing data directory: $rel")
        }
    }
    # Electron/Chromium licenses ship from electron-builder next to the exe.
    if (-not (Test-Path -LiteralPath (Join-Path $Path 'LICENSE.electron.txt') -PathType Leaf)) {
        $problems.Add('missing LICENSE.electron.txt (third-party notices)')
    }
    # A bundle never ships a database -- it is created on first run on the drive.
    $db = @(Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue -Filter 'sovereign*.db*')
    if ($db.Count -gt 0) { $problems.Add("a database was staged (should be created on first run): $($db[0].FullName)") }

    foreach ($launcher in @('SovereignAI.bat')) {
        $lp = Join-Path $Path $launcher
        if (Test-Path -LiteralPath $lp -PathType Leaf) {
            foreach ($p in @(Test-LauncherHygiene -Path $lp)) { $problems.Add($p) }
        }
    }
    return $problems
}
