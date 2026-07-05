"""SurgicalPruner: removes noise INSIDE the mapped container.

Per blueprint Phase 2, this runs *before* content is fetched.
All pruning happens in-page via `evaluate_js` -- no regex on HTML.

v1.0.1 enhancements:
  - prune() returns count of removed nodes
  - prune_and_get_text() prunes then returns innerText directly
  - prune_dynamic() removes blocks identified as noise by ContentAwareScorer
"""

from __future__ import annotations


import os
import sys
_pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)
from fetcher.camofox_client import CamoFoxClient

import json
from typing import List




# A precise, hand-curated noise list. Conservative on purpose: false
# negatives (missing some noise) are accepted; false positives (deleting real
# content) are not.
NOISE_SELECTORS: List[str] = [
    # always-noise structural tags
    "nav",
    "aside",
    "footer",
    "header",
    # ads (specific class/id-style names that are unambiguous)
    ".ad-banner", ".ad-slot", ".ad-container", ".ad-wrapper",
    "#ad-banner", "#ad-slot", "#ad-container",
    # modal/popup/consent
    ".modal", ".popup", ".cookie-banner", ".consent-banner",
    # newsletter / survey
    ".newsletter", "#newsletter", ".newsletter-signup",
    ".survey", "#survey",
    # share / social
    ".social-share", ".share-buttons", ".social-icons",
    # misc widgets that almost never carry article content
    ".sidebar-widget", ".related-posts", ".recommended",
    # scripts/embeds that can survive the mapped-container
    "script", "style", "noscript", "link[rel='import']",
]


def build_prune_js(container_selector: str, selectors: List[str]) -> str:
    """Compose the IIFE that prunes noise inside `container_selector`."""
    sel_json = json.dumps(selectors)
    sel_escaped = container_selector.replace("'", "\\'")
    return """
(function(){{
  const container = document.querySelector('{sel_escaped}');
  if (!container) return {{ ok: false, reason: 'container_not_found' }};
  const sels = {sel_json};
  let removed = 0;
  for (const sel of sels) {{
    try {{
      const nodes = container.querySelectorAll(sel);
      for (const n of nodes) {{
        if (n && n.parentNode) {{ n.parentNode.removeChild(n); removed++; }}
      }}
    }} catch (e) {{
      // selector errored (e.g. invalid CSS) -- skip silently
    }}
  }}
  return {{ ok: true, removed: removed }};
}})()
""".format(sel_escaped=sel_escaped, sel_json=sel_json).strip()


class SurgicalPruner:
    """Prunes noise from inside the mapped container.

    v1.0.1: Added prune_dynamic() for content-aware noise removal.
    """

    def __init__(self, client: CamoFoxClient) -> None:
        self.client = client

    def prune(self, container_selector: str, tab_id: str, user: str) -> int:
        """Execute the pruning IIFE on `tab_id`. Returns the count removed."""
        js = build_prune_js(container_selector, NOISE_SELECTORS)
        result = self.client.evaluate_js(js, tab_id, user)
        if not result:
            return 0
        try:
            data = json.loads(result) if isinstance(result, str) else result
            if isinstance(data, dict):
                return data.get("removed", 0)
        except Exception:
            pass
        return 0

    def prune_and_get_text(
        self, container_selector: str, tab_id: str, user: str
    ) -> tuple:
        """Prune noise then return (text, removed_count).

        This is the preferred method -- it prunes the DOM in-place,
        then reads innerText directly from the live DOM. This avoids
        the stale outerHTML issue where el.outerHTML doesn't reflect
        DOM modifications.
        """
        removed = self.prune(container_selector, tab_id, user)

        # Now read text directly from the pruned DOM
        sel_escaped = container_selector.replace("'", "\\'")
        text_js = (
            f"(function(){{"
            f" const el = document.querySelector('{sel_escaped}');"
            f" if(!el) return '';"
            f" return el.innerText;"
            f"}})()"
        )
        text = self.client.evaluate_js(text_js, tab_id, user, timeout=30) or ""

        return text, removed

    def prune_dynamic(
        self,
        container_selector: str,
        noise_selectors: List[str],
        tab_id: str,
        user: str,
    ) -> int:
        """Prune blocks identified as noise by ContentAwareScorer.

        v1.0.1 addition -- removes blocks that the scorer identified
        as likely noise (high link density, low text density).

        v1.2.1 -- per-node content guard: only remove a matched node if its
        innerText is shorter than a content threshold. This prevents the
        generic-selector over-prune bug: when the noise selector is a bare
        tag like `p` or `td`, querySelectorAll matches ALL instances inside
        the container -- including legitimate content blocks. We skip any
        node whose own innerText exceeds _NOISE_TEXT_CAP, so only true
        short-link/nav fragments get pruned.

        Args:
            container_selector: The parent container selector
            noise_selectors: List of selectors to prune (from scorer)
            tab_id: Browser tab ID
            user: Browser user ID

        Returns:
            Number of nodes removed
        """
        if not noise_selectors:
            return 0

        # Per-node cap: skip removing a node whose own text exceeds this.
        # Scorer only flags short high-link-density blocks as noise, so any
        # matched block longer than this is content that shares the tag and
        # must be preserved.
        _NOISE_TEXT_CAP = 60

        # Escape container selector once
        container_escaped = container_selector.replace("'", "\\'")

        removed = 0
        for sel in noise_selectors:
            sel_escaped = sel.replace("'", "\\'")
            js = (
                "(function(){"
                f" var container = document.querySelector('{container_escaped}');"
                " if(!container) return 0;"
                f" var nodes = container.querySelectorAll('{sel_escaped}');"
                " var count = 0;"
                " for(var i=0;i<nodes.length;i++){"
                "   var n = nodes[i];"
                "   if(!n || !n.parentNode) continue;"
                "   var ownLen = (n.innerText || '').trim().length;"
                "   if(ownLen > " + str(_NOISE_TEXT_CAP) + ") continue;"
                "   n.parentNode.removeChild(n);"
                "   count++;"
                " }"
                " return count;"
                "})()"
            )
            result = self.client.evaluate_js(js, tab_id, user, timeout=15)
            if result:
                try:
                    removed += int(result)
                except (TypeError, ValueError):
                    pass
        return removed
