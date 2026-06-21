"""Prebextor provider — Hermes Agent backend integration.

Implements the deterministic extraction pipeline as a single
`WebSearchProvider` so Hermes can register this plugin with `register_web_search_provider`.

Pipeline order (each atomic unit is a single method call):

    1. open_tab            (browser lifecycle)
    2. StructuralMapper    (Phase 1: discover main container)
    3. SurgicalPruner      (Phase 2: prune noise inside container)
    4. FidelityFetcher     (Phase 3: chunked innerHTML of container)
    5. ZeroNoiseAssertionGate.assert_html  (QA pass 1)
    6. MarkdownConverter   (Phase 4a: HTML -> Markdown)
    7. BoundaryWrapper     (Phase 4b: XML boundary wrap)
    8. ZeroNoiseAssertionGate.assert_xml   (QA pass 2)
    9. close_tab           (cleanup)

Return shape for `extract()` follows the WebSearchProvider contract:
    [{"url", "title", "content" (XML-wrapped md), "raw_content" (cleaned html),
      "metadata" (selector used), "error"?}]
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


from .fetcher.camofox_client import CamoFoxClient
from .pipeline.mapper import StructuralMapper, MappingError
from .pipeline.pruner import SurgicalPruner
from .pipeline.qa import ZeroNoiseAssertionGate, AssertionError_
from .pipeline.transform import MarkdownConverter, BoundaryWrapper


def _extract_title_from_html(html: str) -> str:
    """Pull <title> or first <h1> text from the cleaned HTML."""
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
        self._display = "Prebextor (Deterministic Extraction Engine)"
        self._camofox = CamoFoxClient(default_timeout=30)
        self._mapper = StructuralMapper(self._camofox)
        self._pruner = SurgicalPruner(self._camofox)
        self._qa = ZeroNoiseAssertionGate()
        self._md = MarkdownConverter()
        self._wrap = BoundaryWrapper()

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
        # Prebextor is extraction-only; pair with searxng (or similar) for search.
        return False

    def supports_extract(self) -> bool:
        return True

    # Prebextor does not implement search; raise explicitly so the user is
    # not misled into expecting results.
    def search(self, query: str, **_: Any) -> List[Dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError(
            "PrebextorProvider is extraction-only. "
            "Pair with a search provider (e.g. searxng) for web_search."
        )

    # ---------- core extraction ----------

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
            # Phase 1: structural mapping
            selector = self._mapper.map_selector(tab_id, user)

            # Phase 2: client-side pruning INSIDE the mapped container
            self._pruner.prune(selector, tab_id, user)

            # Phase 3: chunked innerHTML of the mapped container
            cleaned_html = self._camofox.get_html(tab_id, user, selector=selector)
            if cleaned_html is None:
                return {
                    "url": url, "title": "", "content": "",
                    "raw_content": "", "metadata": {"selector": selector},
                    "error": "Failed to fetch container HTML",
                }

            # QA pass 1: cleaned HTML
            self._qa.assert_html(cleaned_html)

            title = _extract_title_from_html(cleaned_html) or url

            # Phase 4a: HTML -> Markdown
            md = self._md.convert(cleaned_html)

            # Phase 4b: XML boundary wrap
            xml_wrapped = self._wrap.wrap(md, title=title, url=url)

            # QA pass 2: boundary integrity + markdown has heading
            self._qa.assert_xml(xml_wrapped)

            return {
                "url": url,
                "title": title,
                "content": xml_wrapped,
                "raw_content": cleaned_html,
                "metadata": {
                    "selector": selector,
                    "extractor": "prebextor",
                    "pipeline": "mapping->pruning->fetching->qa->markdown->wrap->qa",
                },
            }
        except (MappingError, AssertionError_) as e:
            return {
                "url": url, "title": "", "content": "",
                "raw_content": "", "metadata": {}, "error": str(e),
            }
        except Exception as e:  # last-resort isolation
            return {
                "url": url, "title": "", "content": "",
                "raw_content": "", "metadata": {}, "error": f"{type(e).__name__}: {e}",
            }
        finally:
            self._camofox.close_tab(tab_id, user)

    def extract(self, urls: List[str], **kwargs: Any) -> List[Dict[str, Any]]:
        """Extract content from one or more URLs.

        Supported kwargs (per URL):
            - scroll_to_bottom: bool, trigger lazy loading (default: False)
            - wait_after_scroll: ms to wait after scroll (default: 3000)

        Returns list of dicts following the WebSearchProvider contract.
        Failures on individual URLs do NOT abort the batch.
        """
        results: List[Dict[str, Any]] = []
        for url in urls:
            results.append(self._extract_one(url, **kwargs))
        return results
