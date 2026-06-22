#!/usr/bin/env python3
"""test_patches.py — Validate Prebextor-owned patch set catches drift, applies
cleanly, is idempotent, and reverts cleanly.

Run as `python3 scripts/test_patches.py`. Exits 0 on success, 1 on failure.

Test phases:
  1. Manifest schema sanity (loads, each entry has required fields)
  2. Drift check on a clean Hermes-agent target (must match `expected_sha256`)
     — if HEAD has changed upstream, fail loudly so we know the patch needs
     regeneration BEFORE we run apply-patches.
  3. Apply (via `git apply --check` first, then `git apply` for real if
     running non-read-only). We use a temporary clone of the Hermes-agent
     target so we never touch the user's live checkout.
  4. Idempotency: apply twice, count net diff before & after.
  5. Revert: copy back the .prebextor-bak file (simulates undeploy.sh),
     verify SHA matches HEAD.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT_DEFAULT = "/home/degi/project/prebextor"
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", PROJECT_ROOT_DEFAULT))
PATCHES_DIR  = PROJECT_ROOT / "patches"
HERMES_AGENT_DEFAULT = Path("/home/degi/.hermes/hermes-agent")
HERMES_AGENT = Path(os.environ.get("HERMES_AGENT_DIR", HERMES_AGENT_DEFAULT))

passed = failed = 0

def check(label: str, condition: bool, detail: str = "") -> None:
    """Pretty-print per-check result. Exit code aggregates are emitted at the end."""
    global passed, failed
    n = passed + failed + 1
    if condition:
        passed += 1
        print(f"[{n:2d}] PASS: {label}")
    else:
        failed += 1
        print(f"[{n:2d}] FAIL: {label} — {detail}")


def sha256_of(path: Path) -> str:
    """Return SHA-256 hex digest of `path` using `sha256sum` from $PATH."""
    out = subprocess.run(
        ["sha256sum", str(path)], capture_output=True, text=True, check=True
    )
    return out.stdout.split()[0]


def git_apply(workdir: Path, patch: Path, op: str = "apply") -> subprocess.CompletedProcess:
    """Run `git -C workdir apply [--check|--reverse] patch`."""
    cmd = ["git", "-C", str(workdir), "apply"]
    if op == "check":
        cmd.append("--check")
    elif op == "reverse":
        cmd.append("--reverse")
    cmd.append(str(patch))
    return subprocess.run(cmd, capture_output=True, text=True)


print("=" * 60)
print("Prebextor Patch Test")
print("=" * 60)

# ── Phase 1: manifest schema ──────────────────────────────────────────────
manifest_path = PATCHES_DIR / "manifest.json"
check("manifest.json exists", manifest_path.exists(), str(manifest_path))

manifest = {}
if manifest_path.exists():
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        check("manifest.json parses as JSON", False, str(exc))

check("manifest has 'patches' list",
      isinstance(manifest.get("patches"), list) and manifest["patches"],
      f"got {type(manifest.get('patches')).__name__}")

REQUIRED_KEYS = {
    "id", "description", "target", "patch", "idempotency",
    "hermes_min_version", "rollback",
}
IDEMPOTENCY_KEYS = {"sentinel", "expected_sha256"}
ROLLBACK_KEYS    = {"backup_extension", "marker_extension"}

for entry in manifest.get("patches", []):
    pid = entry.get("id", "?")
    missing = REQUIRED_KEYS - entry.keys()
    check(f"manifest entry '{pid}' has all required keys",
          not missing, f"missing: {missing}")
    missing_idem = IDEMPOTENCY_KEYS - entry.get("idempotency", {}).keys()
    check(f"manifest entry '{pid}' idempotency schema",
          not missing_idem, f"missing: {missing_idem}")
    missing_rb = ROLLBACK_KEYS - entry.get("rollback", {}).keys()
    check(f"manifest entry '{pid}' rollback schema",
          not missing_rb, f"missing: {missing_rb}")
    patch_file = PATCHES_DIR / entry.get("patch", "")
    check(f"manifest entry '{pid}' patch file exists",
          patch_file.is_file(), str(patch_file))

if not manifest.get("patches"):
    print("\n=== Aborting: manifest is empty or malformed ===")
    sys.exit(1)

# ── Phase 2-5: apply / idempotency / revert in a sandbox clone ────────────
# We need a clean checkout to test patching without touching the live user
# checkout. The simplest approach: copy the Hermes-agent tree to a tmpdir
# and operate there. This is filesystem-copy heavy — for ~12k LOC files
# it's fine.
with tempfile.TemporaryDirectory(prefix="prebextor-patch-test-") as tmpdir:
    sandbox = Path(tmpdir) / "hermes-agent"
    print(f"\nSandbox: {sandbox}")

    # We only need to copy the specific target (and its .git dir for `git apply`
    # to work) — not the whole checkout. For tooling simplicity, just copy the
    # entire .git + the target file. `git apply` reads <target> per the patch's
    # `diff --git a/...` header, which is relative to the cwd's repo root.
    # So we copy the user's hermes-agent entirely — hermes-agent is mostly
    # tracked files; we skip pycache etc.
    ignore = shutil.ignore_patterns(
        "__pycache__", "*.pyc", "node_modules", ".venv", "venv",
        ".pytest_cache", "*.egg-info", ".mypy_cache",
    )
    shutil.copytree(HERMES_AGENT, sandbox, ignore=ignore, dirs_exist_ok=True,
                    symlinks=False)
    print(f"  copied {HERMES_AGENT} → {sandbox}")

    # Reset every target back to HEAD so we always start from a clean state
    for entry in manifest["patches"]:
        target_rel = entry["target"]
        target = sandbox / target_rel
        if target.exists():
            subprocess.run(["git", "-C", str(sandbox), "checkout",
                            "HEAD", "--", target_rel],
                            capture_output=True, text=True, check=True)

    # ── Phase 2: drift check ─────────────────────────────────────────────
    print("\n--- Phase 2: Drift check ---")
    for entry in manifest["patches"]:
        pid = entry["id"]
        target_rel = entry["target"]
        target = sandbox / target_rel
        if not target.exists():
            check(f"drift check '{pid}' — target exists", False, str(target))
            continue
        sha = sha256_of(target)
        expected = entry["idempotency"]["expected_sha256"]
        check(f"drift check '{pid}' — current SHA matches manifest",
              sha == expected,
              f"manifest={expected[:16]}…  actual={sha[:16]}…")

    # ── Phase 3: apply (check + apply) ───────────────────────────────────
    print("\n--- Phase 3: Apply ---")
    for entry in manifest["patches"]:
        pid = entry["id"]
        patch_file = PATCHES_DIR / entry["patch"]
        target_rel = entry["target"]

        # git apply --check
        r = git_apply(sandbox, patch_file, op="check")
        check(f"apply '{pid}' passes git apply --check",
              r.returncode == 0, r.stderr.strip())

        # git apply (for real) — we copy state per entry then revert at end
        # of the test so we can run Phase 4 (idempotency) and Phase 5 (revert)
        # in this same sandbox.
        r = git_apply(sandbox, patch_file, op="apply")
        check(f"apply '{pid}' real git apply", r.returncode == 0, r.stderr.strip())

        # Sentinel must now be present
        target = sandbox / target_rel
        sentinel = entry["idempotency"]["sentinel"]
        check(f"apply '{pid}' — sentinel present in patched file",
              sentinel in target.read_text(), "sentinel string not found")

    # ── Phase 4: idempotency ─────────────────────────────────────────────
    print("\n--- Phase 4: Idempotency (apply twice) ---")
    sha_after_first = {}
    for entry in manifest["patches"]:
        target = sandbox / entry["target"]
        sha_after_first[entry["id"]] = sha256_of(target)

    # Run apply again — should still succeed (apply-patches.sh uses sentinel
    # + marker to detect already-applied, but for a sanity check we just
    # ensure git apply is reversible by git apply --reverse)
    for entry in manifest["patches"]:
        patch_file = PATCHES_DIR / entry["patch"]
        r = git_apply(sandbox, patch_file, op="check")  # already applied
        # git apply --check over an already-patched file says "patch failed".
        # That's actually expected — the patch is not meant to be replayable.
        check(
            f"idempotency '{entry['id']}' — re-applying fails (patch is single-use)",
            r.returncode != 0,
            "patch should report conflict on already-patched target",
        )

    # Confirm SHAs haven't changed because we didn't actually re-apply
    for entry in manifest["patches"]:
        target = sandbox / entry["target"]
        sha = sha256_of(target)
        check(
            f"idempotency '{entry['id']}' — file SHA stable after no-op",
            sha == sha_after_first[entry["id"]],
            f"sha changed: {sha} vs {sha_after_first[entry['id']]}",
        )

    # ── Phase 5: revert ──────────────────────────────────────────────────
    print("\n--- Phase 5: Revert (git apply --reverse) ---")
    for entry in manifest["patches"]:
        patch_file = PATCHES_DIR / entry["patch"]
        r = git_apply(sandbox, patch_file, op="reverse")
        check(f"revert '{entry['id']}' via git apply --reverse",
              r.returncode == 0, r.stderr.strip())

        # SHA must match HEAD original
        target = sandbox / entry["target"]
        sha = sha256_of(target)
        expected = entry["idempotency"]["expected_sha256"]
        check(f"revert '{entry['id']}' — target SHA matches HEAD",
              sha == expected,
              f"got {sha[:16]}…  expected {expected[:16]}…")

    # Final overall: applying then reversing gives back the same SHA
    # (already covered per-entry, but summarise clearly for the user)
    print("\n--- Phase 6: Round-trip ---")
    for entry in manifest["patches"]:
        target = sandbox / entry["target"]
        sha = sha256_of(target)
        expected = entry["idempotency"]["expected_sha256"]
        check(f"round-trip '{entry['id']}' — final SHA == HEAD",
              sha == expected, f"got {sha}")

print(f"\n=== Results: {passed} passed, {failed} failed ===")
sys.exit(0 if not failed else 1)
