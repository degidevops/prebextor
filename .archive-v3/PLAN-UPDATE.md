# PLAN-UPDATE.md: Prebextor → Hermes Plugin Refarctor

## Context (Why)
Review membuktikan Prebextor **belum bisa** di-drop-in sebagai plugin `web_extract`/`web_search` Hermes Agent. Plant saat ini tinggal sebatas library Python dengan dua struktur direktori paralel dan banyak mock. Plugin yang valid wajib mengikuti preseden `precision-extractor` (bundled di `~/.hermes/hermes-agent/plugins/web/precision-extractor/`) dan struktur `SearXNG` plugin sebagai acuan registrasi.

## Goals
Mengubah `~/project/prebextor/` menjadi plugin Hermes Agent yang siap deploy:
1. Layout satu paket (tidak ada `src/` + `prebextor/` paralel).
2. `plugin.yaml` dengan `provides_web_providers: [prebextor]`.
3. `__init__.py` dengan entry point `register(ctx)`.
4. `provider.py` extend `agent.web_search_provider.WebSearchProvider`.
5. Pemanggilan CamoFox via `camofox` CLI subprocess (bukan mock `mcp_client`).
6. Chunked retrieval untuk handle halaman >1MB.
7. Test parser nyata di target domain riil.

## Aturan Kontrak (precision-extractor sebagai referensi)
- Path: `~/project/prebextor/` adalah sumber plugin. Copy/symlink ke: `~/.hermes/hermes-agent/plugins/web/prebextor/` (bundled) atau `~/.hermes/plugins/web/prebextor/` (user).
- `provider.py` harus extract `WebSearchProvider` dan implement:
  - `name`, `display_name`, `is_available()`
  - `supports_search()`, `supports_extract()`
  - `search(query, **kwargs) -> List[Dict]` (karena plugin juga harus `search` capable sesuai plugin-register contract)
  - `extract(urls: List[str], **kwargs) -> List[Dict]`with return shape:
    ```python
    [{"url", "title", "content" (markdown+xml-tag boundary), "raw_content" (cleaned html), "metadata", "error"?}]
    ```
- Pipeline deterministik (sesuai `PLAN.md` atomic unit, urutan wajib):
  **Mapping → Pruning → Fetching (chunked) → Cleaning (LXML) → Markdown → Boundary XML Wrap → Final QA Gate**

## Atomic Refactor Tasks (untuk sub-agen)
1. **T1 — Single Layout**: Konsolidasi semua modul ke satu pohon paket `prebextor/`. Hapus `src/` sepenuhnya. Hapus `prebextor/provider.py` lama. Buat hierarki jelas: `prebextor/{provider.py, pipeline/, fetcher/, pruner/, mapper/}`.
2. **T2 — Manifest**: Tulis `plugin.yaml` dari bundled plugin preseden.
3. **T3 — Entry Point**: Tulis `__init__.py` dgn `register(ctx)`.
4. **T4 — Provider Contract**: Refactor `provider.py` extend `WebSearchProvider`, signature sesuai kontrak.
5. **T5 — CamoFox CLI Integration**: Ganti `mcp_client` mocks dengan `_camofox_cmd()` submodule (mengikuti preseden `precision-extractor`).
6. **T6 — Chunked Retrieval**: Tambah fungsi `_fetch_full_html(tab_id, user)` yang chunked via `__pe_html.substring(start, end)` di window CamoFox.
7. **T7 — LXML Cleaning** (tambah): Pindah cleaning noise dari JS client-side ke LXML post-fetch (deterministic XPath), sesuai preseden; tetap mempertahankan **1-langkah client-side** pruning via `evaluate_js` untuk ads/script/style **sebelum** fetch (zero-noise gate sesuai `PLAN.md` Atomic Unit E2 & Q1).
8. **T8 — Test Runyata**: Tulis test E2E yang benar-benar fetch 1 domain nyata (contoh: `https://example.com` atau target spesifik) dan assert boundary XML + zero-noise.
9. **T9 — Verification**: Jalankan Hermes check load plugin (`hermes tools list` atau setara) setelah symlink ke `~/.hermes/plugins/web/prebextor/`.

## Out-of-Scope (Tidak dilakukan revisi ini)
- Tidak menyentuh `research/`, `architecture/` (hanya blueprint & riset, bukan kode).
- Tidak menyentuh `PLAN.md` (tetap sebagai blueprint atomic unit).
- Tidak menyentuh `README.md` (akan diupdate setelah deploy sukses).

## Verification Checklist
- [ ] Plugin ter-load dari `~/.hermes/hermes-agent/plugins/web/prebextor/` (bundled) atau `~/.hermes/plugins/web/prebextor/` (user).
- [ ] `hermes tools list` menampilkan plugin `prebextor`.
- [ ] Test `test_real_extract.py` lewat fetch 1 halaman nyata menghasilkan output dengan boundary XML valid.
- [ ] Tidak ada lagi MagicMock/mocks di test.

---
*Refarctor plan dari review komprehensif terhadap preseden bundled plugin precision-extractor.*
