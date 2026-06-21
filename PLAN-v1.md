# PLAN.md: Prebextor Deterministic Extraction Engine (Backend Integration)

## Objective
Implement Prebextor sebagai *Stateful, Deterministic Backend Provider* untuk Hermes Agent (`web_search` & `web_extract`). Fokus utama adalah memindahkan *content-awareness* dari sisi LLM ke sisi *client-side* (CamoFox) melalui pipeline deterministik.

---

## 1. Atomic Unit Catalog (The Functional Contracts)

Setiap unit di bawah ini harus diimplementasikan sebagai *pure functional component* dengan kontrak input/output yang ketat untuk menjamin determinisme.

### Layer 1: Integration (The Backend Contract)
*   **Unit P1: `PrebextorProvider`**
    *   **Tujuan**: Implementasi `WebSearchProvider` & `WebExtractProvider`. Menjembatani permintaan Hermes ke pipeline internal.
    *   **Input**: Query/URLs. **Output**: Terintegrasi ke Hermes Context.

### Layer 2: Lifecycle & Browser (Stateful Orchestration)
*   **Unit L1: `SessionOrchestrator`**
    *   **Tujuan**: Mengelola isolasi tab, `userId`/`sessionKey`, dan *lifespan* browser untuk mencegah deteksi bot.
    *   **Kontrak**: `with_tab(url) -> TabHandle` (Context Manager).

### Layer 3: Extraction Pipeline (The Engine)
*   **Unit E1: `StructuralMapper`**
    *   **Tujuan**: Implementasi *Heuristic-Free Precedence Logic*.
    *   **Kontrak**: `detect_container(TabHandle) -> Selector`.
*   **Unit E2: `SurgicalPruner`**
    *   **Tujuan**: Implementasi *Set-Theoretic Pruning* (DOMContainer \ NoiseSignatures).
    *   **Kontrak**: `prune(TabHandle, Selector) -> CleanDOMState`.
*   **Unit E3: `FidelityFetcher`**
    *   **Tujuan**: Eksekusi `get_page_html` presisi (bypass snapshot).
    *   **Kontrak**: `get_html(TabHandle, Selector) -> PureHTML`.

### Layer 4: Transformation & Boundary (The LLM-Ready Gate)
*   **Unit T1: `MarkdownConverter`**
    *   **Tujuan**: Konversi deterministik HTML ke Markdown yang mempertahankan struktur hirarkis.
    *   **Kontrak**: `convert(PureHTML) -> Markdown`.
*   **Unit T2: `BoundaryWrapper`**
    *   **Tujuan**: Pembungkusan *Non-Negotiable* dengan Semantic XML (`<extraction_result>`, `<main_body>`, dll).
    *   **Kontrak**: `wrap(Markdown) -> XML_Wrapped_Markdown`.

### Layer 5: QA & Assertion (The Zero-Noise Gate)
*   **Unit Q1: `ZeroNoiseAssertionGate`**
    *   **Tujuan**: Verifikasi *Hard-Assertion* sebelum output dikirim kembali ke Hermes.
    *   **Kontrak**: `assert(XML_Wrapped_Markdown) -> Result(Pass/Fail)`.

---

## 2. Implementation Roadmap (Integration Sequence)

Implementasi dilakukan secara *top-down* untuk integrasi, namun *bottom-up* untuk stabilitas unit.

### Sprint 1: Foundation (Layer 1 & 2)
- [x] **U-P1**: Implementasi *skeleton* `PrebextorProvider`.
- [x] **U-L1**: Implementasi `SessionOrchestrator` dengan manajemen sesi per-request.

### Sprint 2: Core Engine (Layer 3)
- [x] **U-E1**: Implementasi `StructuralMapper` (Hierarchy Logic).
- [x] **U-E2**: Implementasi `SurgicalPruner` (JavaScript injection).
- [x] **U-E3**: Implementasi `FidelityFetcher` (Precise DOM retrieval).

### Sprint 3: Transformation (Layer 4)
- [x] **U-T1**: Integrasi *Markdown Converter* (Zero-loss structure).
- [x] **U-T2**: Implementasi `BoundaryWrapper` (Semantic XML protocol).

### Sprint 4: QA & Final Integration (Layer 5)
- [x] **U-Q1**: Implementasi *Middleware* `ZeroNoiseAssertionGate`.
- [x] **Integrasi**: Menghubungkan seluruh pipeline ke `PrebextorProvider`.
- [x] **Uji Integrasi**: Verifikasi E2E dari Hermes request $\rightarrow$ Pipeline $\rightarrow$ Response.

---

## 3. The Zero-Noise Standard (Deterministic Protocol)

Setiap unit di atas wajib mematuhi:
1. **Determinisme**: Input yang sama harus menghasilkan output yang sama secara absolut.
2. **Stateless**: Unit tidak boleh menyimpan sesi di luar `TabHandle`.
3. **Fail-Fast**: Jika sebuah unit tidak bisa memenuhi kontrak (misal: Selector tidak ditemukan), pipeline harus *raise error* secara eksplisit, bukan mencoba tebakan heuristik.
4. **Boundary Clarity**: Output dari `BoundaryWrapper` harus lolos `ZeroNoiseAssertionGate` sebelum diserahkan ke Hermes.

---
*Maintained by Hermes Agent (Dave). Derived from Prebextor core paradigm.*
