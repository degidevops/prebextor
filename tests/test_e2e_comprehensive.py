#!/usr/bin/env python3
"""test_e2e_comprehensive.py — Comprehensive E2E test across website categories.

Tests Prebextor v1.0.1 against diverse real-world websites:
  1. News articles (BBC, Reuters, AP, Guardian, Al Jazeera)
  2. Blogs (Medium, Dev.to, Hashnode, WordPress, Ghost)
  3. Documentation (MDN, Python docs, Rust docs, Go docs, Django docs)
  4. E-commerce (Amazon product, eBay, Etsy, Shopify, AliExpress)
  5. Forums (Stack Overflow, Reddit, Hacker News, Quora, GitHub Discussions)
  6. Wikipedia (en, id, simple)
  7. Government (usa.gov, gov.uk, go.id)
  8. Social media profiles (Twitter/X, LinkedIn, GitHub)

Each category tests 5 URLs. Total: 40 URLs.
Requires camofox CLI to be installed and running.

Run from project root: python tests/test_e2e_comprehensive.py
"""

import sys
import os
import time
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ── Package setup ───────────────────────────────────────────────────
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

PrebextorProvider = sys.modules['prebextor.provider'].PrebextorProvider
__version__ = prebextor_pkg.__version__

# ── Test infrastructure ─────────────────────────────────────────────
passed = 0
failed = 0
skipped = 0
errors = []


def check(label, condition, detail=""):
    global passed, failed, skipped
    num = passed + failed + skipped + 1
    if condition:
        passed += 1
        print(f"  [{num:2d}] PASS: {label}")
    else:
        failed += 1
        errors.append(f"FAIL: {label} — {detail}")
        print(f"  [{num:2d}] FAIL: {label} — {detail}")


def skip(label, reason=""):
    global skipped
    num = passed + failed + skipped + 1
    skipped += 1
    print(f"  [{num:2d}] SKIP: {label} — {reason}")


# ── Provider setup ──────────────────────────────────────────────────
print("=" * 70)
print("Prebextor v1.0.1 — Comprehensive E2E Test")
print("=" * 70)

try:
    provider = PrebextorProvider()
    print(f"Version: {__version__}")
    print(f"CamoFox available: {provider.is_available()}")
except Exception as e:
    print(f"ERROR: Failed to instantiate provider: {e}")
    sys.exit(1)

if not provider.is_available():
    print("SKIP: CamoFox not available")
    sys.exit(0)

# ══════════════════════════════════════════════════════════════════════
# WEBSITE CATEGORIES
# ══════════════════════════════════════════════════════════════════════

CATEGORIES = {
    "News Articles": [
        "https://www.bbc.com/news/world",
        "https://www.reuters.com/world/",
        "https://apnews.com/",
        "https://www.theguardian.com/international",
        "https://www.aljazeera.com/news/",
    ],
    "Blogs": [
        "https://medium.com/",
        "https://dev.to/",
        "https://hashnode.com/",
        "https://wordpress.com/",
        "https://ghost.org/",
    ],
    "Documentation": [
        "https://developer.mozilla.org/en-US/docs/Web/HTML",
        "https://docs.python.org/3/tutorial/",
        "https://doc.rust-lang.org/book/",
        "https://go.dev/doc/",
        "https://docs.djangoproject.com/en/stable/",
    ],
    "E-commerce": [
        "https://www.amazon.com/dp/B08N5WRWNW",
        "https://www.ebay.com/itm/123456789",
        "https://www.etsy.com/listing/123456789",
        "https://www.shopify.com/",
        "https://www.aliexpress.com/item/123456789.html",
    ],
    "Forums & Q&A": [
        "https://stackoverflow.com/questions",
        "https://www.reddit.com/r/programming/",
        "https://news.ycombinator.com/",
        "https://www.quora.com/topic/Programming",
        "https://github.com/orgs/community/discussions",
    ],
    "Wikipedia": [
        "https://en.wikipedia.org/wiki/Web_scraping",
        "https://id.wikipedia.org/wiki/Web_scraping",
        "https://simple.wikipedia.org/wiki/Web_scraping",
        "https://en.wikipedia.org/wiki/Python_(programming_language)",
        "https://en.wikipedia.org/wiki/Artificial_intelligence",
    ],
    "Government": [
        "https://www.usa.gov/",
        "https://www.gov.uk/",
        "https://www.go.id/",
        "https://www.gov.br/",
        "https://www.australia.gov.au/",
    ],
    "Reference/Encyclopedia": [
        "https://www.britannica.com/topic/artificial-intelligence",
        "https://www.wikipedia.org/",
        "https://www.w3.org/",
        "https://ietf.org/",
        "https://www.iso.org/",
    ],
}

# ── Results storage ─────────────────────────────────────────────────
all_results = {}
total_urls = 0
total_success = 0
total_failed = 0
total_skipped = 0

# ══════════════════════════════════════════════════════════════════════
# RUN TESTS PER CATEGORY
# ══════════════════════════════════════════════════════════════════════

for category, urls in CATEGORIES.items():
    print(f"\n{'=' * 70}")
    print(f"Category: {category}")
    print(f"{'=' * 70}")

    cat_results = []
    cat_pass = 0
    cat_fail = 0
    cat_skip = 0

    for url in urls:
        total_urls += 1
        print(f"\n  URL: {url}")
        start_time = time.time()

        try:
            result = provider.extract([url], timeout=30)
            elapsed = time.time() - start_time

            if not isinstance(result, dict):
                check("Returns dict", False, f"type: {type(result)}")
                cat_fail += 1
                total_failed += 1
                continue

            success = result.get("success", False)
            if not success:
                error_msg = result.get("error", "Unknown error")
                check("Extraction success", False, error_msg)
                cat_fail += 1
                total_failed += 1
                cat_results.append({"url": url, "status": "failed", "error": error_msg})
                continue

            data = result.get("data", [])
            if not data:
                check("Has data", False, "empty data")
                cat_fail += 1
                total_failed += 1
                continue

            item = data[0]
            meta = item.get("metadata", {})

            # ── Core validation ────────────────────────────────────
            check("Has content", len(item.get("content", "")) > 0,
                  f"len: {len(item.get('content', ''))}")
            check("Has title", len(item.get("title", "")) > 0,
                  f"title: {item.get('title', '')!r}")
            check("Has selector", "selector" in meta)
            check("Extractor is v3.1", meta.get("extractor") == "prebextor-v3.1",
                  f"extractor: {meta.get('extractor')}")
            check("Pipeline has score", "score" in meta.get("pipeline", ""))
            check("Pipeline has validate", "validate" in meta.get("pipeline", ""))

            # ── v1.0.1 content-aware validation ────────────────────
            check("Has confidence", "confidence" in meta)
            check("content_aware is True", meta.get("content_aware") is True)
            check("Has scored_blocks_count", "scored_blocks_count" in meta)
            check("Has pruned_total", "pruned_total" in meta)
            check("Has validation_pass", "validation_pass" in meta)

            # ── Confidence value validation ────────────────────────
            conf = meta.get("confidence", 0)
            check("Confidence is float", isinstance(conf, (int, float)),
                  f"type: {type(conf)}")
            check("Confidence >= 0.0", conf >= 0.0, f"confidence: {conf}")
            check("Confidence <= 1.0", conf <= 1.0, f"confidence: {conf}")

            # ── Content quality ────────────────────────────────────
            content = item.get("content", "")
            raw = item.get("raw_content", "")
            check("Content has XML wrapper", "<extraction_result>" in content)
            check("Content has main_body", "<main_body>" in content)
            check("Raw content is HTML", "<" in raw and ">" in raw)

            # ── Noise removal ──────────────────────────────────────
            check("No <script in raw", "<script" not in raw.lower())
            check("No <style in raw", "<style" not in raw.lower())

            # ── Performance ────────────────────────────────────────
            check("Elapsed < 30s", elapsed < 30, f"elapsed: {elapsed:.1f}s")

            # ── Store result ───────────────────────────────────────
            cat_results.append({
                "url": url,
                "status": "success",
                "title": item.get("title", ""),
                "selector": meta.get("selector", ""),
                "confidence": conf,
                "content_length": len(content),
                "raw_length": len(raw),
                "scored_blocks": meta.get("scored_blocks_count", 0),
                "pruned_static": meta.get("pruned_static", 0),
                "pruned_dynamic": meta.get("pruned_dynamic", 0),
                "pruned_total": meta.get("pruned_total", 0),
                "validation_pass": meta.get("validation_pass", 0),
                "elapsed": round(elapsed, 1),
            })

            cat_pass += 1
            total_success += 1

            print(f"    -> conf={conf:.3f}, selector={meta.get('selector', '?')}, "
                  f"scored={meta.get('scored_blocks_count', 0)}, "
                  f"pruned={meta.get('pruned_total', 0)}, "
                  f"time={elapsed:.1f}s")

        except Exception as e:
            elapsed = time.time() - start_time
            check("No exception", False, f"{type(e).__name__}: {e}")
            cat_fail += 1
            total_failed += 1
            cat_results.append({"url": url, "status": "error", "error": str(e)})

    all_results[category] = cat_results

    print(f"\n  --- {category} Summary: {cat_pass} OK, {cat_fail} FAIL ---")

# ══════════════════════════════════════════════════════════════════════
# FINAL REPORT
# ══════════════════════════════════════════════════════════════════════

print(f"\n{'=' * 70}")
print("COMPREHENSIVE TEST REPORT")
print(f"{'=' * 70}")

print(f"\nTotal URLs tested: {total_urls}")
print(f"Successful: {total_success}")
print(f"Failed: {total_failed}")
print(f"Success rate: {total_success/max(total_urls,1)*100:.1f}%")

# Per-category summary
print(f"\n{'Category':<25} {'OK':>4} {'FAIL':>4} {'Rate':>6} {'Avg Conf':>10} {'Avg Time':>10}")
print("-" * 65)

for category, results in all_results.items():
    ok = sum(1 for r in results if r["status"] == "success")
    fail = sum(1 for r in results if r["status"] != "success")
    rate = f"{ok/max(len(results),1)*100:.0f}%"

    confs = [r.get("confidence", 0) for r in results if r["status"] == "success"]
    avg_conf = f"{sum(confs)/max(len(confs),1):.3f}" if confs else "N/A"

    times = [r.get("elapsed", 0) for r in results if r["status"] == "success"]
    avg_time = f"{sum(times)/max(len(times),1):.1f}s" if times else "N/A"

    print(f"{category:<25} {ok:>4} {fail:>4} {rate:>6} {avg_conf:>10} {avg_time:>10}")

# Detailed results
print(f"\n{'=' * 70}")
print("DETAILED RESULTS")
print(f"{'=' * 70}")

for category, results in all_results.items():
    print(f"\n--- {category} ---")
    for r in results:
        status = r["status"]
        url = r["url"]
        if status == "success":
            print(f"  OK  {url}")
            print(f"       conf={r['confidence']:.3f}, sel={r['selector']}, "
                  f"scored={r['scored_blocks']}, pruned={r['pruned_total']}, "
                  f"time={r['elapsed']}s")
        else:
            print(f"  ERR {url}")
            print(f"       {r.get('error', 'Unknown error')}")

# Content-aware analysis
print(f"\n{'=' * 70}")
print("CONTENT-AWARE ANALYSIS")
print(f"{'=' * 70}")

all_success = []
for results in all_results.values():
    all_success.extend([r for r in results if r["status"] == "success"])

if all_success:
    confs = [r["confidence"] for r in all_success]
    scored = [r["scored_blocks"] for r in all_success]
    pruned = [r["pruned_total"] for r in all_success]
    times = [r["elapsed"] for r in all_success]

    print("\nConfidence:")
    print(f"  Min:    {min(confs):.3f}")
    print(f"  Max:    {max(confs):.3f}")
    print(f"  Mean:   {sum(confs)/len(confs):.3f}")
    print(f"  Median: {sorted(confs)[len(confs)//2]:.3f}")

    print("\nScored blocks:")
    print(f"  Min:    {min(scored)}")
    print(f"  Max:    {max(scored)}")
    print(f"  Mean:   {sum(scored)/len(scored):.1f}")

    print("\nPruned nodes:")
    print(f"  Min:    {min(pruned)}")
    print(f"  Max:    {max(pruned)}")
    print(f"  Mean:   {sum(pruned)/len(pruned):.1f}")

    print("\nTiming:")
    print(f"  Min:    {min(times):.1f}s")
    print(f"  Max:    {max(times):.1f}s")
    print(f"  Mean:   {sum(times)/len(times):.1f}s")

    # Validation pass distribution
    passes = [r.get("validation_pass", 0) for r in all_success]
    print("\nValidation pass distribution:")
    for p in (1, 2, 3):
        count = sum(1 for v in passes if v == p)
        print(f"  Pass {p}: {count} ({count/max(len(passes),1)*100:.0f}%)")

# Final verdict
print(f"\n{'=' * 70}")
if total_failed == 0:
    print("ALL COMPREHENSIVE TESTS PASSED")
else:
    print(f"FAILURES: {total_failed} URLs failed")
    for e in errors[:20]:
        print(f"  {e}")
print(f"{'=' * 70}")

# Save results to JSON
results_path = os.path.join(PROJECT_ROOT, "tests", "results_comprehensive.json")
with open(results_path, 'w') as f:
    json.dump({
        "version": __version__,
        "total_urls": total_urls,
        "success": total_success,
        "failed": total_failed,
        "results": all_results,
    }, f, indent=2, default=str)
print(f"\nResults saved to: {results_path}")

if total_failed > 0:
    sys.exit(1)
