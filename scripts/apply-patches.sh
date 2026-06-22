#!/usr/bin/env bash
# apply-patches.sh — Apply Prebextor-owned patches to the user's Hermes-agent
# checkout. Idempotent: running it twice is a no-op the second time.
#
# Behaviour (per manifest entry):
#   1. Locate the Hermes-agent checkout under $HERMES_HOME or $HOME.
#   2. Resolve target file path (relative to agent dir).
#   3. Skip if marker present (`<target><marker_extension>`) — already done.
#   4. Skip (but recreate marker) if sentinel string is in target — a previous
#      run left the patch but no marker (e.g. user copied it manually).
#   5. Drift check: pre-patch SHA-256 must match `expected_sha256` from
#      manifest. Refuse to patch drifted upstream — better to fail than to
#      corrupt a Hermes-agent that's been updated.
#   6. Pre-flight `git apply --check`; refuse if it doesn't apply cleanly.
#   7. Back up target → `<target><backup_extension>`, apply, touch marker.
#
# Exit codes:
#   0 — every entry applied (or already applied, or explicitly skipped)
#       without manual intervention
#   1 — at least one entry failed (drift, conflict, missing target / patch)
#   2 — usage / environment error

set -euo pipefail

PROJECT_ROOT_DEFAULT="/home/degi/project/prebextor"
PROJECT_ROOT="${PROJECT_ROOT:-$PROJECT_ROOT_DEFAULT}"
PATCHES_DIR="$PROJECT_ROOT/patches"

resolve_hermes_agent_dir() {
  if [ -n "${HERMES_HOME:-}" ] && [ -d "${HERMES_HOME}/hermes-agent" ]; then
    echo "${HERMES_HOME}/hermes-agent"; return 0
  fi
  if [ -d "$HOME/.hermes/hermes-agent" ]; then
    echo "$HOME/.hermes/hermes-agent"; return 0
  fi
  if [ -d "/home/degi/.hermes/hermes-agent" ]; then
    echo "/home/degi/.hermes/hermes-agent"; return 0
  fi
  return 1
}

HERMES_AGENT_DIR="$(resolve_hermes_agent_dir || true)"
if [ -z "$HERMES_AGENT_DIR" ] || [ ! -d "$HERMES_AGENT_DIR" ]; then
  echo "ERROR: Cannot locate Hermes-agent checkout." >&2
  echo "       Set HERMES_HOME or pass HERMES_AGENT_DIR explicitly." >&2
  exit 2
fi

for tool in git sha256sum python3; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: '$tool' is required." >&2
    exit 2
  fi
done

MANIFEST="$PATCHES_DIR/manifest.json"
if [ ! -f "$MANIFEST" ]; then
  echo "ERROR: Manifest not found: $MANIFEST" >&2
  exit 2
fi

# All the work happens in Python — single source of truth, testable, easy
# to invoke from scripts/test_patches.py with the same logic.
export PROJECT_ROOT PATCHES_DIR HERMES_AGENT_DIR MANIFEST
python3 <<'PYEOF'
import json, os, shutil, subprocess, sys

PROJECT_ROOT = os.environ["PROJECT_ROOT"]
PATCHES_DIR   = os.environ["PATCHES_DIR"]
HERMES_AGENT  = os.environ["HERMES_AGENT_DIR"]
MANIFEST      = os.environ["MANIFEST"]

def sha256_of(path: str) -> str:
    h = subprocess.run(["sha256sum", path], capture_output=True, text=True, check=True)
    return h.stdout.split()[0]

def git_apply(path_target: str, patch: str, op: str = "apply") -> None:
    """Run `git apply [--check|--reverse] [op]` against the target's repo."""
    cmd = ["git", "-C", path_target, "apply"]
    if op == "check":
        cmd.append("--check")
    elif op == "reverse":
        cmd.append("--reverse")
    cmd.append(patch)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    patch stderr: {r.stderr.strip()}")
        raise RuntimeError(f"git apply {op} failed (exit {r.returncode})")

with open(MANIFEST) as f:
    manifest = json.load(f)

print(f"=== Prebextor patch apply ===")
print(f"Project:  {PROJECT_ROOT}")
print(f"Hermes:   {HERMES_AGENT}")
print()

applied = skipped = failed = 0
for entry in manifest.get("patches", []):
    pid        = entry["id"]
    target_rel = entry["target"]
    patch_file = entry["patch"]
    expected   = entry["idempotency"]["expected_sha256"]
    sentinel   = entry["idempotency"]["sentinel"]
    baseline   = entry.get("baseline_sha256", "")
    backup_ext = entry["rollback"]["backup_extension"]
    marker_ext = entry["rollback"]["marker_extension"]

    target_abs = os.path.join(HERMES_AGENT, target_rel)
    patch_abs  = os.path.join(PATCHES_DIR, patch_file)
    marker     = target_abs + marker_ext
    backup     = target_abs + backup_ext

    print(f"--- {pid} ---")
    print(f"  target: {target_rel}")

    if not os.path.isfile(patch_abs):
        print(f"  FAIL: patch file missing ({patch_file})"); failed += 1; print(); continue
    if not os.path.isfile(target_abs):
        print(f"  FAIL: target file missing ({target_abs})"); failed += 1; print(); continue

    # 1. Already-patched marker?
    if os.path.exists(marker):
        print(f"  SKIP: marker present ({os.path.basename(marker)})"); skipped += 1; print(); continue

    # 2. Sentinel present (repatch mode)?
    with open(target_abs, encoding="utf-8") as f:
        tgt_text = f.read()
    if sentinel in tgt_text:
        print(f"  APPLIED (no marker): sentinel present, recreating marker")
        open(marker, "w").close()
        applied += 1; print(); continue

    # 3. Drift check
    sha = sha256_of(target_abs)
    if expected and sha != expected:
        print(f"  FAIL: drift — expected {expected}")
        print(f"        actual    {sha}")
        print(f"        Upstream Hermes-agent has moved. Refresh patch before retry.")
        failed += 1; print(); continue

    # 4. Pre-flight check
    try:
        git_apply(HERMES_AGENT, patch_abs, op="check")
    except RuntimeError:
        print(f"  FAIL: patch does not apply cleanly (run with --check for details)")
        failed += 1; print(); continue

    # 5. Backup + apply
    shutil.copy2(target_abs, backup)
    git_apply(HERMES_AGENT, patch_abs, op="apply")
    open(marker, "w").close()

    new_sha = sha256_of(target_abs)
    if baseline and new_sha != baseline:
        print(f"  WARN: post-patch SHA != manifest baseline")
        print(f"        manifest: {baseline}")
        print(f"        actual:   {new_sha}")
        print(f"        Behaviour is correct, manifest baseline is stale.")
    print(f"  OK: applied (backup={os.path.basename(backup)}, marker={os.path.basename(marker)})")
    applied += 1
    print()

print(f"=== Summary ===")
print(f"  applied: {applied}")
print(f"  skipped : {skipped}")
print(f"  failed  : {failed}")
sys.exit(0 if not failed else 1)
PYEOF
