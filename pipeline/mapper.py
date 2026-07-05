"""StructuralMapper: maps a URL's DOM to one CSS selector for the main content.

Pipeline v3 (NO SNAPSHOT — raw HTML first):
  Phase 1: evaluate_js semantic detection
    1a. Semantic tags: <main>, <article>
    1b. ARIA roles: [role="main"], [role="article"]
    1c. Pattern match: id/class tokens containing content/main/article/body/post/entry/story
  Phase 2: Density fallback (JS-side; highest text-to-tag ratio)
  Phase 3: Ultimate fallback — return body

The mapper never invents selectors. If no pass returns a selector, returns "body".

v1.0.2 changes:
  - Added _wait_for_content() to handle JS-rendered pages
  - Semantic probes now check innerText length (not just element existence)
  - Pattern match skips empty containers (< 50 chars innerText)
  - Pattern match returns best match (most text) instead of first match
"""

from __future__ import annotations

import json
import os
import sys
import time
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

    v1.0.2: Added content-aware waiting and empty-container filtering.
    """

    def __init__(self, client: CamoFoxClient) -> None:
        self.client = client

    # ── Anti-bot / challenge page detection ──

    _ANTI_BOT_TITLE_KEYWORDS = [
        "robot", "captcha", "challenge", "verify", "are you human",
        "access denied", "blocked", "please verify", "unusual activity",
        "security check", "bot detection",
    ]

    _ANTI_BOT_BODY_KEYWORDS = [
        "unusual activity from your computer",
        "please click the box below to let us know you're not a robot",
        "verify you are human",
        "access denied",
        "please verify your identity",
    ]

    def _detect_anti_bot(self, tab_id: str, user: str) -> Optional[str]:
        """Detect if the current page is an anti-bot/challenge page.

        Returns a warning string if detected, None otherwise.
        """
        js = """(function(){
  var title = (document.title || '').toLowerCase();
  var body = (document.body && document.body.innerText || '').toLowerCase();
  var result = { isBot: false, reason: '' };

  var titleKeywords = ['robot','captcha','challenge','verify','are you human',
    'access denied','blocked','please verify','unusual activity',
    'security check','bot detection'];
  for (var i = 0; i < titleKeywords.length; i++) {
    if (title.indexOf(titleKeywords[i]) >= 0) {
      result.isBot = true;
      result.reason = 'title:' + titleKeywords[i];
      return JSON.stringify(result);
    }
  }

  var bodyKeywords = ['unusual activity from your computer',
    'please click the box below to let us know you\\'re not a robot',
    'verify you are human', 'access denied', 'please verify your identity'];
  for (var j = 0; j < bodyKeywords.length; j++) {
    if (body.indexOf(bodyKeywords[j]) >= 0) {
      result.isBot = true;
      result.reason = 'body:' + bodyKeywords[j].substring(0, 40);
      return JSON.stringify(result);
    }
  }

  return JSON.stringify(result);
})()"""
        try:
            raw = self.client.evaluate_js(js, tab_id, user, timeout=10)
            if raw:
                info = json.loads(raw) if isinstance(raw, str) else raw
                if info.get("isBot"):
                    return f"Anti-bot challenge detected ({info.get('reason', 'unknown')})"
        except Exception:
            pass
        return None

    # ── Content waiting for JS-rendered pages ──

    def _wait_for_content(self, tab_id: str, user: str, timeout: int = 15) -> None:
        """Wait for page to have meaningful content.

        Polls document.readyState and body.innerText length.
        Handles JS-rendered SPAs that need time to populate.
        """
        js = """(function(){
  var state = document.readyState;
  var text = (document.body && document.body.innerText || '').trim();
  return JSON.stringify({ state: state, textLen: text.length });
})()"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                raw = self.client.evaluate_js(js, tab_id, user, timeout=5)
                if raw:
                    info = json.loads(raw) if isinstance(raw, str) else raw
                    if info.get("state") == "complete" and info.get("textLen", 0) >= 100:
                        return
            except Exception:
                pass
            time.sleep(0.5)

    # ── Main mapping logic ──

    def map_selector(self, tab_id: str, user: str) -> tuple:
        """Return (CSS selector, confidence) for the main content container.
        Never raises — always returns a valid selector (falls back to "body").
        Confidence: 0.0-1.0 indicating mapping quality."""

        # v1.0.2: Wait for page to have meaningful content before mapping
        self._wait_for_content(tab_id, user, timeout=15)

        # ===== Phase 1a: Semantic tags + ARIA role =====
        # v1.0.2: Now checks innerText length, not just element existence
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
                " if (!el) return null;"
                " const text = (el.innerText || '').trim();"
                " return text.length >= 50 ? 'found' : 'empty';"
                "})()"
            )
            got = self.client.evaluate_js(probe, tab_id, user)
            if got == "found":
                return (sel, 1.0)
            # If "empty", semantic tag exists but JS hasn't rendered content yet
            # Continue to next selector rather than immediately falling through

        # ===== Phase 1b: Pattern match (id/class tokens) =====
        # v1.0.2: Skip empty containers, return best match (most text)
        pattern_js = """(function(){
  var tokens = ['content','main','article','body','post','entry','story'];
  var all = document.querySelectorAll('*[id], *[class]');
  var best = null;
  var bestLen = 0;
  for (var i = 0; i < all.length; i++) {
    var el = all[i];
    var id = el.id || '';
    var cls = el.className || '';
    if (typeof cls !== 'string') cls = '';
    var text = (el.innerText || '').trim();
    if (text.length < 50) continue;
    for (var t = 0; t < tokens.length; t++) {
      if (id.toLowerCase().indexOf(tokens[t]) >= 0) {
        if (text.length > bestLen) {
          bestLen = text.length;
          best = el.tagName.toLowerCase() + '#' + id;
        }
      }
      var clsTokens = cls.split(/\\s+/);
      var matching = clsTokens.filter(function(c){ return c.toLowerCase().indexOf(tokens[t]) >= 0; });
      if (matching.length > 0) {
        if (text.length > bestLen) {
          bestLen = text.length;
          best = el.tagName.toLowerCase() + '.' + matching.join('.');
        }
      }
    }
  }
  return best;
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
