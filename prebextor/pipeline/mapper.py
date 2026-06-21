"""StructuralMapper: maps a URL's DOM to one CSS selector for the main content.

Implements blueprint §2.2 Phase 1 precedence logic, WITHOUT probabilistic
heuristics on content. The decision tree:

    1. semanticTag:   try <main>, then <article>
    2. patternMatch:  scan snapshot for IDs/classes whose tokens include
                      "content", "main", "article", "body", "post"
    3. density:       JS-side scoring of large text-bearing nodes
                      (still deterministic: highest text-to-tag wins)

The mapper never invents selectors. If none of the three passes returns a
selector, the pipeline fails fast.
"""

from __future__ import annotations

import re
from typing import List

from ..fetcher.camofox_client import CamoFoxClient


class MappingError(Exception):
    pass


_COMMON_MAIN_SELECTORS: List[str] = ["main", "article"]

_PATTERN_Tokens: List[str] = [
    "content",
    "main",
    "article",
    "body",
    "post",
    "entry",
    "story",
]


def _has_token(s: str, token: str) -> bool:
    """Case-insensitive substring test. Tokens are deliberately short to be
    deterministic; collisions are mitigated by giving priority to <main>/<article>
    first and id-based selectors over class-based ones."""
    return token.lower() in s.lower()


def _extract_dom_tokens(snapshot: str) -> List[tuple]:
    """Pull (selector_hint, kind) from a camofox snapshot.

    camofox snapshot lines look like:

        generic  [class='post-body']
        heading  "Title"  [level=1]  [ref=e12]

    Returns a list of `(selectorHint, kind)` tuples ready for ranking.
    """
    out: List[tuple] = []
    for line in snapshot.splitlines():
        m_id = re.search(r"\bid=['\"]([^'\"]+)['\"]", line)
        m_class = re.search(r"\bclass=['\"]([^'\"]+)['\"]", line)
        m_tag = re.match(r"^\s*([a-zA-Z][a-zA-Z0-9-]*)", line)
        tag = m_tag.group(1) if m_tag else "div"

        if m_id:
            cid = m_id.group(1).strip()
            for tok in _PATTERN_TOKENS:
                if _has_token(cid, tok):
                    sel = f"{tag}#{cid}" if not cid.startswith("#") else cid
                    out.append((sel, "id"))
                    break
        if m_class:
            tokens = m_class.group(1).strip().split()
            matching = [
                t for t in tokens
                if any(_has_token(t, tok) for tok in _PATTERN_TOKENS)
            ]
            if matching:
                sel = f"{tag}." + ".".join(matching)
                out.append((sel, "class"))
    return out


class StructuralMapper:
    """Maps a DOM to a single CSS selector for the main content container."""

    def __init__(self, client: CamoFoxClient) -> None:
        self.client = client

    def map_selector(self, tab_id: str, user: str) -> str:
        """Return a CSS selector for the main content container. Raises
        MappingError if no selector can be confidently identified."""

        # 1. semantic precedence: <main> then <article>
        for tag in _COMMON_MAIN_SELECTORS:
            probe = (
                "(function(){"
                f" const el = document.querySelector('{tag}');"
                " return el ? 'found' : null;"
                "})()"
            )
            got = self.client.evaluate_js(probe, tab_id, user)
            if got == "found":
                return tag

        # 2. snapshot pattern matching (id before class)
        snap = self.client.snapshot(tab_id, user)
        if snap:
            candidates = _extract_dom_tokens(snap)
            if candidates:
                for sel, kind in candidates:
                    if kind == "id":
                        return sel
                return candidates[0][0]

        # 3. deterministic density fallback (JS-side; highest text-to-tag wins)
        density_expr = (
            "(function(){"
            " const cands = Array.from("
            "   document.querySelectorAll('main,article,section,div')"
            " );"
            " const score = cands.map(el => ({"
            "   el, len: (el.innerText||'').length, tags: el.getElementsByTagName('*').length"
            " })).filter(x => x.len >= 500);"
            " if (!score.length) return null;"
            " score.sort((a,b) => (b.len - b.tags) - (a.len - a.tags));"
            " const best = score[0].el;"
            " if (best.id) { return best.tagName.toLowerCase() + '#' + best.id; }"
            " if (best.className && typeof best.className === 'string') {"
            "   return best.tagName.toLowerCase() + '.' + best.className.trim().split(/\\s+/).join('.')"
            " }"
            " return null;"
            "})()"
        )
        sel = self.client.evaluate_js(density_expr, tab_id, user)
        if sel:
            return sel

        raise MappingError(
            "StructuralMapper: no container identified "
            "(no semantic tag, no pattern match, no high-density candidate)"
        )
