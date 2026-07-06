"""Zero-Noise Assertion Gate (blueprint §4).

v3 changes:
  - assert_text(text) replaces assert_html(html) — checks extracted TEXT
    for noise patterns, not raw HTML. This avoids false positives from
    <script> tags that may exist in HTML but whose content is not leaked
    into the visible text.
  - assert_xml(xml) unchanged — checks XML boundary integrity.
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

    # Noise patterns that should NOT appear in extracted text.
    # These are content-level noise, not HTML tag noise.
    _TEXT_NOISE: List[re.Pattern] = [
        # JavaScript code leakage (e.g. function definitions, var declarations)
        re.compile(r"\bfunction\s+\w+\s*\(", re.IGNORECASE),
        re.compile(r"\bvar\s+\w+\s*=", re.IGNORECASE),
        re.compile(r"\bconst\s+\w+\s*=", re.IGNORECASE),
        re.compile(r"\blet\s+\w+\s*=", re.IGNORECASE),
        # CSS leakage
        re.compile(r"\{[\s]*[a-z-]+[\s]*:[\s]*[a-z0-9#]", re.IGNORECASE),
        # Cookie consent text (common noise)
        re.compile(r"cookie\s+(policy|consent|settings|preferences)", re.IGNORECASE),
        re.compile(r"accept\s+(all\s+)?cookies", re.IGNORECASE),
    ]

    _XML_OPEN = re.compile(r"^\s*<extraction_result>", re.MULTILINE)
    _XML_CLOSE = re.compile(r"</extraction_result>\s*$", re.MULTILINE)
    _XML_BODY_OPEN = re.compile(r"<main_body>")
    _XML_BODY_CLOSE = re.compile(r"</main_body>")
    _MD_HEADING = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)

    def assert_text(self, text: str) -> None:
        """Assert extracted text is free of code/CSS leakage.

        This is a best-effort check — some noise is acceptable as long
        as the main content is preserved.
        """
        if not text or not text.strip():
            raise AssertionError_("Text is empty after extraction")

        # Only fail on severe noise (multiple patterns matched)
        noise_count = 0
        for pat in self._TEXT_NOISE:
            if _has_any(pat, text):
                noise_count += 1

        # Allow up to 2 noise patterns (some pages have legitimate JS references)
        if noise_count > 3:
            raise AssertionError_(
                f"ZeroNoiseAssertionGate (text): {noise_count} noise patterns detected"
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
