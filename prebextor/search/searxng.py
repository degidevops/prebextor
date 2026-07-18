"""SearXNG search engine for Prebextor.

SearXNG is a free, privacy-respecting metasearch engine that aggregates
results from multiple search engines. You self-host it, then point
``SEARXNG_URL`` at your instance.

Usage standalone::

    from prebextor.search.searxng import SearXNGSearchEngine
    engine = SearXNGSearchEngine(searxng_url="http://localhost:8080")
    result = engine.search("latest AI news", limit=5)

Or via env var::

    from prebextor.search.searxng import SearXNGSearchEngine
    import os
    os.environ["SEARXNG_URL"] = "http://localhost:8080"
    engine = SearXNGSearchEngine()  # reads SEARXNG_URL from env

Dependencies:
    - ``httpx`` (recommended, faster)
    - Falls back to ``urllib.request`` from stdlib when httpx is not installed
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _searxng_url_from_env() -> str:
    """Resolve SEARXNG_URL: process env first, then .env file."""
    val = os.getenv("SEARXNG_URL", "")
    if val:
        return val.strip()

    # Try .env file (Hermes-compatible)
    try:
        from dotenv import load_dotenv

        load_dotenv()
        val = os.getenv("SEARXNG_URL", "")
        if val:
            return val.strip()
    except ImportError:
        pass

    return ""


class SearXNGSearchEngine:
    """Search via a user-hosted SearXNG instance.

    Args:
        searxng_url: Base URL of SearXNG instance (e.g. ``http://localhost:8080``).
            Falls back to ``SEARXNG_URL`` env var when ``None``.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        searxng_url: Optional[str] = None,
        timeout: int = 15,
    ) -> None:
        self._url = (searxng_url or _searxng_url_from_env()).rstrip("/")
        self._timeout = timeout

    def is_available(self) -> bool:
        """Return True when SEARXNG_URL is configured."""
        return bool(self._url)

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Execute a search against SearXNG and return normalized results.

        Returns the standard provider envelope::

            {"success": True, "data": {"web": [{title, url, description, position}, ...]}}

        On failure::

            {"success": False, "error": "..."}
        """
        if not self._url:
            return {"success": False, "error": "SEARXNG_URL is not set"}

        params: Dict[str, Any] = {
            "q": query,
            "format": "json",
            "pageno": 1,
        }

        try:
            raw_results = self._call_api(params)
        except Exception as exc:
            logger.warning("SearXNG search failed: %s", exc)
            return {"success": False, "error": f"SearXNG search failed: {exc}"}

        # Sort by score descending and cap to limit
        sorted_results = sorted(
            raw_results,
            key=lambda r: float(r.get("score", 0)),
            reverse=True,
        )[:limit]

        web_results = [
            {
                "title": str(r.get("title", "")),
                "url": str(r.get("url", "")),
                "description": str(r.get("content", "")),
                "position": i + 1,
            }
            for i, r in enumerate(sorted_results)
        ]

        logger.info(
            "SearXNG '%s': %d results (from %d raw, limit %d)",
            query, len(web_results), len(raw_results), limit,
        )
        return {"success": True, "data": {"web": web_results}}

    def _call_api(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Make the HTTP request to SearXNG — tries httpx first, falls back to urllib."""
        try:
            return self._call_via_httpx(params)
        except ImportError:
            return self._call_via_urllib(params)

    def _call_via_httpx(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search using httpx (async-capable, faster)."""
        import httpx

        url = f"{self._url}/search"
        resp = httpx.get(
            url,
            params=params,
            timeout=self._timeout,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])

    def _call_via_urllib(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fallback search using urllib from stdlib."""
        from urllib import request
        from urllib.parse import urlencode

        url = f"{self._url}/search?{urlencode(params)}"
        req = request.Request(url, headers={"Accept": "application/json"})
        with request.urlopen(req, timeout=self._timeout) as resp:
            data = json.loads(resp.read().decode())
        return data.get("results", [])