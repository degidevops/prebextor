"""Zero-Noise Assertion Gate (blueprint §4).

Two assertion passes:

  assert_html(html)  — runs on cleaned container HTML BEFORE conversion.
                       Verifies pruning stripped script/style/iframe/nav/etc.

  assert_xml(xml)    — runs on the final XML-wrapped Markdown.
                       Verifies the boundary tags are present and well-formed,
                       and that the inner Markdown has at least one heading.

The gate is intentionally strict; failure aborts the pipeline with
AssertionError. This is the user's "Zero-Noise Standard" (deterministic
fail-fast) — see PLAN.md §3.
"""

from __future__ import annotations

import re
from typing import List


def _has_any(pat: re.Pattern, s: str) -> bool:
    return pat.search(s) is not None


class AssertionError_(Exception):
    """Raised when the Zero-Noise Gate fails."""


class ZeroNoiseAssertionGate:
    """Strict structural assertions; deterministic and self-contained."""

    # Tags that must NEVER appear inside the main container HTML.
    _HTML_NOISE: List[re.Pattern] = [
        re.compile(r"<script\b", re.IGNORECASE | re.DOTALL),
        re.compile(r"<style\b", re.IGNORECASE | re.DOTALL),
        re.compile(r"<iframe\b", re.IGNORECASE | re.DOTALL),
        re.compile(r"<nav\b", re.IGNORECASE | re.DOTALL),
        re.compile(r"<footer\b", re.IGNORECASE | re.DOTALL),
        re.compile(r"<aside\b", re.IGNORECASE | re.DOTALL),
        re.compile(r"<header\b", re.IGNORECASE | re.DOTALL),
        re.compile(r"<form\b", re.IGNORECASE | re.DOTALL),
    ]

    _XML_OPEN = re.compile(r"^\s*<extraction_result>", re.MULTILINE)
    _XML_CLOSE = re.compile(r"</extraction_result>\s*$", re.MULTILINE)
    _XML_BODY_OPEN = re.compile(r"<main_body>")
    _XML_BODY_CLOSE = re.compile(r"</main_body>")
    _MD_HEADING = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)

    def assert_html(self, html: str) -> None:
        if not html or not html.strip():
            raise AssertionError_("HTML is empty after fetch")
        for pat in self._HTML_NOISE:
            if _has_any(pat, html):
                raise AssertionError_(
                    f"ZeroNoiseAssertionGate (HTML): noise tag {pat.pattern!r} present"
                )

    def assert_xml(self, xml: str) -> str:
        """Asserts the XML boundary is well-formed and returns the inner body.

        Raises AssertionError_ if any check fails.
        """
        if not _has_any(self._XML_OPEN, xml):
            raise AssertionError_("XML: missing <extraction_result> opening tag")
        if not _has_any(self._XML_CLOSE, xml):
            raise AssertionError_("XML: missing </extraction_result> closing tag")
        if not _has_any(self._XML_BODY_OPEN, xml):
            raise AssertionError_("XML: missing <main_body> opening tag")
        if not _has_any(self._XML_BODY_CLOSE, xml):
            raise AssertionError_("XML: missing </main_body> closing tag")

        m = re.search(r"<main_body>(.*?)</main_body>", xml, re.DOTALL)
        if not m:
            raise AssertionError_("XML: malformed <main_body>")
        body = m.group(1).strip()
        if not body:
            raise AssertionError_("XML: <main_body> is empty")

        if not _has_any(self._MD_HEADING, body):
            raise AssertionError_(
                "ZeroNoiseAssertionGate (XML): <main_body> has no Markdown heading"
            )
        return body
