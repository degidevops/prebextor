"""Transformation pipeline: Markdown conversion + XML boundary wrapping.

Implements blueprint §2.2 component C and research/llm_optimal_formats.md.

- After Mapping/Pruning/Fetching, we have cleaned HTML of the main container.
- We convert to Markdown (deterministic, hierarchy-preserving).
- Then wrap the Markdown in semantic XML-style boundary tags so the LLM
  receives unmistakably bounded context blocks, while the inner content
  stays in the model-preferred Markdown form.

The boundary tags themselves (`<extraction_result>`, `<metadata>`,
`<main_body>`) are *literal* (they are the contract). The Markdown inside
the tags is unchanged. The text values of `Title` / `URL` / `Timestamp` are
XML-escaped to keep them out of the markup namespace.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Optional

import markdownify as _md


_LT = "<"
_GT = ">"
_AMP = "&"


def _esc(s: str) -> str:
    return s.replace(_AMP, "&").replace(_LT, "<").replace(_GT, ">")


class MarkdownConverter:
    """Deterministic HTML -> Markdown (ATX headings, dash bullets)."""

    @staticmethod
    def convert(html: str) -> str:
        if not html:
            return ""
        md = _md.markdownify(
            html,
            heading_style="ATX",
            bullets="-",
        )
        # Collapse 3+ blank lines down to 2.
        md = re.sub(r"\n{3,}", "\n\n", md)
        return md.strip()


class BoundaryWrapper:
    """Wraps Markdown in semantic XML boundary tags (per blueprint/v1 §2.2 C)."""

    @staticmethod
    def wrap(
        markdown: str,
        title: str,
        url: str,
        timestamp: Optional[str] = None,
    ) -> str:
        ts = timestamp or _dt.datetime.now(_dt.timezone.utc).isoformat()
        return (
            "<extraction_result>\n"
            "  <metadata>\n"
            f"  Title: {_esc(title)}\n"
            f"  URL: {_esc(url)}\n"
            f"  Timestamp: {_esc(ts)}\n"
            "  </metadata>\n"
            "\n"
            "  <main_body>\n"
            f"{markdown}\n"
            "  </main_body>\n"
            "</extraction_result>\n"
        )
