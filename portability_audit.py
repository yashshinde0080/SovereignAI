"""Portability audit — find writes that escape the project folder (USB pendrive).

Scans backend/, electron/, and launch scripts for:
  - home-dir paths      (Path.home(), ~, USERPROFILE, APPDATA, ...)
  - absolute paths      (C:\, /home/, /Users/, /tmp/, ...)
  - CWD-dependent writes (./models, os.getcwd, ...)

Run: backend/.venv/Scripts/python.exe portability_audit.py
"""
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
SKIP_DIRS = {"node_modules", "__pycache__", ".venv", ".git", ".next",
             "out", "dist", "build", ".claude", ".agents", ".gstack",
             "graphify-out"}
SCAN_DIRS = ["backend", "electron"]
SCAN_FILES = ["launch.bat", "launch.sh", "proxy.py", "install.sh",
              "setup_package.sh"]
EXTS = (".py", ".js", ".ts", ".tsx", ".sh", ".bat", ".mjs", ".cjs")

PATTERNS = [
    ("home-dir", re.compile(
        r"Path\.home\(\)|expanduser|USERPROFILE|HOMEDRIVE|HOMEPATH|"
        r"LOCALAPPDATA|APPDATA|os\.environ\[[\"']HOME|getenv\([\"']HOME")),
    ("abs-win", re.compile(r"[A-Za-z]:[\\/]")),
    ("abs-unix", re.compile(r"/(home|Users|tmp|var|opt|etc|usr)([\\/\s\"'])")),
    ("cwd-write", re.compile(r"\./(models|database|workspace|plugins)|"
                             r"os\.getcwd|Path\.cwd\(|getcwd\(")),
    ("electron-userData", re.compile(r"userData|app\.getPath|homedir\(")),
]


def scan_file(path):
    hits = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, 1):
            for name, rx in PATTERNS:
                if rx.search(line):
                    hits.append((name, i, line.strip()[:110]))
    return hits


all_hits = []
for d in SCAN_DIRS:
    base = os.path.join(ROOT, d)
    if not os.path.isdir(base):
        continue
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(EXTS):
                continue
            p = os.path.join(dirpath, fn)
            try:
                all_hits += [(os.path.relpath(p, ROOT), *h)
                             for h in scan_file(p)]
            except OSError:
                pass

for f in SCAN_FILES:
    p = os.path.join(ROOT, f)
    if os.path.isfile(p):
        all_hits += [(f, *h) for h in scan_file(p)]

print(f"=== Portability audit: {len(all_hits)} hits ===")
for rel, name, lineno, line in sorted(all_hits):
    print(f"{rel}:{lineno} [{name}] {line}")
