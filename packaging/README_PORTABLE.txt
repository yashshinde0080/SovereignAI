SovereignAI Edge - Portable (Windows x64)
=========================================

Runs 100% offline from this folder. No installer, no admin rights, and no
separate Python or Node.js install -- everything needed is inside this package.

HOW TO RUN
----------
1. Extract this whole archive to a folder, USB drive, or external SSD/HDD.
   Keep the folder contents together.
2. Double-click  SovereignAI.bat   (or run  SovereignAI.exe  directly).
3. The app starts its local backend on 127.0.0.1:8000 and opens the UI.
   The first launch is slow while the engine warms up -- that is normal.

If Windows shows "Windows protected your PC", click  More info -> Run anyway.
The .exe is unsigned; this is expected.

Reclaiming space later: just delete the folder. Nothing was installed.

WHERE YOUR DATA LIVES
---------------------
Everything writable stays on this drive, inside the  data\  folder next to the
executable. Nothing is written to %APPDATA% or your user profile.

  data\workspace\database\   settings + app database (created on first run)
  data\workspace\models\     model files you download or import
  data\workspace\plugins\    plugins and custom model catalogs
  data\workspace\logs\       logs (check here if the app will not start)
  data\workspace\sessions\   chat sessions
  data\cache\                temporary work files + HuggingFace cache
  data\electron\             window state / Electron cache

Move the folder (or the whole drive) to another PC and your data comes with it.
Do NOT rename or delete the  data\  folder -- it is what makes the app portable.

NO MODELS ARE INCLUDED
----------------------
Model weights are not bundled (they are large and license-specific). After the
first launch, download or import models through the app, or copy .gguf /
.safetensors files into  data\workspace\models\ .

WHAT IS INCLUDED
----------------
  SovereignAI.exe                            the desktop app (Electron 28)
  resources\backend\SovereignAIBackend.exe   the local engine (frozen Python)
  resources\frontend\                         the user interface
  data\                                       portable writable storage (empty)
  LICENSES\, LICENSE.electron.txt, LICENSES.chromium.html

WHAT NEEDS A NETWORK
--------------------
  Offline (no connection needed): the UI, settings, local inference.
  Online (needs a connection):    downloading models, cloud AI providers
                                  (with your own API key), first-time RAG
                                  model download.

GPU / CUDA: this build runs models on the CPU. GPU acceleration is optional and
not included.

VERIFYING YOUR DOWNLOAD
-----------------------
  Windows:    certutil -hashfile SovereignAI-Portable-Windows-x64-v*.zip SHA256
  macOS/Linux or Git Bash:  sha256sum -c SHA256SUMS.txt

Compare the result with SHA256SUMS.txt in the release folder.

TROUBLESHOOTING
---------------
Started but nothing happened?
  - Port 8000 may be in use. Close other SovereignAI instances and retry.
  - Check  data\workspace\logs\  for details.
"The drive is read-only" / writes fail?
  - Use media that is not write-protected. exFAT is the best choice for a drive
    that must work on both Windows and macOS. Avoid FAT32 (4 GB per-file limit).
Very slow model loading?
  - First load reads model weights from disk. A USB 2.0 stick will be slow;
    an SSD/NVMe is strongly recommended.

Ports: the local server binds 127.0.0.1 only. No telemetry, no outbound
sockets unless you use an online feature.
