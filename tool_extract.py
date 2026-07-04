"""Prebextor standalone extraction tool — independent of web_tools dispatcher."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .provider import PrebextorProvider


_provider = PrebextorProvider()


def _check_available() -> bool:
    """Check function for tool registry — direct provider availability, no core deps."""
    try:
        return _provider.is_available()
    except Exception:
        return False


async def prebextor_extract_handler(args: Dict[str, Any], **_) -> str:
    """Handler: direct call to PrebextorProvider.extract, return JSON string."""
    urls = args.get("urls", [])
    if not isinstance(urls, list) or not urls:
        return json.dumps(
            {"success": False, "error": "urls required (list of strings)"},
            ensure_ascii=False
        )
    
    # Limit to 5 URLs (Hermes convention)
    urls = urls[:5]
    
    # Provider returns envelope: {"success": True, "data": [...]}
    envelope = _provider.extract(
        urls,
        scroll_to_bottom=args.get("scroll_to_bottom", False),
        wait_after_scroll=args.get("wait_after_scroll", 3000),
    )
    
    # Normalize to standard tool output format
    if envelope.get("success"):
        return json.dumps(
            {"success": True, "results": envelope["data"]},
            ensure_ascii=False
        )
    else:
        return json.dumps(
            {"success": False, "error": envelope.get("error", "extraction failed")},
            ensure_ascii=False
        )


# Schema for tool registry
PREBEXTOR_EXTRACT_SCHEMA = {
    "name": "prebextor_extract",
    "description": (
        "Extract content via Prebextor deterministic engine (CamoFox + markdownify). "
        "Returns clean markdown wrapped in XML boundary tags (<extraction_result>, <main_body>). "
        "No API key required — runs locally. Independent of web.extract_backend config."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 5,
                "description": "URLs to extract content from (max 5)"
            },
            "scroll_to_bottom": {
                "type": "boolean",
                "default": False,
                "description": "Scroll to bottom to trigger lazy-loaded content"
            },
            "wait_after_scroll": {
                "type": "integer",
                "default": 3000,
                "description": "Milliseconds to wait after scrolling"
            }
        },
        "required": ["urls"]
    }
}