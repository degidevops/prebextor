"""IframeExtractor: detects and extracts content from significant iframes.

Strategy:
  1. Detect all iframes in the page
  2. Filter out tracking/ads iframes (small size, known ad domains)
  3. For significant iframes (large, content-bearing), open src in new tab
  4. Extract content from the iframe tab recursively
  5. Merge iframe content into parent page result

This handles cases like CME FedWatch where the main content is in a
cross-origin iframe that cannot be accessed via contentDocument.
"""

from __future__ import annotations


import os
import sys
_pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)
from fetcher.camofox_client import CamoFoxClient

import json
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple




# Known tracking/ads domains to skip
_TRACKING_DOMAINS: List[str] = [
    "doubleclick.net", "google-analytics.com", "googletagmanager.com",
    "facebook.net", "facebook.com/tr", "linkedin.com/collect",
    "reddit.com/rp.gif", "sharethis.com", "twitter.com/i",
    "google.com/recaptcha", "google.com/ccm",
    "ads.", "analytics.", "tracking.", "pixel.",
    "fls.doubleclick", "adservice.google",
]

# Minimum iframe dimensions to be considered "content-bearing"
_MIN_IFRAME_WIDTH = 300
_MIN_IFRAME_HEIGHT = 200


def _is_tracking_url(url: str) -> bool:
    """Check if URL is from a known tracking/ads domain."""
    url_lower = url.lower()
    return any(domain in url_lower for domain in _TRACKING_DOMAINS)


class IframeExtractor:
    """Detects and extracts content from significant iframes."""

    def __init__(self, client: CamoFoxClient) -> None:
        self.client = client

    def detect_significant_iframes(
        self, tab_id: str, user: str
    ) -> List[Dict[str, Any]]:
        """Detect iframes that likely contain main content.

        Returns list of dicts with keys: src, width, height, id, class
        """
        js = """(function(){
  var iframes = document.querySelectorAll('iframe');
  var results = [];
  for (var i = 0; i < iframes.length; i++) {
    var f = iframes[i];
    var rect = f.getBoundingClientRect();
    results.push({
      src: f.src || '',
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      id: f.id || '',
      className: f.className || ''
    });
  }
  return JSON.stringify(results);
})()"""
        result = self.client.evaluate_js(js, tab_id, user)
        if not result:
            return []

        try:
            iframes = json.loads(result) if isinstance(result, str) else result
        except Exception:
            return []

        significant = []
        for iframe in iframes:
            src = iframe.get("src", "")
            width = iframe.get("width", 0)
            height = iframe.get("height", 0)

            # Skip tracking/ads
            if _is_tracking_url(src):
                continue

            # Skip tiny iframes (likely tracking pixels)
            if width < _MIN_IFRAME_WIDTH or height < _MIN_IFRAME_HEIGHT:
                continue

            # Skip empty src
            if not src or src == "about:blank":
                continue

            significant.append(iframe)

        return significant

    def extract_iframe_content(
        self,
        iframe_src: str,
        parent_user: str,
        scroll: bool = False,
        wait_ms: int = 3000,
    ) -> Optional[Dict[str, Any]]:
        """Open iframe src in a new tab and extract its content.

        Returns dict with keys: html, text, title, url
        """
        iframe_user = f"iframe_{uuid.uuid4().hex}"
        tab_id = self.client.open_tab(iframe_src, user=iframe_user)
        if not tab_id:
            return None

        try:
            # Wait for content to load
            time.sleep(3)

            # Get the page content
            js = """(function(){
  return JSON.stringify({
    title: document.title || '',
    text: document.body ? document.body.innerText : '',
    url: window.location.href,
    hasContent: document.body ? document.body.innerText.length > 100 : false
  });
})()"""
            result = self.client.evaluate_js(js, tab_id, iframe_user, timeout=30)
            if not result:
                return None

            try:
                data = json.loads(result) if isinstance(result, str) else result
            except Exception:
                return None

            if not data.get("hasContent"):
                return None

            # Try to get the main content HTML
            html = self.client.get_html(tab_id, iframe_user)

            return {
                "html": html or "",
                "text": data.get("text", ""),
                "title": data.get("title", ""),
                "url": data.get("url", iframe_src),
            }
        finally:
            self.client.close_tab(tab_id, iframe_user)
