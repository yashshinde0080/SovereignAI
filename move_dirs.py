import os
import shutil
from pathlib import Path

ROOT_DIR = Path(r"d:\SovereignAI")
BACKEND_DIR = ROOT_DIR / "backend"
WORKSPACE_DIR = ROOT_DIR / "workspace"

os.makedirs(WORKSPACE_DIR, exist_ok=True)

dirs_to_move = ["models", "offload_cache", "database", "data"]

for d in dirs_to_move:
    src = BACKEND_DIR / d
    dst = WORKSPACE_DIR / d
    if src.exists():
        if dst.exists():
            # Merge or overwrite? Let's assume merge/move
            for root, _, files in os.walk(src):
                rel_path = os.path.relpath(root, src)
                dst_root = dst / rel_path
                os.makedirs(dst_root, exist_ok=True)
                for file in files:
                    src_file = os.path.join(root, file)
                    dst_file = os.path.join(dst_root, file)
                    if not os.path.exists(dst_file):
                        shutil.move(src_file, dst_file)
            print(f"Moved contents of {d} to workspace/{d} and removing empty src")
            shutil.rmtree(src, ignore_errors=True)
        else:
            shutil.move(str(src), str(dst))
            print(f"Moved {d} to workspace/{d}")
    else:
        print(f"Source {d} does not exist: {src}")
