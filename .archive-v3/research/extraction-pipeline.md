# Research: Prebextor Extraction Pipeline

## Goal
Achieve 100% deterministic, zero-noise content extraction by shifting content-awareness from LLM-inference to client-side DOM execution using CamoFox/MCP CamoFox.

## Core Philosophy
- **No Heuristics**: Avoid probabilistic guessing of "main content".
- **Zero-Noise**: Eliminate both external noise (header/footer) and internal noise (ads/widgets inside the main content).
- **Client-Side Processing**: Use CamoFox to filter content before it reaches the backend/LLM to minimize token waste and maximize precision.

## Technical Workflow

### Phase 1: Discovery (Structural Mapping)
- **Tool**: `mcp_camofox_snapshot`
- **Action**: Retrieve the accessibility tree snapshot.
- **Purpose**: Identify the primary content container (e.g., `main`, `article`, or a specific ID/Class like `#content`).
- **Constraint**: Use snapshot ONLY for mapping, not for final content extraction (to avoid truncation).

### Phase 2: Surgical Extraction & Micro-Pruning
- **Tool**: `mcp_camofox_camofox_evaluate_js`
- **Action**: Execute a JS script that performs two steps:
    1. **Targeted Selection**: Isolate the main container found in Phase 1.
    2. **Micro-Pruning**: Remove "Internal Noise" elements located *inside* the selected container (e.g., `.ad-container`, `nav`, `aside`, `.newsletter-box`, `script`, `style`).
- **Purpose**: Ensure the returned HTML is "pure" and contains only the actual content.

### Phase 3: High-Fidelity Retrieval
- **Tool**: `mcp_camofox_camofox_get_page_html`
- **Action**: Retrieve the rendered HTML of the pruned element using its specific selector.
- **Purpose**: Guarantee full content retrieval without truncation.

### Phase 4: Transformation & Wrapping
- **Process**: `Rendered HTML` $\rightarrow$ `Markdownify` $\rightarrow$ `XML Tags`.
- **Output Format**: Wrap the final markdown in semantic XML tags (e.g., `<page_content>`, `<main_body>`, `<metadata>`) to provide clear boundaries for the LLM.

## Pitfalls & Lessons Learned
- **The "Internal Noise" Trap**: Simply selecting the `<main>` or `<article>` tag is insufficient. Many sites embed ads, surveys, and sidebars inside these tags. **Micro-Pruning** is mandatory for Zero-Noise.
- **Snapshot Truncation**: Never use snapshot data as the final content source. Always transition to `evaluate_js` or `get_page_html` for the actual data payload.

## Verification Steps
1. Verify that the `snapshot` identifies a valid container.
2. Verify that the `evaluate_js` output does not contain tags like `<nav>` or `.ad-box`.
3. Verify that the final XML-wrapped Markdown matches the visual content of the page without extra clutter.
