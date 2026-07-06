#!/usr/bin/env python3
"""validate_v102.py — Simple sanity-check for the v1.2.1 provider.

Run: python tests/validate_v102.py
"""
import sys, os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from prebextor.provider import PrebextorProvider
from prebextor.pipeline.scorer import ScoredBlock, ContentAwareScorer
from prebextor.pipeline.validator import ValidationResult

passed, failed = 0, 0

def check(label, condition, detail=""):
    global passed, failed
    num = passed + failed + 1
    if condition:
        passed += 1
        print(f"[{num:2d}] PASS: {label}")
    else:
        failed += 1
        print(f"[{num:2d}] FAIL: {label} — {detail}")

inst = PrebextorProvider(enable_quality_filter=False, enable_metrics=False)
check("Provider instantiated", inst is not None)
check("Has _scorer", hasattr(inst, "_scorer"))
check("Has _validator", hasattr(inst, "_validator"))

# Verify public API surface (name + supports)
check("Provider name == 'prebextor'", inst.name == "prebextor")
check("supports_extract()", inst.supports_extract() is True)
check("NOT supports_search()", inst.supports_search() is False)

# Verify provider has the async extract entry point
check("Has async extract method", hasattr(inst, "extract"))

vr = ValidationResult("div.test", 300, 5, 0.2, 3.0, 0.7, 1)
check("ValidationResult confidence ~0.7", abs(vr.confidence - 0.7) < 0.01)
check("ValidationResult no warning", vr.warning is None)

sb = ScoredBlock("div.ok", 500, 5, 10, 3)
check("ScoredBlock score > 0", sb.score > 0)
check("ScoredBlock NOT noise", not sb.is_likely_noise)

ns = ScoredBlock("nav.bad", 30, 1, 25, 0)
check("Noise block IS noise", ns.is_likely_noise)
check("Content > noise score", sb.score > ns.score)

print(f"\n=== Results: {passed} passed, {failed} failed ===")
sys.exit(0 if failed == 0 else 1)