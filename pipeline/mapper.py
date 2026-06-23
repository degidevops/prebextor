"""StructuralMapper: maps a URL's DOM to one CSS selector for the main content.

import sys
import os
_pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)
Pipeline v3 (NO SNAPSHOT — raw HTML first):
  Phase 1: evaluate_js semantic detection
    1a. Semantic tags: <main>, <article>
    1b. ARIA roles: [role="main"], [role="article"]
    1c. Pattern match: id/class tokens containing content/main/article/body/post/entry/story
  Phase 2: Density fallback (JS-side; highest text-to-tag ratio)
  Phase 3: Ultimate fallback — return body

The mapper never invents selectors. If no pass returns a selector, returns "body".
"""

from __future__ import annotations


import os
import sys
_pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)
from fetcher.camofox_client import CamoFoxClient

import re
from typing import List, Optional




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

    v1.0.1: Now returns (selector, confidence) tuple.
      Confidence levels:
        1.0 — semantic tag found (<main>, <article>)
        0.8 — ARIA role found
        0.6 — pattern match (id/class tokens)
        0.4 — density fallback
        0.2 — ultimate fallback (body)
    """

    def __init__(self, client: CamoFoxClient) -> None:
        self.client = client

    def map_selector(self, tab_id: str, user: str) -> tuple:
        """Return (CSS selector, confidence) for the main content container.
        Never raises — always returns a valid selector (falls back to "body").
        Confidence: 0.0-1.0 indicating mapping quality."""

        # ===== Phase 1a: Semantic tags + ARIA role =====
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
                return (sel, 1.0)

        # ===== Phase 1b: Pattern match (id/class tokens) =====
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
            return (sel, 0.6)

        # ===== Phase 2: Density fallback =====
        density_expr = """(function(){
  var cands = Array.from(document.querySelectorAll('main,article,section,div'));
  var score = cands.map(function(el){
    return { el: el, len: (el.innerText||'').length, tags: el.getElementsByTagName('*').length };
  }).filter(function(x){ return x.len >= 50; });
  if (!score.length) return null;
  score.sort(function(a,b){ return (b.len - b.tags) - (a.len - a.tags); });
  var best = score[0].el;
  if (best.id) { return best.tagName.toLowerCase() + '#' + best.id; }
  if (best.className && typeof best.className === 'string') {
    var cls = best.className.trim().split(/\\s+/).join('.');
    cls = cls.replace(/[^a-zA-Z0-9_\\-\\.]/g, '');
    if(cls) return best.tagName.toLowerCase() + '.' + cls;
  }
  return best.tagName.toLowerCase();
})()"""
        sel = self.client.evaluate_js(density_expr, tab_id, user)
        if sel:
            return (sel, 0.4)

        # ===== Phase 3: Ultimate fallback =====
        return ("body", 0.2)
