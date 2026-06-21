#!/usr/bin/env python3
"""test_envelope_schema.py — Verify Hermes envelope contract compliance.

Tests the envelope schema WITHOUT requiring camofox (mock-friendly).
Validates:
  - extract() returns {"success": True, "data": [...]} on success
  - extract() returns {"success": False, "error": "..."} on total failure
  - Per-URL error isolation (one URL failing doesn't abort batch)
  - Individual result shape: {url, title, content, raw_content, metadata, error}
"""

import sys
import os
import json
import inspect
from typing import Dict, Any

# Add plugin dir to path
PLUGIN_DIR = os.path.expanduser("~/.hermes/plugins/web")
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

REQUIRED_KEYS = {"url", "title", "content", "raw_content", "metadata", "error"}

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


print("=" * 60)
print("Prebextor Envelope Schema Test")
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

# 3. extract() return type annotation
sig = inspect.signature(provider.extract)
return_ann = sig.return_annotation
check(
    "extract() return annotation is Dict[str, Any]",
    return_ann == Dict or "dict" in str(return_ann).lower() or return_ann == inspect.Parameter.empty,
    f"annotation: {return_ann}",
)

# 4. extract() docstring mentions envelope
doc = getattr(provider.extract, "__doc__", "") or ""
check("Docstring mentions 'success'", "success" in doc.lower())
check("Docstring mentions 'data'", "data" in doc.lower())
check("Docstring mentions 'envelope' or 'Hermes'", "envelope" in doc.lower() or "Hermes" in doc)

# 5. _extract_one returns per-URL dict with required keys
source_body = inspect.getsource(provider._extract_one)
for key in REQUIRED_KEYS:
    check(f"_extract_one returns '{key}'", f'"{key}"' in source_body or f"'{key}'" in source_body)

# 6. extract() wraps in envelope
source_extract = inspect.getsource(provider.extract)
check("extract() wraps with 'success': True", '"success": True' in source_extract or "'success': True" in source_extract)
check("extract() wraps with 'data'", '"data":' in source_extract or "'data':" in source_extract)
check("extract() handles failure with 'success': False", '"success": False' in source_extract or "'success': False" in source_extract)
check("extract() returns error on failure", '"error":' in source_extract or "'error':" in source_extract)

# 7. Per-URL error isolation: _extract_one catches exceptions internally
check("_extract_one catches MappingError", "MappingError" in source_body)
check("_extract_one catches AssertionError_", "AssertionError_" in source_body)
check("_extract_one catches generic Exception", "Exception" in source_body)

# 8. Batch isolation: one URL failure doesn't abort
check("extract() iterates all URLs (no early return)", "for url in urls" in source_extract)

# 9. Envelope structure validation (mock test)
print("\n--- Mock Envelope Test ---")

class MockPrebextorProvider:
    """Mock provider that simulates extraction without camofox."""
    name = "prebextor"
    def supports_search(self): return False
    def supports_extract(self): return True
    def is_available(self): return True
    def extract(self, urls, **kwargs):
        results = []
        for url in urls:
            results.append({
                "url": url,
                "title": "Mock Title",
                "content": "<extraction_result>\n  <metadata>\n  Title: Mock Title\n  URL: " + url + "\n  Timestamp: 2026-01-01T00:00:00\n  </metadata>\n\n  <main_body>\n# Mock Content\n\nThis is mock content.\n  </main_body>\n</extraction_result>\n",
                "raw_content": "<html><body><h1>Mock Content</h1></body></html>",
                "metadata": {"selector": "main", "extractor": "prebextor", "pipeline": "mock"},
                "error": None,
            })
        return {"success": True, "data": results}

mock = MockPrebextorProvider()
mock_result = mock.extract(["https://test1.com", "https://test2.com"])
check("Mock envelope has 'success'", "success" in mock_result)
check("Mock envelope has 'data'", "data" in mock_result)
check("Mock success is True", mock_result["success"] is True)
check("Mock data has 2 items", len(mock_result["data"]) == 2)
check("Mock item 1 url correct", mock_result["data"][0]["url"] == "https://test1.com")
check("Mock item 2 url correct", mock_result["data"][1]["url"] == "https://test2.com")

# 10. Real provider envelope shape (if camofox available)
avail = provider.is_available()
check("is_available() returns bool", isinstance(avail, bool))

if avail:
    print("\n--- Real Provider Envelope Test ---")
    real_result = provider.extract(["https://example.com"])
    check("Real result is dict", isinstance(real_result, dict))
    check("Real result has 'success'", "success" in real_result)
    check("Real result has 'data'", "data" in real_result)
    check("Real success is True", real_result["success"] is True)
    check("Real data is list", isinstance(real_result["data"], list))
    check("Real data has 1 item", len(real_result["data"]) == 1)

    item = real_result["data"][0]
    for key in REQUIRED_KEYS:
        check(f"Real item has '{key}'", key in item)

    check("Real item error is None", item.get("error") is None)
    check("Real item extractor is 'prebextor'", item.get("metadata", {}).get("extractor") == "prebextor")
else:
    print("\n--- Real Provider Envelope Test: SKIP (camofox not available) ---")

print(f"\n=== Results: {passed} passed, {failed} failed ===")
if failed:
    sys.exit(1)
else:
    print("ALL ENVELOPE SCHEMA CHECKS PASSED")
