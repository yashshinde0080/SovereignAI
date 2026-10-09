"""Frozen-build entry point for the packaged backend.

`main.py` reads the repo's settings DB to pick host/port, which doesn't exist
next to an installed app. Here host/port come from the command line (the
Electron shell passes them) and every writable path hangs off
SOVEREIGN_DATA_ROOT so nothing is written into the install directory.
"""
import argparse
import os
import sys
import traceback
from pathlib import Path


def _data_root() -> Path:
    env = os.environ.get("SOVEREIGN_DATA_ROOT")
    if env:
        return Path(env).expanduser()
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "SovereignAI"


def main() -> int:
    parser = argparse.ArgumentParser(prog="SovereignAIBackend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    root = _data_root()
    os.environ["SOVEREIGN_DATA_ROOT"] = str(root)
    log_dir = root / "workspace" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    try:
        import uvicorn
        from app.main import app as fastapi_app

        print(f"SovereignAI backend on {args.host}:{args.port} (data={root})", flush=True)
        uvicorn.run(fastapi_app, host=args.host, port=args.port, log_config=None)
    except Exception:
        # A windowed/packaged app has no visible console — this file is the only
        # way a failed boot is diagnosable from the UI's error dialog.
        try:
            (log_dir / "backend-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
