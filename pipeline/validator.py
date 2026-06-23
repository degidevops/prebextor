"""ContentValidator: Multi-pass content validation with fallback.

Validates that extracted content is substantial and not over-pruned.
Implements a 3-pass strategy:

  Pass 1 (strict):  High thresholds -- content must be substantial
  Pass 2 (relaxed): Lower thresholds -- accept less content
  Pass 3 (fallback): Return body with warning -- better than nothing

Key principle: It's better to return some noise than to lose content.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# Support both package import and direct file import
_pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)
from fetcher.camofox_client import CamoFoxClient

# Lazy import to avoid circular deps during module loading
_scorer_mod = None

def _get_scorer_mod():
    global _scorer_mod
    if _scorer_mod is None:
        from prebextor.pipeline import scorer as _scorer_mod
    return _scorer_mod


# -- Pass thresholds --
_PASS1_MIN_TEXT = 200
_PASS1_MIN_COMMAS = 2
_PASS1_MIN_SCORE = 3.0
_PASS1_MAX_LINK_DENSITY = 0.4

_PASS2_MIN_TEXT = 100
_PASS2_MIN_COMMAS = 1
_PASS2_MIN_SCORE = 1.0
_PASS2_MAX_LINK_DENSITY = 0.6

_PASS3_MIN_TEXT = 50   # Absolute minimum -- almost anything


class ValidationResult:
    """Result of content validation."""

    def __init__(
        self,
        selector: str,
        text_length: int,
        comma_count: int,
        link_density: float,
        avg_score: float,
        confidence: float,
        pass_used: int,
        warning: Optional[str] = None,
    ):
        self.selector = selector
        self.text_length = text_length
        self.comma_count = comma_count
        self.link_density = link_density
        self.avg_score = avg_score
        self.confidence = confidence
        self.pass_used = pass_used
        self.warning = warning

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selector": self.selector,
            "text_length": self.text_length,
            "comma_count": self.comma_count,
            "link_density": round(self.link_density, 3),
            "avg_score": round(self.avg_score, 3),
            "confidence": self.confidence,
            "pass_used": self.pass_used,
            "warning": self.warning,
        }


def _build_content_check_js(selector: str) -> str:
    """Build JS to check content metrics of a selector."""
    sel_escaped = selector.replace("'", "\\'")
    return (
        "(function(){"
        f" var el = document.querySelector('{sel_escaped}');"
        " if(!el) return null;"
        " var text = (el.innerText||'').trim();"
        " var links = el.querySelectorAll('a');"
        " var linkLen = 0;"
        " for(var i=0;i<links.length;i++){"
        "   linkLen += (links[i].innerText||'').trim().length;"
        " }"
        " var commas = (text.match(/,/g)||[]).length;"
        " var ld = text.length > 0 ? linkLen / text.length : 0;"
        " return JSON.stringify({"
        "   textLen: text.length,"
        "   commas: commas,"
        "   linkDensity: ld,"
        "   hasContent: text.length > 0"
        " });"
        "})()"
    )


class ContentValidator:
    """Validates extracted content with multi-pass fallback.

    Pass 1 (strict):  Requires substantial content with good metrics
    Pass 2 (relaxed): Accepts less content with moderate metrics
    Pass 3 (fallback): Returns body-level content with warning

    The validator never discards content -- it only adjusts confidence.
    """

    def __init__(self, client: CamoFoxClient) -> None:
        self.client = client

    def validate(
        self,
        selector: str,
        scored_blocks: Optional[List[Any]] = None,
        tab_id: str = "",
        user: str = "",
    ) -> ValidationResult:
        """Run multi-pass validation on the extracted content.

        Returns ValidationResult with confidence and pass_used.
        """
        # Check content metrics
        js = _build_content_check_js(selector)
        raw = self.client.evaluate_js(js, tab_id, user, timeout=15)
        if not raw:
            return self._fallback_result(selector, "Content check returned empty")

        try:
            metrics = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return self._fallback_result(selector, "Failed to parse content metrics")

        if not metrics or not metrics.get("hasContent"):
            return self._fallback_result(selector, "No content found in selector")

        text_len = int(metrics.get("textLen", 0))
        commas = int(metrics.get("commas", 0))
        link_density = float(metrics.get("linkDensity", 0.0))

        # Average score of scored blocks
        avg_score = 0.0
        if scored_blocks:
            top = scored_blocks[:5]
            avg_score = sum(b.score for b in top) / len(top)

        # -- Pass 1: Strict --
        if (
            text_len >= _PASS1_MIN_TEXT
            and commas >= _PASS1_MIN_COMMAS
            and avg_score >= _PASS1_MIN_SCORE
            and link_density <= _PASS1_MAX_LINK_DENSITY
        ):
            confidence = min(1.0, 0.7 + (avg_score / 10.0) * 0.3)
            return ValidationResult(
                selector=selector,
                text_length=text_len,
                comma_count=commas,
                link_density=link_density,
                avg_score=avg_score,
                confidence=round(confidence, 3),
                pass_used=1,
            )

        # -- Pass 2: Relaxed --
        if (
            text_len >= _PASS2_MIN_TEXT
            and commas >= _PASS2_MIN_COMMAS
            and avg_score >= _PASS2_MIN_SCORE
            and link_density <= _PASS2_MAX_LINK_DENSITY
        ):
            confidence = min(0.7, 0.4 + (avg_score / 10.0) * 0.3)
            return ValidationResult(
                selector=selector,
                text_length=text_len,
                comma_count=commas,
                link_density=link_density,
                avg_score=avg_score,
                confidence=round(confidence, 3),
                pass_used=2,
                warning="Relaxed validation -- content may include some noise",
            )

        # -- Pass 3: Fallback --
        if text_len >= _PASS3_MIN_TEXT:
            return ValidationResult(
                selector=selector,
                text_length=text_len,
                comma_count=commas,
                link_density=link_density,
                avg_score=avg_score,
                confidence=0.2,
                pass_used=3,
                warning=f"Fallback validation -- low confidence ({text_len} chars, {commas} commas)",
            )

        # -- Ultimate fallback: body --
        return self._fallback_result(
            selector,
            f"Content too short ({text_len} chars) -- consider body fallback",
        )

    def _fallback_result(
        self, selector: str, warning: str
    ) -> ValidationResult:
        """Create a low-confidence fallback result."""
        return ValidationResult(
            selector=selector,
            text_length=0,
            comma_count=0,
            link_density=0.0,
            avg_score=0.0,
            confidence=0.1,
            pass_used=3,
            warning=warning,
        )
