"""ContentAwareScorer: CETD-inspired text density analysis for DOM blocks.

Algorithm (based on "DOM Based Content Extraction via Text Density" -- Sun et al., SIGIR 2011):
  1. Traverse DOM tree from mapped container
  2. For each leaf block (p, pre, td, h1-h6, div with direct text):
     - Calculate text density = textLength / numberOfChildTags
     - Calculate link density = linkTextLength / totalTextLength
     - Calculate punctuation score = comma count
     - Composite score = textDensity * (1 - linkDensity) + punctuationBonus
  3. Propagate scores upward to parent nodes
  4. Return scored blocks sorted by composite score

Key principle: This scorer does NOT select "content". It identifies "noise".
High score = likely content. Low score = likely noise.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from ..fetcher.camofox_client import CamoFoxClient


# -- Tunable thresholds --
_MIN_TEXT_LENGTH = 25          # Below this, block scores 0
_LINK_DENSITY_NOISE = 0.5       # Above this, likely navigation/noise
_TEXT_DENSITY_THRESHOLD = 0.5  # Below this after penalty = likely noise
_PUNCTUATION_WEIGHT = 0.1      # Bonus per comma
_LINK_PENALTY_WEIGHT = 1.0     # Penalty multiplier for link density (full penalty)

# CETD formula: composite score per block
# text_density = text_length / (tag_count + 1)  [+1 to avoid div by zero]
# link_penalty = 1.0 - (link_text_length / total_text_length) * LINK_PENALTY_WEIGHT
# score = text_density * link_penalty + comma_count * PUNCTUATION_WEIGHT
# Normalized: divide by 100 to keep scores in 0-5 range


class ScoredBlock:
    """Represents a DOM block with its content-aware scores."""

    def __init__(
        self,
        selector: str,
        text_length: int,
        tag_count: int,
        link_text_length: int,
        comma_count: int,
    ):
        self.selector = selector
        self.text_length = text_length
        self.tag_count = tag_count
        self.link_text_length = link_text_length
        self.comma_count = comma_count

        # Derived metrics
        self.link_density = (
            link_text_length / text_length if text_length > 0 else 0.0
        )
        self.text_density = (
            text_length / tag_count if tag_count > 0 else 0.0
        )

        # Composite score (CETD-inspired formula)
        if text_length < _MIN_TEXT_LENGTH:
            self.score = 0.0
        else:
            # text_density: chars per tag (normalized)
            text_density = text_length / (tag_count + 1)
            # link_penalty: 1.0 for no links, 0.0 for all links
            link_penalty = 1.0 - (link_text_length / text_length) * _LINK_PENALTY_WEIGHT
            link_penalty = max(0.0, link_penalty)
            # Normalize to 0-5 range
            self.score = (text_density * link_penalty) / 100.0 + comma_count * _PUNCTUATION_WEIGHT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selector": self.selector,
            "score": round(self.score, 3),
            "text_length": self.text_length,
            "tag_count": self.tag_count,
            "link_density": round(self.link_density, 3),
            "text_density": round(self.text_density, 3),
            "comma_count": self.comma_count,
        }

    @property
    def is_likely_noise(self) -> bool:
        """Heuristic: low score + high link density = noise.

        Guard (v1.2.1): content-bearing tags (p, article, section, li, td,
        blockquote, pre, h1-h6) with substantial text are NEVER flagged as
        noise, even when link density is high. These tags frequently carry
        the main content on list pages (Hacker News), tables
        (economic calendars), and article sites. Over-pruning them was the
        leading cause of "Empty content extracted" failures on legitimate
        pages.
        """
        if self.score >= _TEXT_DENSITY_THRESHOLD:
            return False
        # Content-bearing tags with substantial text are protected.
        if self.text_length >= _CONTENT_TAG_MIN_TEXT:
            tag = self.selector.split(".")[0].split("#")[0].lower()
            if tag in _CONTENT_TAGS:
                return False
        # Short text inside non-content tags + high link density = noise.
        return self.link_density > _LINK_DENSITY_NOISE


# Tags that frequently carry the main content. They are protected from
# dynamic noise pruning when they have substantial text.
_CONTENT_TAGS: frozenset = frozenset({
    "p", "article", "section", "li", "td", "blockquote", "pre",
    "h1", "h2", "h3", "h4", "h5", "h6", "dt", "dd", "figcaption",
})
# Below this text length, a block is considered too short to protect.
_CONTENT_TAG_MIN_TEXT = 15


def _build_scoring_js(container_selector: str) -> str:
    """Build the JS expression that scores all leaf blocks inside container."""
    sel_escaped = container_selector.replace("'", "\\'")
    return (
        "(function(){"
        f" var container = document.querySelector('{sel_escaped}');"
        " if(!container) return '[]';"
        " var results = [];"
        " var leafTags = ['P','PRE','TD','LI','H1','H2','H3','H4','H5','H6','BLOCKQUOTE','FIGCAPTION','DT','DD'];"
        " function isLeafBlock(el){"
        "   if(leafTags.indexOf(el.tagName)>=0) return true;"
        "   if(el.tagName==='DIV'&&el.children.length===0) return true;"
        "   if(el.tagName==='DIV'){"
        "     var allText = true;"
        "     for(var i=0;i<el.children.length;i++){"
        "       var cn = el.children[i];"
        "       if(cn.tagName==='DIV'||cn.tagName==='P'||cn.tagName==='UL'||cn.tagName==='OL'||cn.tagName==='TABLE'){allText=false;break;}"
        "     }"
        "     if(allText) return true;"
        "   }"
        "   return false;"
        " }"
        " function getTextLen(el){"
        "   return (el.innerText||'').trim().length;"
        " }"
        " function getLinkTextLen(el){"
        "   var links = el.querySelectorAll('a');"
        "   var total = 0;"
        "   for(var i=0;i<links.length;i++){"
        "     total += (links[i].innerText||'').trim().length;"
        "   }"
        "   return total;"
        " }"
        " function getTagCount(el){"
        "   return el.querySelectorAll('*').length;"
        " }"
        " function getCommaCount(el){"
        "   var text = (el.innerText||'').trim();"
        "   var m = text.match(/,/g);"
        "   return m ? m.length : 0;"
        " }"
        " function getSelector(el){"
        "   if(el.id) return el.tagName.toLowerCase()+'#'+el.id;"
        "   if(el.className && typeof el.className === 'string'){"
        "     var cls = el.className.trim().split(/\\s+/).join('.');"
        "     cls = cls.replace(/[^a-zA-Z0-9_\\-\\.]/g,'');"
        "     if(cls) return el.tagName.toLowerCase()+'.'+cls;"
        "   }"
        "   return el.tagName.toLowerCase();"
        " }"
        " function walk(el){"
        "   if(isLeafBlock(el)){"
        "     var tl = getTextLen(el);"
        "     var lt = getLinkTextLen(el);"
        "     var tc = getTagCount(el);"
        "     var cc = getCommaCount(el);"
        "     results.push({sel:getSelector(el),tl:tl,lt:lt,tc:tc,cc:cc});"
        "     return;"
        "   }"
        "   for(var i=0;i<el.children.length;i++){"
        "     walk(el.children[i]);"
        "   }"
        " }"
        " walk(container);"
        " return JSON.stringify(results);"
        "})()"
    )


class ContentAwareScorer:
    """Scores DOM blocks using CETD-inspired text density analysis.

    This scorer identifies noise (navigation, ads, sidebars) by analyzing
    text density, link density, and punctuation patterns. It does NOT
    select "content" -- it identifies what to REMOVE.

    High score = likely content (keep).
    Low score + high link density = likely noise (prune).
    """

    def __init__(self, client: CamoFoxClient) -> None:
        self.client = client

    def score_blocks(
        self, container_selector: str, tab_id: str, user: str
    ) -> List[ScoredBlock]:
        """Score all leaf blocks inside the container.

        Returns list of ScoredBlock, sorted by score descending.
        """
        js = _build_scoring_js(container_selector)
        raw = self.client.evaluate_js(js, tab_id, user, timeout=30)
        if not raw:
            return []

        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return []

        blocks: List[ScoredBlock] = []
        for item in data:
            try:
                block = ScoredBlock(
                    selector=item.get("sel", ""),
                    text_length=int(item.get("tl", 0)),
                    tag_count=int(item.get("tc", 0)),
                    link_text_length=int(item.get("lt", 0)),
                    comma_count=int(item.get("cc", 0)),
                )
                blocks.append(block)
            except (TypeError, ValueError):
                continue

        # Sort by score descending (highest = most likely content)
        blocks.sort(key=lambda b: b.score, reverse=True)
        return blocks

    def get_noise_selectors(
        self, scored_blocks: List[ScoredBlock], max_noise_blocks: int = 10
    ) -> List[str]:
        """Return selectors of blocks that are likely noise.

        Filters blocks where:
          - score < TEXT_DENSITY_THRESHOLD
          - link_density > LINK_DENSITY_NOISE
        Returns up to max_noise_blocks selectors.
        """
        noise = []
        for block in scored_blocks:
            if block.is_likely_noise:
                noise.append(block.selector)
            if len(noise) >= max_noise_blocks:
                break
        return noise

    def compute_confidence(self, scored_blocks: List[ScoredBlock]) -> float:
        """Compute overall content confidence from scored blocks.

        Returns 0.0-1.0 based on:
          - Ratio of high-score blocks to total blocks
          - Average score of top blocks
          - Presence of substantial text content
        """
        if not scored_blocks:
            return 0.0

        total = len(scored_blocks)
        if total == 0:
            return 0.0

        # Count high-score blocks (likely content)
        high_score_count = sum(
            1 for b in scored_blocks
            if b.score >= _TEXT_DENSITY_THRESHOLD
        )
        ratio = high_score_count / total

        # Average score of top 3 blocks
        top_scores = [b.score for b in scored_blocks[:3]]
        avg_top = sum(top_scores) / len(top_scores) if top_scores else 0.0

        # Total text length
        total_text = sum(b.text_length for b in scored_blocks)
        text_factor = min(1.0, total_text / 2000)  # Normalize to 2000 chars

        # Weighted combination
        confidence = (ratio * 0.4) + (min(1.0, avg_top / 5.0) * 0.3) + (text_factor * 0.3)
        return round(min(1.0, max(0.0, confidence)), 3)
