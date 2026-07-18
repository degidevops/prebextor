"""Prebextor standalone search tool — independent of web_tools dispatcher.

Can be used directly from Python (for pi, scripts, etc.)::

    from prebextor import PrebextorProvider
    provider = PrebextorProvider(searxng_url="http://localhost:8080")
    result = provider.search("latest AI news", limit=5)
    print(result["data"]["web"])
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from .provider import PrebextorProvider

# Singleton provider with SearXNG search enabled
_provider = PrebextorProvider(
    max_concurrent=3,
    timeout=30,
    cache_ttl_hours=168,
    enable_quality_filter=True,
    enable_metrics=False,
    searxng_url=os.getenv("SEARXNG_URL"),
)


def _check_available() -> bool:
    """Check function for tool registry — CamoFox OR SearXNG must be available."""
    try:
        return _provider.is_available() or bool(os.getenv("SEARXNG_URL"))
    except Exception:
        return False


async def prebextor_search_handler(args: Dict[str, Any], **_) -> str:
    """Handler: direct call to PrebextorProvider.search, return JSON string."""
    query = args.get("query", "")
    if not query or not isinstance(query, str):
        return json.dumps(
            {"success": False, "error": "query required (string)"},
            ensure_ascii=False
        )

    limit = min(int(args.get("limit", 5)), 20)

    envelope = _provider.search(query, limit=limit)

    if envelope.get("success"):
        return json.dumps(
            {"success": True, "results": envelope["data"]["web"]},
            ensure_ascii=False
        )
    else:
        return json.dumps(
            {"success": False, "error": envelope.get("error", "search failed")},
            ensure_ascii=False
        )


# Schema for tool registry
PREBEXTOR_SEARCH_SCHEMA = {
    "name": "prebextor_search",
    "description": (
        "Search the web via Prebextor engine (SearXNG backend). "
        "Returns title, URL, and description for each result. "
        "Requires SEARXNG_URL environment variable pointing to a SearXNG instance. "
        "No API key required — SearXNG is self-hosted."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "limit": {
                "type": "integer",
                "default": 5,
                "description": "Maximum number of results (max 20)"
            }
        },
        "required": ["query"]
    }
}