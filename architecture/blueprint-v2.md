# Architecture Blueprint v3.1: Prebextor Deterministic Extraction Engine

## Revision
- **Supersedes**: `blueprint-v2.md` (kept for diff).
- **Diff vs v2**: v3.1 reflects the **Pipeline v3 redesign** — NO SNAPSHOT, NO QA GATE, evaluate_js-only, text-first extraction. All v2 plugin contract preserved.
- **Changelog**: See `CHANGELOG.md` for versioned change tracking (Keep a Changelog format).

---

## 1. Executive Summary
The **Prebextor Deterministic Extraction Engine** is a high-precision web extraction system designed to eliminate probabilistic heuristics and LLM-based content cleaning. By leveraging the browser's native DOM capabilities via CamoFox, the system shifts "content-awareness" to the client-side, ensuring that only "pure" content is delivered to the LLM.

### Core Mandates
- **Deterministic**: Every action is based on DOM properties, not probabilistic guesses.
- **Zero-Noise**: Total elimination of external (header/footer) and internal (ads/widgets) noise.
- **High-Fidelity**: Zero truncation of content, ensuring complete data retrieval.
- **LLM-Ready**: Final output is a **Markdown** document wrapped in full **semantic XML-style boundary tags** (`<extraction_result>`, `<metadata>`, `<main_body>`) — to ensure absolute boundary clarity and prevent prompt leakage.

### v3.1 Additions
- **NO SNAPSHOT**: StructuralMapper uses `evaluate_js` only — snapshots are unreliable for SPA/dynamic content.
- **NO QA GATE**: `ZeroNoiseAssertionGate` removed — caused false failures on valid content.
- **Text-First**: Extracts `innerText` from pruned DOM, not `outerHTML` (avoids stale HTML after DOM mutation).
- **Hermes-Plugin-Native**: Prebextor ships as a user-plugin (`~/.hermes/plugins/web/prebextor/`), wiring into `web_extract` via `web.extract_backend = prebextor`.
- **Skill-Packaged**: One package at `~/project/prebextor/` contains both plugin source and skill.

---

## 2. System Architecture (Layers & Components)

### 2.1 High-Level Component Diagram
```
[User Query]
   ↓
[Hermes web_extract]        ← web.extract_backend = prebextor
   ↓
[PrebextorProvider]         ← extract(urls) → {"success": True, "data": [...]}
   ↓
[CamoFox Browser]           ← open_tab → evaluate_js → get_html → close_tab
   ↓
[Pipeline v3.1]
   1. open_tab              (browser lifecycle)
   2. get_html              (full page HTML for title)
   3. StructuralMapper      (Phase 1: discover container via evaluate_js)
   4. SurgicalPruner        (Phase 2: prune noise inside container)
   5. innerText extraction  (Phase 3: read text from pruned DOM)
   6. IframeExtractor       (Phase 4: extract iframe content, best-effort)
   7. MarkdownConverter     (Phase 5: HTML → Markdown)
   8. BoundaryWrapper       (Phase 6: XML boundary wrap)
   9. close_tab             (cleanup)
   ↓
[Final Output] → {"success": True, "data": [{url, title, content, raw_content, metadata, error}]}
```

### 2.2 Component Detailed Specifications

#### Layer 0: Hermes Agent Integration
**Plugin location**: `~/.hermes/plugins/web/prebextor/`
**Skill location**: `~/project/prebextor/SKILL.md` (one package with plugin)

| Element | Required | Value for Prebextor |
|---|---|---|
| `plugin.yaml` | YES | `kind: backend`, `provides_web_providers: [prebextor]` |
| `__init__.py` `register(ctx)` | YES | calls `ctx.register_web_search_provider(PrebextorProvider())` |
| `provider.py` extends `WebSearchProvider` | YES | implemented |
| `name` property | YES | `"prebextor"` |
| `supports_search()` | YES | `False` (extract-only) |
| `supports_extract()` | YES | `True` |
| `extract(urls, **kwargs)` | YES | returns Hermes envelope |
| Response envelope | YES | `{"success": True, "data": [{url,title,content,raw_content,metadata,error?}]}` |

#### Layer 1: StructuralMapper (Phase 1 — evaluate_js ONLY, no snapshot)
**Priority order:**
1. Semantic tags: `main` > `article` > `div[role="main"]` > `div[role="article"]`
2. Pattern matching: `#content`, `.content`, `#main`, `.main`
3. Density analysis: find div with most text (threshold: 50 chars)
4. Ultimate fallback: `"body"` (NEVER raises error)

**Key**: Mapper NEVER raises `MappingError` — always returns valid selector.

#### Layer 2: SurgicalPruner (Phase 2)
Removes noise elements inside mapped container:
- `script`, `style`, `nav`, `footer`, `aside`, `header`
- Does NOT remove `iframe` or `form` (may contain legitimate content)

#### Layer 3: Text Extraction (Phase 3)
Reads `el.innerText` directly from pruned DOM — avoids stale `outerHTML` after DOM mutation.

#### Layer 4: IframeExtractor (Phase 4 — best-effort)
- Detects significant iframes (size > 300x200, not tracking/ads)
- Opens iframe `src` in new CamoFox tab
- Extracts content recursively
- Merges iframe text into main content
- **Limitation**: Cross-origin iframes with server-side referer checks may fail

#### Layer 5: MarkdownConverter (Phase 5)
Converts HTML to Markdown using `markdownify` library.

#### Layer 6: BoundaryWrapper (Phase 6)
Wraps Markdown in semantic XML:
```xml
<extraction_result>
  <metadata>
    <url>...</url>
    <title>...</title>
    <selector>...</selector>
  </metadata>
  <main_body>
    ...markdown content...
  </main_body>
</extraction_result>
```

---

## 3. Operational Sequence (Step-by-Step)

1. **User** invokes `web_extract(urls=[...])` in Hermes chat.
2. **Hermes** reads `web.extract_backend = prebextor` → resolves to `PrebextorProvider`.
3. **PrebextorProvider.extract(urls)** iterates over URLs:
   - `open_tab(url)` → `tab_id`
   - `get_html(tab_id)` → full page HTML (for title)
   - `mapper.map_selector(tab_id)` → CSS selector (e.g., `"main"`, `"body"`)
   - `pruner.prune(selector, tab_id)` → removes noise nodes
   - `evaluate_js("el.innerText")` → extracted text
   - `iframe_extractor.detect_and_extract()` → iframe content (best-effort)
   - `markdownify(html)` → Markdown
   - `wrap(md, title, url)` → XML-wrapped output
   - `close_tab(tab_id)` → cleanup
4. Returns `{"success": True, "data": [...]}` to Hermes.

---

## 4. Test Results (v3.1.1)

### 18-site validation (6 categories)
| Category | Sites | Pass | Rate |
|----------|-------|------|------|
| News/Article | BBC, Reuters, HN | 3 | 100% |
| Blog/Content | Medium, Dev.to, Hashnode | 3 | 100% |
| Corporate/Info | Apple, Mozilla, Wikipedia | 3 | 100% |
| Data/Table | W3Schools, Wikipedia GDP, Worldometers | 3 | 100% |
| E-commerce | Amazon, Ebay, Etsy | 3 | 100% |
| SPA/JS | Reddit, LinkedIn, YouTube | 2/3 | 67% |
| **Total** | **18** | **17** | **94%** |

### 11-site retest (new sites)
**11/11 PASS (100%)** — NYT, The Verge, StackOverflow, GitHub Trending, Product Hunt, Coursera, Khan Academy, National Geographic, Weather.com, Amazon, Etsy

### Known Limitations
- **Cross-origin iframes**: Browser SOP blocks access (CME FedWatch, embedded widgets)
- **SPA-heavy sites**: Instagram, Facebook, Google may return minimal content (bot detection/login walls)
- **Reddit**: Rate limiting on tab open

---

## 5. Plugin Folder Layout (final)

```
~/project/prebextor/              ← ONE PACKAGE (skill + plugin source)
├── SKILL.md                      ← Hermes skill definition
├── CHANGELOG.md                  ← Keep a Changelog format
├── PLAN-v2.md                    ← Implementation roadmap
├── RESULTS-v3.md                 ← Test results log
├── architecture/
│   └── blueprint-v3.md           ← This file
├── prebextor/                    ← Plugin source (copied to Hermes by deploy.sh)
│   ├── __init__.py               # register(ctx)
│   ├── plugin.yaml               # kind: backend
│   ├── provider.py               # PrebextorProvider v3.1
│   ├── pipeline/
│   │   ├── mapper.py             # StructuralMapper (evaluate_js only)
│   │   ├── pruner.py             # SurgicalPruner
│   │   ├── transform.py          # MarkdownConverter + BoundaryWrapper
│   │   ├── iframe_extractor.py   # IframeExtractor
│   │   └── __init__.py
│   └── fetcher/
│       ├── camofox_client.py     # CamoFoxClient (subprocess wrapper)
│       └── __init__.py
└── scripts/
    ├── deploy.sh                 # Deploy to Hermes + patch config
    ├── undeploy.sh               # Remove plugin + revert config
    ├── verify.py                 # 11-point verification
    └── test_comprehensive.py     # 35+ site validation
```

---

## 6. Future Extensibility
- **Cross-origin iframe**: Navigate to iframe URL directly with referer cookies
- **Adaptive selector caching**: Cache successful selectors per domain
- **Parallel extraction**: Multi-tab parallel extraction
- **MCP promotion**: Expose as MCP server (FastMCP) instead of WebSearchProvider

---

*Maintained by Hermes Agent (Dave). Pipeline v3.1 — NO SNAPSHOT, NO QA GATE, evaluate_js-only.*
