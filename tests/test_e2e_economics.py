#!/usr/bin/env python3
"""test_e2e_economics.py — E2E extraction test for economics/finance/fedwatch sites.

Tests Prebextor v1.0.1 against real-world economics websites:
- News ekonomi (Bloomberg, Reuters, CNBC, FT, The Economist)
- Kalender ekonomi (Forex Factory, Investing.com, TradingEconomics)
- Fed Watch tools (CME FedWatch, Investing.com Fed Rate Monitor, MacroMicro)

Run from project root: python tests/test_e2e_economics.py
"""

import sys
import os
import json
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

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

passed = 0
failed = 0
skipped = 0
results_log = []


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


# ── Import & Instantiate ─────────────────────────────────────────────
try:
    from provider import PrebextorProvider
    from prebextor import __version__
    check("Import PrebextorProvider", True)
    check("Version is 1.0.1", __version__ == "1.0.1", f"version: {__version__}")
except ImportError as e:
    check("Import PrebextorProvider", False, str(e))
    sys.exit(1)

try:
    provider = PrebextorProvider()
    check("Instantiation", True)
    check("Provider has _scorer", hasattr(provider, "_scorer"))
    check("Provider has _validator", hasattr(provider, "_validator"))
except Exception as e:
    check("Instantiation", False, str(e))
    sys.exit(1)

avail = provider.is_available()
check("camofox is_available()", isinstance(avail, bool), f"type: {type(avail)}")

if not avail:
    skip("All E2E extraction", "camofox not available")
    print(f"\n=== Results: {passed} passed, {failed} failed, {skipped} skipped ===")
    sys.exit(0 if not failed else 1)


# ══════════════════════════════════════════════════════════════════════
# TEST SUITES
# ══════════════════════════════════════════════════════════════════════

# Kategori 1: Berita Ekonomi (5 sites)
ECONOMICS_NEWS = [
    ("Bloomberg", "https://www.bloomberg.com"),
    ("Reuters Business", "https://www.reuters.com/business/"),
    ("CNBC Economy", "https://www.cnbc.com/economy/"),
    ("Financial Times", "https://www.ft.com"),
    ("The Economist", "https://www.economist.com"),
]

# Kategori 2: Kalender Ekonomi (5 sites)
ECONOMIC_CALENDARS = [
    ("Forex Factory Calendar", "https://www.forexfactory.com/calendar"),
    ("Investing.com Calendar", "https://www.investing.com/economic-calendar"),
    ("TradingEconomics", "https://tradingeconomics.com/calendar"),
    ("DailyFX Calendar", "https://www.dailyfx.com/economic-calendar"),
    ("MQL5 Calendar", "https://www.mql5.com/en/economic-calendar"),
]

# Kategori 3: Fed Watch Tools (5 sites)
FED_WATCH_TOOLS = [
    ("CME FedWatch", "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"),
    ("Investing Fed Monitor", "https://www.investing.com/central-banks/fed-rate-monitor"),
    ("MacroMicro Fed", "https://en.macromicro.me/collections/4238/us-federal/77/probability-fed-rate-hike"),
    ("CentralBank Watch", "https://centralbank.watch/federal-reserve/"),
    ("Atlanta Fed Tracker", "https://www.atlantafed.org/research-and-data/data/market-probability-tracker"),
]


def test_category(category_name, urls):
    """Test extraction for a category of URLs."""
    global results_log

    print(f"\n{'=' * 60}")
    print(f"Category: {category_name}")
    print(f"{'=' * 60}")

    for name, url in urls:
        print(f"\n--- {name} ({url}) ---")
        try:
            t0 = time.time()
            result = provider.extract([url])
            elapsed = time.time() - t0

            check(f"[{name}] extract() returns dict", isinstance(result, dict), f"type: {type(result)}")

            if not isinstance(result, dict):
                results_log.append({
                    "name": name, "url": url, "status": "FAIL",
                    "reason": "not a dict", "time": elapsed
                })
                continue

            success = result.get("success", False)
            check(f"[{name}] success is True", success is True, f"success: {success}")

            if not success:
                error_msg = result.get("error", "unknown")
                results_log.append({
                    "name": name, "url": url, "status": "FAIL",
                    "reason": error_msg, "time": elapsed
                })
                continue

            data = result.get("data", [])
            check(f"[{name}] data has 1 item", len(data) == 1, f"len: {len(data)}")

            if not data:
                results_log.append({
                    "name": name, "url": url, "status": "FAIL",
                    "reason": "empty data", "time": elapsed
                })
                continue

            item = data[0]
            content = item.get("content", "")
            raw = item.get("raw_content", "")
            meta = item.get("metadata", {})
            title = item.get("title", "")
            error = item.get("error")

            # Basic envelope checks
            check(f"[{name}] has required keys",
                  all(k in item for k in ["url", "title", "content", "raw_content", "metadata", "error"]))

            # Content checks
            content_len = len(content)
            check(f"[{name}] content non-empty", content_len > 0, f"len: {content_len}")
            check(f"[{name}] has <extraction_result>", "<extraction_result>" in content)
            check(f"[{name}] has </extraction_result>", "</extraction_result>" in content)
            check(f"[{name}] has <main_body>", "<main_body>" in content)
            check(f"[{name}] has </main_body>", "</main_body>" in content)

            # Raw content checks
            raw_len = len(raw)
            check(f"[{name}] raw_content non-empty", raw_len > 0, f"len: {raw_len}")

            # Noise removal
            has_script = "<script" in raw.lower()
            has_style = "<style" in raw.lower()
            check(f"[{name}] no <script> in raw", not has_script, "found <script>")
            check(f"[{name}] no <style> in raw", not has_style, "found <style>")

            # v1.0.1 metadata
            check(f"[{name}] has confidence", "confidence" in meta)
            check(f"[{name}] has content_aware", "content_aware" in meta)
            check(f"[{name}] has pruned_static", "pruned_static" in meta)
            check(f"[{name}] has pruned_dynamic", "pruned_dynamic" in meta)
            check(f"[{name}] has scored_blocks_count", "scored_blocks_count" in meta)
            check(f"[{name}] has validation_pass", "validation_pass" in meta)

            conf = meta.get("confidence", 0)
            scored = meta.get("scored_blocks_count", 0)
            pruned_s = meta.get("pruned_static", 0)
            pruned_d = meta.get("pruned_dynamic", 0)
            pruned_t = meta.get("pruned_total", 0)
            val_pass = meta.get("validation_pass", 0)
            selector = meta.get("selector", "N/A")
            extractor = meta.get("extractor", "N/A")

            check(f"[{name}] confidence in [0,1]", 0.0 <= conf <= 1.0, f"conf: {conf}")
            check(f"[{name}] scored_blocks >= 0", scored >= 0, f"scored: {scored}")
            check(f"[{name}] pruned_total >= pruned_static", pruned_t >= pruned_s,
                  f"total: {pruned_t}, static: {pruned_s}")
            check(f"[{name}] validation_pass in (1,2,3)", val_pass in (1, 2, 3), f"pass: {val_pass}")

            # Error should be None
            check(f"[{name}] error is None", error is None, f"error: {error}")

            # Log result
            results_log.append({
                "name": name, "url": url, "status": "PASS",
                "time": round(elapsed, 1),
                "confidence": conf,
                "content_len": content_len,
                "raw_len": raw_len,
                "scored_blocks": scored,
                "pruned_static": pruned_s,
                "pruned_dynamic": pruned_d,
                "pruned_total": pruned_t,
                "validation_pass": val_pass,
                "selector": selector,
                "extractor": extractor,
                "title": title[:80] if title else "N/A",
            })

            # Print summary
            print(f"  >> Title: {title[:60] if title else 'N/A'}")
            print(f"  >> Selector: {selector} | Confidence: {conf:.3f}")
            print(f"  >> Content: {content_len} chars | Raw: {raw_len} chars")
            print(f"  >> Scored: {scored} | Pruned: {pruned_t} (static={pruned_s}, dynamic={pruned_d})")
            print(f"  >> Validation: Pass {val_pass} | Time: {elapsed:.1f}s")

        except Exception as e:
            check(f"[{name}] No exception", False, f"{type(e).__name__}: {e}")
            results_log.append({
                "name": name, "url": url, "status": "ERROR",
                "reason": f"{type(e).__name__}: {e}"
            })


# ── Run all categories ───────────────────────────────────────────────
test_category("Berita Ekonomi", ECONOMICS_NEWS)
test_category("Kalender Ekonomi", ECONOMIC_CALENDARS)
test_category("Fed Watch Tools", FED_WATCH_TOOLS)


# ══════════════════════════════════════════════════════════════════════
# SUMMARY REPORT
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 70}")
print("COMPREHENSIVE E2E TEST REPORT — Economics/Finance/FedWatch")
print(f"{'=' * 70}")

# Group by category
categories = [
    ("Berita Ekonomi", ECONOMICS_NEWS),
    ("Kalender Ekonomi", ECONOMIC_CALENDARS),
    ("Fed Watch Tools", FED_WATCH_TOOLS),
]

for cat_name, cat_urls in categories:
    cat_results = [r for r in results_log if any(r["name"] == n for n, _ in cat_urls)]
    if not cat_results:
        continue

    print(f"\n## {cat_name}")
    print(f"{'Site':<30} {'Status':<8} {'Conf':>6} {'Content':>8} {'Scored':>7} {'Pruned':>7} {'Pass':>5} {'Time':>6}")
    print("-" * 85)

    cat_pass = 0
    cat_fail = 0
    cat_confs = []
    cat_times = []

    for r in cat_results:
        status = r["status"]
        if status == "PASS":
            cat_pass += 1
            cat_confs.append(r["confidence"])
            cat_times.append(r["time"])
            print(f"{r['name']:<30} {status:<8} {r['confidence']:>6.3f} {r['content_len']:>8} {r['scored_blocks']:>7} {r['pruned_total']:>7} {r['validation_pass']:>5} {r['time']:>5.1f}s")
        else:
            cat_fail += 1
            reason = r.get("reason", "unknown")[:40]
            print(f"{r['name']:<30} {status:<8} {'N/A':>6} {'N/A':>8} {'N/A':>7} {'N/A':>7} {'N/A':>5} {'N/A':>6}")
            print(f"  >> Reason: {reason}")

    avg_conf = sum(cat_confs) / len(cat_confs) if cat_confs else 0
    avg_time = sum(cat_times) / len(cat_times) if cat_times else 0
    print(f"\n  Category: {cat_pass} pass / {cat_fail} fail | Avg Confidence: {avg_conf:.3f} | Avg Time: {avg_time:.1f}s")

# Overall summary
all_pass = sum(1 for r in results_log if r["status"] == "PASS")
all_fail = sum(1 for r in results_log if r["status"] != "PASS")
all_confs = [r["confidence"] for r in results_log if r["status"] == "PASS"]
all_times = [r["time"] for r in results_log if r["status"] == "PASS"]
all_scored = [r["scored_blocks"] for r in results_log if r["status"] == "PASS"]
all_pruned = [r["pruned_total"] for r in results_log if r["status"] == "PASS"]

print(f"\n{'=' * 70}")
print(f"OVERALL: {all_pass} passed / {all_fail} failed out of {len(results_log)} sites")
if all_confs:
    print(f"  Avg Confidence: {sum(all_confs)/len(all_confs):.3f} (min={min(all_confs):.3f}, max={max(all_confs):.3f})")
    print(f"  Avg Time: {sum(all_times)/len(all_times):.1f}s (min={min(all_times):.1f}s, max={max(all_times):.1f}s)")
    print(f"  Avg Scored Blocks: {sum(all_scored)/len(all_scored):.0f}")
    print(f"  Avg Pruned Nodes: {sum(all_pruned)/len(all_pruned):.0f}")
print(f"{'=' * 70}")

# Export JSON report
report_path = os.path.join(PROJECT_ROOT, "tests", "report_economics.json")
with open(report_path, "w") as f:
    json.dump({
        "version": __version__,
        "total": len(results_log),
        "passed": all_pass,
        "failed": all_fail,
        "results": results_log
    }, f, indent=2)
print(f"\nJSON report saved: {report_path}")

if failed:
    sys.exit(1)
else:
    print("\nALL E2E CHECKS PASSED")
