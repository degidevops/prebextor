#!/usr/bin/env python3
"""validate_content.py — Content validation for economics/finance/fedwatch sites.

Extracts and displays full content for manual verification.
Run: python tests/validate_content.py
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
provider = PrebextorProvider()

# Sites to validate — pick representative ones
SITES = [
    # Anti-bot / challenge page
    ("Bloomberg (anti-bot check)", "https://www.bloomberg.com"),
    # Good content expected
    ("Reuters Business", "https://www.reuters.com/business/"),
    # JS-heavy, low content
    ("CNBC Economy", "https://www.cnbc.com/economy/"),
    # Paywall site
    ("Financial Times", "https://www.ft.com"),
    # Huge HTML table
    ("TradingEconomics", "https://tradingeconomics.com/calendar"),
    # Best calendar
    ("MQL5 Calendar", "https://www.mql5.com/en/economic-calendar"),
    # Fed watch with data
    ("CME FedWatch", "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"),
    # Best fed watch
    ("Atlanta Fed Tracker", "https://www.atlantafed.org/research-and-data/data/market-probability-tracker"),
    # MacroMicro
    ("MacroMicro Fed", "https://en.macromicro.me/collections/4238/us-federal/77/probability-fed-rate-hike"),
]

for name, url in SITES:
    print(f"\n{'='*70}")
    print(f"VALIDATING: {name}")
    print(f"URL: {url}")
    print(f"{'='*70}")

    try:
        t0 = time.time()
        result = provider.extract([url])
        elapsed = time.time() - t0

        if not result.get("success"):
            print(f"FAILED: {result.get('error', 'unknown')}")
            continue

        item = result["data"][0]
        content = item.get("content", "")
        raw = item.get("raw_content", "")
        meta = item.get("metadata", {})
        title = item.get("title", "")

        print(f"Title: {title}")
        print(f"Selector: {meta.get('selector', 'N/A')}")
        print(f"Confidence: {meta.get('confidence', 0):.3f}")
        print(f"Validation Pass: {meta.get('validation_pass', 'N/A')}")
        print(f"Content length: {len(content)} chars")
        print(f"Raw length: {len(raw)} chars")
        print(f"Scored blocks: {meta.get('scored_blocks_count', 0)}")
        print(f"Pruned: {meta.get('pruned_total', 0)} (static={meta.get('pruned_static', 0)}, dynamic={meta.get('pruned_dynamic', 0)})")
        print(f"Time: {elapsed:.1f}s")

        # Check for anti-bot content
        anti_bot_indicators = ["robot", "captcha", "challenge", "verify", "are you human",
                               "access denied", "blocked", "please verify"]
        content_lower = content.lower()
        title_lower = title.lower()
        for indicator in anti_bot_indicators:
            if indicator in content_lower or indicator in title_lower:
                print(f"⚠️  ANTI-BOT DETECTED: '{indicator}' found in title/content")

        # Check content quality
        if len(content) < 100:
            print(f"⚠️  VERY SHORT CONTENT ({len(content)} chars) — likely anti-bot or redirect")
        elif len(content) < 500:
            print(f"⚡ SHORT CONTENT ({len(content)} chars) — may be paywall/JS-rendered")
        elif len(content) > 5000:
            print(f"✅ GOOD CONTENT ({len(content)} chars)")

        # Check for actual economic keywords
        econ_keywords = ["rate", "fed", "fomc", "economy", "economic", "gdp", "inflation",
                        "interest", "calendar", "event", "forecast", "probability", "market",
                        "trading", "news", "business", "financial"]
        found_keywords = [kw for kw in econ_keywords if kw in content_lower]
        print(f"Keywords found: {', '.join(found_keywords) if found_keywords else 'NONE'}")

        # Print content preview (first 800 chars)
        print(f"\n--- Content Preview (first 800 chars) ---")
        print(content[:800])
        print(f"--- End Preview ---")

        # Save full content to file for inspection
        safe_name = name.replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")
        out_path = os.path.join(PROJECT_ROOT, "tests", f"validate_{safe_name}.txt")
        with open(out_path, "w") as f:
            f.write(f"# {name}\n")
            f.write(f"# URL: {url}\n")
            f.write(f"# Title: {title}\n")
            f.write(f"# Selector: {meta.get('selector', 'N/A')}\n")
            f.write(f"# Confidence: {meta.get('confidence', 0):.3f}\n")
            f.write(f"# Content length: {len(content)} chars\n")
            f.write(f"# Raw length: {len(raw)} chars\n\n")
            f.write("=== FULL CONTENT ===\n\n")
            f.write(content)
            f.write("\n\n=== FULL RAW HTML ===\n\n")
            f.write(raw)
        print(f"Full output saved: {out_path}")

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
