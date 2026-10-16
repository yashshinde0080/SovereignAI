import argparse
import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path


def get_server_config():
    """Read server config directly from the settings DB if it exists"""
    db_path = str(Path(__file__).parent.parent / "workspace" / "database" / "sovereign_settings.db")

    # Defaults
    host = "0.0.0.0"
    port = 8000

    if os.path.exists(db_path):
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT data FROM settings WHERE section = ?", ("security",))
            row = cursor.fetchone()
            if row:
                security = json.loads(row["data"])
                port = security.get("api_port", 8000)
                if security.get("bind_localhost_only", True):
                    host = "127.0.0.1"
                else:
                    host = "0.0.0.0"
        except Exception as e:
            print(f"Warning: Could not read settings DB for server config: {e}")
        finally:
            if conn:
                conn.close()

    return host, port


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="SovereignAI backend")
    parser.add_argument("--host", default=None, help="bind address (default: settings DB)")
    parser.add_argument("--port", type=int, default=None, help="listen port (default: settings DB)")
    return parser.parse_args(argv)


def _resolve_host_port(args):
    """CLI flag > SOVEREIGN_API_PORT > settings DB.

    The desktop shell passes an explicit port because it is the one that knows
    whether the port it picked is actually free; this entry point has to honor
    that or the frontend's injected port would point at nothing.
    """
    host, port = get_server_config()
    env_port = (os.environ.get("SOVEREIGN_API_PORT") or "").strip()
    if args.host:
        host = args.host
    if args.port:
        port = args.port
    elif env_port.isdigit():
        port = int(env_port)
    return host, port


async def _serve(app, host: str, port: int) -> None:
    """Serve with a graceful-stop hook.

    ``uvicorn.run()`` gives no way to ask for a shutdown, and on Windows
    terminating the process (taskkill) skips every ``finally``/lifespan teardown
    — which is what left SQLite locked and aiosqlite threads crashing on a
    closed loop. Owning the Server lets /v1/system/shutdown set ``should_exit``
    and take the exact Ctrl+C path instead.
    """
    import uvicorn

    from app.lib.server_lifecycle import shutdown_requested

    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_config=None))
    serving = asyncio.ensure_future(server.serve())
    while not serving.done():
        if shutdown_requested():
            server.should_exit = True
        await asyncio.sleep(0.2)
    await serving


def main(argv=None) -> int:
    args = _parse_args(argv)
    host, port = _resolve_host_port(args)

    from app.config import settings
    from app.lib.server_lifecycle import (
        clear_state, port_is_free, write_state,
    )

    if not port_is_free(host, port):
        # Never kill the holder — it may be another application, or a
        # SovereignAI the user is already running.
        print(
            f"[startup] {host}:{port} is already in use; not starting a second "
            f"backend. Set SOVEREIGN_API_PORT to a free port, or reuse the "
            f"process that is listening.",
            file=sys.stderr,
        )
        return 3

    write_state(
        settings.workspace_dir,
        pid=os.getpid(),
        host=host,
        port=port,
        app=settings.app_name,
        version=settings.app_version,
        data_root=str(settings.workspace_dir.parent),
    )

    # Hot-reload is a dev convenience; it doubles startup cost and can mask
    # state bugs in production. Dev-only via env flag.
    reload = os.environ.get("SOVEREIGN_RELOAD", "").lower() in ("1", "true", "yes")
    print(f"Launching SovereignAI Server on {host}:{port} (reload={reload})")
    try:
        if reload:
            import uvicorn
            uvicorn.run("app.main:app", host=host, port=port, reload=True)
        else:
            from app.main import app as fastapi_app
            asyncio.run(_serve(fastapi_app, host, port))
    finally:
        clear_state(settings.workspace_dir, os.getpid())
    return 0


if __name__ == "__main__":
    sys.exit(main())
