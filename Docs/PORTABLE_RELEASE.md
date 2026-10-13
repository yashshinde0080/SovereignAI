# SovereignAI Edge — Portable Windows Release

Two PowerShell scripts at the repository root build a self-contained,
relocatable Windows x64 release of SovereignAI Edge:

| Script | Purpose | Output |
|---|---|---|
| `Script_portable.ps1` | Builds/stages a complete portable application | `build_zip\portable\` |
| `Script_zip.ps1` | Packages that staging into a versioned, checksum-verified ZIP | `build_zip\*.zip`, `SHA256SUMS.txt`, `build-report.txt` |

Both scripts resolve the repository root from their **own location**, so they can
be run from any working directory. All generated artifacts stay under
`build_zip\`. Nothing outside `build_zip\` (source, `workspace\`, `releases\`,
`build_exe\`) is written or deleted.

This is a **separate** workflow from `scripts\build-release.ps1`, which packages
the same app into `releases\` for the multi-platform CI pipeline. Both reuse the
same build (`build_windows.ps1`) and the same archiving helper
(`scripts\release_lib.py`).

---

## Quick start

```powershell
# 1. Stage the portable application into build_zip\portable
.\Script_portable.ps1

# 2. Package it into build_zip\SovereignAI-Portable-Windows-x64-v<version>.zip
.\Script_zip.ps1 -SkipBuild

# --- or one command for both ---
.\Script_zip.ps1
```

Extract the ZIP anywhere (folder, USB drive, external SSD) and run
`SovereignAI.bat`. No installer, no admin rights, no Python/Node install.

---

## Creating a portable build (`Script_portable.ps1`)

```powershell
.\Script_portable.ps1                       # full build + stage
.\Script_portable.ps1 -SkipBuild            # re-stage from an existing build_exe\win-unpacked
.\Script_portable.ps1 -Clean                # clear generated reports/staging, then rebuild
.\Script_portable.ps1 -Configuration Release
.\Script_portable.ps1 -Architecture x64
```

| Parameter | Default | Meaning |
|---|---|---|
| `-Configuration` | `Release` | Build configuration label (`Release` / `Debug`). |
| `-Clean` | off | Remove generated staging + reports before rebuilding. Never touches user data. |
| `-SkipBuild` | off | Reuse the existing `build_exe\win-unpacked` instead of compiling. |
| `-Architecture` | `x64` | Only `x64` is supported; other values are rejected. |
| `-OutputDirectory` | `build_zip\portable` | Staging path; **must** be inside `build_zip\`. |

The staging directory is always rebuilt from scratch, so repeated runs never
accumulate stale files.

If `build_windows.ps1` fails, `Script_portable.ps1` stops immediately, prints the
log location, and exits with a nonzero status — it never reports success just
because a directory exists.

## Creating a ZIP release (`Script_zip.ps1`)

```powershell
.\Script_zip.ps1                 # runs Script_portable.ps1, then packages
.\Script_zip.ps1 -SkipBuild      # package the existing staging directory
.\Script_zip.ps1 -Force          # overwrite an existing ZIP of the same version
.\Script_zip.ps1 -Clean          # rebuild staging from scratch, then package
```

| Parameter | Default | Meaning |
|---|---|---|
| `-Configuration` | `Release` | Passed through to `Script_portable.ps1`. |
| `-Clean` | off | Rebuild the staging directory from scratch first. |
| `-SkipBuild` | off | Do not rebuild; validate and package the existing staging directory. |
| `-Architecture` | `x64` | Only `x64`. |
| `-Force` | off | Overwrite an existing artifact. Without it, a collision produces a timestamped filename. |
| `-OutputDirectory` | `build_zip` | Where the ZIP/report go; must be inside `build_zip\`. |
| `-PortableDirectory` | `build_zip\portable` | Staging directory to package. |

An existing artifact is **never** overwritten silently: without `-Force` the
script writes `SovereignAI-Portable-Windows-x64-v<version>-<UTCstamp>.zip` and
says so in the log.

---

## Output layout

```
build_zip\
├── portable\                                     staging (the app as shipped)
│   ├── SovereignAI.exe                           Electron 28 shell (entry point)
│   ├── SovereignAI.bat                           launcher (relative paths only)
│   ├── README_PORTABLE.txt                       end-user leaflet
│   ├── LICENSES\                                 project licenses
│   ├── LICENSE.electron.txt, LICENSES.chromium.html
│   ├── resources\
│   │   ├── backend\SovereignAIBackend.exe        frozen CPython backend (+ _internal\)
│   │   └── frontend\                             Next.js static export
│   └── data\                                     portable writable storage (empty)
├── SovereignAI-Portable-Windows-x64-v<version>.zip
├── SHA256SUMS.txt
├── build-report.txt
├── portable-report.txt, portable-build.json
└── logs\portable-<timestamp>.log                 only when a build was run
```

Inside the ZIP there is a **single** top-level folder
(`SovereignAI-Portable-Windows-x64-v<version>\`) — never a nested `portable\`.

---

## Required build tools

The build machine needs the same toolchain as `build_windows.ps1`:

| Tool | Used for | Notes |
|---|---|---|
| Windows PowerShell 5.1+ | running the scripts | works in `pwsh` 7 too |
| Node.js 20+ / npm | `npm run build` (frontend), electron-builder | `frontend\node_modules` and `electron\node_modules` |
| Python 3.11 (`backend\.venv-build`) | PyInstaller backend freeze | created on first `build_windows.ps1` run |
| Python 3 (any) | `scripts\release_lib.py` (zip + checksums) | stdlib only |

For a `-SkipBuild` re-package, only Windows PowerShell and a Python 3 interpreter
(for `release_lib.py`) are needed. **End users need none of these** — the
released bundle carries Electron and a frozen CPython backend.

`-SkipBuild` requires an already-built `build_exe\win-unpacked` produced by
`build_windows.ps1`.

## Supported platform

- **OS:** 64-bit Windows 10 / 11.
- **Architecture:** `x64` only (the Electron build target is `x64`).
- Unsigned binaries: Windows SmartScreen may warn on first run ("More info →
  Run anyway"). No registry writes, no machine-wide install, no admin required.

## What is bundled

- **Electron 28** runtime (Chromium + Node) — `SovereignAI.exe` and its DLLs/paks.
- **Frozen CPython backend** — `resources\backend\SovereignAIBackend.exe`
  (PyInstaller onedir, CPU `torch`), so no system Python is required.
- **Next.js static export** — `resources\frontend\`, served over the `app://`
  protocol.
- **Licenses / notices** — `LICENSES\`, `LICENSE.electron.txt`,
  `LICENSES.chromium.html`.
- **Empty `data\`** — the portable writable store.

## What remains external

- **Model weights** — none are bundled (size + licensing). Download/import after
  first launch into `data\workspace\models\`.
- **GPU / CUDA torch** — the shipped backend is CPU-only. `build_exe\extras\enable-gpu.ps1`
  restores GPU inference after a local build.
- **Network** for model downloads, cloud providers (with the user's own API key),
  and the first-time RAG embedding model download.
- **Code signing** — the binaries are unsigned.

## How to launch

Double-click `SovereignAI.bat`, or run `SovereignAI.exe` directly. The
**Electron shell** owns startup ordering: it starts the backend on
`127.0.0.1:8000`, waits for `/health`, then loads the UI, showing a diagnostic
dialog with the log path if the backend fails. It never spawns a second backend
and skips spawning if one is already answering. The `.bat` only resolves its own
directory and launches the exe, so it works from paths containing spaces and
from an external drive.

## Where portable data is stored

`electron\main.js` treats a sibling `data\` folder as the portable-mode marker.
When present it pins Electron `userData` to `data\electron\`, redirects
`TEMP`/`TMP`/`HF_HOME`/`XDG_*` under `data\`, and starts the backend with
`SOVEREIGN_DATA_ROOT=<root>\data`. The backend appends `workspace` to that root
(`backend\app\config.py`), giving:

| Path | Contents |
|---|---|
| `data\workspace\database\` | `sovereign_settings.db`, `sovereign.db` (created on first run) |
| `data\workspace\models\` | model weights |
| `data\workspace\plugins\` | plugins, custom model catalogs |
| `data\workspace\logs\` | backend + app logs |
| `data\workspace\sessions\` | chat session snapshots |
| `data\cache\` | temp work files, HuggingFace cache |
| `data\electron\` | Electron userData |
| `data\config\`, `data\share\` | redirected XDG roots |

`build_zip\portable\` pre-creates exactly the directories the app uses — no
placeholder folders. No database is ever shipped; it is created on the drive at
first run.

> The generic `workshop\` name used in some portable-app templates maps here to
> the app's real data store, `data\` (whose settings/models/plugins/logs live
> under `data\workspace\`). The folder is deliberately **not** renamed: `data\`
> is the marker the Electron shell and the portability gate
> (`scripts\check_portable.sh`) already expect.

## Migrating existing `workspace\` data

The repository's `workspace\` (and any existing portable `data\workspace\`) is
your live data — the build scripts never read, move, or delete it. To carry it
into a new portable install:

1. Extract the new ZIP somewhere fresh.
2. Close any running instance on both the old and new copy.
3. Copy the old store over the new one, **keeping the destination folder**:
   `workspace\...` → `<new>\data\workspace\...`
   (or `data\workspace\...` → `<new>\data\workspace\...`).
4. Do not copy a `data\workspace\database\*-wal`/`-shm` pair alone; copy the
   database files together, or let the app recreate them.
5. Launch and verify in Settings; delete the old folder once confirmed.

Copying is idempotent: re-running it only adds/updates files. Take a backup of
the old `data\`/`workspace\` folder first — the scripts never do this for you.

## Upgrading without losing user data

Extract the new ZIP to a **new** folder and move your `data\` folder into it (or
extract over the top while keeping `data\` — the archive only contains an empty
`data\` seed plus interior directories). Never delete `data\workspace\` to
"start clean"; that folder *is* the user's data.

## Verifying the checksum

```powershell
# Windows
certutil -hashfile build_zip\SovereignAI-Portable-Windows-x64-v0.0.1.zip SHA256
Get-Content build_zip\SHA256SUMS.txt          # compare with the line above
```

```bash
# macOS / Linux / Git Bash
sha256sum -c build_zip/SHA256SUMS.txt
```

`schema` of `SHA256SUMS.txt`: `<lowercase sha256>  <filename>`, LF, no BOM, so
`sha256sum -c` accepts it.

## Long paths (Windows MAX_PATH)

The frozen `transformers` runtime ships deep example paths — the longest inside
this build is 154 characters — so an extracted bundle has a hard 260-character
budget. With the top-level folder `SovereignAI-Portable-Windows-x64-v<version>`
(39 chars), the **extraction folder must be shorter than ~65 characters**.

`Script_portable.ps1` therefore prints the longest path and the exact budget,
and warns when that budget drops under 80 characters:

```
[WARN] long paths: keep the extraction folder under 65 chars (Windows MAX_PATH).
       Longest: resources\backend\_internal\transformers\models\deprecated\...
```

Fine: `E:\SovereignAI-Portable\`, `D:\Apps\SovereignAI\`, `C:\Users\me\Downloads\SovereignAI\`.
Too deep: `C:\Users\me\AppData\Local\Temp\<deep-temp>\SovereignAI\` — extracting
here fails partway with "Could not find a part of the path".

Fixes: extract into a shorter folder, or enable long-path support
(`HKLM\SYSTEM\CurrentControlSet\Control\FileSystem\LongPathsEnabled = 1`, plus
the `LongPathsEnabled` group policy). This is a pre-existing property of bundling
HuggingFace `transformers` — the same limit applies to the `releases/` artifact,
which is built from the same frozen backend.

## Reproducibility

The ZIP is **not bit-reproducible**: ZIP entries carry file modification times,
and directory entries carry the packaging time, so two runs over identical
content produce different bytes (and therefore different SHA-256 values) while
unpacking to identical trees. Quote the checksum next to the artifact you built,
not across builds.

## Known limitations & troubleshooting

| Symptom | Cause / fix |
|---|---|
| `python is required…` from `Script_zip.ps1` | Install any Python 3 on the build machine, or use `scripts\build-release.ps1` (same dependency). |
| `staging is not a complete portable application` | Run `.\Script_portable.ps1` first, or drop `-SkipBuild`. |
| `build_exe\win-unpacked` not found with `-SkipBuild` | Run `build_windows.ps1` once, or omit `-SkipBuild`. |
| App starts but no window / backend dialog | Port 8000 busy — close other instances. Logs: `data\workspace\logs\`. |
| Writes fail on a USB stick | Media is read-only or FAT32. Use exFAT/NTFS. |
| `-Clean` refused a path | `-Clean` only deletes inside `build_zip\`; it refuses `workspace\`, `releases\`, `build_exe\`, the repo root and drive roots. |
| Text files flagged with a "Windows drive path" warning | Reported only (not fatal); vendored/minified JS may contain one. Hardcoded repo paths are fatal. |
| `ExtractToDirectory` fails with "Could not find a part of the path" | Windows MAX_PATH. Extract into a folder shorter than the printed budget (~65 chars). See *Long paths* above. |

**Validation performed by the scripts:** bundle contract (entry point, backend,
frontend, data dirs, no shipped DB), secret scan (`.env`, keys, certificates,
shipped DBs), hardcoded repository-path scan, launcher hygiene (no absolute
paths, references the exe), archive opens, expected entries present, no nested
`portable\`, no git/`node_modules`/`.env`/source-map entries, and SHA-256
re-verified against the file on disk. A failing check exits nonzero and does not
write a success report.

> The scripts do **not** launch the GUI during a build. A full runtime smoke test
> (actually booting the extracted app) is a separate, manual step — see
> `scripts\check_portable.sh` for the automated backend smoke test used by the CI
> release pipeline.

## Cleaning generated build artifacts safely

```powershell
.\Script_portable.ps1 -Clean        # clears build_zip\portable + generated reports
.\Script_zip.ps1 -Clean             # same, then rebuilds and re-packages
```

Or delete them by hand — they are all generated and git-ignored:

```powershell
Remove-Item -Recurse -Force build_zip
```

Never delete `workspace\`, `releases\`, or `build_exe\` to clean this workflow:
`workspace\` is user data, `releases\` holds previous released artifacts (kept
intact by design), and `build_exe\` is the shared build output reused by
`-SkipBuild`.
