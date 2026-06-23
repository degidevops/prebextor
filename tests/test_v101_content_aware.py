#!/usr/bin/env python3
"""test_v101_content_aware.py — Unit tests for v1.0.1 content-aware modules.

Run from project root: python -m tests.test_v101_content_aware
"""

import sys
import os

# Ensure project root is in path
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


# ── Import modules ──────────────────────────────────────────────────
# We need to set up the package path so relative imports work
import importlib

# First, ensure the prebextor package is importable
# The trick: add project root to sys.path and import as package
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Now import the pipeline modules through the package
# But __init__.py has relative imports that fail, so we import directly
# by manipulating sys.modules

# Create a fake 'prebextor' package
import types
prebextor_pkg = types.ModuleType('prebextor')
prebextor_pkg.__path__ = [PROJECT_ROOT]
prebextor_pkg.__package__ = 'prebextor'
sys.modules['prebextor'] = prebextor_pkg

pipeline_pkg = types.ModuleType('prebextor.pipeline')
pipeline_pkg.__path__ = [os.path.join(PROJECT_ROOT, 'pipeline')]
pipeline_pkg.__package__ = 'prebextor.pipeline'
sys.modules['prebextor.pipeline'] = pipeline_pkg

fetcher_pkg = types.ModuleType('prebextor.fetcher')
fetcher_pkg.__path__ = [os.path.join(PROJECT_ROOT, 'fetcher')]
fetcher_pkg.__package__ = 'prebextor.fetcher'
sys.modules['prebextor.fetcher'] = fetcher_pkg

# Now load the actual modules by executing them into the package
# We need to manually load each module into sys.modules first

def _load_module_into_package(module_name, file_path, package_name):
    """Load a module from file into sys.modules under a package."""
    with open(file_path, 'r') as f:
        source = f.read()
    
    mod = types.ModuleType(module_name)
    mod.__package__ = package_name
    mod.__file__ = file_path
    sys.modules[module_name] = mod
    
    # Execute the module code
    exec(compile(source, file_path, 'exec'), mod.__dict__)
    return mod

# Load fetcher first (dependency)
fetcher_dir = os.path.join(PROJECT_ROOT, 'fetcher')
for fname in os.listdir(fetcher_dir):
    if fname.endswith('.py') and not fname.startswith('_'):
        mod_name = fname[:-3]
        full_mod_name = f'prebextor.fetcher.{mod_name}'
        file_path = os.path.join(fetcher_dir, fname)
        _load_module_into_package(full_mod_name, file_path, 'prebextor.fetcher')

# Load pipeline modules in dependency order
# scorer first (no deps), then validator (depends on scorer)
pipeline_dir = os.path.join(PROJECT_ROOT, 'pipeline')
_pipeline_files_ordered = [
    'scorer.py', 'pruner.py', 'mapper.py', 'transform.py', 'qa.py',
    'iframe_extractor.py', 'validator.py',  # validator last (uses scorer types)
]
for fname in _pipeline_files_ordered:
    full_mod_name = f'prebextor.pipeline.{fname[:-3]}'
    file_path = os.path.join(pipeline_dir, fname)
    if os.path.exists(file_path):
        _load_module_into_package(full_mod_name, file_path, 'prebextor.pipeline')

# Load provider
_load_module_into_package(
    'prebextor.provider',
    os.path.join(PROJECT_ROOT, 'provider.py'),
    'prebextor'
)

# Load __init__
with open(os.path.join(PROJECT_ROOT, '__init__.py'), 'r') as f:
    init_source = f.read()
prebextor_pkg.__file__ = os.path.join(PROJECT_ROOT, '__init__.py')
exec(compile(init_source, prebextor_pkg.__file__, 'exec'), prebextor_pkg.__dict__)

# Now import the classes
ScoredBlock = sys.modules['prebextor.pipeline.scorer'].ScoredBlock
ContentAwareScorer = sys.modules['prebextor.pipeline.scorer'].ContentAwareScorer
ValidationResult = sys.modules['prebextor.pipeline.validator'].ValidationResult
StructuralMapper = sys.modules['prebextor.pipeline.mapper'].StructuralMapper
SurgicalPruner = sys.modules['prebextor.pipeline.pruner'].SurgicalPruner
NOISE_SELECTORS = sys.modules['prebextor.pipeline.pruner'].NOISE_SELECTORS
PrebextorProvider = sys.modules['prebextor.provider'].PrebextorProvider
__version__ = prebextor_pkg.__version__


# ══════════════════════════════════════════════════════════════════════
# SECTION 1: ScoredBlock
# ══════════════════════════════════════════════════════════════════════
print("=" * 60)
print("Section 1: ScoredBlock")
print("=" * 60)

b1 = ScoredBlock("div.article", 1000, 10, 50, 20)
check("High-content score > 0.5", b1.score > 0.5, f"score: {b1.score}")
check("High-content link_density < 0.1", b1.link_density < 0.1)
check("High-content NOT noise", not b1.is_likely_noise)

b2 = ScoredBlock("div.sidebar", 100, 5, 80, 0)
check("High-link score < 0.5", b2.score < 0.5, f"score: {b2.score}")
check("High-link link_density > 0.5", b2.link_density > 0.5)
check("High-link IS noise", b2.is_likely_noise)

b3 = ScoredBlock("span.tiny", 10, 1, 0, 0)
check("Short text score == 0", b3.score == 0.0)

b4 = ScoredBlock("p.para", 200, 2, 0, 5)
check("Medium score 0.1-2.0", 0.1 < b4.score < 2.0)
check("Medium NOT noise", not b4.is_likely_noise)

d = b1.to_dict()
for k in ("selector", "score", "text_length", "link_density", "text_density", "comma_count"):
    check(f"to_dict has '{k}'", k in d)

check("Content > noise score", b1.score > b2.score)


# ══════════════════════════════════════════════════════════════════════
# SECTION 2: ContentAwareScorer
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("Section 2: ContentAwareScorer")
print("=" * 60)

from unittest.mock import MagicMock
mock_client = MagicMock()
scorer = ContentAwareScorer(mock_client)
# 2.1: noise selector filtering
blocks = [b1, b2, b3, b4]
noise = scorer.get_noise_selectors(blocks)
check("Noise selectors found for high-link blocks", len(noise) >= 1, f"noise: {noise}")
check("Noise excludes article", "div.article" not in noise)

cg = scorer.compute_confidence([b1, b4])
check("Good confidence > 0.5", cg > 0.5, f"conf: {cg}")

cb = scorer.compute_confidence([b2, b3])
check("Bad confidence < 0.6", cb < 0.6, f"conf: {cb}")

ce = scorer.compute_confidence([])
check("Empty confidence == 0", ce == 0.0)

cm = scorer.compute_confidence([b1, b2, b4])
check("Mixed confidence 0.3-0.9", 0.3 < cm < 0.9, f"conf: {cm}")
# 2.6: max noise limit — create blocks that ARE noise (low score + high link density)
many = [ScoredBlock(f"div.n{i}", 30, 1, 25, 0) for i in range(20)]
nl = scorer.get_noise_selectors(many, max_noise_blocks=5)
check("Max noise limit respected", len(nl) <= 5, f"len: {len(nl)}")


# ══════════════════════════════════════════════════════════════════════
# SECTION 3: ValidationResult
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("Section 3: ValidationResult")
print("=" * 60)

vr1 = ValidationResult("div.main", 500, 10, 0.1, 5.0, 0.9, 1)
check("Pass 1 confidence > 0.7", vr1.confidence > 0.7)
check("Pass 1 no warning", vr1.warning is None)

vr2 = ValidationResult("div.art", 150, 3, 0.3, 2.0, 0.5, 2, "Relaxed")
check("Pass 2 confidence 0.3-0.7", 0.3 < vr2.confidence < 0.7)
check("Pass 2 has warning", vr2.warning is not None)

vr3 = ValidationResult("body", 60, 1, 0.5, 0.5, 0.2, 3, "Fallback")
check("Pass 3 confidence < 0.3", vr3.confidence < 0.3)
check("Pass 3 warning has Fallback", vr3.warning is not None and "Fallback" in vr3.warning)

d = vr1.to_dict()
for k in ("selector", "confidence", "pass_used", "warning"):
    check(f"to_dict has '{k}'", k in d)


# ══════════════════════════════════════════════════════════════════════
# SECTION 4: StructuralMapper confidence
# ══════════════════════════════════════════════════════════════════════
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


# ══════════════════════════════════════════════════════════════════════
# SECTION 5: SurgicalPruner dynamic
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("Section 5: SurgicalPruner dynamic")
print("=" * 60)

check("prune_dynamic exists", hasattr(SurgicalPruner, "prune_dynamic"))
sig = inspect.signature(SurgicalPruner.prune_dynamic)
params = list(sig.parameters.keys())
for p in ("container_selector", "noise_selectors", "tab_id", "user"):
    check(f"prune_dynamic has '{p}'", p in params)

for s in ("nav", "aside", "footer", "script", ".ad-banner"):
    check(f"NOISE_SELECTORS has '{s}'", s in NOISE_SELECTORS)
check("NOISE_SELECTORS >= 20", len(NOISE_SELECTORS) >= 20)


# ══════════════════════════════════════════════════════════════════════
# SECTION 6: Provider integration
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("Section 6: Provider integration")
print("=" * 60)

si = inspect.getsource(PrebextorProvider.__init__)
check("Has _scorer", "_scorer" in si)
check("Has _validator", "_validator" in si)

se = inspect.getsource(PrebextorProvider._extract_one)
for item in ("score_blocks", "get_noise_selectors", "prune_dynamic",
             "validator.validate", "final_confidence", "confidence",
             "content_aware", "pruned_static", "pruned_dynamic"):
    check(f"_extract_one has '{item}'", item in se)
check("Pipeline tag v3.1", "prebextor-v3.1" in se)


# ══════════════════════════════════════════════════════════════════════
# SECTION 7: Version
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("Section 7: Version")
print("=" * 60)

check("Version is 1.0.1", __version__ == "1.0.1", f"version: {__version__}")


# ══════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"Results: {passed} passed, {failed} failed")
print(f"{'=' * 60}")
if failed:
    sys.exit(1)
else:
    print("ALL v1.0.1 CONTENT-AWARE CHECKS PASSED")
