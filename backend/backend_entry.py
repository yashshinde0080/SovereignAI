"""Frozen-build entry point for the packaged backend.

`main.py` reads the repo's settings DB to pick host/port, which doesn't exist
next to an installed app. Here host/port come from the command line (the
Electron shell passes them) and every writable path hangs off
SOVEREIGN_DATA_ROOT so nothing is written into the install directory.
"""
import argparse
import asyncio
import os
import sys
import traceback
from pathlib import Path


def _data_root() -> Path:
    env = os.environ.get("SOVEREIGN_DATA_ROOT")
    if env:
        return Path(env).expanduser()
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "SovereignAI"


async def _serve(app, host: str, port: int) -> None:
    """Serve with a graceful-stop hook — see backend/main.py:_serve()."""
    import uvicorn

    from app.lib.server_lifecycle import shutdown_requested

    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_config=None))
    serving = asyncio.ensure_future(server.serve())
    while not serving.done():
        if shutdown_requested():
            server.should_exit = True
        await asyncio.sleep(0.2)
    await serving


def main() -> int:
    parser = argparse.ArgumentParser(prog="SovereignAIBackend")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--data-root", default=None)
    args = parser.parse_args()

    root = Path(args.data_root).expanduser() if args.data_root else _data_root()
    os.environ["SOVEREIGN_DATA_ROOT"] = str(root)
    log_dir = root / "workspace" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    from app.config import settings
    from app.lib.server_lifecycle import (
        DEFAULT_PORT, clear_state, port_is_free, write_state,
    )

    host = args.host or "127.0.0.1"
    env_port = (os.environ.get("SOVEREIGN_API_PORT") or "").strip()
    port = args.port or (int(env_port) if env_port.isdigit() else None) or DEFAULT_PORT

    print(f"SovereignAI backend on {host}:{port} (data={root})", flush=True)

    if not port_is_free(host, port):
        # Exit before the web server ever touches the DB: a second backend on a
        # busy port is what left two processes writing the same SQLite file
        # ("database is locked") and could not be seen in the task list.
        message = (
            f"{host}:{port} is already in use; this backend will not start. "
            f"Another SovereignAI (or an unrelated application) owns that port."
        )
        print(f"[startup] {message}", file=sys.stderr, flush=True)
        try:
            (log_dir / "backend-error.log").write_text(message + "\n", encoding="utf-8")
        except OSError:
            pass
        return 3

    write_state(
        settings.workspace_dir,
        pid=os.getpid(),
        host=host,
        port=port,
        app=settings.app_name,
        version=settings.app_version,
        data_root=str(root),
    )

    try:
        from app.main import app as fastapi_app

        asyncio.run(_serve(fastapi_app, host, port))
    except Exception:
        # A windowed/packaged app has no visible console — this file is the only
        # way a failed boot is diagnosable from the UI's error dialog.
        try:
            (log_dir / "backend-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        traceback.print_exc()
        return 1
    finally:
        # Only clears the file this process wrote (pid-scoped).
        clear_state(settings.workspace_dir, os.getpid())
    return 0


if __name__ == "__main__":
    sys.exit(main())
