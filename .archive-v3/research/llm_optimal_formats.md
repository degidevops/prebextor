# Research: Optimal Data Formats for LLM Agents

## Executive Summary
Selecting the optimal data format for LLM-based agents involves balancing **Token Efficiency**, **Structural Parsing Accuracy**, and **Model Inherent Bias**. Recent research (2025-2026) suggests that there is no "one-size-fits-all" format; the optimal choice depends heavily on whether the task is long-form reasoning, complex data extraction, or agentic tool invocation.

---

## Comparative Analysis of Formats

### 1. Markdown (The "Readability" King)
*   **Best For:** Long-form context, narrative reasoning, and general-purpose document retrieval.
*   **Why:** LLMs are trained heavily on Markdown-formatted web content. They inherently understand the hierarchy of `#`, `##`, and `-` lists. It is highly token-efficient for structured text compared to JSON.
*   **Limitation:** Brittle for strictly deterministic data extraction where schema validation is required.

### 2. XML / Tagged Structures (The "Boundary" King)
*   **Best For:** Tool invocation, chain-of-thought isolation (e.g., `<thought>...</thought>`), and complex multi-part prompts.
*   **Why:** High-performance models (Claude 3.5+, GPT-5 series) show significant improvements in instruction-following when XML tags are used to define distinct context blocks. It prevents "prompt leakage" between sections.
*   **Limitation:** Increased token usage due to closing tags.

### 3. JSON (The "Integration" King)
*   **Best For:** Data extraction pipelines, API-based tool responses, and scenarios requiring rigid schema validation.
*   **Why:** Universally supported by software infrastructure. Modern LLMs are excellent at generating JSON if the schema is explicitly provided.
*   **Limitation:** Highly verbose; repetitive key names consume significant token budget. Fragile if not strictly parsed; LLMs often fail to close braces correctly in long outputs (though "constrained generation" libraries alleviate this).

---

## Comparative Matrix

| Feature | Markdown | XML/Tags | JSON |
| :--- | :--- | :--- | :--- |
| **Token Efficiency** | High | Low (Verbosity) | Medium-Low |
| **Schema Validation** | Low | Medium | High |
| **Boundary Clarity** | Low | High | Medium |
| **Model Preference** | High | Very High (Tooling) | High (Data) |

---

## Synthesis: Recommended Strategy for Agentic Pipelines

For a robust web extraction agent (like the one we are building):

1.  **Ingestion (Internal Agent Context):** Use **Markdown** to convert raw HTML. It provides the best balance of readability and structure preservation while keeping the token count low.
2.  **Tool Output / Structuring:** Use **XML tags** to enclose the extracted content. This allows the agentic orkestrator (Hermes) to easily parse the output without risking confusion with other parts of the conversation.
3.  **Data Extraction (Specific Schema):** Only invoke **JSON** when the user explicitly requests structured data (e.g., "extract product prices to a JSON object").

---

## References & Further Reading
*   *Improving Agents (2025):* [Which Nested Data Format Do LLMs Understand Best?](https://www.improvingagents.com/blog/best-nested-data-format/)
*   *OpenAI Community Discussions (2026):* [XML vs Markdown for high performance tasks](https://community.openai.com/t/xml-vs-markdown-for-high-performance-tasks/1260014)
*   *Medium (2025):* [What's the Best Way to Feed Data to an LLM? I Tested 5 Formats](https://medium.com/@martinkeywood/whats-the-best-way-to-feed-data-to-an-llm-i-tested-5-formats-with-code-b04d7b81d78a)
*   *Medium (2025):* [Beyond JSON: Picking the Right Format for LLM Pipelines](https://medium.com/@michael.hannecke/beyond-json-picking-the-right-format-for-llm-pipelines-b65f15f77f7d)
