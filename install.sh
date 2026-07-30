#!/bin/bash
# SovereignAI Edge — one-line install
set -e

REPO="${REPO:-yashshinde0080/SovereignAI}"
BRANCH="${BRANCH:-main}"
DEST="${DEST:-$HOME/.sovereignai}"

echo "╔═══════════════════════════════════════╗"
echo "║       SovereignAI Edge Installer      ║"
echo "╚═══════════════════════════════════════╝"

if command -v git &>/dev/null; then
  echo "→ Cloning $REPO to $DEST"
  git clone --depth 1 --branch "$BRANCH" "https://github.com/$REPO.git" "$DEST"
  cd "$DEST"
elif command -v curl &>/dev/null; then
  echo "→ Downloading archive..."
  mkdir -p "$DEST"
  curl -fsSL "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" | tar -xz --strip=1 -C "$DEST"
  cd "$DEST"
else
  echo "Error: need git or curl" >&2
  exit 1
fi

echo "→ Starting SovereignAI..."
case "$(uname -s)" in
  Linux|Darwin) bash launch.sh ;;
  CYGWIN*|MINGW*|MSYS*) cmd /c launch.bat ;;
  *) echo "Unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac
