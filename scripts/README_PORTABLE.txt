# SovereignAI Edge — Portable

Runs 100% offline from this folder. No installer, no admin, no network.

## Run
- Windows: double-click `SovereignAI-Edge.exe` (zip form).
- macOS/Linux: `bash launch.sh` from a terminal.

Put the app on an **exFAT** drive for cross-OS (Windows + macOS + Linux).
NTFS is writable on Windows only; FAT32 is discouraged (4 GB per-file cap).
An SSD/NVMe is recommended; on a spinning HDD LayerStream is slow.

## Where your data lives
Everything writable stays on **this drive** under `data/`:
- `data/models` — model weights you download (none are bundled)
- `data/workspace` — settings DB, chat sessions, RAG index (created on first run)
- `data/cache` — temp/HF cache (temp redirected here, not to the host)

`sovereign.db` is **not** shipped — it is created on first run so the drive is
self-contained and portable between machines.

## No models bundled
SovereignAI Edge ships **no GGUF/weights**. Download or import models after
first launch. This keeps the drive small and license-clean.

## Verifying your download
```
sha256sum -c SHA256SUMS.txt        # macOS/Linux
certutil -hashfile <file> SHA256   # Windows
```

## Windows SmartScreen
The `.exe` is unsigned. Windows may show "Windows protected your PC" — click
**More info → Run anyway**. This is expected for an unsigned binary.

## The one unavoidable temp write (standalone .exe only)
The single-file **NSIS portable `.exe`** self-extracts to `%TEMP%` on launch
(that is how the portable-target format works); it sets
`PORTABLE_EXECUTABLE_DIR` so state still lands here, and cleans the extracted
temp on exit. If you require zero host writes, use the **`.zip` form** instead —
it runs directly from this folder with no extraction.

## Portability notes
- Server binds `127.0.0.1` only; no outbound sockets; no telemetry.
- SQLite uses a rollback journal + `synchronous=FULL` (safe if the drive is
  yanked mid-write).
