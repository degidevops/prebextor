# Architecture Blueprint v2: Prebextor Deterministic Extraction Engine

## Revision
- **Supersedes**: `blueprint-v1.md` (kept as `blueprint-v1.md.original` for diff).
- **Diff vs v1**: v2 adds the **Hermes Agent Integration Layer** (plugin contract + skill packaging). All v1 core mandates are preserved verbatim.
- **Research basis**: `research/hermes_plugin_research.md`, `research/skill_research.md`, `research/hermes-provider-contract-research.md`.
- **Changelog**: See `CHANGELOG.md` for versioned change tracking (Keep a Changelog format).

---

## 1. Executive Summary (unchanged from v1)
The **Prebextor Deterministic Extraction Engine** is a high-precision web extraction system designed to eliminate probabilistic heuristics and LLM-based content cleaning. By leveraging the browser's native DOM capabilities via CamoFox, the system shifts "content-awareness" to the client-side, ensuring that only "pure" content is delivered to the LLM.

### Core Mandates
- **Deterministic**: Every action is based on DOM properties, not probabilistic guesses.
- **Zero-Noise**: Total elimination of external (header/footer) and internal (ads/widgets) noise.
- **High-Fidelity**: Zero truncation of content, ensuring complete data retrieval.
- **LLM-Ready**: Final output is a **Markdown** document wrapped in full **semantic XML-style boundary tags** (`<extraction_result>`, `<metadata>`, `<main_body>`) — to ensure absolute boundary clarity and prevent prompt leakage.

### v2 Additions
- **Hermes-Plugin-Native**: Prebextor ships as a user-plugin to Hermes Agent (`~/.hermes/plugins/web/prebextor/`), wiring into Hermes's `web_extract` tool via `web.extract_backend = prebextor`.
- **Skill-Packaged Deployment**: A companion Hermes skill (`prebextor-extractor`) at `~/.hermes/skills/web-extraction/prebextor-extractor/SKILL.md` handles source-to-plugin deployment (real file copy), dependency bootstrap, and `config.yaml` patching.
- **Search Paired via SearXNG**: Prebextor is **extract-only**. Search is delegated to the official SearXNG provider (`web.search_backend = searxng`). The combination is the documented "extract + search split" pattern.

---

## 2. System Architecture (Layers & Components)

### 2.1 High-Level Component Diagram
```
[User Query]
   ↓
[SearXNG Module]            ← web.search_backend = searxng (built-in)
   ↓
[Prebextor Provider Model]  ← web.extract_backend = prebextor (our plugin)
   ↓
[CamoFox Extraction Engine] ← Mapping → Pruning → Fetching → QA → Transform → Wrap → Final QA
   ↓
[Transformation Pipeline]   ← Markdown + Semantic XML Boundary
   ↓
[Final Output (extract)] → into Hermes's web_extract tool envelope `{"success": True, "data": [...]}`
```

### 2.2 Component Detailed Specifications

#### Layer 0: Hermes Agent Integration Layer (NEW in v2)
**Plugin location**: `~/.hermes/plugins/web/prebextor/`
**Skill location**: `~/.hermes/skills/web-extraction/prebextor-extractor/`

**Plugin contract** (per research/hermes_provider_contract_research.md):

| Element | Required | Value for Prebextor |
|---|---|---|
| `plugin.yaml` | YES; `kind: backend`, `provides_web_providers: [prebextor]` | applied |
| `__init__.py` `register(ctx)` | YES; calls `ctx.register_web_search_provider(...)` | applied |
| `provider.py` extends `agent.web_search_provider.WebSearchProvider` | YES | applied |
| `name` property | YES; lowercase id | `"prebextor"` |
| `display_name` | optional | `"Prebextor (Deterministic Extraction Engine)"` |
| `is_available()` | YES; cheap gate, **NO network** | check `camofox --version` |
| `supports_search()` | optional (default `True`) | `False` (extract-only by design) |
| `supports_extract()` | optional (default `False`) | `True` |
| `search(query, limit)` | conditional | **not implemented** → raise `NotImplementedError` |
| `extract(urls, **kwargs)` | conditional | implemented; returns Hermes envelope |
| Response envelope | YES | `{"success": True, "data": [{url,title,content,raw_content,metadata,error?}, ...]}` |

**Capability boundary**: Prebextor returns `False` for `supports_search()` and never implements `search()`. Search is delegated to SearXNG. This is the exact pairing described in the Hermes docs: *"SearXNG is search-only with a documented 'pair me with an extract provider' workflow."*

#### Layer 1: Search Gateway (unchanged from v1)
SearXNG → `URL_1`, `URL_2`, ...

#### Layer 2: CamoFox Extraction Engine (Surgical Core) — UNCHANGED
**Phase 1: Structural Discovery (Mapping)** — `mcp_camofox_snapshot` / `camofox snapshot`.
Hierarchical precedence: `<main>` → `<article>` → pattern match → text-density.
**Phase 2: Surgical Pruning (Internal Cleaning)** — `mcp_camofox_camofox_evaluate_js` / `camofox eval`.
Noise signatures: `nav`, `aside`, `footer`, `header`, ad-classes, popups, `script`, `style`, `iframe`.
**Phase 3: High-Fidelity Retrieval (Fetch)** — `mcp_camofox_camofox_get_page_html` / `eval document.querySelector(<selector>).outerHTML`.
Bypass snapshot to avoid truncation.

#### Layer 3: Transformation Pipeline — UNCHANGED
1. `Markdownify` (or equivalent deterministic): preserve H1-H6, lists, tables.
2. **Full Semantic XML Wrapping**: `<extraction_result>` with `<metadata>` + `<main_body>`.

#### Layer 4: Zero-Noise Gate (NEW per v1 §4, kept; promoted as Layer 4)
Two-pass `ZeroNoiseAssertionGate`:
- `assert_html(cleaned_html)` — runs on container HTML **before** markdown conversion.
- `assert_xml(xml_wrapped_md)` — runs on the final XML-wrapped Markdown.
Failures are hard errors, never silent fallbacks.

#### Layer 5: Hermes Response Enveloper (NEW in v2)
Wraps the Prebextor pipeline output in the official Hermes envelope:

```python
{
  "success": True,
  "data": [
    {
      "url": "...",
      "title": "...",
      "content": "<XML-wrapped Markdown>",  # the LLM-ready payload
      "raw_content": "<cleaned container HTML>",  # for debugging / re-transformation
      "metadata": {"selector": "...", "extractor": "prebextor", "pipeline": "mapping->..."},
      "error": null,  # or string on per-URL failure
    },
    ...
  ]
}
```

Drives the contract change for `extract()` in `provider.py`: it **must** return the envelope, never raw `List[Dict]`.

---

## 3. Operational Sequence (Step-by-Step, end-to-end)

1. **User** invokes `web_extract(urls=[...])` in Hermes chat.
2. **Hermes web_extract** reads `web.extract_backend` from config → resolves to provider `"prebextor"`.
3. **Hermes dispatcher** calls `PrebextorProvider.extract(urls, **kwargs)`.
4. For each URL, `_extract_one(url, **kwargs)` runs the v1 pipeline:
   Mapping → Pruning → Fetching → QA(HTML) → Markdown → Wrap → QA(XML).
5. The list is wrapped in the **Hermes envelope** and returned to the dispatcher.
6. **Hermes web_extract** JSON-serializes and forwards to the LLM as a tool result.
7. For search, Hermes dispatches to **SearXNG** via `web.search_backend = searxng`. Prebextor is not involved.

---

## 4. Verification & Quality Assurance (v2-expanded)

### 4.1 v1 tests (kept verbatim)
| Test Case | Method | Success Criteria |
| :--- | :--- | :--- |
| External Noise | Header/Footer Check | No nav/footer in `<main_body>`. |
| Internal Noise | Ad/Widget Check | No `.ad`, `.survey` in output. |
| Fidelity | Length Comparison | Content length ≈ visual length. |
| Structure | Hierarchy Check | H1 → H2 → H3 preserved. |
| Boundary Check | Tag Validation | `<extraction_result>`, `<metadata>`, `<main_body>` strictly present. |

### 4.2 v2 tests (NEW)
| Test Case | Method | Success Criteria |
| :--- | :--- | :--- |
| Plugin discovery | `hermes tools \| grep prebextor` | `prebextor` listed under web providers |
| Plugin load | `python -c "import plugins.web.prebextor; register(...)"` | no ImportError, register() runs |
| Search delegation | `web.search_backend = searxng` + `web.extract_backend = prebextor` | both `web_search` and `web_extract` resolve |
| Envelope schema | JSON schema check on `extract()` return | always `{"success","data\|error"}` |
| Skill lifecycle | `/prebextor-extractor install` → file at `~/.hermes/plugins/web/prebextor/` | plugin tree exists post-run |
| Real-domain extract | `extract(['https://example.com'])` against running CamoFox | content is non-empty, deterministic |

---

## 5. Future Extensibility
- **Dynamic Content Handling**: `wait_for_selector` for SPAs.
- **Adaptive Selector Learning**: cache successful selectors per domain.
- **Parallelization**: multi-tab parallel extraction.
- **MCP promotion (optional)**: if Prebextor graduates beyond a regular plugin, expose it as an MCP server (FastMCP) instead of a `WebSearchProvider` subclass — the tool surface and config keys are different.

---

## Appendix A: Plugin Folder Layout (final)

```
~/.hermes/plugins/web/prebextor/
├── __init__.py      # def register(ctx): ctx.register_web_search_provider(PrebextorProvider())
├── plugin.yaml      # kind: backend; provides_web_providers: [prebextor]
├── provider.py      # class PrebextorProvider(WebSearchProvider)
│                     #   name="prebextor"
│                     #   supports_search() -> False
│                     #   supports_extract() -> True
│                     #   search() -> NotImplementedError
│                     #   extract(urls, **kw) -> {success, data}
├── pipeline/
│   ├── mapper.py    # StructuralMapper (Phase 1)
│   ├── pruner.py    # SurgicalPruner (Phase 2)
│   ├── transform.py # MarkdownConverter + BoundaryWrapper (Phase 3)
│   ├── qa.py        # ZeroNoiseAssertionGate (Layer 4, two-pass)
│   └── __init__.py
└── fetcher/
    ├── camofox_client.py  # subprocess wrapper for camofox CLI
    └── __init__.py
```

## Appendix B: Skill Folder Layout

```
~/.hermes/skills/web-extraction/prebextor-extractor/
├── SKILL.md         # frontmatter (name, description, version, metadata.hermes.category, tags)
├── scripts/
│   ├── deploy.sh    # real-file copy + config patch
│   ├── undeploy.sh  # remove plugin dir + revert config patch
│   └── verify.py    # import + envelope schema check
└── references/
    ├── plugin-layout.md
    └── troubleshooting.md
```

---

## Bab 4: Iframe Extraction Strategy (v3)

### 4.1 Masalah Cross-Origin Iframe

Banyak website modern memuat konten utama di dalam iframe cross-origin:
- **CME FedWatch**: Data tabel probability di-load dari `cmegroup-tools.quikstrike.net`
- **Embedded widgets**: Maps, charts, calculators dari domain ketiga
- **SPA micro-frontends**: Komponen UI dari subdomain berbeda

Cross-origin policy memblokir akses ke `contentDocument` iframe dari parent page.

### 4.2 Solusi: Recursive Iframe Extraction

```
1. Detect significant iframes (ukuran > 300x200, bukan tracking/ads)
2. Buka iframe src di tab CamoFox baru
3. Extract content dari tab iframe secara recursive
4. Merge iframe text ke parent content
```

### 4.3 Implementasi

File: `prebextor/pipeline/iframe_extractor.py`

```python
class IframeExtractor:
    def detect_significant_iframes(tab_id, user) -> List[Dict]
    def extract_iframe_content(iframe_src, parent_user) -> Optional[Dict]
```

### 4.4 Tracking/Ads Filter

Iframe dari domain berikut di-skip:
- `doubleclick.net`, `google-analytics.com`, `googletagmanager.com`
- `facebook.net`, `linkedin.com/collect`, `reddit.com/rp.gif`
- `sharethis.com`, `google.com/recaptcha`
- Iframe dengan ukuran < 300x200 pixel

### 4.5 Limitations

- Iframe yang memerlukan session/context dari parent page (seperti QuikStrike)
  mungkin gagal load jika dibuka langsung
- Solusi: gunakan `evaluate_js` untuk inject content setelah iframe load
  atau gunakan CME FedWatch API publik ($25/bulan)
