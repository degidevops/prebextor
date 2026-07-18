#!/usr/bin/env python3
"""Prebextor CLI — callable as ``python3 -m prebextor <command>``.

Usage::

    # Search
    python3 -m prebextor search "query" --limit 5
    
    # Extract
    python3 -m prebextor extract https://example.com --scroll
    
    # Info
    python3 -m prebextor info

Requires ``SEARXNG_URL`` env var for search (atau via ``--searxng-url``).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_search(args: List[str]) -> int:
    """prebextor search <query> [--limit N] [--searxng-url URL]"""
    from prebextor import PrebextorProvider

    query = None
    limit = 5
    searxng_url = os.getenv("SEARXNG_URL")

    i = 0
    while i < len(args):
        if args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        elif args[i] == "--searxng-url" and i + 1 < len(args):
            searxng_url = args[i + 1]
            i += 2
        elif not query:
            query = args[i]
            i += 1
        else:
            print(f"Unknown arg: {args[i]}", file=sys.stderr)
            return 1

    if not query:
        print("Usage: prebextor search <query> [--limit N] [--searxng-url URL]", file=sys.stderr)
        return 1

    provider = PrebextorProvider(searxng_url=searxng_url)
    result = provider.search(query, limit=limit)
    _print_json(result)
    return 0 if result.get("success") else 1


def cmd_extract(args: List[str]) -> int:
    """prebextor extract <url> [--scroll] [--wait MS]"""
    from prebextor import PrebextorProvider

    urls: List[str] = []
    scroll = False
    wait = 3000

    i = 0
    while i < len(args):
        if args[i] == "--scroll":
            scroll = True
            i += 1
        elif args[i] == "--wait" and i + 1 < len(args):
            wait = int(args[i + 1])
            i += 2
        elif args[i].startswith("http"):
            urls.append(args[i])
            i += 1
        else:
            print(f"Unknown arg: {args[i]}", file=sys.stderr)
            return 1

    if not urls:
        print("Usage: prebextor extract <url> [<url2> ...] [--scroll] [--wait MS]", file=sys.stderr)
        return 1

    provider = PrebextorProvider()
    result = provider.extract(urls, scroll_to_bottom=scroll, wait_after_scroll=wait)
    _print_json(result)
    return 0 if result.get("success") else 1


def cmd_info(args: List[str]) -> int:
    """prebextor info — show provider status"""
    from prebextor import PrebextorProvider, __version__

    provider = PrebextorProvider()
    info = {
        "version": __version__,
        "name": provider.name,
        "display_name": provider.display_name,
        "supports_search": provider.supports_search(),
        "supports_extract": provider.supports_extract(),
        "camofox_available": False,
        "searxng_configured": False,
    }

    try:
        info["camofox_available"] = provider.is_available()
    except Exception:
        pass

    info["searxng_configured"] = bool(os.getenv("SEARXNG_URL"))

    _print_json(info)
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 -m prebextor <search|extract|info> [args...]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Commands:", file=sys.stderr)
        print("  search <query>     Search web via SearXNG", file=sys.stderr)
        print("  extract <url>      Extract content from URL", file=sys.stderr)
        print("  info               Show provider status", file=sys.stderr)
        return 1

    cmd = sys.argv[1]
    cmd_args = sys.argv[2:]

    if cmd == "search":
        return cmd_search(cmd_args)
    elif cmd == "extract":
        return cmd_extract(cmd_args)
    elif cmd == "info":
        return cmd_info(cmd_args)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print("Available: search, extract, info", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())