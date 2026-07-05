# Prebextor: Deterministic Extraction Engine

## 1. Core Architecture
Prebextor adalah backend provider deterministik untuk ekstraksi web (`web_extract`) di Hermes Agent. Engine ini memindahkan *content-awareness* ke sisi peramban (CamoFox) untuk menjamin data bersih (Zero-Noise) dan efisien secara token.

- **Output Format**: Markdown dibungkus dengan *Semantic XML-style boundary tags* (`<extraction_result>`, `<main_body>`, dst). Presisi batas konten tanpa mengorbankan keterbacaan bagi LLM.
- **Determinisme**: Seluruh pipeline bersifat *stateless* dan berbasis aturan (Rule-Based), bukan heuristik probabilitas.
- **Content-Aware**: Skor text-density (CETD-style) mengidentifikasi noise (navigasi, iklan, sidebar) dan membuangnya sebelum ekstraksi konten.
- **Structure Cache (v1.2.0)**: Pipeline decisions (CSS selector, noise selectors, scoring) di-cache ke disk. HTML selalu segar — aman untuk situs dinamis (economic calendars, harga, news).

Pipeline dasar: **Mapping → Scoring → Pruning → Validation → Text → Iframe → Markdown → Boundary Wrap → Close**.

## 2. Integration with Hermes Agent
Prebextor diintegrasikan melalui sistem plugin Hermes, mendukung **dua mode**:
1. **Provider** — terdaftar via `register_web_search_provider`. Diaktifkan dengan `web.extract_backend: prebextor` di config.yaml.
2. **Standalone Tool** — terdaftar via `register_tool` sebagai `prebextor_extract`. Bypass `web_tools` dispatcher, zero-config. Disarankan untuk penggunaan langsung.

### Contract Compliance
Provider mengimplementasikan kontrak `WebSearchProvider` dari Hermes Agent core:
- `supports_extract()`: mengembalikan `True`.
- `extract(urls: List[str], **kwargs)`: Pipeline deterministik internal, return envelope `{"success": True, "data": [...]}`.
- `supports_search()`: mengembalikan `False` (eks traction-only; pairing dengan search provider seperti SearXNG untuk web_search).
- `is_available()`: Cek ketersediaan CamoFox CLI.

### Plugin Registration
1. Path plugin: `~/.hermes/plugins/web/prebextor/`.
2. Dual-mode registration otomatis via `register(ctx)` di `__init__.py`.
3. Skill internal `prebextor:install` ter-bundle didalam plugin (reachable via `skill_view('prebextor:install')`).

## 3. Installation Guide
1. **Dependencies**: `markdownify>=0.11`, `beautifulsoup4>=4.12`, `pyyaml>=6.0` terinstal di environment Hermes.
2. **Plugin Install**: Gunakan perintah Hermes CLI (lihat dokumen install skill untuk detail).
3. **Verification**: Jalankan `hermes tools list` untuk memastikan `web.prebextor_extract` muncul.

### Direct usage (tanpa config)
```python
from prebextor import PrebextorProvider

provider = PrebextorProvider(
    max_concurrent=3,         # parallel extraction via asyncio.Semaphore
    timeout=30,               # per-URL extraction timeout
    cache_ttl_hours=168,      # 7 days for structure cache
    enable_quality_filter=True,
    enable_metrics=True,
)

result = provider.extract([
    "https://example.com/article",
    "https://example.com/another",
], scroll_to_bottom=True)

if result["success"]:
    for r in result["data"]:
        print(r["url"], r["title"], r["content"][:200])
```

## 4. Operational Sequence (The Deterministic Pipeline)
Setiap request `extract()` mengikuti alur kaku (pipeline v3.1):

1. **Tab Open**: `CamoFoxClient.open_tab` (browser lifecycle).
2. **Anti-bot Detection**: `StructuralMapper._detect_anti_bot()` — deteksi challenge/captcha page, return early dengan error kalau ketemu.
3. **Structural Mapping**: `StructuralMapper.map_selector()` — discover main container via `evaluate_js` (semantic tags → ARIA roles → pattern match → density fallback). Tidak pakai snapshot.
4. **Content-Aware Scoring**: `ContentAwareScorer.score_blocks()` — skor DOM blocks by text/link density. Identifikasi noise selectors.
5. **Surgical Pruning** (dua-pass):
   - **Static**: `SurgicalPruner.prune()` — noise selectors hardcoded (nav, footer, ads).
   - **Dynamic**: `SurgicalPruner.prune_dynamic()` — noise selectors dari scorer (high link density + low text).
6. **Content Validation**: `ContentValidator.validate()` — strict → relaxed → fallback (3-pass dengan warning).
7. **Text Extraction**: `CamoFoxClient.get_text()` — `innerText` langsung dari pruned DOM (no outerHTML round-trip).
8. **Empty Content Detection**: Reject extraction < 30 chars (indikasi JS-render atau block).
9. **Iframe Extraction**: `IframeExtractor.detect_significant_iframes()` — extract content dari cross-origin iframes (CME FedWatch, widgets).
10. **Markdown**: `MarkdownConverter.convert()` — hierarchy-preserving markdown.
11. **Boundary Wrap**: `BoundaryWrapper.wrap()` — XML semantic tags.
12. **Tab Close**: Selalu dijalankan di `finally` block untuk menjaga CamoFox clean.

### Structure Cache (v1.2.0)
Pada cache hit: skip fase 3-6 (map/score/prune/validate), apply struktur yang di-cache ke HTML segar, lanjut dari fase 7. Sekitar 30-50% lebih cepat. Cache disimpan ke `~/.cache/prebextor_structure/` dengan TTL 7 hari.

### Features
- **Parallel Batch Extraction** — `asyncio.Semaphore` controlled concurrency (default 3).
- **Retry with Exponential Backoff** — mencoba ulang transient failures (network, timeout) sampai 3x.
- **Content Quality Filter** — boilplate removal (cookie, GDPR, newsletter), language detection (id/en), quality scoring, schema.org detection.
- **Structured Metrics** — `ExtractionMetrics` capture per-URL timing (fetch_ms, parse_ms, quality_score, structure_cache_hit). Akses via `provider.get_metrics()`.
- **XML Boundary Tags**: `<extraction_result>`, `<extraction_url>`, `<extraction_title>`, `<main_body>`.

## 5. Output Format
```json
{
  "success": true,
  "data": [
    {
      "url": "...",
      "title": "...",
      "content": "<extraction_result><extraction_url>...</extraction_url><main_body>...markdown...</main_body></extraction_result>",
      "raw_content": "...",
      "metadata": {
        "selector": "main",
        "extractor": "prebextor-v3.1",
        "pipeline": "map->score->prune->validate->text->iframe->md->wrap",
        "confidence": 0.85,
        "mapper_confidence": 1.0,
        "scorer_confidence": 0.7,
        "validator_confidence": 0.9,
        "validation_pass": 1,
        "validation_warning": null,
        "scored_blocks_count": 14,
        "noise_selectors_found": 6,
        "pruned_static": 5,
        "pruned_dynamic": 3,
        "pruned_total": 8,
        "iframes_extracted": 0,
        "text_length": 2348,
        "content_aware": true,
        "fetch_ms": 1200,
        "parse_ms": 45,
        "structure_cache_hit": false
      },
      "error": null
    }
  ]
}
```

## 6. Project Structure
```
prebextor/
├── __init__.py            # Plugin registration (provider + tool + skill)
├── provider.py            # PrebextorProvider — pipeline orchestrator + StructureCache + Metrics
├── tool_extract.py        # Standalone tool handler for prebextor_extract
├── plugin.yaml            # Plugin manifest
├── pyproject.toml         # Package metadata
├── fetcher/
│   ├── __init__.py
│   └── camofox_client.py  # CamoFox CLI wrapper
├── pipeline/
│   ├── __init__.py
│   ├── mapper.py          # StructuralMapper — container discovery via evaluate_js
│   ├── scorer.py          # ContentAwareScorer — text/link density scoring
│   ├── pruner.py          # SurgicalPruner — static + dynamic noise removal
│   ├── validator.py       # ContentValidator — 3-pass validation with fallback
│   ├── iframe_extractor.py # IframeExtractor — cross-origin iframe content
│   ├── transform.py       # MarkdownConverter + BoundaryWrapper
│   └── qa.py              # ZeroNoiseAssertionGate (legacy, tidak dipakai di pipeline)
├── skill_internal/
│   └── SKILL.md           # Embedded install skill (prebextor:install)
├── tests/
│   ├── test_e2e_v101.py            # Content-aware pipeline tests
│   ├── test_v101_content_aware.py # Unit tests for scoring/validation
│   ├── test_e2e_economics.py       # E2E for finance/economics sites
│   ├── test_e2e_comprehensive.py   # E2E across 8 categories
│   ├── validate_content.py        # Content validation checks
│   ├── validate_v102.py           # v1.0.2 anti-bot + empty content checks
│   └── validate_*.txt             # Test result snapshots
├── README.md              # This file
├── CHANGELOG.md           # Version history
└── INTEGRATION.md         # Hermes integration notes
```

---
*Maintained by degi.*
