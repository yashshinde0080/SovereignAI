#!/usr/bin/env python3
"""Shared release helpers for SovereignAI Edge portable builds.

Used by scripts/build-release.ps1 (Windows) and scripts/build-release.sh
(macOS/Linux) so the archiving, checksums and manifest logic lives in one
place instead of two divergent shell implementations.

    python scripts/release_lib.py zip      <stage_dir> <out.zip>
    python scripts/release_lib.py tar      <stage_dir> <out.tar.gz>
    python scripts/release_lib.py finalize <releases_root> "<app name>" <version>
    python scripts/release_lib.py selfcheck

`finalize` is idempotent: it scans releases/**/build.json (one sidecar per
built artifact), hashes every artifact that actually exists, and rewrites
releases/MANIFEST.json + SHA256SUMS.txt. Re-run it after building any platform.
No network, no publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import zipfile
from datetime import datetime, timezone

TARGETS = [("windows", "x64"), ("macos", "arm64"), ("macos", "x64"),
           ("linux", "x64"), ("linux", "arm64")]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_commit(releases_root: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", releases_root, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _sorted_walk(stage: str):
    for root, dirs, files in os.walk(stage):
        dirs.sort()
        for f in sorted(files):
            yield root, f


def zip_dir(stage: str, out: str, top: str | None = None) -> str:
    """Deflate the whole stage dir into out.zip with a single top-level folder.

    `top` overrides the folder name inside the archive (defaults to the stage
    dir's own name). Used by Script_zip.ps1 so a stage named `portable` does not
    ship as a `portable/` folder in the release.
    """
    stage = os.path.abspath(stage)
    top = top or os.path.basename(stage.rstrip("/\\"))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # Directory entries are written explicitly: os.walk yields files only,
        # so empty dirs (data/plugins, data/cache) would otherwise vanish.
        for root, dirs, files in os.walk(stage):
            dirs.sort()
            rel = os.path.relpath(root, stage).replace("\\", "/")
            prefix = top if rel == "." else top + "/" + rel
            if rel != ".":
                zf.writestr(prefix + "/", "")
            for f in sorted(files):
                zf.write(os.path.join(root, f), prefix + "/" + f)
    return out


def tar_dir(stage: str, out: str) -> str:
    """tar.gz the stage dir, preserving unix permissions/symlinks absent."""
    stage = os.path.abspath(stage)
    top = os.path.basename(stage.rstrip("/\\"))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with tarfile.open(out, "w:gz") as tf:
        tf.add(stage, arcname=top)
    return out


def finalize(releases_root: str, app_name: str, version: str) -> dict:
    releases_root = os.path.abspath(releases_root)
    artifacts = []
    for root, _dirs, files in os.walk(releases_root):
        parts = os.path.normpath(root).split(os.sep)
        if ".stage" in parts or "checksums" in parts:
            continue
        if "build.json" not in files:
            continue
        # utf-8-sig: PowerShell's Set-Content -Encoding UTF8 writes a BOM.
        with open(os.path.join(root, "build.json"), encoding="utf-8-sig") as fh:
            meta = json.load(fh)
        art = meta.get("artifact")
        if not art:
            continue
        art_path = os.path.join(root, art)
        if os.path.isfile(art_path):
            size = os.path.getsize(art_path)
            meta.update(status="built", sha256=_sha256(art_path),
                        size_bytes=size, size_mb=round(size / 1048576, 1))
        else:
            meta["status"] = "missing"
        meta["path"] = os.path.relpath(art_path, releases_root).replace(os.sep, "/")
        artifacts.append(meta)

    artifacts.sort(key=lambda m: (m.get("os", ""), m.get("arch", "")))
    built = {(m.get("os"), m.get("arch")) for m in artifacts if m.get("status") == "built"}
    platforms = []
    for os_, arch in TARGETS:
        row = {"os": os_, "arch": arch,
               "status": "built" if (os_, arch) in built else "not-built"}
        for m in artifacts:
            if (m.get("os"), m.get("arch")) == (os_, arch):
                row["artifact"] = m.get("artifact")
        platforms.append(row)

    manifest = {
        "app": app_name,
        "version": version,
        "generated": _utc_now(),
        "git_commit": _git_commit(releases_root),
        "platforms": platforms,
        "artifacts": artifacts,
    }
    with open(os.path.join(releases_root, "MANIFEST.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")

    lines = [f"{m['sha256']}  {m['path']}" for m in artifacts if m.get("sha256")]
    sums = "\n".join(lines) + ("\n" if lines else "")
    with open(os.path.join(releases_root, "SHA256SUMS.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(sums)
    checks_dir = os.path.join(releases_root, "checksums")
    os.makedirs(checks_dir, exist_ok=True)
    with open(os.path.join(checks_dir, "SHA256SUMS.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(sums)
    return manifest


def selfcheck() -> int:
    import shutil
    import tempfile

    d = tempfile.mkdtemp(prefix="sov-release-check-")
    try:
        stage = os.path.join(d, "SovereignAI-Test-Bundle")
        os.makedirs(os.path.join(stage, "resources", "frontend"))
        with open(os.path.join(stage, "SovereignAI.exe"), "w") as fh:
            fh.write("MZ not-really")
        with open(os.path.join(stage, "resources", "frontend", "index.html"), "w") as fh:
            fh.write("<html></html>")

        z = zip_dir(stage, os.path.join(d, "out", "a.zip"))
        with zipfile.ZipFile(z) as zf:
            names = zf.namelist()
            assert "SovereignAI-Test-Bundle/SovereignAI.exe" in names, names
            assert any(n.endswith("resources/frontend/index.html") for n in names), names

        # --top overrides the folder name; empty dirs must still be entries.
        os.makedirs(os.path.join(stage, "data", "cache"))
        z2 = zip_dir(stage, os.path.join(d, "out", "b.zip"), "Custom-Top")
        with zipfile.ZipFile(z2) as zf:
            names2 = zf.namelist()
            assert "Custom-Top/SovereignAI.exe" in names2, names2
            assert "Custom-Top/data/cache/" in names2, names2
            assert not any(n.startswith("SovereignAI-Test-Bundle") for n in names2), names2

        tg = tar_dir(stage, os.path.join(d, "out", "a.tar.gz"))
        with tarfile.open(tg) as tf:
            assert "SovereignAI-Test-Bundle/SovereignAI.exe" in tf.getnames()

        rel = os.path.join(d, "releases")
        art_dir = os.path.join(rel, "windows", "x64")
        os.makedirs(art_dir)
        shutil.copy(z, os.path.join(art_dir, "SovereignAI-Windows-x64-Portable.zip"))
        with open(os.path.join(art_dir, "build.json"), "w") as fh:
            json.dump({"app": "test", "version": "9.9.9", "os": "windows",
                       "arch": "x64", "artifact": "SovereignAI-Windows-x64-Portable.zip",
                       "format": "zip", "status": "built"}, fh)

        manifest = finalize(rel, "SovereignAI Edge", "9.9.9")
        assert manifest["artifacts"], "no artifacts in manifest"
        entry = manifest["artifacts"][0]
        assert entry["sha256"] == _sha256(os.path.join(art_dir, entry["artifact"]))
        row = [p for p in manifest["platforms"] if p["os"] == "windows" and p["arch"] == "x64"][0]
        assert row["status"] == "built", row
        assert os.path.isfile(os.path.join(rel, "SHA256SUMS.txt"))
        assert os.path.isfile(os.path.join(rel, "checksums", "SHA256SUMS.txt"))
        assert "SovereignAI-Windows-x64-Portable.zip" in open(
            os.path.join(rel, "SHA256SUMS.txt"), encoding="utf-8").read()
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print("release_lib selfcheck: PASS")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("zip"); p.add_argument("stage"); p.add_argument("out")
    p.add_argument("--top", default=None, help="top-level folder name inside the archive")
    p = sub.add_parser("tar"); p.add_argument("stage"); p.add_argument("out")
    p = sub.add_parser("finalize")
    p.add_argument("releases_root"); p.add_argument("app_name"); p.add_argument("version")
    sub.add_parser("selfcheck")
    a = ap.parse_args(argv)

    if a.cmd == "zip":
        print("wrote", zip_dir(a.stage, a.out, a.top), os.path.getsize(a.out), "bytes")
    elif a.cmd == "tar":
        print("wrote", tar_dir(a.stage, a.out), os.path.getsize(a.out), "bytes")
    elif a.cmd == "finalize":
        m = finalize(a.releases_root, a.app_name, a.version)
        built = [p for p in m["platforms"] if p["status"] == "built"]
        print(f"manifest: {len(m['artifacts'])} artifact(s), {len(built)} platform(s) built")
    elif a.cmd == "selfcheck":
        return selfcheck()
    return 0


if __name__ == "__main__":
    sys.exit(main())
