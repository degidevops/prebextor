# PLAN-v2: Prebextor Deterministic Extraction Engine (Hermes Plugin Integration)

## Revision
- **Supersedes**: `PLAN-v1.md` (original atomic unit catalog, kept for reference).
- **Diff vs v1**: v2 adds **Layer 0: Hermes Plugin Integration** (plugin contract + skill packaging + deployment). All v1 atomic units and sprints are preserved.
- **Research basis**: `research/hermes_provider_contract_research.md`, `research/skill_research.md`, `research/hermes_skill_system.md`.

---

## Objective
Implement Prebextor as a **Hermes Agent User Plugin** (`web.extract_backend = prebextor`) with companion **Skill** for one-command deployment. The extraction pipeline remains deterministic and rule-based (v1 core).

---

## 1. Atomic Unit Catalog (v1 units + v2 additions)

Setiap unit di bawah ini harus diimplementasikan sebagai *pure functional component* dengan kontrak input/output yang ketat untuk menjamin determinisme.

### Layer 0: Hermes Plugin Integration (NEW in v2)
*   **Unit H0: `PrebextorProvider` (Plugin Contract)**
    *   **Tujuan**: Implementasi `WebSearchProvider` ABC. Menjembatani permintaan Hermes `web_extract` ke pipeline internal.
    *   **Input**: `urls: List[str]`, `**kwargs`. **Output**: `{"success": bool, "data": [...]}`
    *   **Contract**:
        - `name = "prebextor"`
        - `supports_search() → False` (extract-only; paired with SearXNG)
        - `supports_extract() → True`
        - `extract(urls, **kwargs) → {"success": True, "data": [{url,title,content,raw_content,metadata,error?}]}`
        - `search(...)` → raises `NotImplementedError`

*   **Unit H1: `plugin.yaml` (Manifest)**
    *   **Tujuan**: Plugin manifest untuk Hermes discovery.
    *   **Contract**:
        ```yaml
        name: prebextor
        version: 1.0.0
        description: "Prebextor Deterministic Extraction Engine"
        author: degi
        kind: backend
        provides_web_providers:
          - prebextor
        ```

*   **Unit H2: `__init__.py` (Entry Point)**
    *   **Tujuan**: Registrasi provider ke Hermes via `register(ctx)`.
    *   **Contract**: `ctx.register_web_search_provider(PrebextorProvider())`

*   **Unit H3: `prebextor-extractor` Skill**
    *   **Tujuan**: Skill yang membungkus plugin untuk one-command deployment.
    *   **Lokasi**: `~/.hermes/skills/web-extraction/prebextor-extractor/SKILL.md`
    *   **Capabilities**: deploy (real file copy), undeploy, verify, config patch (`web.extract_backend = prebextor`)

### Layer 1: Integration (v1, unchanged)
*   **Unit P1: `PrebextorProvider` (Pipeline Bridge)**
    *   **Tujuan**: Orkestrasi pipeline ekstraksi dari input URL ke output envelope.
    *   **Input**: Query/URLs. **Output**: Hermes envelope.

### Layer 2: Lifecycle & Browser (v1, unchanged)
*   **Unit L1: `SessionOrchestrator`**
    *   **Tujuan**: Mengelola isolasi tab, `userId`/`sessionKey`, dan *lifespan* browser.
    *   **Kontrak**: `with_tab(url) → TabHandle` (Context Manager).

### Layer 3: Extraction Pipeline (v1, unchanged)
*   **Unit E1: `StructuralMapper`** — `detect_container(TabHandle) → Selector`
*   **Unit E2: `SurgicalPruner`** — `prune(TabHandle, Selector) → CleanDOMState`
*   **Unit E3: `FidelityFetcher`** — `get_html(TabHandle, Selector) → PureHTML`

### Layer 4: Transformation & Boundary (v1, unchanged)
*   **Unit T1: `MarkdownConverter`** — `convert(PureHTML) → Markdown`
*   **Unit T2: `BoundaryWrapper`** — `wrap(Markdown) → XML_Wrapped_Markdown`

### Layer 5: QA & Assertion (v1, unchanged)
*   **Unit Q1: `ZeroNoiseAssertionGate`** — `assert(XML_Wrapped_Markdown) → Result(Pass/Fail)`

---

## 2. Implementation Roadmap (v2 Sequence)

### Sprint 0: Hermes Plugin Foundation (NEW)
- [x] **U-H0**: `PrebextorProvider` — `WebSearchProvider` subclass with envelope return
- [x] **U-H1**: `plugin.yaml` — manifest
- [x] **U-H2**: `__init__.py` — `register(ctx)` entry point
- [ ] **U-H3**: `prebextor-extractor` Skill (SKILL.md + deploy/undeploy scripts)

### Sprint 1: Foundation (Layer 1 & 2)
- [x] **U-P1**: Pipeline bridge via `PrebextorProvider`
- [x] **U-L1**: `SessionOrchestrator` via CamoFox client

### Sprint 2: Core Engine (Layer 3)
- [x] **U-E1**: `StructuralMapper` (Hierarchy Logic)
- [x] **U-E2**: `SurgicalPruner` (JavaScript injection)
- [x] **U-E3**: `FidelityFetcher` (Precise DOM retrieval)

### Sprint 3: Transformation (Layer 4)
- [x] **U-T1**: `MarkdownConverter` (Zero-loss structure)
- [x] **U-T2**: `BoundaryWrapper` (Semantic XML protocol)

### Sprint 4: QA & Final Integration (Layer 5)
- [x] **U-Q1**: `ZeroNoiseAssertionGate` (two-pass)
- [x] **Integrasi**: Full pipeline wiring
- [ ] **Uji Integrasi**: E2E verification via `hermes tools` + real-domain extract test

### Sprint 5: Plugin Deployment & Documentation (NEW)
- [ ] Deploy plugin to `~/.hermes/plugins/web/prebextor/`
- [ ] Install skill to `~/.hermes/skills/web-extraction/prebextor-extractor/`
- [ ] Patch `config.yaml`: `web.extract_backend = prebextor`
- [ ] Write `CHANGELOG.md` entry for v2.0.0
- [ ] Tag `v2.0.0`

---

## 3. The Zero-Standard (v1, unchanged)

1. **Determinisme**: Input yang sama → output yang sama secara absolut.
2. **Stateless**: Unit tidak boleh menyimpan sesi di luar `TabHandle`.
3. **Fail-Fast**: Gagal → raise error eksplisit, tidak ada heuristic fallback.
4. **Boundary Clarity**: Output wajib lolos `ZeroNoiseAssertionGate`.

---

## 4. Verification Checklist (v2 additions)

- [ ] `hermes tools | grep prebextor` — plugin discovered
- [ ] `python -c "from prebextor import register"` — import clean
- [ ] `extract(['https://example.com'])` — returns non-empty, deterministic content
- [ ] Response envelope schema check — `{"success": True, "data": [...]}`
- [ ] Skill `/prebextor-extractor install` — deploys plugin + patches config
- [ ] `web.extract_backend = prebextor` active in Hermes config

---

*Maintained by Hermes Agent (Dave). Derived from Prebextor core paradigm + Hermes plugin integration layer.*
