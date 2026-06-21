# Architecture Blueprint v1: Prebextor Deterministic Extraction Engine

## 1. Executive Summary
The **Prebextor Deterministic Extraction Engine** is a high-precision web extraction system designed to eliminate probabilistic heuristics and LLM-based content cleaning. By leveraging the browser's native DOM capabilities via CamoFox, the system shifts "content-awareness" to the client-side, ensuring that only "pure" content is delivered to the LLM.

### Core Mandates
- **Deterministic**: Every action is based on DOM properties, not probabilistic guesses.
- **Zero-Noise**: Total elimination of external (header/footer) and internal (ads/widgets) noise.
- **High-Fidelity**: Zero truncation of content, ensuring complete data retrieval.
- **LLM-Ready**: Final output is a Markdown document wrapped in full semantic XML-style tags to ensure absolute boundary clarity and prevent prompt leakage.

---

## 2. System Architecture

### 2.1 High-Level Component Diagram
`[User Query]` $\rightarrow$ `[SearXNG Module]` $\rightarrow$ `[CamoFox Extraction Engine]` $\rightarrow$ `[Transformation Pipeline]` $\rightarrow$ `[Final Output]`

### 2.2 Component Detailed Specifications

#### A. SearXNG Module (Search Gateway)
- **Function**: Orchestrates the discovery of target URLs.
- **Logic**: 
    - Executes search queries via SearXNG.
    - Filters results based on domain authority and relevance.
    - Returns a prioritized list of URLs for the extraction pipeline.
- **Interface**: JSON API $\rightarrow$ List of URLs.

#### B. CamoFox Extraction Engine (The Surgical Core)
This module operates in three distinct phases to guarantee precision.

**Phase 1: Structural Discovery (Mapping)**
- **Tool**: `mcp_camofox_snapshot`
- **Logic**: 
    - Analyzes the accessibility tree to dynamically identify the "Main Content Container" using a hierarchical fallback strategy:
        1. **Semantic Tags**: Prioritize `<main>` $\rightarrow$ `<article>`.
        2. **Pattern Matching**: Search for IDs/Classes matching patterns like `content`, `main`, `article`, `body`, `post` (e.g., `div#main-content` or `.article-body`).
        3. **Text-Density Analysis**: If no semantic/pattern match is found, identify the container with the highest text-to-HTML tag ratio.
- **Output**: A dynamic CSS selector specific to the current page.

**Phase 2: Surgical Pruning (Internal Cleaning)**
- **Tool**: `mcp_camofox_camofox_evaluate_js`
- **Logic**:
    - Isolate the container found in Phase 1.
    - **Micro-Pruning Algorithm**: Within the isolated container, identify and remove elements that match "Noise Signatures".
    - **Noise Signatures**: 
        - `nav`, `aside`, `footer`, `header`.
        - Classes/IDs containing: `ad`, `banner`, `survey`, `newsletter`, `popup`, `social-share`, `widget`.
        - `script`, `style`, `iframe` (unless specifically marked as content).
- **Output**: A pruned DOM state within the browser session.

**Phase 3: High-Fidelity Retrieval (Fetch)**
- **Tool**: `mcp_camofox_camofox_get_page_html`
- **Logic**:
    - Request the `.innerHTML` of the pruned selector.
- **Constraint**: Must bypass snapshots to avoid truncation.
- **Output**: Pure, cleaned HTML of the main content.

#### C. Transformation Pipeline (The Refiner)
Converts raw HTML into the optimal format for LLM ingestion, combining Markdown's readability with XML's boundary precision.

1.  **Markdown Conversion**:
    - **Tool**: `Markdownify` (or equivalent deterministic converter).
    - **Requirement**: Preserve hierarchical structures (H1-H6), lists, and tables.
2.  **Full Semantic XML Wrapping**:
    - The final Markdown content is strictly enclosed in semantic XML tags to ensure the LLM treats each section as a distinct context block.
    - **Format Example**:
      ```markdown
      <extraction_result>
        <metadata>
        Title: {page_title}
        URL: {page_url}
        Timestamp: {iso_date}
        </metadata>

        <main_body>
        # {H1 Title}
        {Markdown Content...}
        </main_body>

        <artifacts>
        {extracted_links_or_tables}
        </artifacts>
      </extraction_result>
      ```

---

## 3. Operational Sequence (Step-by-Step)

1.  **Input**: User provides a query.
2.  **Search**: `SearXNG` returns `URL_1`, `URL_2`, etc.
3.  **Navigate**: CamoFox creates a tab and navigates to `URL_n`.
4.  **Map**: `snapshot` $\rightarrow$ Identify `[Dynamic Selector]` (e.g., `main`, `.article-body`, or density-based container).
5.  **Prune**: `evaluate_js` $\rightarrow$ Execute pruning logic on the `[Dynamic Selector]`.
6.  **Fetch**: `get_page_html` $\rightarrow$ Retrieve cleaned HTML of the `[Dynamic Selector]`.
7.  **Transform**: `HTML` $\rightarrow$ `Markdown` $\rightarrow$ `Full Semantic XML Wrapping`.
8.  **Deliver**: Final Markdown string wrapped in semantic XML tags sent to LLM.

---

## 4. Verification & Quality Assurance (The Zero-Noise Gate)

To maintain the deterministic standard, the system must pass the following tests:

| Test Case | Method | Success Criteria |
| :--- | :--- | :--- |
| **External Noise** | Header/Footer Check | No `nav` or `footer` tags present in `<main_body>`. |
| **Internal Noise** | Ad/Widget Check | No elements with `.ad` or `.survey` classes in the final output. |
| **Fidelity** | Length Comparison | Content length $\approx$ visual length (no abrupt truncation). |
| **Structure** | Hierarchy Check | H1 $\rightarrow$ H2 $\rightarrow$ H3 sequence is preserved in Markdown. |
| **Boundary Check** | Tag Validation | Content is strictly enclosed in `<extraction_result>`, `<metadata>`, and `<main_body>`. |

---

## 5. Future Extensibility
- **Dynamic Content Handling**: Integration of `waitForSelector` for SPAs (Single Page Applications).
- **Adaptive Selector Learning**: Storing successful selectors for recurring domains to skip Phase 1.
- **Parallelization**: Multi-tab extraction for simultaneous URL processing.
