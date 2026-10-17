#!/usr/bin/env bash
# Build the portable SovereignAI Edge release for the HOST platform (macOS/Linux).
# Local only: never pushes commits/branches/tags and never publishes.
#
#   scripts/build-release.sh [--reuse] [--force] [--version V]
#                            [--platform macos|linux] [--arch arm64|x64]
#
#   --reuse   assemble from an existing electron-builder --dir output under
#             build_exe/ instead of rebuilding (frontend/backend/electron).
#
# Windows is built with scripts/build-release.ps1 (this script refuses win32).
# Produces releases/<os>/<arch>/SovereignAI-<OS>-<arch>-Portable.tar.gz + metadata.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
RELEASES="$ROOT/releases"
LIB="$ROOT/scripts/release_lib.py"
APP_NAME="SovereignAI Edge"

REUSE=0; FORCE=0; VERSION_ARG=""; PLATFORM=""; ARCH=""
while [ $# -gt 0 ]; do
  case "$1" in
    --reuse) REUSE=1;;
    --force) FORCE=1;;
    --version) VERSION_ARG="${2:-}"; shift;;
    --platform) PLATFORM="${2:-}"; shift;;
    --arch) ARCH="${2:-}"; shift;;
    -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
  shift
done

case "$(uname -s)" in
  Darwin) HOST_OS=macos;;
  Linux)  HOST_OS=linux;;
  MINGW*|MSYS*|CYGWIN*|Windows_NT) echo "error: use scripts/build-release.ps1 on Windows" >&2; exit 1;;
  *) echo "unsupported host: $(uname -s)" >&2; exit 1;;
esac
[ -n "$PLATFORM" ] || PLATFORM="$HOST_OS"
[ -n "$ARCH" ] || ARCH="$(uname -m)"
case "$ARCH" in aarch64|arm64) ARCH=arm64;; x86_64|amd64|x64) ARCH=x64;; esac
[ "$PLATFORM" = "$HOST_OS" ] || { echo "error: build $PLATFORM artifacts on a $PLATFORM host (native runners only)" >&2; exit 1; }

VERSION="$VERSION_ARG"
[ -n "$VERSION" ] || VERSION="$(cat VERSION 2>/dev/null | tr -d '[:space:]')"
[ -n "$VERSION" ] || VERSION="0.0.0-dev"
echo "== SovereignAI Edge $VERSION ($PLATFORM-$ARCH) =="

# ---- 1. build (or reuse) -------------------------------------------------
if [ "$REUSE" = 0 ]; then
  command -v npm >/dev/null || { echo "error: npm required" >&2; exit 1; }
  echo "-- frontend build"; ( cd frontend && { [ -d node_modules ] || npm ci; } && npm run build )
  [ -f backend/SovereignAIBackend.spec ] && {
    echo "-- backend (PyInstaller)"; ( cd backend && python -m PyInstaller --noconfirm --clean SovereignAIBackend.spec )
  }
  echo "-- electron package ($PLATFORM --dir)"
  ( cd electron && npx electron-builder --"$PLATFORM" --"$ARCH" --dir )
else
  echo "-- reusing existing build_exe/ output (--reuse)"
fi

# Locate the electron-builder --dir output for this host.
UNPACK=""
if [ "$PLATFORM" = macos ]; then
  for c in "build_exe/mac-$ARCH" "build_exe/mac" "build_exe/mac-universal"; do
    [ -d "$c/SovereignAI.app" ] && UNPACK="$c" && break
  done
else
  for c in "build_exe/linux-$ARCH-unpacked" "build_exe/linux-unpacked" "build_exe/linux-arm64-unpacked"; do
    [ -d "$c" ] && UNPACK="$c" && break
  done
fi
[ -n "$UNPACK" ] || { echo "error: electron-builder --dir output not found under build_exe/" >&2; exit 1; }
echo "-- unpacked: $UNPACK"

if [ "$PLATFORM" = macos ]; then OS_LABEL="macOS"; ART="SovereignAI-macOS-$ARCH-Portable.tar.gz"; BUNDLE="SovereignAI-macOS-$ARCH-Portable"
else OS_LABEL="Linux"; ART="SovereignAI-Linux-$ARCH-Portable.tar.gz"; BUNDLE="SovereignAI-Linux-$ARCH-Portable"; fi
OUTDIR="$RELEASES/$PLATFORM/$ARCH"
TAR_OUT="$OUTDIR/$ART"
STAGE_ROOT="$RELEASES/.stage"; STAGE="$STAGE_ROOT/$BUNDLE"

[ -f "$TAR_OUT" ] && [ "$FORCE" = 0 ] && { echo "error: $TAR_OUT exists (use --force)" >&2; exit 1; }

# ---- 2. stage ------------------------------------------------------------
echo "-- staging $BUNDLE"
rm -rf "$STAGE_ROOT"; mkdir -p "$STAGE" "$OUTDIR" "$STAGE/data/models" "$STAGE/data/plugins" "$STAGE/data/cache"
cp -R "$UNPACK"/. "$STAGE"/
printf 'Download or import models into this folder. No models are bundled.\n' > "$STAGE/data/models/README.txt"
[ -d LICENSES ] && cp -R LICENSES "$STAGE/LICENSES" || mkdir -p "$STAGE/LICENSES"
cp scripts/README_PORTABLE.txt "$STAGE/README_PORTABLE.txt"
# strip JS source maps (dev artifacts)
find "$STAGE" -name '*.map' -type f -delete 2>/dev/null || true

if [ "$PLATFORM" = macos ]; then
  cat > "$STAGE/Launch-SovereignAI.command" <<'EOF'
#!/bin/bash
# Launch SovereignAI Edge from this folder (portable; no install). Double-click friendly.
HERE="$(cd "$(dirname "$0")" && pwd)"
export PORTABLE_EXECUTABLE_DIR="$HERE"   # pin portable data root to this folder
export SOVEREIGN_PORTABLE=1
exec "$HERE/SovereignAI.app/Contents/MacOS/SovereignAI" "$@"
EOF
  cp "$STAGE/Launch-SovereignAI.command" "$STAGE/Launch-SovereignAI.sh"
  chmod +x "$STAGE/Launch-SovereignAI.command" "$STAGE/Launch-SovereignAI.sh"
else
  cat > "$STAGE/Launch-SovereignAI.sh" <<'EOF'
#!/bin/bash
# Launch SovereignAI Edge from this folder (portable; no install).
HERE="$(cd "$(dirname "$0")" && pwd)"
export PORTABLE_EXECUTABLE_DIR="$HERE"
export SOVEREIGN_PORTABLE=1
exec "$HERE/SovereignAI" "$@"
EOF
  chmod +x "$STAGE/Launch-SovereignAI.sh" "$STAGE/SovereignAI" 2>/dev/null || true
fi

# ---- 3. portability gate -------------------------------------------------
echo "-- check_portable.sh"
bash scripts/check_portable.sh "$STAGE" "$ROOT"

# ---- 4. archive ----------------------------------------------------------
echo "-- tar -> $TAR_OUT"
python "$LIB" tar "$STAGE" "$TAR_OUT"
SIZE_MB=$(python -c "import os;print(round(os.path.getsize('$TAR_OUT')/1048576,1))")
SHA=$(python -c "import hashlib;h=hashlib.sha256();f=open('$TAR_OUT','rb');[h.update(b) for b in iter(lambda:f.read(1<<20),b'')];print(h.hexdigest())")

# ---- 5. metadata ---------------------------------------------------------
cat > "$OUTDIR/BUILD-INFO.txt" <<EOF
SovereignAI Edge - $OS_LABEL $ARCH Portable
============================================
app        : $APP_NAME
version    : $VERSION
platform   : $PLATFORM $ARCH
artifact   : $ART
format     : tar.gz
built (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)
built on   : $(uname -srm)
archive MB : $SIZE_MB
sha256     : $SHA

Included runtimes / assets
  - Electron 28 runtime (Chromium + Node).
  - CPython runtime frozen with PyInstaller -> resources/backend/SovereignAIBackend.exe.
  - Next.js static export -> resources/frontend/.

External prerequisites
  - None to launch (no separate Python/Node, no admin).
  - GPU (CUDA) inference not bundled (CPU torch).
  - No models bundled; download/import into data/models after first run (needs network).

Offline support
  - Full UI + local inference: offline. Cloud providers + model downloads: network + your keys.

Portable mode
  - PORTABLE_EXECUTABLE_DIR is pinned to this folder by the launcher; all writable
    state (userData, TEMP/TMP, HF_HOME, XDG_*, SOVEREIGN_DATA_ROOT) stays under data/.

Notes
  - macOS: unsigned/non-notarized .app. First run needs right-click > Open, or
    'xattr -dr com.apple.quarantine "SovereignAI.app"'. Gatekeeper will warn.
  - Linux: see check_portable.sh output for glibc/system-library expectations.

Verify: sha256sum -c SHA256SUMS.txt (from releases/)
EOF

cat > "$OUTDIR/build.json" <<EOF
{
  "app": "$APP_NAME",
  "version": "$VERSION",
  "os": "$PLATFORM",
  "arch": "$ARCH",
  "artifact": "$ART",
  "format": "tar.gz",
  "built_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "built_on": "$(uname -srm)",
  "git": "$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)",
  "portable": true,
  "offline": true,
  "runtimes": ["Electron 28", "CPython (PyInstaller)", "Next.js static export"],
  "external_prereqs": [],
  "bundled_models": false,
  "status": "built"
}
EOF

# ---- 6. finalize ---------------------------------------------------------
echo "-- finalize MANIFEST.json + SHA256SUMS.txt"
python "$LIB" finalize "$RELEASES" "$APP_NAME" "$VERSION"
rm -rf "$STAGE_ROOT"

echo "== done: $TAR_OUT ($SIZE_MB MB) sha256=$SHA =="
