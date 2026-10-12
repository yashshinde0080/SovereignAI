#!/usr/bin/env bash
# Portability gate. Exit 1 on any violation. Usage:
#   check_portable.sh <bundle_dir> [source_root]
# <bundle_dir> is the assembled SovereignAI-Edge/ tree (not a zip).
# Runs on Windows (Git Bash) and unix. Cross-OS bundles are still gated
# statically; the runtime smoke test only fires where the host can run it.
set -u
BUNDLE="${1:?usage: check_portable.sh <bundle_dir> [source_root]}"
SRC="${2:-$(cd "$(dirname "$0")/.." && pwd)}"
FAIL=0
fail(){ printf 'FAIL: %s\n' "$*"; FAIL=1; }
ok(){   printf 'ok:   %s\n' "$*"; }
note(){ printf 'note: %s\n' "$*"; }

# ---- 1. no absolute host paths in code + launchers ----------------
SCAN_DIRS=(
  "$SRC/backend/app" "$SRC/backend/main.py" "$SRC/backend/backend_entry.py"
  "$SRC/electron/main.js" "$SRC/electron/preload.js" "$SRC/electron/menu.js" "$SRC/electron/tray.js"
  "$SRC/frontend/app" "$SRC/frontend/lib" "$SRC/frontend/components" "$SRC/frontend/next.config.ts"
  "$SRC/launch.sh" "$SRC/launch.bat" "$SRC/install.sh" "$SRC/setup_package.sh"
  "$SRC/scripts/build-release.sh" "$SRC/scripts/build-release.ps1" "$SRC/scripts/release_lib.py"
)
# A real drive path has the drive + at least one subdir (two backslashes);
# this avoids matching escaped newlines ('s:\n') and URLs ('app://') in strings.
hits=$(grep -rInE '([A-Za-z]:\\[^ ]*\\|/home/[A-Za-z]|/Users/[A-Za-z])' \
        --include='*.py' --include='*.js' --include='*.ts' --include='*.tsx' \
        --include='*.sh' --include='*.bat' "${SCAN_DIRS[@]}" 2>/dev/null \
      | grep -vE 'url|http|127\.0\.0\.1|win32|__file__|SOVEREIGN_' || true)
[ -z "$hits" ] && ok "no absolute host paths in source/launchers" \
               || { fail "absolute host paths found:"; printf '%s\n' "$hits" | head -n 20; }

# ---- 2. temp/cache/config redirected to the drive -----------------
m="$SRC/electron/main.js"
for token in PORTABLE_EXECUTABLE_DIR SOVEREIGN_DATA_ROOT 'TEMP:' 'TMP:' HF_HOME XDG_CACHE_HOME PYTHONDONTWRITEBYTECODE; do
  grep -q "$token" "$m" 2>/dev/null || fail "main.js missing redirect token: $token"
done
grep -q 'SOVEREIGN_DATA_ROOT' "$SRC/backend/app/config.py" 2>/dev/null \
  || fail "backend config.py does not honor SOVEREIGN_DATA_ROOT"
[ "$FAIL" = 0 ] && ok "temp/cache/userData redirect wired (main.js + config.py)"

# ---- 3. no symlinks (exFAT/FAT32) ---------------------------------
ln=$(find "$BUNDLE" -type l 2>/dev/null || true)
[ -z "$ln" ] && ok "no symlinks" || { fail "symlinks present:"; printf '%s\n' "$ln" | head; }

# ---- 4. filename safety: bad chars, >255 chars, case collisions ---
bad=$(find "$BUNDLE" -name '*[:<>"|?*]*' 2>/dev/null || true)
[ -z "$bad" ] && ok "no illegal filename characters" || { fail "illegal filename chars:"; printf '%s\n' "$bad" | head; }
long=$(find "$BUNDLE" -printf '%f\n' 2>/dev/null | awk 'length>255' || true)
[ -z "$long" ] && ok "no filename component >255 chars" || { fail "names >255 chars:"; printf '%s\n' "$long" | head; }
dupe=$(find "$BUNDLE" -printf '%P\n' 2>/dev/null | sort -f | uniq -di | grep -v '^$' || true)
[ -z "$dupe" ] && ok "no case-only filename collisions" || { fail "case collisions:"; printf '%s\n' "$dupe" | head; }

# ---- 5. no single file >4 GB (FAT32) ------------------------------
big=$(find "$BUNDLE" -type f -size +4G 2>/dev/null || true)
[ -z "$big" ] && ok "no file >4 GB" || { fail "files >4 GB (split or avoid FAT32):"; printf '%s\n' "$big"; }

# ---- 6. localhost bind, no telemetry ------------------------------
grep -q "'127.0.0.1'" "$m" && ok "backend spawned on 127.0.0.1" \
  || fail "electron shell does not pin 127.0.0.1"
grep -rqiE 'bind_localhost_only' "$SRC/backend/app" && ok "backend has localhost-only bind setting" \
  || fail "backend missing bind_localhost_only default"
tele=$(grep -rIliE --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=.venv \
        --exclude-dir=__pycache__ --exclude-dir=out --exclude-dir=.next --exclude-dir=build_exe \
        'google-analytics|googletagmanager|sentry\.io|posthog|segment\.io|mixpanel|amplitude' \
        "$SRC/backend/app" "$SRC/electron" "$SRC/frontend/app" "$SRC/frontend/lib" 2>/dev/null || true)
[ -z "$tele" ] && ok "no telemetry SDK references" || { fail "telemetry references:"; printf '%s\n' "$tele"; }

# ---- 7. SQLite portable settings ---------------------------------
grep -q 'journal_mode = "DELETE"' "$SRC/backend/app/database/manager.py" 2>/dev/null \
  && ok "journal_mode DELETE (no WAL)" || fail "manager.py journal_mode is not DELETE"
grep -q 'synchronous = FULL' "$SRC/backend/app/database/connection.py" 2>/dev/null \
  && ok "synchronous FULL" || fail "connection.py synchronous is not FULL"
grep -q 'journal_mode=DELETE' "$SRC/backend/app/settings/database.py" 2>/dev/null \
  && ok "settings DB journal_mode DELETE" || fail "settings/database.py still uses WAL"

# ---- sovereign.db must NOT ship; data dirs must exist --------------
if find "$BUNDLE" -name 'sovereign*.db*' 2>/dev/null | grep -q .; then
  fail "a sovereign DB was shipped (should be created on first run)"
else ok "no shipped DB (created on first run)"; fi
missing=""
for d in data data/models data/plugins data/cache; do
  [ -d "$BUNDLE/$d" ] || missing="$missing $d"
done
[ -z "$missing" ] && ok "data dirs present (data/{models,plugins,cache})" \
                  || fail "missing data dirs:$missing"

# ---- 8. runtime smoke: space-in-path, no host leak ----------------
smoke(){
  local exe="$BUNDLE/resources/backend/SovereignAIBackend.exe"
  if [ ! -f "$exe" ]; then
    note "smoke: no Windows backend exe in bundle; skipping runtime test"
    return
  fi
  local work port db marker pid
  work="${TMPDIR:-${TEMP:-/tmp}}/Sov Test Dir"
  port=8079; db="$work/data"
  rm -rf "$work"; mkdir -p "$db/cache/temp"
  # Optional full-bundle copy (spec's literal test); off by default (heavy).
  local target="$work"
  if [ "${SMOKE_COPY:-0}" = "1" ]; then
    target="$work/SovereignAI-Edge"
    cp -r "$BUNDLE" "$target" || { fail "smoke: copy to space-path failed"; return; }
    exe="$target/resources/backend/SovereignAIBackend.exe"
  fi
  marker="$work/.marker"; : > "$marker"
  note "smoke: launching $(basename "$exe") from '$work' on 127.0.0.1:$port"
  ( cd "$work" && \
    SOVEREIGN_DATA_ROOT="$db" \
    TEMP="$db/cache/temp" TMP="$db/cache/temp" HF_HOME="$db/cache/hf" \
    XDG_CACHE_HOME="$db/cache" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    "$exe" --host 127.0.0.1 --port "$port" >"$work/backend.log" 2>&1 ) &
  pid=$!
  local up=0
  for _ in $(seq 1 120); do
    if python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:$port/health',timeout=2); sys.exit(0)" 2>/dev/null; then up=1; break; fi
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done
  powershell -NoProfile -Command "Stop-Process -Id $pid -Force" 2>/dev/null || kill -9 "$pid" 2>/dev/null
  sleep 1
  [ "$up" = 1 ] && ok "smoke: /health answered (space-in-path OK)" \
                || { fail "smoke: backend did not answer /health"; tail -n 15 "$work/backend.log" 2>/dev/null; }

  # positive: DB landed on the drive under the redirected data root
  if find "$db" -name 'sovereign*.db' 2>/dev/null | grep -q .; then
    ok "smoke: DB created under redirected data root (stays on drive)"
  else fail "smoke: no DB under data root -- redirect not honored"; fi

  # negative: nothing new leaked into the host home / appdata
  leak=$(find "$HOME" "$LOCALAPPDATA" "$APPDATA" -newer "$marker" -type f 2>/dev/null \
         | grep -v "$work" | head -n 20 || true)
  [ -z "$leak" ] && ok "smoke: no host home/appdata writes" \
                 || { fail "smoke: host writes detected:"; printf '%s\n' "$leak"; }
  rm -rf "$work"
}
smoke

echo "----------------------------------------"
if [ "$FAIL" = 0 ]; then echo "PORTABILITY: PASS"; exit 0; else echo "PORTABILITY: FAIL"; exit 1; fi
