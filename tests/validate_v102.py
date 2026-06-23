#!/usr/bin/env python3
"""validate_v102.py — Content validation for v102 fixes.

Tests the same sites as v101 to compare results.
Run: python tests/validate_v102.py
"""
import sys, os, json, time

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

print(f"Prebextor version: {__version__}")
provider = PrebextorProvider()

# Sites that were problematic in v1.0.1
PROBLEMATIC_SITES = [
    ("Bloomberg (anti-bot)", "https://www.bloomberg.com"),
    ("CNBC Economy (JS-render)", "https://www.cnbc.com/economy/"),
    ("CME FedWatch (JS-render)", "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"),
    ("The Economist (over-prune)", "https://www.economist.com"),
    ("Financial Times (paywall)", "https://www.ft.com"),
    ("Forex Factory (wrong selector)", "https://www.forexfactory.com/calendar"),
    ("Investing.com Calendar (wrong selector)", "https://www.investing.com/economic-calendar"),
    ("DailyFX (redirect)", "https://www.dailyfx.com/economic-calendar"),
    ("CentralBank Watch (breadcrumb)", "https://centralbank.watch/federal-reserve/"),
    # Sites that worked in v1.0.1 — verify still work
    ("Reuters Business (should work)", "https://www.reuters.com/business/"),
    ("MQL5 Calendar (should work)", "https://www.mql5.com/en/economic-calendar"),
    ("Atlanta Fed Tracker (should work)", "https://www.atlantafed.org/research-and-data/data/market-probability-tracker"),
    ("TradingEconomics (should work)", "https://tradingeconomics.com/calendar"),
    ("MacroMicro Fed (should work)", "https://en.macromicro.me/collections/4238/us-federal/77/probability-fed-rate-hike"),
]

results = []
for name, url in PROBLEMATIC_SITES:
    print(f"\n{'='*70}")
    print(f"VALIDATING: {name}")
    print(f"URL: {url}")
    print(f"{'='*70}")

    try:
        t0 = time.time()
        result = provider.extract([url])
        elapsed = time.time() - t0

        success = result.get("success", False)
        error = result.get("error")

        if not success:
            print(f"RESULT: FAILED — {error}")
            results.append({"name": name, "url": url, "status": "FAIL", "error": error, "time": round(elapsed, 1)})
            continue

        item = result["data"][0]
        content = item.get("content", "")
        raw = item.get("raw_content", "")
        meta = item.get("metadata", {})
        title = item.get("title", "")
        item_error = item.get("error")

        print(f"Title: {title}")
        print(f"Selector: {meta.get('selector', 'N/A')}")
        print(f"Confidence: {meta.get('confidence', 0):.3f}")
        print(f"Content length: {len(content)} chars")
        print(f"Raw length: {len(raw)} chars")
        print(f"Error: {item_error}")
        print(f"Time: {elapsed:.1f}s")

        # v1.0.2 specific checks
        anti_bot = meta.get("anti_bot_detected", False)
        empty_content = meta.get("empty_content", False)

        if anti_bot:
            print(f"✅ ANTI-BOT DETECTED — correctly flagged")
            status = "PASS (anti-bot)"
        elif empty_content:
            print(f"✅ EMPTY CONTENT DETECTED — correctly flagged")
            status = "PASS (empty)"
        elif item_error:
            print(f"⚠️  ERROR: {item_error}")
            status = "ERROR"
        elif len(content) < 100:
            print(f"⚠️  SHORT CONTENT ({len(content)} chars)")
            status = "SHORT"
        elif len(content) > 500:
            print(f"✅ GOOD CONTENT ({len(content)} chars)")
            status = "PASS"
        else:
            print(f"⚡ MODERATE CONTENT ({len(content)} chars)")
            status = "OK"

        results.append({
            "name": name, "url": url, "status": status,
            "confidence": meta.get("confidence", 0),
            "content_len": len(content),
            "error": item_error,
            "anti_bot": anti_bot,
            "empty_content": empty_content,
            "time": round(elapsed, 1),
        })

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        results.append({"name": name, "url": url, "status": "EXCEPTION", "error": str(e)})

# Summary
print(f"\n{'='*70}")
print("V1.0.2 VALIDATION SUMMARY")
print(f"{'='*70}")

for r in results:
    status = r["status"]
    conf = r.get("confidence", 0)
    clen = r.get("content_len", 0)
    err = r.get("error", "")
    t = r.get("time", 0)
    print(f"{r['name']:<40} {status:<20} conf={conf:.3f} len={clen:>6} {t:>5.1f}s {err[:40] if err else ''}")

# Count
pass_count = sum(1 for r in results if r["status"].startswith("PASS") or r["status"] in ("OK", "SHORT"))
fail_count = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "EXCEPTION"))
anti_bot_count = sum(1 for r in results if r.get("anti_bot"))
empty_count = sum(1 for r in results if r.get("empty_content"))

print(f"\nTotal: {len(results)} | Pass/OK: {pass_count} | Fail: {fail_count}")
print(f"Anti-bot detected: {anti_bot_count} | Empty content detected: {empty_count}")

# Save report
report_path = os.path.join(PROJECT_ROOT, "tests", "report_v102_validation.json")
with open(report_path, "w") as f:
    json.dump({"version": __version__, "results": results}, f, indent=2)
print(f"\nReport saved: {report_path}")
