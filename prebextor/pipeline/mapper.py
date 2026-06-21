"""StructuralMapper: maps a URL's DOM to one CSS selector for the main content.

Pipeline (deterministic, rule-based):
  Phase 1: Snapshot-based structure detection (fast, no truncation)
    1a. Semantic tags: <main>, <article> (via snapshot refs)
    1b. ARIA roles: [role="main"], [role="article"] (via snapshot refs)
    1c. Pattern match: id/class tokens containing content/main/article/body/post/entry/story
  Phase 2: Raw HTML fallback (if snapshot returns no candidates)
    2a. evaluate_js semantic query: document.querySelector('main'), etc.
    2b. evaluate_js ARIA role query: document.querySelector('[role="main"]')
    2c. Density analysis: highest text-to-tag ratio

The mapper never invents selectors. If no pass returns a selector, fail fast.
"""

from __future__ import annotations

import re
from typing import List, Optional

from ..fetcher.camofox_client import CamoFoxClient


class MappingError(Exception):
    pass


# Tokens for pattern matching in id/class names
_PATTERN_TOKENS: List[str] = [
    "content", "main", "article", "body", "post", "entry", "story",
]


def _has_token(s: str, token: str) -> bool:
    return token.lower() in s.lower()


def _extract_candidates_from_snapshot(snapshot: str) -> List[tuple]:
    """Extract (selector, kind) candidates from a camofox snapshot.

    Snapshot lines look like:
        navigation:
        main:
        article:
        generic  [class='post-body']
        heading  "Title"  [level=1]  [ref=e12]

    We look for:
    - Top-level semantic roles: main, article
    - Elements with id/class matching content tokens
    """
    candidates: List[tuple] = []
    seen_roles = set()

    for line in snapshot.splitlines():
        stripped = line.strip()

        # Check for semantic role lines (e.g., "main:", "article:", "navigation:")
        role_match = re.match(r"^(main|article|navigation|complementary|banner|contentinfo|search|form|region)\s*:", stripped)
        if role_match:
            role = role_match.group(1)
            if role in ("main", "article") and role not in seen_roles:
                seen_roles.add(role)
                # Map ARIA role to CSS selector
                if role == "main":
                    candidates.append(('[role="main"]', 'aria_role'))
                elif role == "article":
                    candidates.append(('[role="article"]', 'aria_role'))
            continue

        # Check for id/class patterns in any line
        m_id = re.search(r"\bid=['\"]([^'\"]+)['\"]", line)
        m_class = re.search(r"\bclass=['\"]([^'\"]+)['\"]", line)
        m_tag = re.match(r"^\s*([a-zA-Z][a-zA-Z0-9-]*)", line)
        tag = m_tag.group(1) if m_tag else "div"

        if m_id:
            cid = m_id.group(1).strip()
            for tok in _PATTERN_TOKENS:
                if _has_token(cid, tok):
                    sel = f"{tag}#{cid}" if not cid.startswith("#") else cid
                    candidates.append((sel, 'id'))
                    break

        if m_class:
            tokens = m_class.group(1).strip().split()
            matching = [
                t for t in tokens
                if any(_has_token(t, tok) for tok in _PATTERN_TOKENS)
            ]
            if matching:
                sel = f"{tag}." + ".".join(matching)
                candidates.append((sel, 'class'))

    return candidates


class StructuralMapper:
    """Maps a DOM to a single CSS selector for the main content container.

    Strategy: Snapshot first (fast, structural), then evaluate_js fallback.
    """

    def __init__(self, client: CamoFoxClient) -> None:
        self.client = client

    def map_selector(self, tab_id: str, user: str) -> str:
        """Return a CSS selector for the main content container.
        Raises MappingError if no selector can be found."""

        # ===== Phase 1: Snapshot-based detection (fast, no truncation) =====
        snap = self.client.snapshot(tab_id, user)
        if snap:
            candidates = _extract_candidates_from_snapshot(snap)

            # 1a. Prefer ARIA role selectors first (most specific)
            for sel, kind in candidates:
                if kind == 'aria_role':
                    return sel

            # 1b. Then id-based pattern matches
            for sel, kind in candidates:
                if kind == 'id':
                    return sel

            # 1c. Then class-based pattern matches
            for sel, kind in candidates:
                if kind == 'class':
                    return sel

        # ===== Phase 2: Raw HTML / evaluate_js fallback =====
        # 2a. Semantic tag + ARIA role via evaluate_js
        _js_semantic = [
            "main",
            "article",
            '[role="main"]',
            '[role="article"]',
        ]
        for sel in _js_semantic:
            probe = (
                "(function(){"
                f" const el = document.querySelector('{sel}');"
                " return el ? 'found' : null;"
                "})()"
            )
            got = self.client.evaluate_js(probe, tab_id, user)
            if got == "found":
                return sel

        # 2b. Density fallback (JS-side; highest text-to-tag wins)
        density_expr = """(function(){
 const cands = Array.from(
   document.querySelectorAll('main,article,section,div')
 );
 const score = cands.map(el => ({
   el, len: (el.innerText||'').length, tags: el.getElementsByTagName('*').length
 })).filter(x => x.len >= 100);
 if (!score.length) return null;
 score.sort((a,b) => (b.len - b.tags) - (a.len - a.tags));
 const best = score[0].el;
 if (best.id) { return best.tagName.toLowerCase() + '#' + best.id; }
 if (best.className && typeof best.className === 'string') {
   return best.tagName.toLowerCase() + '.' + best.className.trim().split(/\\s+/).join('.')
 }
 return best.tagName.toLowerCase();
})()"""
        sel = self.client.evaluate_js(density_expr, tab_id, user)
        if sel:
            return sel

        raise MappingError(
            "StructuralMapper: no container identified "
            "(snapshot empty, no semantic tag, no ARIA role, no pattern match, no density candidate)"
        )
