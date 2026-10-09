# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the packaged backend (SovereignAIBackend.exe).

Build (from backend/, with a CPU-only torch — see build_windows.ps1):
    python -m PyInstaller --noconfirm --clean SovereignAIBackend.spec

Env knobs:
    SOVEREIGN_STRIP_CUDA=1  drop CUDA runtime DLLs (safety net for a cuXXX venv;
                            NSIS cannot package installers over ~2 GB)
"""
import glob
import os
import sys

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
    get_package_paths,
)

BACKEND_DIR = SPECPATH
ROOT = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)

STRIP_CUDA = os.environ.get("SOVEREIGN_STRIP_CUDA") == "1"

# --------------------------------------------------------------------------- #
# Hidden imports
# --------------------------------------------------------------------------- #
# Transformers resolves AutoModel*/tokenizers through _LazyModule -> importlib,
# which static analysis cannot follow; without the full submodule list the
# frozen app dies on the first model load.
hiddenimports = []
for _pkg in ("app", "uvicorn", "limits", "transformers", "sentence_transformers"):
    try:
        hiddenimports += collect_submodules(_pkg)
    except Exception as exc:  # pragma: no cover - build-time diagnostic only
        print(f"[spec] WARNING: collect_submodules({_pkg}) failed: {exc}")

hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "multipart",
    "aiofiles",
    "aiosqlite",
    "psutil",
    "yaml",
    "pypdf",
    # GGUF fallbacks, imported inside try/except in fullram/executor.py
    "llama_cpp",
    "ik_llama_cpp",
    "faiss",
]

# --------------------------------------------------------------------------- #
# Binaries
# --------------------------------------------------------------------------- #
binaries = []
for _pkg in ("llama_cpp", "ik_llama_cpp", "faiss_cpu"):
    try:
        binaries += collect_dynamic_libs(_pkg)
    except Exception as exc:
        print(f"[spec] WARNING: collect_dynamic_libs({_pkg}) failed: {exc}")

# faiss-cpu ships its OpenMP/BLAS runtime in a sibling `faiss_cpu.libs` dir.
try:
    _faiss_base, _faiss_pkg = get_package_paths("faiss")
    _faiss_libs = os.path.join(_faiss_base, "faiss_cpu.libs")
    if os.path.isdir(_faiss_libs):
        binaries += [(p, "faiss_cpu.libs") for p in glob.glob(os.path.join(_faiss_libs, "*.dll"))]
except Exception as exc:
    print(f"[spec] WARNING: faiss_cpu.libs not collected: {exc}")

# --------------------------------------------------------------------------- #
# Data files / dist metadata (importlib.metadata lookups at runtime)
# --------------------------------------------------------------------------- #
datas = []
for _dist in (
    "transformers", "tokenizers", "sentence_transformers", "huggingface_hub",
    "safetensors", "faiss-cpu", "gguf", "numpy", "torch", "packaging",
    "filelock", "regex", "requests", "tqdm", "pyyaml", "bcrypt", "slowapi",
):
    try:
        datas += copy_metadata(_dist)
    except Exception:
        pass  # optional dependency not installed in this venv

try:
    datas += collect_data_files("sentence_transformers")
except Exception:
    pass

# --------------------------------------------------------------------------- #
# Excludes — packages this application never imports, several of them
# multi-hundred-MB (tensorflow is 1.4 GB in the dev venv).
# --------------------------------------------------------------------------- #
excludes = [
    "tensorflow", "tensorboard", "keras",
    "matplotlib", "IPython", "jupyter", "notebook", "nbformat",
    "pytest", "_pytest", "tkinter",
    "cv2", "torchvision", "torchaudio",
    "datasets", "pyarrow", "airllm",
    "sphinx", "docutils",
]

# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
a = Analysis(
    [os.path.join(BACKEND_DIR, "backend_entry.py")],
    pathex=[BACKEND_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

# Build-time-only artifacts: import libraries, headers, debug symbols. PyInstaller's
# torch hook picks these up via collect_data_files and they are never loaded.
_LINKTIME_EXT = (".lib", ".h", ".hpp", ".hxx", ".cuh", ".cmake", ".pdb", ".exp", ".c", ".cpp", ".pyi")
_CUDA_MARKERS = (
    "cudnn", "cublas", "cufft", "curand", "cusolver", "cusparse", "nccl",
    "nvrtc", "nvjitlink", "cupti", "torch_cuda", "nvtoolext", "cudart", "shm.dll",
)


def _runtime_artifact(dest: str) -> bool:
    low = dest.lower().replace("\\", "/")
    if low.endswith(_LINKTIME_EXT):
        return False
    if STRIP_CUDA:
        base = low.rsplit("/", 1)[-1]
        if any(marker in base for marker in _CUDA_MARKERS):
            return False
    return True


_dropped = [x for x in (a.binaries + a.datas) if not _runtime_artifact(x[0])]
a.binaries = [x for x in a.binaries if _runtime_artifact(x[0])]
a.datas = [x for x in a.datas if _runtime_artifact(x[0])]
print(f"[spec] dropped {len(_dropped)} build-time/CUDA artifact(s) from the bundle")

_icon = os.path.join(ROOT, "electron", "assets", "icon.ico")
if not os.path.isfile(_icon):
    _icon = None

# --------------------------------------------------------------------------- #
# EXE + COLLECT (onedir: onefile would unpack ~1 GB of torch to %TEMP per launch)
# --------------------------------------------------------------------------- #
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SovereignAIBackend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SovereignAIBackend",
)
