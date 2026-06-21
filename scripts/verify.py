#!/usr/bin/env python3
"""verify.py — Verify Prebextor plugin deployment."""

import sys
import os

PLUGIN_DIR = os.path.expanduser("~/.hermes/plugins/web")
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

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
    check("Import register", register is not None)
    check("Import PrebextorProvider", PrebextorProvider is not None)
except ImportError as e:
    check("Import register/PrebextorProvider", False, str(e))
    sys.exit(1)

try:
    provider = PrebextorProvider()
    check("Instantiation", True)
except Exception as e:
    check("Instantiation", False, str(e))
    sys.exit(1)

check("name == 'prebextor'", provider.name == "prebextor", f"got: {provider.name!r}")
check("supports_search() == False", provider.supports_search() == False)
check("supports_extract() == True", provider.supports_extract() == True)

try:
    avail = provider.is_available()
    check("is_available() is bool", isinstance(avail, bool))
except Exception as e:
    check("is_available()", False, str(e))

check("extract method exists", hasattr(provider, "extract") and callable(provider.extract))

doc = getattr(provider.extract, "__doc__", "") or ""
check("Docstring mentions 'success'", "success" in doc.lower())
check("Docstring mentions 'data'", "data" in doc.lower())

print(f"\n=== {passed} passed, {failed} failed ===")
if failed:
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
