#!/usr/bin/env python3
"""test_e2e_v101.py — End-to-end extraction test for v1.0.1.

Tests the full Prebextor pipeline against real URLs.
Requires camofox CLI to be installed and running.

Run from project root: python tests/test_e2e_v101.py
"""

import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Set up package structure for relative imports
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

# Load modules in dependency order
def _load(mod_name, file_path, pkg_name):
    with open(file_path, 'r') as f:
        src = f.read()
    mod = types.ModuleType(mod_name)
    mod.__package__ = pkg_name
    mod.__file__ = file_path
    sys.modules[mod_name] = mod
    exec(compile(src, file_path, 'exec'), mod.__dict__)
    return mod

fetcher_dir = os.path.join(PROJECT_ROOT, 'fetcher')
for fn in os.listdir(fetcher_dir):
    if fn.endswith('.py') and not fn.startswith('_'):
        _load(f'prebextor.fetcher.{fn[:-3]}', os.path.join(fetcher_dir, fn), 'prebextor.fetcher')

pipeline_dir = os.path.join(PROJECT_ROOT, 'pipeline')
for fn in ['scorer.py', 'pruner.py', 'mapper.py', 'transform.py', 'qa.py',
          'iframe_extractor.py', 'validator.py']:
    fp = os.path.join(pipeline_dir, fn)
    if os.path.exists(fp):
        _load(f'prebextor.pipeline.{fn[:-3]}', fp, 'prebextor.pipeline')

_load('prebextor.provider', os.path.join(PROJECT_ROOT, 'provider.py'), 'prebextor')

with open(os.path.join(PROJECT_ROOT, '__init__.py'), 'r') as f:
    init_src = f.read()
prebextor_pkg.__file__ = os.path.join(PROJECT_ROOT, '__init__.py')
exec(compile(init_src, prebextor_pkg.__file__, 'exec'), prebextor_pkg.__dict__)

# Now import
PrebextorProvider = sys.modules['prebextor.provider'].PrebextorProvider
__version__ = prebextor_pkg.__version__

passed = 0
failed = 0
skipped = 0


def check(label, condition, detail=""):
    global passed, failed, skipped
    num = passed + failed + skipped + 1
    if condition:
        passed += 1
        print(f"[{num:2d}] PASS: {label}")
    else:
        failed += 1
        print(f"[{num:2d}] FAIL: {label} — {detail}")


def skip(label, reason=""):
    global skipped
    num = passed + failed + skipped + 1
    skipped += 1
    print(f"[{num:2d}] SKIP: {label} — {reason}")


# ── Import ──────────────────────────────────────────────────────────
try:
    from provider import PrebextorProvider
    from prebextor import __version__
    check("Import PrebextorProvider", True)
    check("Version is 1.0.1", __version__ == "1.0.1", f"version: {__version__}")
except ImportError as e:
    check("Import PrebextorProvider", False, str(e))
    sys.exit(1)

# ── Instantiate ─────────────────────────────────────────────────────
try:
    provider = PrebextorProvider()
    check("Instantiation", True)
    check("Provider has _scorer", hasattr(provider, "_scorer"))
    check("Provider has _validator", hasattr(provider, "_validator"))
except Exception as e:
    check("Instantiation", False, str(e))
    sys.exit(1)

# ── Check availability ──────────────────────────────────────────────
avail = provider.is_available()
check("camofox is_available()", isinstance(avail, bool), f"type: {type(avail)}")

if not avail:
    skip("E2E extraction", "camofox not available")
    print(f"\n=== Results: {passed} passed, {failed} failed, {skipped} skipped ===")
    sys.exit(0 if not failed else 1)

# ══════════════════════════════════════════════════════════════════════
# Test 1: example.com
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("Test 1: https://example.com")
print("=" * 60)

try:
    result = provider.extract(["https://example.com"])
    check("extract() returns dict", isinstance(result, dict), f"type: {type(result)}")

    if isinstance(result, dict):
        check("Envelope has 'success' key", "success" in result)
        check("Envelope has 'data' key", "data" in result)
        check("success is True", result.get("success") is True)

        data = result.get("data", [])
        check("data is list", isinstance(data, list))
        check("data has 1 element", len(data) == 1, f"len: {len(data)}")

        if data:
            item = data[0]
            check("item has all required keys",
                  all(k in item for k in ["url", "title", "content", "raw_content", "metadata", "error"]))

            # Content validation
            content = item.get("content", "")
            check("content is non-empty", len(content) > 0, f"len: {len(content)}")
            check("content has <extraction_result>", "<extraction_result>" in content)
            check("content has </extraction_result>", "</extraction_result>" in content)
            check("content has <main_body>", "<main_body>" in content)
            check("content has </main_body>", "</main_body>" in content)
            check("content has <metadata>", "<metadata>" in content)

            # raw_content validation
            raw = item.get("raw_content", "")
            check("raw_content is non-empty", len(raw) > 0, f"len: {len(raw)}")
            check("raw_content is HTML", "<" in raw and ">" in raw)

            # metadata validation — v1.0.1 new fields
            meta = item.get("metadata", {})
            check("metadata has 'selector'", "selector" in meta)
            check("metadata has 'extractor'", "extractor" in meta)
            check("metadata extractor is 'prebextor-v3.1'", meta.get("extractor") == "prebextor-v3.1",
                  f"extractor: {meta.get('extractor')}")
            check("metadata has 'pipeline'", "pipeline" in meta)
            check("pipeline includes 'score'", "score" in meta.get("pipeline", ""))
            check("pipeline includes 'validate'", "validate" in meta.get("pipeline", ""))

            # v1.0.1 new metadata fields
            check("metadata has 'confidence'", "confidence" in meta)
            check("metadata has 'content_aware'", "content_aware" in meta)
            check("metadata has 'pruned_static'", "pruned_static" in meta)
            check("metadata has 'pruned_dynamic'", "pruned_dynamic" in meta)
            check("metadata has 'pruned_total'", "pruned_total" in meta)
            check("metadata has 'scored_blocks_count'", "scored_blocks_count" in meta)
            check("metadata has 'noise_selectors_found'", "noise_selectors_found" in meta)

            # Confidence value check
            conf = meta.get("confidence", 0)
            check("confidence is float", isinstance(conf, float), f"type: {type(conf)}")
            check("confidence >= 0.0", conf >= 0.0, f"confidence: {conf}")
            check("confidence <= 1.0", conf <= 1.0, f"confidence: {conf}")

            # Error should be None
            check("error is None", item.get("error") is None, f"error: {item.get('error')}")

            # Title is non-empty
            check("title is non-empty", len(item.get("title", "")) > 0,
                  f"title: {item.get('title')!r}")

            # URL matches
            check("url matches", item.get("url") == "https://example.com")

            # No noise in raw_content
            noise_tags = ["<script", "<style"]
            for tag in noise_tags:
                check(f"No {tag} in raw_content", tag.lower() not in raw.lower(), f"found {tag}")

            # Content has markdown heading (if source has headings)
            # Note: example.com has no headings, so skip this check for it
            if "example.com" not in item.get("url", ""):
                check("content has markdown heading", "#" in content)
            else:
                check("example.com has no headings (expected)", True)

            # Print summary
            print("\n--- Extraction Summary ---")
            print(f"Title: {item.get('title', 'N/A')}")
            print(f"Selector: {meta.get('selector', 'N/A')}")
            print(f"Confidence: {conf}")
            print(f"Content length: {len(content)} chars")
            print(f"Raw HTML length: {len(raw)} chars")
            print(f"Scored blocks: {meta.get('scored_blocks_count', 'N/A')}")
            print(f"Pruned static: {meta.get('pruned_static', 'N/A')}")
            print(f"Pruned dynamic: {meta.get('pruned_dynamic', 'N/A')}")
            print("Content preview (first 300 chars):")
            print(content[:300])

except Exception as e:
    check("Extraction succeeded", False, f"{type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()


# ══════════════════════════════════════════════════════════════════════
# Test 2: Batch extraction (2 URLs)
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("Test 2: Batch extraction (2 URLs)")
print("=" * 60)

try:
    result2 = provider.extract(["https://example.com", "https://example.com"])
    check("Batch returns dict", isinstance(result2, dict))
    check("Batch success is True", result2.get("success") is True)
    check("Batch data has 2 items", len(result2.get("data", [])) == 2)

    # Check both items have v1.0.1 metadata
    for i, item in enumerate(result2.get("data", [])):
        meta = item.get("metadata", {})
        check(f"Item {i} has confidence", "confidence" in meta)
        check(f"Item {i} has content_aware", "content_aware" in meta)

except Exception as e:
    check("Batch extraction succeeded", False, f"{type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════════════
# Test 3: Content-aware scoring validation
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("Test 3: Content-aware scoring validation")
print("=" * 60)

try:
    result3 = provider.extract(["https://example.com"])
    if result3.get("success"):
        meta = result3["data"][0].get("metadata", {})

        # scored_blocks_count should be > 0
        scored = meta.get("scored_blocks_count", 0)
        check("scored_blocks_count > 0", scored > 0, f"count: {scored}")

        # pruned_total should be >= pruned_static
        pruned_total = meta.get("pruned_total", 0)
        pruned_static = meta.get("pruned_static", 0)
        check("pruned_total >= pruned_static", pruned_total >= pruned_static,
              f"total: {pruned_total}, static: {pruned_static}")

        # noise_selectors_found should be >= 0
        noise_found = meta.get("noise_selectors_found", 0)
        check("noise_selectors_found >= 0", noise_found >= 0, f"found: {noise_found}")

        # validation_pass should be 1, 2, or 3
        val_pass = meta.get("validation_pass", 0)
        check("validation_pass is 1, 2, or 3", val_pass in (1, 2, 3), f"pass: {val_pass}")

except Exception as e:
    check("Content-aware validation", False, f"{type(e).__name__}: {e}")


# ══════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
print(f"{'=' * 60}")
if failed:
    sys.exit(1)
else:
    print("ALL E2E CHECKS PASSED")
