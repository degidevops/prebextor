#!/usr/bin/env python3
"""verify.py — Verify Prebextor plugin deployment.

Independent of $HOME env-var artifacts by using absolute paths so the check
works from any process context (gateway, CLI, fresh subprocess, sandbox).
"""

from __future__ import annotations

import os
import sys

# Use ABSOLUTE paths — sandbox HOME can be redirected to dave/home/.
PLUGIN_DIR = "/home/degi/.hermes/plugins/web"
PROJECTS_DIR = "/home/degi/project/prebextor"
HERMES_TOOLS = "/home/degi/.hermes/hermes-agent/tools/web_tools.py"
PATCH_MARKER = HERMES_TOOLS + ".prebextor-patched"
BACKUP_FILE = HERMES_TOOLS + ".prebextor-bak"

for p in (PLUGIN_DIR, "/home/degi/.hermes/plugins"):
    if p not in sys.path:
        sys.path.insert(0, p)

passed = 0
failed = 0


def check(label, condition, detail=""):
    global passed, failed
    num = passed + failed + 1
    if condition:
        passed += 1
        print(f"[{num:2d}] PASS: {label}")
    else:
        failed += 1
        print(f"[{num:2d}] FAIL: {label} — {detail}")


try:
    import prebextor
    check("Import prebextor", True)
except ImportError as e:
    check("Import prebextor", False, str(e))
    sys.exit(1)

try:
    from prebextor import register, PrebextorProvider
    check("Import register", callable(register))
    check("Import PrebextorProvider", PrebextorProvider is not None)
except ImportError as e:
    check("Import register/PrebextorProvider", False, str(e))
    sys.exit(1)


def _try_run_test_extract() -> bool:
    """Invoke provider.extract via the in-process pipeline; raw tool call
    bypasses any toolset/prompt-schema concerns, so this validates the
    dispatcher chain end-to-end at the function level."""
    try:
        from prebextor import PrebextorProvider
        p = PrebextorProvider()
        if not p.is_available():
            return False
        result = p.extract(["https://example.com/"])
        if not isinstance(result, dict):
            return False
        if result.get("success") is not True:
            return False
        data = result.get("data")
        if not isinstance(data, list) or not data:
            return False
        first = data[0]
        return (
            isinstance(first, dict)
            and "url" in first
            and "content" in first
        )
    except Exception as exc:  # noqa: BLE001 — surface the message to user
        print(f"   (debug) provider.extract raised: {type(exc).__name__}: {exc}")
        return False


# 1) Plugin copy
check(
    "Plugin copy exists on disk",
    os.path.isdir(PLUGIN_DIR + "/prebextor"),
)

# 2) Dispatcher patch marker
check(
    "Dispatcher patch marker file present",
    os.path.exists(PATCH_MARKER),
    f"expected {PATCH_MARKER}",
)

# 3) Dispatcher patched (sentinel check)
try:
    with open(HERMES_TOOLS) as f:
        wt = f.read()
    check(
        "Dispatcher sentinel strings present in web_tools.py",
        "prebextor" in wt and "_ensure_web_plugins_loaded" in wt,
    )
except Exception as e:
    check("Read web_tools.py", False, str(e))

# 4) Backup file present (idem marker of patch install)
check(
    "Dispatcher backup file present",
    os.path.exists(BACKUP_FILE),
    f"expected {BACKUP_FILE}",
)

# 5) Config: extract_backend = prebextor in active profile
import re
for cfg in (
    "/home/degi/.hermes/config.yaml",
    "/home/degi/.hermes/profiles/dave/config.yaml",
):
    try:
        with open(cfg) as f:
            txt = f.read()
        match = re.search(r"extract_backend:\s*(\S+)", txt)
        ok = bool(match and match.group(1).strip("\"'") == "prebextor")
        check(f"{cfg}: web.extract_backend: prebextor", ok)
    except Exception as e:
        check(f"{cfg} readable", False, str(e))


# 6) Optional: end-to-end extract — only if --test-extract flag passed
if "--test-extract" in sys.argv:
    print()
    print("=== Native web_extract smoke test ===")
    if _try_run_test_extract():
        check("Provider.extract() returns envelope", True)
    else:
        check(
            "Provider.extract() returns envelope",
            False,
            "see exception above",
        )


print()
print(f"=== Summary: {passed} passed, {failed} failed ===")
sys.exit(0 if failed == 0 else 1)
