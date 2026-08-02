"""Runtime check: every storage/model path must resolve strictly inside <project>/workspace.

Run: backend/.venv/Scripts/python.exe verify_workspace.py   (from project root)
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT / "backend"))

WORKSPACE = (ROOT / "workspace").resolve()

checks = {}

# ── app.config settings ──
from app.config import settings

for name in ("workspace_dir", "models_dir", "plugins_dir",
             "database_path", "data_dir", "catalog_dir"):
    checks[f"config.{name}"] = Path(getattr(settings, name))

# ── env (HF caches) ──
checks["HF_HOME"] = Path(os.environ["HF_HOME"])
import huggingface_hub.constants as hfc
checks["HF_HUB_CACHE"] = Path(hfc.HF_HUB_CACHE)

# ── settings DB (SettingsService default, no arg) ──
from app.settings.database import SettingsDatabase
checks["settings_db (workspace/database)"] = Path(SettingsDatabase().db_path)

# ── server-entry settings DB read (backend/main.py) ──
checks["main.py settings DB read"] = ROOT / "workspace" / "database" / "sovereign_settings.db"

# ── database manager default (storage.toml absent) ──
from app.database.manager import DatabaseManager
checks["app db (DatabaseManager)"] = Path(DatabaseManager().db_path)

# ── unification: both managers must use the SAME file ──
import sqlite3 as _sq
checks["UNIFIED: DatabaseManager == ModelRegistry"] = Path(DatabaseManager().db_path)
_conn = _sq.connect(str(Path(DatabaseManager().db_path)))
_tables = {r[0] for r in _conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
if "models" in _tables and {"sessions", "audit_log", "schema_version"} <= _tables:
    print("OK   UNIFIED FILE has registry(models) + app(sessions,audit_log,schema_version)")
else:
    print(f"OUT  UNIFIED FILE missing tables: {sorted(_tables)}")
    ok = False
_conn.close()

# ── vector store defaults ──
from app.vectorstore.config import VectorStoreConfig
vsc = VectorStoreConfig()
checks["vector index dir"] = Path(vsc.index_path)
checks["vector metadata db"] = Path(vsc.metadata_db_path)

# ── services model manager ──
from app.services.model_manager import ModelManager
checks["model manager models_dir"] = Path(ModelManager().models_dir)

# ── plugin manager ──
from app.plugins.manager import PluginManager
checks["user plugins dir"] = Path(PluginManager().user_plugins_path)

# ── workspace snapshots API ──
checks["workspace sessions"] = WORKSPACE / "sessions"

# ── local provider default ──
from app.providers.local import LocalProvider
checks["local provider models"] = Path(LocalProvider().models_dir)

# ── layerstream offload cache ──
checks["offload_cache"] = WORKSPACE / "offload_cache"

ok = True
for name, p in checks.items():
    resolved = Path(p).expanduser()
    try:
        resolved = resolved.resolve()
    except OSError:
        pass
    inside = str(resolved).startswith(str(WORKSPACE))
    ok &= inside
    print(f"{'OK  ' if inside else 'OUT '} {name:34} {resolved}")

print()
print("ALL STORAGE INSIDE workspace/ - PASS" if ok else "VIOLATIONS FOUND - FAIL")
sys.exit(0 if ok else 1)
