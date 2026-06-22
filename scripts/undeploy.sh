#!/usr/bin/env bash
# undeploy.sh — Remove Prebextor plugin AND revert Prebextor-owned patches
# from the user's Hermes-agent checkout.
#
# Patch revert strategy: if `<target><backup_extension>` exists (was
# created during apply-patches.sh), restore it. Then delete the marker
# file. This restores the user's Hermes-agent to the exact pre-install
# state — without git history (we never `git commit`ed the patch).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PATCHES_DIR="$PROJECT_ROOT/patches"
PLUGIN_DIR="$HOME/.hermes/plugins/web/prebextor"
DAVE_CONFIG="$HOME/.hermes/profiles/dave/config.yaml"

echo "=== Prebextor Undeploy ==="

# 1. Revert Prebextor-owned patches before removing the plugin (the plugin
#    can still be discovered while patches are mid-revert).
if [ -f "$PATCHES_DIR/manifest.json" ]; then
    python3 - "$PATCHES_DIR/manifest.json" <<'PYEOF'
import json, os, shutil, subprocess, sys

manifest_path = sys.argv[1]
HERMES_HOME_DEFAULT = "/home/degi/.hermes"
HERMES_HOME = os.environ.get("HERMES_HOME", HERMES_HOME_DEFAULT)
HERMES_AGENT = os.path.join(HERMES_HOME, "hermes-agent")
if not os.path.isdir(HERMES_AGENT):
    # fallback to HOME
    HERMES_AGENT = os.path.join(os.environ.get("HOME", "/home/degi"), ".hermes", "hermes-agent")
print(f"  Hermes-agent directory: {HERMES_AGENT}")

with open(manifest_path) as f:
    manifest = json.load(f)

reverted = skipped = failed = 0
for entry in manifest.get("patches", []):
    pid = entry["id"]
    target_rel = entry["target"]
    backup_ext = entry["rollback"]["backup_extension"]
    marker_ext = entry["rollback"]["marker_extension"]
    target_abs = os.path.join(HERMES_AGENT, target_rel)
    backup     = target_abs + backup_ext
    marker     = target_abs + marker_ext
    print(f"--- {pid} ---")
    if not (os.path.exists(marker) or os.path.exists(backup)):
        # No marker or backup → patch was never applied by us (e.g. user ran
        # undeploy on a clean checkout). Skip without touching anything.
        print("  SKIP: no marker .prebextor-patched or backup .prebextor-bak (was this ever installed?).")
        skipped += 1; print(); continue

    if not os.path.isfile(backup):
        print(f"  FAIL: marker present but backup missing — refusing to revert.")
        failed += 1; continue

    shutil.copy2(backup, target_abs)
    print(f"  OK: restored {target_rel} from {os.path.basename(backup)}")

    if os.path.exists(marker):
        os.remove(marker)
        print(f"      removed marker {os.path.basename(marker)}")
    # Clean up the backup itself; it has served its purpose. undeploy is
    # idempotent — a subsequent deploy will produce a fresh backup.
    os.remove(backup)
    print(f"      removed backup {os.path.basename(backup)}")
    reverted += 1; print()

print(f"=== Patch revert summary ===")
print(f"  reverted: {reverted}")
print(f"  skipped : {skipped}")
print(f"  failed  : {failed}")
sys.exit(0 if not failed else 1)
PYEOF
fi

# 2. Remove plugin directory
if [ -d "$PLUGIN_DIR" ]; then
    rm -rf "$PLUGIN_DIR"
    echo "[2/3] Plugin directory removed: $PLUGIN_DIR"
else
    echo "[2/3] Plugin directory not found (already removed?)"
fi

# 3. Revert config (root + dave profile)
for CONFIG in "$HOME/.hermes/config.yaml" "$DAVE_CONFIG"; do
    if [ ! -f "$CONFIG" ]; then
        echo "[3/3] Skipped config (missing): $CONFIG"
        continue
    fi
    if [ -f "$CONFIG.bak.prebextor" ]; then
        cp "$CONFIG.bak.prebextor" "$CONFIG"
        echo "[3/3] Config restored from backup: $CONFIG"
    else
        sed -i '/extract_backend: prebextor/d' "$CONFIG"
        echo "[3/3] Config patched (removed extract_backend line): $CONFIG"
    fi
done

echo "=== Undeploy Complete ==="
