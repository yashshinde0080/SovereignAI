#Requires -Version 5.1
<#
.SYNOPSIS
    Builds the complete SovereignAI Windows x64 desktop application.

.DESCRIPTION
    Frontend (Next.js static export) -> Backend (PyInstaller: SovereignAIBackend.exe)
    -> Electron (electron-builder NSIS installer). All generated artifacts land
    under <repo>\build_exe. Safe to re-run: only known intermediate directories
    are cleaned, reports/logs/checksums are preserved and rewritten.

    The backend is packaged from a build-only virtualenv (backend\.venv-build)
    with the CPU torch wheel. A CUDA torch wheel adds ~3.2 GB of DLLs, and NSIS
    cannot package installers over ~2 GB, so the shipped backend runs on CPU;
    build_exe\extras\enable-gpu.ps1 restores GPU inference after install.

.EXAMPLE
    .\build_windows.ps1
    .\build_windows.ps1 -SkipBackend          # frontend + installer only
    .\build_windows.ps1 -SkipInstallerTest    # skip launching the packaged app
    .\build_windows.ps1 -TestInstall          # also run a real install/uninstall cycle
#>
[CmdletBinding()]
param(
    [switch]$SkipFrontend,
    [switch]$SkipBackend,
    [switch]$SkipElectron,
    [switch]$SkipInstallerTest,
    # Runs the NSIS installer for real (installs into build_exe\install_test,
    # creates Start Menu/desktop shortcuts, then uninstalls). Opt-in: the
    # default build never touches the user's installed programs.
    [switch]$TestInstall,
    [switch]$AllowCudaRuntime,
    [int]$SmokePort = 8123,
    # Chromium debug port used to confirm the packaged UI actually rendered.
    [int]$DebugPort = 9333
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# --------------------------------------------------------------------------- #
# Module path
# --------------------------------------------------------------------------- #
# If this script is launched from a shell that inherited PowerShell 7's (or a
# POSIX shell's) PSModulePath, Windows PowerShell 5.1 fails to autoload its own
# cmdlets -- Get-FileHash, Get-CimInstance and friends come back "not
# recognized". Pin the standard 5.1 module directories before anything else.
# --------------------------------------------------------------------------- #
$env:PSModulePath = (@(
        (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'WindowsPowerShell\Modules'),
        (Join-Path $env:ProgramFiles 'WindowsPowerShell\Modules'),
        (Join-Path $PSHOME 'Modules')
    ) | Where-Object { Test-Path -LiteralPath $_ }) -join ';'
Import-Module Microsoft.PowerShell.Utility -ErrorAction SilentlyContinue

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
$ProjectRoot = $PSScriptRoot
$BuildDir    = Join-Path $ProjectRoot "build_exe"
$ReportsDir  = Join-Path $BuildDir "reports"
$LogsDir     = Join-Path $BuildDir "logs"
$ChecksumsDir = Join-Path $BuildDir "checksums"
$ExtrasDir   = Join-Path $BuildDir "extras"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$ElectronDir = Join-Path $ProjectRoot "electron"
$BackendDir  = Join-Path $ProjectRoot "backend"
$BackendOut  = Join-Path $BuildDir "backend"
$PyInstallerDist = Join-Path $BuildDir "_pyinstaller"
$PyInstallerWork = Join-Path $BuildDir "_pyinstaller_work"
$BuildVenv   = Join-Path $BackendDir ".venv-build"
$VenvPython  = Join-Path $BuildVenv "Scripts\python.exe"
$SmokeDataRoot = Join-Path $BuildDir "tmp_smoke"

$InstallerPath = Join-Path $BuildDir "SovereignAI-Setup-x64.exe"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogFile = Join-Path $LogsDir "build-$Timestamp.log"

New-Item -ItemType Directory -Force -Path $BuildDir, $ReportsDir, $LogsDir, $ChecksumsDir, $ExtrasDir | Out-Null

$script:BuildLines = New-Object System.Collections.Generic.List[string]
$script:TestLines  = New-Object System.Collections.Generic.List[string]
$script:StartedAt  = Get-Date
$script:Stages     = New-Object System.Collections.Generic.List[object]

function Write-Report([string]$Message) {
    $script:BuildLines.Add($Message)
    Write-Host $Message
}

function Write-Test([string]$Name, [bool]$Passed, [string]$Detail) {
    $status = if ($Passed) { "PASS" } else { "FAIL" }
    $line = "[$status] $Name :: $Detail"
    $script:TestLines.Add($line)
    if ($Passed) { Write-Host $line -ForegroundColor Green } else { Write-Host $line -ForegroundColor Red }
}

function Invoke-Exe {
    param(
        [Parameter(Mandatory)][string]$File,
        [string[]]$Arguments = @(),
        [string]$WorkDir = $ProjectRoot,
        [string]$Stage = ""
    )
    Push-Location $WorkDir
    $previous = $ErrorActionPreference
    # Native stderr must not become a terminating error; the exit code is the
    # contract we check instead.
    $ErrorActionPreference = "Continue"
    try {
        & $File @Arguments 2>&1 | Tee-Object -FilePath $LogFile -Append | ForEach-Object { Write-Host $_ }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
        Pop-Location
    }
    if ($code -ne 0) {
        throw "$Stage failed: $File $($Arguments -join ' ') (exit code $code)"
    }
}

function Invoke-Stage {
    param([string]$Name, [scriptblock]$Body)
    Write-Report ""
    Write-Report "== $Name"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    & $Body
    $sw.Stop()
    $script:Stages.Add([pscustomobject]@{ Name = $Name; Seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1) })
    Write-Report "   -> ok ($([math]::Round($sw.Elapsed.TotalSeconds, 1))s)"
}

function Assert-File([string]$Path, [string]$What) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$What not found: $Path"
    }
}

function Get-SizeMb([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return 0 }
    if ((Get-Item -LiteralPath $Path).PSIsContainer) {
        $bytes = (Get-ChildItem -LiteralPath $Path -Recurse -File | Measure-Object -Property Length -Sum).Sum
    } else {
        $bytes = (Get-Item -LiteralPath $Path).Length
    }
    return [math]::Round($bytes / 1MB, 1)
}

function Get-Rcedit {
    # electron-builder's winCodeSign archive carries macOS symlinks, which 7-Zip
    # cannot create without admin/Developer Mode, so electron-builder's own
    # rcedit step is disabled (win.signAndEditExecutable = false) and we stamp
    # the icon/version ourselves. The cache often already holds rcedit-x64.exe
    # from a partially extracted archive; otherwise fetch the Windows tools only.
    $cacheRoot = Join-Path $env:LOCALAPPDATA "electron-builder\Cache\winCodeSign"
    $cached = Get-ChildItem -Path $cacheRoot -Recurse -Filter "rcedit-x64.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cached) { return $cached.FullName }

    $sevenZip = Join-Path $ElectronDir "node_modules\7zip-bin\win\x64\7za.exe"
    if (-not (Test-Path -LiteralPath $sevenZip)) { return $null }

    $out = Join-Path $cacheRoot "rcedit"
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    $archive = Join-Path $cacheRoot "winCodeSign-2.6.0.7z"
    if (-not (Test-Path -LiteralPath $archive)) {
        Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/electron-userland/electron-builder-binaries/releases/download/winCodeSign-2.6.0/winCodeSign-2.6.0.7z" -OutFile $archive
    }
    & $sevenZip x -bd $archive "-o$out" "-x!darwin" -y 2>&1 | Out-Null
    $found = Get-ChildItem -Path $out -Recurse -Filter "rcedit-x64.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { return $found.FullName }
    return $null
}

function Stop-ProcessTree([int]$ProcessId) {
    # /T scopes the kill to this process tree only.
    # Routed through cmd.exe so taskkill's stderr (a normal message when a child
    # has already exited) never becomes a PowerShell error record: under
    # $ErrorActionPreference='Stop' that would abort the pipeline after a
    # successful build. Cleanup failures never fail the build.
    try {
        & cmd.exe /c "taskkill /pid $ProcessId /T /F >nul 2>&1" | Out-Null
    } catch {
        Write-Report "note: could not terminate process tree $ProcessId (already gone)"
    }
}

# Stops the desktop app and its spawned backend, so a later launch starts from a
# clean slate. Only these two process names are ever touched.
function Stop-AppProcesses {
    @("SovereignAI", "SovereignAIBackend") | ForEach-Object {
        Get-Process -Name $_ -ErrorAction SilentlyContinue | ForEach-Object { Stop-ProcessTree $_.Id }
    }
    Start-Sleep -Seconds 2
}

function Wait-ForHealth([int]$Port, [int]$TimeoutSeconds, [int]$ProcessId) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $uri = "http://127.0.0.1:$Port/health"
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200 -and $response.Content -match '"status"\s*:\s*"healthy"') { return $true }
        } catch {
            # backend still starting
        }
        if ($ProcessId -gt 0 -and -not (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
            return $false
        }
        Start-Sleep -Milliseconds 750
    }
    return $false
}

Write-Host ""
Write-Host "SovereignAI Windows build" -ForegroundColor Cyan
Write-Host "  root   : $ProjectRoot"
Write-Host "  output : $BuildDir"
Write-Host "  log    : $LogFile"
Write-Host ""

try {
    # ----------------------------------------------------------------------- #
    Invoke-Stage "Preflight: environment" {
        if (-not ($env:OS -eq "Windows_NT")) { throw "This script builds the Windows application and must run on Windows." }
        if ([Environment]::Is64BitOperatingSystem -ne $true) { throw "64-bit Windows is required." }

        foreach ($dir in @($BackendDir, $FrontendDir, $ElectronDir)) {
            if (-not (Test-Path -LiteralPath $dir -PathType Container)) { throw "Expected repository directory missing: $dir" }
        }
        foreach ($file in @("backend\backend_entry.py", "backend\SovereignAIBackend.spec", "frontend\package.json", "electron\package.json", "electron\main.js")) {
            Assert-File (Join-Path $ProjectRoot $file) "Required source file"
        }

        $tools = @("node", "npm", "python")
        foreach ($tool in $tools) {
            if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Required build tool not found on PATH: $tool" }
        }

        $nodeVersion = (& node --version) -join ""
        $npmVersion = (& npm --version) -join ""
        $pythonVersion = (& python --version 2>&1) -join ""
        $lockfile = Join-Path $FrontendDir "package-lock.json"
        if (-not (Test-Path -LiteralPath $lockfile)) { throw "frontend\package-lock.json missing - cannot install reproducibly (npm ci)." }

        Write-Report "OS            : $([Environment]::OSVersion.VersionString) (x64)"
        Write-Report "PowerShell    : $($PSVersionTable.PSVersion)"
        Write-Report "node          : $nodeVersion"
        Write-Report "npm           : $npmVersion"
        Write-Report "python        : $pythonVersion"
        Write-Report "package mgr   : npm (frontend/package-lock.json present -> npm ci)"
        Write-Report "Build venv    : $BuildVenv"
        Write-Test "Preflight/toolchain" $true "node $nodeVersion, npm $npmVersion, $pythonVersion"
    }

    # ----------------------------------------------------------------------- #
    if (-not $SkipFrontend) {
        Invoke-Stage "Frontend: install dependencies + production build" {
            $npmCiArgs = @("ci", "--no-audit", "--no-fund")
            try {
                Invoke-Exe "npm.cmd" $npmCiArgs -WorkDir $FrontendDir -Stage "npm ci"
                Write-Report "npm ci          : ok (lockfile-installed)"
            } catch {
                Write-Report "npm ci          : FAILED ($($_.Exception.Message))"
                Write-Report "                  falling back to 'npm install' - lockfile may be out of sync with package.json."
                Invoke-Exe "npm.cmd" @("install", "--no-audit", "--no-fund") -WorkDir $FrontendDir -Stage "npm install"
            }

            # next.config.ts has output: 'export' -> static HTML in frontend/out,
            # which the Electron shell serves over the app:// protocol.
            Invoke-Exe "npm.cmd" @("run", "build") -WorkDir $FrontendDir -Stage "npm run build"

            $index = Join-Path $FrontendDir "out\index.html"
            Assert-File $index "Next.js static export"
            $routes = @("models", "console", "system", "documents", "benchmark", "workspace")
            foreach ($route in $routes) {
                Assert-File (Join-Path $FrontendDir "out\$route\index.html") "Exported route /$route"
            }
            Write-Report "frontend/out    : $([math]::Round((Get-SizeMb (Join-Path $FrontendDir 'out')), 1)) MB, $($routes.Count + 1) routes exported"
            Write-Test "Frontend/static-export" $true "out\index.html + $($routes.Count) routes present"
        }
    } else {
        Write-Report "== Frontend skipped (-SkipFrontend)"
    }

    # ----------------------------------------------------------------------- #
    if (-not $SkipBackend) {
        Invoke-Stage "Backend: build virtualenv (CPU torch)" {
            if (-not (Test-Path -LiteralPath $VenvPython)) {
                Write-Report "creating build venv: $BuildVenv"
                Invoke-Exe "python" @("-m", "venv", $BuildVenv) -Stage "create build venv"
                Invoke-Exe $VenvPython @("-m", "pip", "install", "--upgrade", "pip") -Stage "pip upgrade"
                Invoke-Exe $VenvPython @("-m", "pip", "install", "torch==2.5.1", "--index-url", "https://download.pytorch.org/whl/cpu") -Stage "install CPU torch"
                try {
                    Invoke-Exe $VenvPython @("-m", "pip", "install", "-r", (Join-Path $BackendDir "requirements.txt")) -Stage "install requirements"
                } catch {
                    # ik-llama-cpp-python has no prebuilt Windows wheel; it is an
                    # optional GGUF fallback for architectures transformers cannot load.
                    Write-Report "requirements install failed ($($_.Exception.Message)); retrying without the optional GGUF fallbacks"
                    $filtered = Join-Path $BuildDir "_requirements_nogguf.txt"
                    Get-Content (Join-Path $BackendDir "requirements.txt") |
                        Where-Object { $_ -notmatch "llama-cpp-python|ik-llama-cpp-python|llmfit" } |
                        Set-Content $filtered
                    Invoke-Exe $VenvPython @("-m", "pip", "install", "-r", $filtered) -Stage "install requirements (filtered)"
                }
            } else {
                Write-Report "reusing build venv: $BuildVenv"
            }

            Invoke-Exe $VenvPython @("-m", "pip", "install", "--upgrade", "pyinstaller") -Stage "install pyinstaller"

            $torchInfo = (& $VenvPython -c "import torch, sys; sys.stdout.write((torch.version.cuda or 'cpu') + '|' + torch.__version__)") -join ""
            Write-Report "build venv torch: $torchInfo"
            if ($torchInfo -notmatch "^cpu\|") {
                if ($AllowCudaRuntime) {
                    Write-Report "CUDA runtime kept (-AllowCudaRuntime): bundle will exceed the ~2 GB NSIS limit."
                } else {
                    Write-Report "swapping CUDA torch for the CPU wheel (NSIS cannot package > ~2 GB installers)"
                    Invoke-Exe $VenvPython @("-m", "pip", "install", "--force-reinstall", "--no-deps", "torch==2.5.1", "--index-url", "https://download.pytorch.org/whl/cpu") -Stage "swap in CPU torch"
                }
            }
            $torchAfter = (& $VenvPython -c "import torch, sys; sys.stdout.write(torch.__version__ + '|cuda=' + str(torch.cuda.is_available()))") -join ""
            Write-Report "build venv torch: $torchAfter"
            Write-Test "Backend/build-venv" $true $torchAfter
        }

        Invoke-Stage "Backend: PyInstaller package (SovereignAIBackend.exe)" {
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $PyInstallerDist, $PyInstallerWork
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $BackendOut
            New-Item -ItemType Directory -Force -Path $PyInstallerDist, $BackendOut | Out-Null

            # Safety net: drop CUDA DLLs even if a CUDA venv slipped through.
            if ($AllowCudaRuntime) { Remove-Item Env:SOVEREIGN_STRIP_CUDA -ErrorAction SilentlyContinue }
            else { $env:SOVEREIGN_STRIP_CUDA = "1" }

            Invoke-Exe $VenvPython @(
                "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level=INFO",
                "--distpath", $PyInstallerDist,
                "--workpath", $PyInstallerWork,
                (Join-Path $BackendDir "SovereignAIBackend.spec")
            ) -WorkDir $BackendDir -Stage "pyinstaller"

            $builtDir = Join-Path $PyInstallerDist "SovereignAIBackend"
            $builtExe = Join-Path $builtDir "SovereignAIBackend.exe"
            Assert-File $builtExe "PyInstaller output"
            Copy-Item -Path (Join-Path $builtDir "*") -Destination $BackendOut -Recurse -Force

            $exePath = Join-Path $BackendOut "SovereignAIBackend.exe"
            Assert-File $exePath "Packaged backend"
            $exeMb = Get-SizeMb $exePath
            $treeMb = Get-SizeMb $BackendOut
            if ($exeMb -lt 1) { throw "Packaged backend looks wrong ($exeMb MB)" }
            Write-Report "backend exe     : $exePath ($exeMb MB)"
            Write-Report "backend bundle  : $treeMb MB total (onedir; onefile would unpack torch to %TEMP on every launch)"
            Write-Test "Backend/executable-built" $true "SovereignAIBackend.exe $exeMb MB, bundle $treeMb MB"
        }

        Invoke-Stage "Backend: start + health check the packaged executable" {
            $exePath = Join-Path $BackendOut "SovereignAIBackend.exe"
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $SmokeDataRoot

            $stdout = Join-Path $LogsDir "backend-smoke-$Timestamp.out.log"
            $stderr = Join-Path $LogsDir "backend-smoke-$Timestamp.err.log"
            $env:SOVEREIGN_DATA_ROOT = $SmokeDataRoot
            $proc = Start-Process -FilePath $exePath `
                -ArgumentList @("--host", "127.0.0.1", "--port", "$SmokePort") `
                -WorkingDirectory $BackendOut -PassThru -NoNewWindow `
                -RedirectStandardOutput $stdout -RedirectStandardError $stderr
            $healthy = $false
            try {
                $healthy = Wait-ForHealth -Port $SmokePort -TimeoutSeconds 180 -ProcessId $proc.Id
            } finally {
                if (-not $proc.HasExited) { Stop-ProcessTree $proc.Id }
                Remove-Item Env:SOVEREIGN_DATA_ROOT -ErrorAction SilentlyContinue
            }

            $dbCreated = Test-Path -LiteralPath (Join-Path $SmokeDataRoot "workspace\database\sovereign.db")
            $logSize = if (Test-Path -LiteralPath $stdout) { (Get-Item $stdout).Length } else { 0 }
            Write-Report "GET /health     : $(if ($healthy) { 'healthy' } else { 'no response' })"
            Write-Report "writable data   : $(if ($dbCreated) { "created in $SmokeDataRoot (not next to the exe)" } else { "NOT created in $SmokeDataRoot" })"
            if (-not $healthy -and $logSize -gt 0) {
                Write-Report "--- backend stdout (tail) ---"
                Get-Content -LiteralPath $stdout -Tail 25 | ForEach-Object { Write-Report "    $_" }
            }
            if (-not $healthy -and (Test-Path -LiteralPath $stderr)) {
                $err = Get-Content -LiteralPath $stderr -Tail 25
                if ($err) { Write-Report "--- backend stderr (tail) ---"; $err | ForEach-Object { Write-Report "    $_" } }
            }
            Write-Test "Backend/executable-health" $healthy "GET http://127.0.0.1:$SmokePort/health"
            Write-Test "Backend/writable-data-redirect" $dbCreated "SOVEREIGN_DATA_ROOT -> $SmokeDataRoot"
            if (-not $healthy) { throw "Packaged backend did not answer /health within 180s (see $stdout)." }
        }
    } else {
        Write-Report "== Backend skipped (-SkipBackend)"
    }

    # ----------------------------------------------------------------------- #
    if (-not $SkipElectron) {
        Invoke-Stage "Electron: build unpacked app + Windows x64 NSIS installer" {
            $backendExe = Join-Path $BackendOut "SovereignAIBackend.exe"
            Assert-File $backendExe "Packaged backend (extraResources input)"
            Assert-File (Join-Path $FrontendDir "out\index.html") "Frontend export (extraResources input)"

            $unpacked = Join-Path $BuildDir "win-unpacked"
            $appExe = Join-Path $unpacked "SovereignAI.exe"
            $iconPath = Join-Path $ElectronDir "assets\icon.ico"

            # 1. unpacked application (exe editing disabled - see Get-Rcedit)
            Invoke-Exe "npm.cmd" @("run", "build:win:dir") -WorkDir $ElectronDir -Stage "electron-builder --dir"
            Assert-File $appExe "Unpacked application"

            # 2. stamp icon + version info onto the app executable
            $rcedit = Get-Rcedit
            if ($rcedit -and (Test-Path -LiteralPath $iconPath)) {
                & $rcedit $appExe --set-icon $iconPath `
                    --set-version-string "ProductName" "SovereignAI" `
                    --set-version-string "FileDescription" "SovereignAI Edge" `
                    --set-version-string "CompanyName" "SovereignAI" `
                    --set-file-version "1.0.0.0" --set-product-version "1.0.0.0" 2>&1 | Out-Null
                Write-Report "exe metadata    : icon + version stamped with $rcedit"
                Write-Test "Electron/exe-metadata" $true "rcedit applied icon.ico + version 1.0.0.0"
            } else {
                Write-Report "exe metadata    : rcedit unavailable - using the default Electron icon/version"
                Write-Test "Electron/exe-metadata" $false "rcedit not found; exe keeps default icon"
            }

            # 3. pack the installer from the stamped directory
            Invoke-Exe "npx.cmd" @("electron-builder", "--win", "nsis", "--x64", "--prepackaged", $unpacked) -WorkDir $ElectronDir -Stage "electron-builder nsis"
            Assert-File $InstallerPath "NSIS installer"
            Write-Report "installer       : $InstallerPath ($(Get-SizeMb $InstallerPath) MB)"
            Write-Test "Electron/installer-built" $true "$InstallerPath ($(Get-SizeMb $InstallerPath) MB)"
        }
    } else {
        Write-Report "== Electron skipped (-SkipElectron)"
    }

    # ----------------------------------------------------------------------- #
    Invoke-Stage "Verify: installer contents and packaged layout" {
        Assert-File $InstallerPath "Installer"
        $installerMb = Get-SizeMb $InstallerPath
        if ($installerMb -lt 50) { throw "Installer is suspiciously small ($installerMb MB)." }
        if ($installerMb -gt 2047) {
            Write-Test "Verify/installer-size" $false "$installerMb MB exceeds the ~2 GB NSIS limit"
        } else {
            Write-Test "Verify/installer-size" $true "$installerMb MB (under the ~2 GB NSIS ceiling)"
        }

        $unpacked = Join-Path $BuildDir "win-unpacked"
        $appExe = Join-Path $unpacked "SovereignAI.exe"
        $bundledBackend = Join-Path $unpacked "resources\backend\SovereignAIBackend.exe"
        $bundledFrontend = Join-Path $unpacked "resources\frontend\index.html"
        Assert-File $appExe "Unpacked application"
        Assert-File $bundledBackend "Backend inside the packaged app"
        Assert-File $bundledFrontend "Frontend inside the packaged app"
        Assert-File (Join-Path $unpacked "resources\backend\_internal\torch\version.py") "Bundled torch package"
        if (-not (Test-Path -LiteralPath (Join-Path $unpacked "Uninstall SovereignAI.exe"))) {
            Write-Report "note: electron-builder writes the uninstaller into the installer, not win-unpacked"
        }
        Write-Report "win-unpacked    : $(Get-SizeMb $unpacked) MB; backend.exe + frontend/index.html present in resources\"
        Write-Test "Verify/packaged-layout" $true "SovereignAI.exe + resources\backend + resources\frontend"
    }

    # Runs whenever an unpacked app is present, so -SkipElectron can still be
    # used to re-test an already-built package without repacking it.
    if (-not $SkipInstallerTest -and (Test-Path -LiteralPath (Join-Path $BuildDir "win-unpacked\SovereignAI.exe"))) {
        Invoke-Stage "Test: launch the packaged application" {
            $unpacked = Join-Path $BuildDir "win-unpacked"
            $appExe = Join-Path $unpacked "SovereignAI.exe"
            Stop-AppProcesses   # a stale instance would own the backend port
            $proc = Start-Process -FilePath $appExe -WorkingDirectory $unpacked -ArgumentList "--remote-debugging-port=$DebugPort" -PassThru
            $healthy = $false
            try {
                # Electron spawns the frozen backend on port 8000 and waits for /health.
                $healthy = Wait-ForHealth -Port 8000 -TimeoutSeconds 180 -ProcessId 0
                Write-Test "Installer/app-backend-start" $healthy "backend answered on port 8000 after the packaged app launched"

                # Ask the renderer what it actually loaded: the packaged static
                # export is only "working" if a page target points at app://.
                $rendered = $false
                $seen = "no renderer target"
                for ($i = 0; $i -lt 20 -and -not $rendered; $i++) {
                    try {
                        $targets = (Invoke-WebRequest -Uri "http://127.0.0.1:$DebugPort/json/list" -UseBasicParsing -TimeoutSec 5).Content | ConvertFrom-Json
                        foreach ($t in $targets) {
                            if ($t.type -eq "page") {
                                $seen = "title='$($t.title)' url=$($t.url)"
                                if ($t.url -like "app://*") { $rendered = $true }
                            }
                        }
                    } catch {
                        # window still coming up
                    }
                    if (-not $rendered) { Start-Sleep -Seconds 2 }
                }
                Write-Report "renderer        : $seen"
                Write-Test "Installer/frontend-rendered" $rendered "packaged UI served from $seen"
            } finally {
                if (-not $proc.HasExited) { Stop-ProcessTree $proc.Id }
                Get-Process -Name "SovereignAIBackend" -ErrorAction SilentlyContinue |
                    ForEach-Object { Write-Report "cleaning up leftover backend pid $($_.Id)"; Stop-ProcessTree $_.Id }
                Get-Process -Name "SovereignAI" -ErrorAction SilentlyContinue |
                    ForEach-Object { Stop-ProcessTree $_.Id }
            }

            # Data must have been written to the per-user data dir, not the install dir.
            $userData = Join-Path $env:APPDATA "SovereignAI"
            $dbInUserData = Test-Path -LiteralPath (Join-Path $userData "workspace\database\sovereign.db")
            $dbNextToExe = Test-Path -LiteralPath (Join-Path $unpacked "workspace\database\sovereign.db")
            Write-Report "user data dir   : $userData (db present: $dbInUserData)"
            Write-Test "Installer/user-data-persistence" $dbInUserData "state written to %APPDATA%\SovereignAI"
            Write-Test "Installer/install-dir-clean" (-not $dbNextToExe) "no writable state created inside the install directory"
        }
    }

    # ----------------------------------------------------------------------- #
    if ($TestInstall) {
        Invoke-Stage "Test: install, restart, uninstall (real NSIS cycle)" {
            $testRoot   = Join-Path $BuildDir "install_test"
            $installDir = Join-Path $testRoot "app"
            $uninstaller = Join-Path $installDir "Uninstall SovereignAI.exe"
            $startMenu  = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\SovereignAI.lnk"
            $desktopLnk = Join-Path ([Environment]::GetFolderPath('Desktop')) "SovereignAI.lnk"
            $userData   = Join-Path $env:APPDATA "SovereignAI"
            $dbPath     = Join-Path $userData "workspace\database\sovereign.db"

            Remove-Item -Recurse -Force -LiteralPath $testRoot -ErrorAction SilentlyContinue
            New-Item -ItemType Directory -Force -Path $testRoot | Out-Null

            Stop-AppProcesses
            # /D must be last and unquoted (NSIS rule), so the test path must be
            # space-free and is relative to a space-free repo.
            if ($installDir -match ' ') { throw "install_test path contains spaces; NSIS /D cannot be quoted: $installDir" }
            $installedExe = Join-Path $installDir "SovereignAI.exe"
            # A just-written 271 MB self-extracting installer is a favourite target
            # for a real-time AV scan, which can make the first launch die with an
            # access violation before it extracts. Retry, then check the result:
            # what matters is that the app is installed, not that attempt 1 worked.
            $setup = $null
            for ($attempt = 1; $attempt -le 3; $attempt++) {
                if ($attempt -gt 1) { Write-Report "note: retrying the silent install (attempt $attempt)"; Start-Sleep -Seconds 5 }
                $setup = Start-Process -FilePath $InstallerPath -ArgumentList "/S", "/D=$installDir" -PassThru -Wait
                Write-Report "silent install  : attempt $attempt exit code $($setup.ExitCode)"
                if (Test-Path -LiteralPath $installedExe) { break }
            }
            Write-Test "Install/silent-install" (Test-Path -LiteralPath $installedExe) "SovereignAI.exe installed after $attempt attempt(s), exit code $($setup.ExitCode)"
            Assert-File $installedExe "Installed application exe"
            Assert-File (Join-Path $installDir "resources\backend\SovereignAIBackend.exe") "Installed backend exe"
            Assert-File $uninstaller "Uninstaller"
            Write-Test "Install/layout" $true "SovereignAI.exe + resources\backend + uninstaller under $installDir"
            Write-Test "Install/start-menu-shortcut" (Test-Path -LiteralPath $startMenu) "$startMenu"
            Write-Test "Install/desktop-shortcut" (Test-Path -LiteralPath $desktopLnk) "$desktopLnk"

            # Launch from the install dir, with no source repo on the path.
            Stop-AppProcesses
            $null = Start-Process -FilePath $installedExe -WorkingDirectory $installDir -PassThru
            $firstRun = Wait-ForHealth -Port 8000 -TimeoutSeconds 180 -ProcessId 0
            $dbAfterFirst = Test-Path -LiteralPath $dbPath
            Write-Test "Install/app-starts-outside-repo" $firstRun "backend answered on 127.0.0.1:8000 from the installed app"
            Stop-AppProcesses

            # Restart: the same per-user data must still be there.
            $null = Start-Process -FilePath $installedExe -WorkingDirectory $installDir -PassThru
            $secondRun = Wait-ForHealth -Port 8000 -TimeoutSeconds 180 -ProcessId 0
            $dbAfterRestart = Test-Path -LiteralPath $dbPath
            Write-Test "Install/data-persists-across-restart" ($firstRun -and $secondRun -and $dbAfterFirst -and $dbAfterRestart) "same DB at $dbPath on both runs"
            Stop-AppProcesses
            $leftover = @(Get-Process -Name "SovereignAI", "SovereignAIBackend" -ErrorAction SilentlyContinue)
            Write-Test "Install/no-orphan-processes" ($leftover.Count -eq 0) "nothing left running after shutdown"

            # Uninstall.
            $un = Start-Process -FilePath $uninstaller -ArgumentList "/S" -PassThru -Wait
            for ($i = 0; $i -lt 20 -and (Test-Path -LiteralPath $installedExe); $i++) { Start-Sleep -Seconds 1 }
            Write-Test "Uninstall/removes-application" (-not (Test-Path -LiteralPath $installedExe)) "uninstaller exit $($un.ExitCode) removed $installedExe"
            Write-Test "Uninstall/removes-shortcuts" ((-not (Test-Path -LiteralPath $startMenu)) -and (-not (Test-Path -LiteralPath $desktopLnk))) "Start Menu + desktop links removed"
            Write-Test "Uninstall/keeps-user-data" (Test-Path -LiteralPath $dbPath) "models/data under %APPDATA%\SovereignAI preserved"

            Remove-Item -Recurse -Force -LiteralPath $testRoot -ErrorAction SilentlyContinue
        }
    } else {
        Write-Report ""
        Write-Report "== Test: install, restart, uninstall skipped (pass -TestInstall to run it)"
    }

    # ----------------------------------------------------------------------- #
    Invoke-Stage "Extras: optional GPU support" {
        $gpuScript = Join-Path $ProjectRoot "packaging\enable-gpu.ps1"
        if (Test-Path -LiteralPath $gpuScript) {
            Copy-Item -LiteralPath $gpuScript -Destination (Join-Path $ExtrasDir "enable-gpu.ps1") -Force
            $readme = Join-Path $ExtrasDir "README-GPU.txt"
            @"
SovereignAI - optional GPU (CUDA) support
=========================================

The installer ships a CPU-only torch runtime. A CUDA torch wheel carries
~3.2 GB of DLLs and NSIS (electron-builder's Windows installer target)
corrupts installers larger than ~2 GB, so CUDA is not in the installer.

To enable GPU inference after installing SovereignAI:

    powershell -ExecutionPolicy Bypass -File "..\extras\enable-gpu.ps1"

It copies the cu124 torch runtime into
    <install>\resources\backend\_internal\torch
using a local cu124 torch if one is present, otherwise downloading it.
Model/data files are untouched; reinstall or uninstall restores CPU-only.

GPU inference is optional: without it SovereignAI runs FullRAM/LayerStream
on CPU (device selection uses torch.cuda.is_available()).
"@ | Set-Content -Path $readme -Encoding UTF8
            Write-Report "extras          : $ExtrasDir\enable-gpu.ps1 + README-GPU.txt"
            Write-Test "Extras/gpu-pack" $true "enable-gpu.ps1 + README-GPU.txt copied to build_exe\extras"
        } else {
            Write-Test "Extras/gpu-pack" $false "packaging\enable-gpu.ps1 missing"
        }
    }

    # ----------------------------------------------------------------------- #
    Invoke-Stage "Reports + checksums" {
        $artifactPaths = @($InstallerPath)
        $unpacked = Join-Path $BuildDir "win-unpacked"
        foreach ($p in @((Join-Path $unpacked "SovereignAI.exe"), (Join-Path $unpacked "resources\backend\SovereignAIBackend.exe"))) {
            if (Test-Path -LiteralPath $p) { $artifactPaths += $p }
        }
        $lines = foreach ($p in $artifactPaths) {
            $hash = Get-FileHash -LiteralPath $p -Algorithm SHA256
            "$($hash.Hash.ToLower())  $(Split-Path $p -Leaf)   [$($hash.Path)]"
        }
        $lines | Set-Content -Path (Join-Path $ChecksumsDir "SHA256SUMS.txt") -Encoding ASCII
        $lines | ForEach-Object { Write-Report "sha256          : $_" }
        Write-Test "Reports/checksums" $true "$($artifactPaths.Count) artifact hashes in checksums\SHA256SUMS.txt"
    }

    Write-Report ""
    Write-Report "BUILD STATUS: SUCCESS"
}
catch {
    Write-Report ""
    Write-Report "BUILD STATUS: FAILED"
    Write-Report "error: $($_.Exception.Message)"
    Write-Test "Build pipeline" $false $_.Exception.Message
}
finally {
    $elapsed = [math]::Round(((Get-Date) - $script:StartedAt).TotalSeconds, 1)

    $buildReport = @()
    $buildReport += "SovereignAI Windows x64 build report"
    $buildReport += "generated : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    $buildReport += "duration  : $elapsed s"
    $buildReport += "host      : $([Environment]::OSVersion.VersionString) | PS $($PSVersionTable.PSVersion) | node $((& node --version) -join '') | npm $((& npm --version) -join '')"
    $buildReport += ""
    $buildReport += "STAGES"
    foreach ($stage in $script:Stages) { $buildReport += ("  {0,-58} {1,8}s" -f $stage.Name, $stage.Seconds) }
    if ($script:Stages.Count -eq 0) { $buildReport += "  (no stage completed)" }
    $buildReport += ""
    $buildReport += "DETAIL"
    $buildReport += $script:BuildLines
    $buildReport += ""
    $buildReport += "ARTIFACTS"
    foreach ($candidate in @($InstallerPath, $BackendOut, (Join-Path $BuildDir "win-unpacked"), (Join-Path $ChecksumsDir "SHA256SUMS.txt"))) {
        if (Test-Path -LiteralPath $candidate) {
            $buildReport += ("  {0,-58} {1,8} MB" -f $candidate, (Get-SizeMb $candidate))
        }
    }
    $buildReport | Set-Content -Path (Join-Path $ReportsDir "build-report.txt") -Encoding UTF8

    $testReport = @()
    $testReport += "SovereignAI Windows x64 test report"
    $testReport += "generated : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    $testReport += ""
    $testReport += "RESULTS"
    $testReport += $script:TestLines
    $testReport += ""
    $testReport += "SCOPE NOTES"
    $testReport += "  - Frontend, packaged backend and packaged application were exercised on the"
    $testReport += "    build machine. A clean-machine (no dev tooling) test was NOT performed."
    if ($TestInstall) {
        $testReport += "  - The NSIS installer ran a real silent install -> launch -> restart ->"
        $testReport += "    uninstall cycle against build_exe\install_test (shortcuts included)."
    } else {
        $testReport += "  - The NSIS installer was built and inspected; it was not installed. Run"
        $testReport += "    .\build_windows.ps1 -TestInstall for a real install/uninstall cycle."
    }
    $testReport += "  - Local model inference requires model weights (workspace\models);"
    $testReport += "    none are bundled, so no generation test was run."
    $testReport += "  - RAG embeddings require a one-time download of the sentence-transformers"
    $testReport += "    model; chat with cloud providers requires API keys. Both need network."
    $testReport | Set-Content -Path (Join-Path $ReportsDir "test-report.txt") -Encoding UTF8

    Write-Host ""
    Write-Host "reports : $(Join-Path $ReportsDir 'build-report.txt')"
    Write-Host "          $(Join-Path $ReportsDir 'test-report.txt')"
    Write-Host "log     : $LogFile"
    if (Test-Path -LiteralPath $InstallerPath) {
        Write-Host "installer: $InstallerPath ($(Get-SizeMb $InstallerPath) MB)" -ForegroundColor Cyan
    } else {
        Write-Host "installer: NOT PRODUCED" -ForegroundColor Red
    }
}
