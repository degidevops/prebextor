#!/usr/bin/env python3
"""test_v101_content_aware.py — Unit tests for v1.0.1+ content-aware modules.

Run from project root with editable install active:
  python3 tests/test_v101_content_aware.py
"""

import sys, os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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

# ── Direct imports from installed package ──
from prebextor.pipeline.scorer import ScoredBlock, ContentAwareScorer
from prebextor.pipeline.validator import ValidationResult
from prebextor.pipeline.mapper import StructuralMapper
from prebextor.pipeline.pruner import SurgicalPruner, NOISE_SELECTORS
from prebextor.provider import PrebextorProvider
import prebextor
__version__ = prebextor.__version__

# ═══════════════════════════════════════════════════════════════
# SECTION 1: ScoredBlock
# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("Section 1: ScoredBlock")
print("=" * 60)

b1 = ScoredBlock("div.article", 500, 5, 10, 3)
check("High-content score > 0.5", b1.score > 0.5)
check("High-content link_density < 0.1", b1.link_density < 0.1)
check("High-content NOT noise", not b1.is_likely_noise)

b2 = ScoredBlock("nav.links", 30, 2, 25, 0)
check("High-link score < 0.5", b2.score < 0.5)
check("High-link link_density > 0.5", b2.link_density > 0.5)
check("High-link IS noise", b2.is_likely_noise)

b3 = ScoredBlock("span.tiny", 10, 1, 0, 0)
check("Short text score == 0", b3.score == 0.0)

b4 = ScoredBlock("p.para", 100, 2, 5, 1)
check("Medium score 0.1-2.0", 0.1 < b4.score < 2.0)
check("Medium NOT noise", not b4.is_likely_noise)

d = b1.to_dict()
for k in ("selector", "score", "text_length", "link_density", "text_density", "comma_count"):
    check(f"to_dict has '{k}'", k in d)

check("Content > noise score", b1.score > b2.score)

# ═══════════════════════════════════════════════════════════════
# SECTION 2: ContentAwareScorer
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("Section 2: ContentAwareScorer")
print("=" * 60)

from unittest.mock import MagicMock
mock_client = MagicMock()
scorer = ContentAwareScorer(mock_client)

blocks = [b1, b2, b3, b4]
noise = scorer.get_noise_selectors(blocks)
check("Noise selectors found for high-link blocks", len(noise) >= 1)
check("Noise excludes article", b1.selector not in noise)

cg = scorer.compute_confidence([b1, b4])
check("Good confidence > 0.3", cg > 0.3, f"got: {cg}")

cb = scorer.compute_confidence([b2, b3])
check("Bad confidence < 0.3", cb < 0.3, f"got: {cb}")

ce = scorer.compute_confidence([])
check("Empty confidence == 0", ce == 0.0)

cm = scorer.compute_confidence([b1, b2, b4])
check("Mixed confidence > 0.2", cm > 0.2, f"got: {cm}")

many = [ScoredBlock(f"div.n{i}", 30, 1, 25, 0) for i in range(20)]
nl = scorer.get_noise_selectors(many, max_noise_blocks=5)
check("Max noise limit respected", len(nl) <= 5)

# ═══════════════════════════════════════════════════════════════
# SECTION 3: ValidationResult
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("Section 3: ValidationResult")
print("=" * 60)

vr1 = ValidationResult("div.main", 500, 10, 0.1, 5.0, 0.9, 1)
check("Pass 1 confidence > 0.7", vr1.confidence > 0.7)
check("Pass 1 no warning", vr1.warning is None)

vr2 = ValidationResult("div.art", 150, 3, 0.3, 2.0, 0.5, 2, "Relaxed")
check("Pass 2 confidence 0.3-0.7", 0.3 < vr2.confidence < 0.7)
check("Pass 2 has warning", vr2.warning is not None)

vr3 = ValidationResult("div.short", 80, 1, 0.5, 1.0, 0.2, 3, "Fallback")
check("Pass 3 confidence < 0.3", vr3.confidence < 0.3)
check("Pass 3 warning has Fallback", "Fallback" in (vr3.warning or ""))

for k in ("selector", "confidence", "pass_used", "warning"):
    check(f"to_dict has '{k}'", k in vr1.to_dict())

# ═══════════════════════════════════════════════════════════════
# SECTION 4: StructuralMapper confidence
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("Section 4: StructuralMapper confidence")
print("=" * 60)

import inspect
src = inspect.getsource(StructuralMapper.map_selector)
check("Returns tuple", "tuple" in src or "return (sel" in src)
check("Has 1.0 confidence", "1.0" in src)
check("Has 0.6 confidence", "0.6" in src)
check("Has 0.4 confidence", "0.4" in src)
check("Has 0.2 confidence", "0.2" in src)

# ═══════════════════════════════════════════════════════════════
# SECTION 5: SurgicalPruner dynamic
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("Section 5: SurgicalPruner dynamic")
print("=" * 60)

check("prune_dynamic exists", hasattr(SurgicalPruner, "prune_dynamic"))
sig = inspect.signature(SurgicalPruner.prune_dynamic)
params = list(sig.parameters.keys())
for p in ("container_selector", "noise_selectors", "tab_id", "user"):
    check(f"prune_dynamic has '{p}'", p in params)

for ns in ("nav", "aside", "footer", "script", ".ad-banner"):
    check(f"NOISE_SELECTORS has '{ns}'", ns in NOISE_SELECTORS)
check("NOISE_SELECTORS >= 20", len(NOISE_SELECTORS) >= 20)

# ═══════════════════════════════════════════════════════════════
# SECTION 6: Provider integration
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("Section 6: Provider integration")
print("=" * 60)

p_inst = PrebextorProvider(enable_quality_filter=False, enable_metrics=False)
check("Has _scorer", hasattr(p_inst, "_scorer"))
check("Has _validator", hasattr(p_inst, "_validator"))

# ═══════════════════════════════════════════════════════════════
# SECTION 7: Version
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("Section 7: Version")
print("=" * 60)

check("Version is 1.2.1", __version__ == "1.2.1", f"version: {__version__}")

# ── Summary ──
print(f"\n{'='*60}")
print(f"Results: {passed} passed, {failed} failed")
print(f"{'='*60}")

sys.exit(0 if failed == 0 else 1)