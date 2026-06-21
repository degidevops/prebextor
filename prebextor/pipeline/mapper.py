"""StructuralMapper: maps a URL's DOM to one CSS selector for the main content.

Pipeline v3 (NO SNAPSHOT — raw HTML first):
  Phase 1: evaluate_js semantic detection
    1a. Semantic tags: <main>, <article>
    1b. ARIA roles: [role="main"], [role="article"]
    1c. Pattern match: id/class tokens containing content/main/article/body/post/entry/story
  Phase 2: Density fallback (JS-side; highest text-to-tag ratio)

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


class StructuralMapper:
    """Maps a DOM to a single CSS selector for the main content container.

    Strategy: evaluate_js only (no snapshot). Raw HTML detection via JS.
    """

    def __init__(self, client: CamoFoxClient) -> None:
        self.client = client

    def map_selector(self, tab_id: str, user: str) -> str:
        """Return a CSS selector for the main content container.
        Raises MappingError if no selector can be found."""

        # ===== Phase 1: evaluate_js semantic detection =====
        # 1a. Semantic tags + ARIA role via evaluate_js
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

        # 1b. Pattern match via evaluate_js (id/class tokens)
        pattern_js = """(function(){
  var tokens = ['content','main','article','body','post','entry','story'];
  var all = document.querySelectorAll('*[id], *[class]');
  for (var i = 0; i < all.length; i++) {
    var el = all[i];
    var id = el.id || '';
    var cls = el.className || '';
    if (typeof cls !== 'string') cls = '';
    for (var t = 0; t < tokens.length; t++) {
      if (id.toLowerCase().indexOf(tokens[t]) >= 0) {
        return el.tagName.toLowerCase() + '#' + id;
      }
      var clsTokens = cls.split(/\\s+/);
      var matching = clsTokens.filter(function(c){ return c.toLowerCase().indexOf(tokens[t]) >= 0; });
      if (matching.length > 0) {
        return el.tagName.toLowerCase() + '.' + matching.join('.');
      }
    }
  }
  return null;
})()"""
        sel = self.client.evaluate_js(pattern_js, tab_id, user)
        if sel:
            return sel

        # ===== Phase 2: Density fallback (JS-side; highest text-to-tag wins) =====
        density_expr = """(function(){
  var cands = Array.from(
    document.querySelectorAll('main,article,section,div')
  );
  var score = cands.map(function(el){
    return {
      el: el,
      len: (el.innerText||'').length,
      tags: el.getElementsByTagName('*').length
    };
  }).filter(function(x){ return x.len >= 100; });
  if (!score.length) return null;
  score.sort(function(a,b){ return (b.len - b.tags) - (a.len - a.tags); });
  var best = score[0].el;
  if (best.id) { return best.tagName.toLowerCase() + '#' + best.id; }
  if (best.className && typeof best.className === 'string') {
    return best.tagName.toLowerCase() + '.' + best.className.trim().split(/\\s+/).join('.');
  }
  return best.tagName.toLowerCase();
})()"""
        sel = self.client.evaluate_js(density_expr, tab_id, user)
        if sel:
            return sel

        raise MappingError(
            "StructuralMapper: no container identified "
            "(no semantic tag, no ARIA role, no pattern match, no density candidate)"
        )
