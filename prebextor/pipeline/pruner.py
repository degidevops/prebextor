"""SurgicalPruner: removes noise INSIDE the mapped container.

Per blueprint §2.2 Phase 2, this runs *before* content is fetched.
All pruning happens in-page via `evaluate_js` — no regex on HTML.

v3 changes:
  - prune() returns count of removed nodes
  - prune_and_get_text() prunes then returns innerText directly
    (avoids stale outerHTML issue)
"""

from __future__ import annotations

import json
from typing import List

from ..fetcher.camofox_client import CamoFoxClient


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
    return f"""
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
      // selector errored (e.g. invalid CSS) — skip silently
    }}
  }}
  return {{ ok: true, removed: removed }};
}})()
""".strip()


class SurgicalPruner:
    """Prunes noise from inside the mapped container."""

    def __init__(self, client: CamoFoxClient) -> None:
        self.client = client

    def prune(self, container_selector: str, tab_id: str, user: str) -> int:
        """Execute the pruning IIFE on `tab_id`. Returns the count removed."""
        js = build_prune_js(container_selector, NOISE_SELECTORS)
        result = self.client.evaluate_js(js, tab_id, user)
        if not result:
            return 0
        # Try to parse result as JSON to get removed count
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

        This is the preferred method — it prunes the DOM in-place,
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
