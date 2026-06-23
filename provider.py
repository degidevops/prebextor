"""Prebextor provider — Hermes Agent backend integration.

Implements the deterministic extraction pipeline as a single
`WebSearchProvider` so Hermes can register this plugin with `register_web_search_provider`.

Pipeline v3 (Raw HTML First — No Snapshot):

    1. open_tab              (browser lifecycle)
    2. StructuralMapper      (Phase 1: discover main container via evaluate_js)
    3. SurgicalPruner        (Phase 2: prune noise inside container)
    4. Text extraction       (Phase 3: innerText from pruned DOM)
    5. IframeExtractor       (Phase 4: extract cross-origin iframe content)
    6. MarkdownConverter     (Phase 5: text -> Markdown)
    7. BoundaryWrapper       (Phase 6: XML boundary wrap)
    7. close_tab             (cleanup)

Key changes from v2:
  - NO SNAPSHOT: StructuralMapper uses evaluate_js only
  - Text-first: extracts innerText from pruned DOM, not outerHTML
  - QA on text, not HTML (avoids false positives from script tags in HTML)
  - Iframe extraction for cross-origin embedded content
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any, Dict, List, Optional

# Lazy import: `agent.web_search_provider` is only resolvable when Hermes is
# installed. We import at runtime inside the class so that the package can
# still be imported in environments where Hermes is missing (e.g. unit tests).
try:
    from agent.web_search_provider import WebSearchProvider  # type: ignore
except Exception:  # pragma: no cover
    WebSearchProvider = object  # type: ignore[misc,assignment]

import sys, os
_pkg = os.path.dirname(os.path.abspath(__file__))
if _pkg not in sys.path:
    sys.path.insert(0, _pkg)

from fetcher.camofox_client import CamoFoxClient
from pipeline.mapper import StructuralMapper
from pipeline.pruner import SurgicalPruner
from pipeline.transform import MarkdownConverter, BoundaryWrapper
from pipeline.iframe_extractor import IframeExtractor
from pipeline.scorer import ContentAwareScorer
from pipeline.validator import ContentValidator


def _extract_title_from_text(text: str) -> str:
    """Pull the first meaningful line from extracted text as title."""
    if not text:
        return ""
    for line in text.splitlines():
        line = line.strip()
        if line and len(line) > 3 and not line.startswith("#"):
            return line[:200]
    return ""


def _extract_title_from_html(html: str) -> str:
    """Pull <title> or first <h1> text from HTML."""
    if not html:
        return ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return ""


class PrebextorProvider(WebSearchProvider):  # type: ignore[misc]
    """Deterministic extraction provider (CamoFox + markdownify)."""

    def __init__(self) -> None:
        self._name = "prebextor"
        self._display = "Prebextor (Deterministic Extraction Engine v3)"
        self._camofox = CamoFoxClient(default_timeout=60)
        self._mapper = StructuralMapper(self._camofox)
        self._pruner = SurgicalPruner(self._camofox)
        self._md = MarkdownConverter()
        self._wrap = BoundaryWrapper()
        self._iframe = IframeExtractor(self._camofox)
        self._scorer = ContentAwareScorer(self._camofox)
        self._validator = ContentValidator(self._camofox)

    # ---------- WebSearchProvider surface ----------

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return self._display

    def is_available(self) -> bool:
        return CamoFoxClient.is_available()

    def supports_search(self) -> bool:
        return False

    def supports_extract(self) -> bool:
        return True

    def search(self, query: str, **_: Any) -> List[Dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError(
            "PrebextorProvider is extraction-only. "
            "Pair with a search provider (e.g. searxng) for web_search."
        )

    # ----------

    def _extract_iframes(self, tab_id: str, user: str, **kwargs: Any) -> List[Dict[str, Any]]:
        """Extract content from significant iframes.

        Returns list of dicts with keys: html, text, title, url
        """
        results: List[Dict[str, Any]] = []
        try:
            iframes = self._iframe.detect_significant_iframes(tab_id, user)
            for iframe_info in iframes:
                src = iframe_info.get("src", "")
                if not src:
                    continue
                iframe_data = self._iframe.extract_iframe_content(
                    src, user,
                    scroll=bool(kwargs.get("scroll_to_bottom", False)),
                    wait_ms=int(kwargs.get("wait_after_scroll", 3000)),
                )
                if iframe_data and iframe_data.get("text"):
                    results.append(iframe_data)
        except Exception:
            pass  # Iframe extraction is best-effort; don't fail the main extraction
        return results

    # ----------

    def _extract_one(self, url: str, **kwargs: Any) -> Dict[str, Any]:
        scroll = bool(kwargs.get("scroll_to_bottom", False))
        wait_ms = int(kwargs.get("wait_after_scroll", 3000))
        user = f"prebextor_{uuid.uuid4().hex}"
        tab_id = self._camofox.open_tab(url, user=user)
        if not tab_id:
            return {
                "url": url, "title": "", "content": "",
                "raw_content": "", "metadata": {}, "error": "Failed to open tab",
            }

        try:
            # Phase 0: Get full page HTML for title extraction
            full_html = self._camofox.get_html(tab_id, user) or ""

            # Phase 1: structural mapping (evaluate_js only, no snapshot)
            # v1.0.1: mapper now returns (selector, confidence)
            selector, mapper_confidence = self._mapper.map_selector(tab_id, user)

            # Phase 2: content-aware scoring (v1.0.1 NEW)
            scored_blocks = self._scorer.score_blocks(selector, tab_id, user)
            noise_selectors = self._scorer.get_noise_selectors(scored_blocks)
            scorer_confidence = self._scorer.compute_confidence(scored_blocks)

            # Phase 3: prune noise inside the mapped container
            # 3a: static noise selectors (existing)
            removed_static = self._pruner.prune(selector, tab_id, user)
            # 3b: dynamic noise from scorer (v1.0.1 NEW)
            removed_dynamic = self._pruner.prune_dynamic(
                selector, noise_selectors, tab_id, user
            )
            removed_total = removed_static + removed_dynamic

            # Phase 4: content validation (v1.0.1 NEW)
            validation = self._validator.validate(
                selector, scored_blocks, tab_id, user
            )

            # Phase 5: get text directly from pruned DOM
            raw_text = self._camofox.get_text(tab_id, user, selector=selector) or ""

            # Also get HTML for raw_content (best-effort)
            raw_html = self._camofox.get_html(tab_id, user, selector=selector) or ""

            # Phase 6: iframe extraction for cross-origin embedded content
            iframe_texts = self._extract_iframes(tab_id, user, **kwargs)

            # Merge iframe text into main text
            merged_text = raw_text
            for iframe_data in iframe_texts:
                iframe_text = iframe_data.get("text", "")
                if iframe_text:
                    merged_text += f"\n\n---\n\n### Embedded: {iframe_data.get('title', 'iframe')}\n\n{iframe_text}"

            # Extract title from FULL page HTML (not just container)
            title = _extract_title_from_html(full_html) or _extract_title_from_html(raw_html) or _extract_title_from_text(merged_text) or url

            # Phase 7: text -> Markdown conversion
            if raw_html and len(raw_html) > 100:
                try:
                    md = self._md.convert(raw_html)
                except Exception:
                    md = merged_text
            else:
                md = merged_text

            # Phase 8: XML boundary wrap
            xml_wrapped = self._wrap.wrap(md, title=title, url=url)

            # Compute final confidence
            final_confidence = round(
                (mapper_confidence * 0.3)
                + (scorer_confidence * 0.3)
                + (validation.confidence * 0.4),
                3,
            )

            return {
                "url": url,
                "title": title,
                "content": xml_wrapped,
                "raw_content": raw_html,
                "metadata": {
                    "selector": selector,
                    "extractor": "prebextor-v3.1",
                    "pipeline": "map->score->prune->validate->text->iframe->md->wrap",
                    "confidence": final_confidence,
                    "mapper_confidence": mapper_confidence,
                    "scorer_confidence": scorer_confidence,
                    "validator_confidence": validation.confidence,
                    "validation_pass": validation.pass_used,
                    "validation_warning": validation.warning,
                    "scored_blocks_count": len(scored_blocks),
                    "noise_selectors_found": len(noise_selectors),
                    "pruned_static": removed_static,
                    "pruned_dynamic": removed_dynamic,
                    "pruned_total": removed_total,
                    "iframes_extracted": len(iframe_texts),
                    "text_length": len(merged_text),
                    "content_aware": True,
                },
                "error": None,
            }
        except Exception as e:
            return {
                "url": url, "title": "", "content": "",
                "raw_content": "", "metadata": {}, "error": f"{type(e).__name__}: {e}",
            }
        finally:
            # Always close the tab to keep CamoFox clean
            self._camofox.close_tab(tab_id, user)

    def extract(self, urls: List[str], **kwargs: Any) -> Dict[str, Any]:
        """Extract content from one or more URLs.

        Returns the Hermes WebSearchProvider envelope:
            {"success": True, "data": [{url,title,content,raw_content,metadata,error?}, ...]}
        On total failure: {"success": False, "error": "..."}

        Supported kwargs (per URL):
            - scroll_to_bottom: bool, trigger lazy loading (default: False)
            - wait_after_scroll: ms to wait after scroll (default: 3000)

        Failures on individual URLs do NOT abort the batch.
        """
        try:
            results: List[Dict[str, Any]] = []
            for url in urls:
                results.append(self._extract_one(url, **kwargs))
            return {"success": True, "data": results}
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}"}
