---

## Sprint 6: Iframe Extraction & Pipeline v3 (Raw HTML First)

### Tujuan
- Redesign pipeline: **NO SNAPSHOT**, raw HTML first via evaluate_js
- Tambah iframe extraction untuk cross-origin embedded content
- Fix stale `outerHTML` issue setelah DOM pruning

### Perubahan Fundamental

| Aspek | v2 (lama) | v3 (baru) |
|-------|-----------|-----------|
| Structure detection | Snapshot-first | evaluate_js only |
| Content extraction | `el.outerHTML` (stale) | `el.innerText` (live DOM) |
| QA gate | Check HTML for `<script>` tags | Check text for code leakage |
| Iframe handling | None | Recursive extraction |
| get_html | `window.__pe_html` staging | Direct eval + chunked fallback |

### Files Changed
- `fetcher/camofox_client.py` — `get_html` tanpa staging, tambah `get_text()`
- `pipeline/mapper.py` — Hapus snapshot, evaluate_js only
- `pipeline/pruner.py` — Tambah `prune_and_get_text()`
- `pipeline/qa.py` — Text-based assertion, bukan HTML
- `pipeline/iframe_extractor.py` — Baru
- `pipeline/transform.py` — Handle plain text input
- `provider.py` — Pipeline v3

### Test Results
| Website | v2 | v3 |
|---------|----|----|
| example.com | ✅ 363 chars | ✅ 363 chars |
| tradingeconomics.com | ✅ 82,864 chars | ✅ 9,903 chars |
| cmegroup.com/fedwatch | ❌ Script noise | ✅ "target rate" found, 1 iframe extracted |

### Known Limitations
- CME FedWatch: Data probability ada di cross-origin iframe (QuikStrike)
  yang gagal load jika dibuka langsung (perlu session dari parent page)
- Solusi alternatif: CME FedWatch API ($25/bulan) atau intercept XHR dari parent
