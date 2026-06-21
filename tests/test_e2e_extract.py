#!/usr/bin/env python3
"""test_e2e_extract.py — End-to-end extraction test with real websites.

Tests the full Prebextor pipeline against multiple real domains.
Requires camofox CLI to be installed and available.
"""

import sys
import os
import json

# Add plugin dir to path
PLUGIN_DIR = os.path.expanduser("~/.hermes/plugins/web")
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

passed = 0
failed = 0
skipped = 0


def check(label, condition, detail=""):
    global passed, failed, skipped
    num = passed + failed + skipped + 1
    if condition:
        passed += 1
        print(f"[{num}] PASS: {label}")
    else:
        failed += 1
        print(f"[{num}] FAIL: {label} — {detail}")


def skip(label, reason=""):
    global skipped
    num = passed + failed + skipped + 1
    skipped += 1
    print(f"[{num}] SKIP: {label} — {reason}")


print("=" * 60)
print("Prebextor E2E Extraction Test")
print("=" * 60)

# 1. Import
try:
    from prebextor import PrebextorProvider
    check("Import PrebextorProvider", True)
except ImportError as e:
    check("Import PrebextorProvider", False, str(e))
    sys.exit(1)

# 2. Instantiate
try:
    provider = PrebextorProvider()
    check("Instantiation", True)
except Exception as e:
    check("Instantiation", False, str(e))
    sys.exit(1)

# 3. Check availability
avail = provider.is_available()
check("camofox is_available()", isinstance(avail, bool), f"type: {type(avail)}")

if not avail:
    skip("E2E extraction", "camofox not available")
    print(f"\n=== Results: {passed} passed, {failed} failed, {skipped} skipped ===")
    sys.exit(0 if not failed else 1)

# 4. Run extraction on example.com
print("\n--- Test 1: https://example.com ---")
try:
    result = provider.extract(["https://example.com"])
    check("extract() returns dict", isinstance(result, dict), f"type: {type(result)}")

    if isinstance(result, dict):
        # Envelope validation
        check("Envelope has 'success' key", "success" in result, f"keys: {list(result.keys())}")
        check("Envelope has 'data' key", "data" in result, f"keys: {list(result.keys())}")
        check("success is True", result.get("success") is True)

        data = result.get("data", [])
        check("data is list", isinstance(data, list))
        check("data has 1 element", len(data) == 1, f"len: {len(data)}")

        if data:
            item = data[0]
            check("item has all required keys", all(k in item for k in ["url", "title", "content", "raw_content", "metadata", "error"]))

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

            # metadata validation
            meta = item.get("metadata", {})
            check("metadata has 'selector'", "selector" in meta)
            check("metadata has 'extractor'", "extractor" in meta)
            check("metadata extractor == 'prebextor'", meta.get("extractor") == "prebextor")
            check("metadata has 'pipeline'", "pipeline" in meta)

            # Error should be None
            check("error is None", item.get("error") is None, f"error: {item.get('error')}")

            # Title is non-empty
            check("title is non-empty", len(item.get("title", "")) > 0, f"title: {item.get('title')!r}")

            # URL matches
            check("url matches", item.get("url") == "https://example.com")

            # No noise in raw_content
            noise_tags = ["<script", "<style", "<iframe"]
            for tag in noise_tags:
                check(f"No {tag} in raw_content", tag.lower() not in raw.lower(), f"found {tag}")

            # Content has markdown heading
            check("content has markdown heading", "#" in content)

            # Print summary
            print(f"\n--- Extraction Summary ---")
            print(f"Title: {item.get('title', 'N/A')}")
            print(f"Selector: {meta.get('selector', 'N/A')}")
            print(f"Content length: {len(content)} chars")
            print(f"Raw HTML length: {len(raw)} chars")
            print(f"Content preview (first 300 chars):")
            print(content[:300])
except Exception as e:
    check("Extraction succeeded", False, f"{type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# 5. Test batch extraction (2 URLs)
print("\n--- Test 2: Batch extraction (2 URLs) ---")
try:
    result2 = provider.extract(["https://example.com", "https://example.com"])
    check("Batch returns dict", isinstance(result2, dict))
    check("Batch success is True", result2.get("success") is True)
    check("Batch data has 2 items", len(result2.get("data", [])) == 2)
except Exception as e:
    check("Batch extraction succeeded", False, f"{type(e).__name__}: {e}")

print(f"\n=== Results: {passed} passed, {failed} failed, {skipped} skipped ===")
if failed:
    sys.exit(1)
else:
    print("ALL E2E CHECKS PASSED")
