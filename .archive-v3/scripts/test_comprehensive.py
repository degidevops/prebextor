#!/usr/bin/env python3
"""
Prebextor v3.1 — Comprehensive Multi-Site Validation Test
Tests 35+ websites across 7 categories with detailed metrics.
"""

import sys
import json
import time
import traceback

sys.path.insert(0, '/home/degi/project/prebextor')
from prebextor.provider import PrebextorProvider

provider = PrebextorProvider()

# ============================================================
# TEST SUITE: 35+ websites, 7 categories
# ============================================================
TEST_SITES = {
    "News/Article": [
        "https://www.bbc.com/news",
        "https://www.cnn.com",
        "https://www.reuters.com",
        "https://www.theguardian.com/international",
        "https://www.aljazeera.com",
        "https://news.ycombinator.com",
    ],
    "E-commerce/Product": [
        "https://www.amazon.com/dp/B08N5WRWNW",
        "https://www.ebay.com/itm/123456789",
        "https://www.etsy.com",
        "https://www.walmart.com",
        "https://www.bestbuy.com",
    ],
    "SPA/Dynamic JS": [
        "https://twitter.com",
        "https://www.reddit.com",
        "https://www.linkedin.com",
        "https://www.instagram.com",
        "https://www.youtube.com",
        "https://www.facebook.com",
    ],
    "Blog/Content": [
        "https://medium.com",
        "https://dev.to",
        "https://hashnode.com",
        "https://www.wordpress.com",
        "https://www.blogger.com",
        "https://substack.com",
    ],
    "Corporate/Info": [
        "https://www.apple.com",
        "https://www.microsoft.com",
        "https://www.google.com",
        "https://www.mozilla.org",
        "https://www.wikipedia.org",
        "https://www.github.com",
    ],
    "Data-heavy/Table": [
        "https://www.w3schools.com/html/html_tables.asp",
        "https://en.wikipedia.org/wiki/List_of_countries_by_GDP_(nominal)",
        "https://www.worldometers.info/world-population/",
        "https://finance.yahoo.com/quote/AAPL/",
        "https://www.tradingeconomics.com/united-states/interest-rate",
        "https://coinmarketcap.com",
    ],
    "Education/Reference": [
        "https://www.khanacademy.org",
        "https://www.coursera.org",
        "https://www.nationalgeographic.com",
        "https://weather.com",
        "https://stackoverflow.com",
        "https://github.com/trending",
    ],
}


def test_url(url, timeout=90):
    """Test a single URL. Returns result dict."""
    start = time.time()
    try:
        result = provider.extract([url], wait_after_scroll=5000)
        elapsed = time.time() - start

        if result.get('success') and result.get('data'):
            item = result['data'][0]
            content = item.get('content', '')
            metadata = item.get('metadata', {})
            error = item.get('error')

            content_len = len(content) if content else 0
            title = item.get('title', '')
            selector = metadata.get('selector', '')
            pruned = metadata.get('pruned_nodes', 0)
            iframes = metadata.get('iframes_extracted', 0)
            text_len = metadata.get('text_length', 0)

            has_content = content_len > 100
            has_error = error is not None

            status = "PASS" if (has_content and not has_error) else "FAIL"

            return {
                "url": url,
                "status": status,
                "title": title[:100] if title else "",
                "content_len": content_len,
                "text_len": text_len,
                "selector": selector,
                "pruned": pruned,
                "iframes": iframes,
                "error": str(error)[:200] if error else "",
                "elapsed": round(elapsed, 1),
            }
        else:
            return {
                "url": url,
                "status": "FAIL",
                "title": "",
                "content_len": 0,
                "text_len": 0,
                "selector": "",
                "pruned": 0,
                "iframes": 0,
                "error": result.get('error', 'unknown')[:200],
                "elapsed": round(elapsed, 1),
            }
    except Exception as e:
        return {
            "url": url,
            "status": "ERROR",
            "title": "",
            "content_len": 0,
            "text_len": 0,
            "selector": "",
            "pruned": 0,
            "iframes": 0,
            "error": str(e)[:200],
            "elapsed": round(time.time() - start, 1),
        }


# ============================================================
# RUN TESTS
# ============================================================
print("=" * 80)
print("PREBEXTOR v3.1 — COMPREHENSIVE MULTI-SITE VALIDATION TEST")
print("=" * 80)
print()

all_results = {}
total_pass = 0
total_fail = 0
total_error = 0
total_sites = 0

for category, urls in TEST_SITES.items():
    print(f"\n{'─' * 80}")
    print(f"CATEGORY: {category}")
    print(f"{'─' * 80}")

    category_results = []
    for url in urls:
        total_sites += 1
        print(f"  [{total_sites:02d}] Testing: {url[:70]}...", end=" ", flush=True)

        result = test_url(url)
        category_results.append(result)

        status_icon = "✓" if result["status"] == "PASS" else ("✗" if result["status"] == "FAIL" else "!")
        print(f"{status_icon} {result['status']} | {result['content_len']} chars | {result['elapsed']}s")

        if result["status"] == "PASS":
            total_pass += 1
        elif result["status"] == "FAIL":
            total_fail += 1
        else:
            total_error += 1

        if result["error"]:
            print(f"       Error: {result['error'][:100]}")

    all_results[category] = category_results

# ============================================================
# SUMMARY
# ============================================================
print(f"\n{'=' * 80}")
print("SUMMARY")
print(f"{'=' * 80}")
print(f"Total sites: {total_sites}")
print(f"PASS: {total_pass} ({total_pass*100//total_sites if total_sites else 0}%)")
print(f"FAIL: {total_fail} ({total_fail*100//total_sites if total_sites else 0}%)")
print(f"ERROR: {total_error} ({total_error*100//total_sites if total_sites else 0}%)")
print()

for category, results in all_results.items():
    cat_pass = sum(1 for r in results if r["status"] == "PASS")
    cat_total = len(results)
    cat_rate = f"{cat_pass*100//cat_total}%" if cat_total else "N/A"
    print(f"  {category}: {cat_pass}/{cat_total} PASS ({cat_rate})")

    for r in results:
        icon = "✓" if r["status"] == "PASS" else ("✗" if r["status"] == "FAIL" else "!")
        print(f"    {icon} {r['url'][:65]:65s} | {r['content_len']:>7,} chars | sel={r['selector'][:30]}")
        if r["error"]:
            print(f"      Error: {r['error'][:100]}")

# Save results to file
with open('/tmp/test_results_v31.json', 'w') as f:
    json.dump({
        "summary": {
            "total": total_sites,
            "pass": total_pass,
            "fail": total_fail,
            "error": total_error,
            "pass_rate": f"{total_pass*100//total_sites if total_sites else 0}%"
        },
        "results": all_results
    }, f, indent=2)

print(f"\nResults saved to /tmp/test_results_v31.json")
