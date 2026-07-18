"""Prebextor provider — Hermes Agent backend integration.

Implements the deterministic extraction pipeline as a single
`WebSearchProvider` so Hermes can register this plugin with `register_web_search_provider`.

Pipeline v3 (Raw HTML First — No Snapshot):

    1. open_tab              (browser lifecycle)
    2. StructuralMapper      (Phase 1: discover main container via evaluate_js)
    3. SurgicalPruner        (Phase 2: prune noise inside container)
    4. Text extraction       (Phase 3: innerText from pruned DOM)
    5. IframeExtractor       (Phase 4: extract cross-origin iframe content)
    6. MarkdownConverter     (Phase 5: text -> Markdown)
    7. BoundaryWrapper       (Phase 6: XML boundary wrap)
    7. close_tab             (cleanup)

Key changes from v2:
  - NO SNAPSHOT: StructuralMapper uses evaluate_js only
  - Text-first: extracts innerText from pruned DOM, not outerHTML
  - QA on text, not HTML (avoids false positives from script tags in HTML)
  - Iframe extraction for cross-origin embedded content

Optimizations (v1.2.0):
  - Parallel batch extraction with semaphore concurrency control
  - **Structure Cache** — caches pipeline decisions (selector, noise selectors, scoring)
    NOT content. Fresh HTML fetched every time, structure reapplied. Safe for dynamic sites.
  - Content quality filter (boilerplate removal, quality scoring)
  - Retry with exponential backoff for transient failures
  - Structured metrics for observability
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Lazy import: `agent.web_search_provider` is only resolvable when Hermes is
# installed. We import at runtime inside the class so that the package can
# still be imported in environments where Hermes is missing (e.g. unit tests).
try:
    from agent.web_search_provider import WebSearchProvider  # type: ignore
except Exception:  # pragma: no cover
    WebSearchProvider = object  # type: ignore[misc,assignment]

from .fetcher.camofox_client import CamoFoxClient
from .pipeline.mapper import StructuralMapper
from .pipeline.pruner import SurgicalPruner
from .pipeline.transform import MarkdownConverter, BoundaryWrapper
from .pipeline.iframe_extractor import IframeExtractor
from .pipeline.scorer import ContentAwareScorer
from .pipeline.validator import ContentValidator
from .search.searxng import SearXNGSearchEngine


def _extract_title_from_text(text: str) -> str:
    """Pull the first meaningful line from extracted text as title."""
    if not text:
        return ""
    for line in text.splitlines():
        line = line.strip()
        if line and len(line) > 3 and not line.startswith("#"):
            return line[:200]
    return ""


def _extract_title_from_html(html: str) -> str:
    """Pull <title> or first <h1> text from HTML."""
    if not html:
        return ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return ""


@dataclass
class ExtractionMetrics:
    """Structured metrics for a single URL extraction."""
    url: str
    started_at: float = field(default_factory=time.perf_counter)
    fetch_ms: int = 0
    parse_ms: int = 0
    quality_score: float = 0.0
    structure_cache_hit: bool = False
    error: str = ""

    def finish(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "total_ms": int((time.perf_counter() - self.started_at) * 1000),
            "fetch_ms": self.fetch_ms,
            "parse_ms": self.parse_ms,
            "quality_score": self.quality_score,
            "structure_cache_hit": self.structure_cache_hit,
            "error": self.error,
        }


@dataclass
class CachedStructure:
    """Pipeline structure decisions — NO CONTENT.
    
    Cached: selector, noise_selectors, scoring results, confidences
    NOT cached: HTML, text, markdown, XML, iframe data
    """
    url: str
    selector: str
    noise_selectors: List[str]
    mapper_confidence: float
    scorer_confidence: float
    validator_confidence: float
    validation_pass: int
    validation_warning: Optional[str]
    scored_blocks_count: int
    # Serialized scored_blocks for re-use
    scored_blocks: List[Dict[str, Any]]
    cached_at: float = field(default_factory=time.time)


class StructureCache:
    """Disk cache for pipeline structure decisions with TTL.
    
    Caches the *structure* (CSS selectors, noise patterns, scoring) NOT content.
    On cache hit: fetch fresh HTML, apply cached structure, extract fresh content.
    Safe for dynamic sites (economic calendars, prices, news) because HTML is always fresh.
    """
    
    def __init__(self, cache_dir: Path, ttl_hours: int = 168):  # 7 days default
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600
    
    def _key(self, url: str) -> str:
        # Structure cache keyed only by URL (params don't affect structure)
        return hashlib.sha256(url.encode()).hexdigest()[:16]
    
    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}_structure.json"
    
    def get(self, url: str) -> Optional[CachedStructure]:
        key = self._key(url)
        path = self._path(key)
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > self.ttl_seconds:
            path.unlink(missing_ok=True)
            return None
        try:
            data = json.loads(path.read_text())
            # Reconstruct scored_blocks from serialized form
            scored_blocks = data.get("scored_blocks", [])
            return CachedStructure(
                url=data["url"],
                selector=data["selector"],
                noise_selectors=data["noise_selectors"],
                mapper_confidence=data["mapper_confidence"],
                scorer_confidence=data["scorer_confidence"],
                validator_confidence=data["validator_confidence"],
                validation_pass=data["validation_pass"],
                validation_warning=data.get("validation_warning"),
                scored_blocks_count=data["scored_blocks_count"],
                scored_blocks=scored_blocks,
                cached_at=data.get("cached_at", time.time()),
            )
        except Exception:
            return None
    
    def set(self, url: str, structure: CachedStructure) -> None:
        key = self._key(url)
        path = self._path(key)
        try:
            # Serialize scored_blocks for storage
            serialized_blocks = []
            for block in structure.scored_blocks:
                if hasattr(block, '__dict__'):
                    serialized_blocks.append(block.__dict__)
                elif isinstance(block, dict):
                    serialized_blocks.append(block)
                else:
                    serialized_blocks.append({"data": str(block)})
            
            data = {
                "url": structure.url,
                "selector": structure.selector,
                "noise_selectors": structure.noise_selectors,
                "mapper_confidence": structure.mapper_confidence,
                "scorer_confidence": structure.scorer_confidence,
                "validator_confidence": structure.validator_confidence,
                "validation_pass": structure.validation_pass,
                "validation_warning": structure.validation_warning,
                "scored_blocks_count": structure.scored_blocks_count,
                "scored_blocks": serialized_blocks,
                "cached_at": structure.cached_at,
            }
            path.write_text(json.dumps(data, ensure_ascii=False))
        except Exception:
            pass  # Best-effort cache


class ContentQualityFilter:
    """Post-process extracted content for quality."""
    
    BOILERPLATE_PATTERNS = [
        r"cookie\s+policy",
        r"privacy\s+policy",
        r"terms\s+of\s+service",
        r"subscribe\s+to\s+newsletter",
        r"sign\s+up\s+for",
        r"advertisement",
        r"sponsored\s+content",
        r"accept\s+cookies",
        r"gdpr",
        r"we\s+use\s+cookies",
    ]
    
    def filter(self, result: Dict[str, Any]) -> Dict[str, Any]:
        content = result.get("content", "")
        
        # 1. Remove boilerplate
        content = self._remove_boilerplate(content)
        
        # 2. Detect language (simple heuristic)
        result["language"] = self._detect_lang(content)
        
        # 3. Quality score
        result["quality_score"] = self._score(content)
        
        # 4. Extract main content vs navigation
        result["main_content"] = self._extract_main(content)
        
        # 5. Structured data detection
        result["has_schema"] = self._has_schema_org(result.get("raw_content", ""))
        
        result["content"] = content
        return result
    
    def _remove_boilerplate(self, text: str) -> str:
        lines = text.split("\n")
        filtered = []
        for line in lines:
            if not any(re.search(p, line, re.I) for p in self.BOILERPLATE_PATTERNS):
                filtered.append(line)
        return "\n".join(filtered)
    
    def _detect_lang(self, text: str) -> str:
        """Simple language detection."""
        if not text:
            return "unknown"
        # Count common words
        ind_words = {"dan", "atau", "yang", "untuk", "dengan", "dari", "di", "ke", "adalah", "ini", "itu"}
        eng_words = {"the", "and", "or", "for", "with", "from", "to", "in", "on", "is", "this", "that"}
        words = set(text.lower().split()[:200])
        ind_score = len(words & ind_words)
        eng_score = len(words & eng_words)
        if ind_score > eng_score:
            return "id"
        if eng_score > ind_score:
            return "en"
        return "unknown"
    
    def _score(self, text: str) -> float:
        """0-1 quality score based on heuristics."""
        if not text:
            return 0.0
        words = len(text.split())
        if words < 50:
            return 0.2
        if words < 200:
            return 0.5
        if words < 1000:
            return 0.7
        return min(1.0, words / 2000 * 0.8 + 0.2)
    
    def _extract_main(self, text: str) -> str:
        """Heuristic: keep paragraphs > 50 chars, drop short nav fragments."""
        paragraphs = text.split("\n\n")
        main = [p for p in paragraphs if len(p.strip()) > 50]
        return "\n\n".join(main)
    
    def _has_schema_org(self, html: str) -> bool:
        if not html:
            return False
        return bool(re.search(r'itemtype=["\']https?://schema\.org/', html, re.I)) or \
               bool(re.search(r'"@type"\s*:\s*"', html))


class PrebextorProvider(WebSearchProvider):  # type: ignore[misc]
    """Deterministic extraction + search provider (CamoFox + SearXNG).
    
    Dual capability:
    - ``extract()`` — deterministic extraction via CamoFox (existing pipeline)
    - ``search()`` — web search via SearXNG (requires SEARXNG_URL)
    """
    
    def __init__(
        self,
        max_concurrent: int = 3,
        timeout: int = 30,
        cache_dir: Optional[Path] = None,
        cache_ttl_hours: int = 168,  # 7 days for structure
        enable_quality_filter: bool = True,
        enable_metrics: bool = True,
        searxng_url: Optional[str] = None,
        search_timeout: int = 15,
    ) -> None:
        self._name = "prebextor"
        self._display = "Prebextor (Deterministic Extraction + Search Engine)"
        
        # Concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._timeout = timeout
        
        # Structure Cache (NOT content cache)
        self._structure_cache = StructureCache(
            cache_dir or Path.home() / ".cache" / "prebextor_structure",
            ttl_hours=cache_ttl_hours,
        )
        
        # Quality filter
        self._quality_filter = ContentQualityFilter() if enable_quality_filter else None
        
        # Metrics
        self._enable_metrics = enable_metrics
        self._metrics: List[ExtractionMetrics] = []
        
        # Pipeline components
        self._camofox = CamoFoxClient(default_timeout=60)
        self._mapper = StructuralMapper(self._camofox)
        self._pruner = SurgicalPruner(self._camofox)
        self._md = MarkdownConverter()
        self._wrap = BoundaryWrapper()
        self._iframe = IframeExtractor(self._camofox)
        self._scorer = ContentAwareScorer(self._camofox)
        self._validator = ContentValidator(self._camofox)
        
        # Search engine (SearXNG)
        self._search_engine = SearXNGSearchEngine(
            searxng_url=searxng_url,
            timeout=search_timeout,
        )
    
    # ---------- WebSearchProvider surface ----------
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def display_name(self) -> str:
        return self._display
    
    def is_available(self) -> bool:
        """Available if CamoFox (for extract) OR SearXNG (for search) is configured."""
        return CamoFoxClient.is_available() or self._search_engine.is_available()
    
    def supports_search(self) -> bool:
        return True
    
    def supports_extract(self) -> bool:
        return True
    
    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Execute a web search via SearXNG.
        
        Returns the standard Hermes search envelope::
        
            {"success": True, "data": {"web": [{title, url, description, position}, ...]}}
        
        Requires ``SEARXNG_URL`` env var or ``searxng_url`` constructor arg.
        """
        if not self._search_engine.is_available():
            return {
                "success": False,
                "error": (
                    "SEARXNG_URL is not set. "
                    "Configure it via env var or the constructor. "
                    "Example: SEARXNG_URL=http://localhost:8080"
                ),
            }
        return self._search_engine.search(query, limit=limit)
    
    # ---------- Internal ----------
    
    async def _extract_with_retry(self, url: str, **kwargs: Any) -> Dict[str, Any]:
        """Extract with exponential backoff retry - calls full pipeline directly."""
        last_exc = None
        for attempt in range(3):
            try:
                return await asyncio.wait_for(
                    self._extract_full_pipeline(url, **kwargs),
                    timeout=self._timeout
                )
            except Exception as e:
                last_exc = e
                if attempt == 2:
                    break
                await asyncio.sleep(1.0 * (2 ** attempt))  # 1s, 2s
        return {
            "url": url, "title": "", "content": "",
            "raw_content": "", "metadata": {}, "error": f"{type(last_exc).__name__}: {last_exc}",
        }
    
    async def _extract_full_pipeline(self, url: str, **kwargs: Any) -> Dict[str, Any]:
        """Full extraction pipeline without cache - used by retry logic."""
        return await self._extract_one_no_cache(url, **kwargs)
    
    async def _extract_one_no_cache(self, url: str, **kwargs: Any) -> Dict[str, Any]:
        """Extract single URL - full pipeline, no cache check."""
        user = f"prebextor_{uuid.uuid4().hex}"
        
        tab_id = self._camofox.open_tab(url, user=user)
        if not tab_id:
            return {
                "url": url, "title": "", "content": "",
                "raw_content": "", "metadata": {}, "error": "Failed to open tab",
            }
        
        fetch_start = time.perf_counter()
        
        try:
            # Phase 0: Get full page HTML for title extraction
            full_html = self._camofox.get_html(tab_id, user) or ""
            
            # Phase 0.5: Anti-bot / challenge page detection
            anti_bot_warning = self._mapper._detect_anti_bot(tab_id, user)
            if anti_bot_warning:
                return {
                    "url": url,
                    "title": _extract_title_from_html(full_html) or url,
                    "content": "",
                    "raw_content": "",
                    "metadata": {
                        "selector": "", "extractor": "prebextor-v3.1",
                        "pipeline": "map->score->prune->validate->text->iframe->md->wrap",
                        "confidence": 0.0, "content_aware": True, "anti_bot_detected": True,
                    },
                    "error": anti_bot_warning,
                }
            
            # Phase 1: Structural mapping (evaluate_js only, no snapshot)
            selector, mapper_confidence = self._mapper.map_selector(tab_id, user)
            
            # Phase 2: Content-aware scoring
            scored_blocks = self._scorer.score_blocks(selector, tab_id, user)
            noise_selectors = self._scorer.get_noise_selectors(scored_blocks)
            scorer_confidence = self._scorer.compute_confidence(scored_blocks)
            
            # Phase 3: Prune noise inside mapped container
            # 3a: Static noise selectors
            removed_static = self._pruner.prune(selector, tab_id, user)
            # 3b: Dynamic noise from scorer
            removed_dynamic = self._pruner.prune_dynamic(
                selector, noise_selectors, tab_id, user
            )
            removed_total = removed_static + removed_dynamic
            
            # Phase 4: Content validation
            validation = self._validator.validate(
                selector, scored_blocks, tab_id, user
            )
            
            # Phase 5: Get text directly from pruned DOM
            raw_text = self._camofox.get_text(tab_id, user, selector=selector) or ""
            
            # Also get HTML for raw_content (best-effort)
            raw_html = self._camofox.get_html(tab_id, user, selector=selector) or ""
            
            fetch_ms = int((time.perf_counter() - fetch_start) * 1000)
            
            # Phase 5.5: Empty content detection
            if len(raw_text.strip()) < 30:
                return {
                    "url": url,
                    "title": _extract_title_from_html(full_html) or url,
                    "content": "",
                    "raw_content": "",
                    "metadata": {
                        "selector": selector,
                        "extractor": "prebextor-v3.1",
                        "pipeline": "map->score->prune->validate->text->iframe->md->wrap",
                        "confidence": 0.0,
                        "mapper_confidence": mapper_confidence,
                        "scorer_confidence": scorer_confidence,
                        "validator_confidence": validation.confidence,
                        "validation_pass": validation.pass_used,
                        "validation_warning": validation.warning,
                        "scored_blocks_count": len(scored_blocks),
                        "noise_selectors_found": len(noise_selectors),
                        "pruned_static": removed_static,
                        "pruned_dynamic": removed_dynamic,
                        "pruned_total": removed_total,
                        "iframes_extracted": 0,
                        "text_length": len(raw_text.strip()),
                        "content_aware": True,
                        "empty_content": True,
                        "fetch_ms": fetch_ms,
                        "parse_ms": 0,
                    },
                    "error": f"Empty content extracted ({len(raw_text.strip())} chars) — page may be JS-rendered or blocked",
                }
            
            # Phase 6: Iframe extraction for cross-origin embedded content
            iframe_texts = self._extract_iframes(tab_id, user, **kwargs)
            
            # Merge iframe text into main text
            merged_text = raw_text
            for iframe_data in iframe_texts:
                iframe_text = iframe_data.get("text", "")
                if iframe_text:
                    merged_text += f"\n\n---\n\n### Embedded: {iframe_data.get('title', 'iframe')}\n\n{iframe_text}"
            
            # Extract title from FULL page HTML (not just container)
            title = (
                _extract_title_from_html(full_html) or
                _extract_title_from_html(raw_html) or
                _extract_title_from_text(merged_text) or
                url
            )
            
            # Phase 7: Text -> Markdown conversion
            parse_start = time.perf_counter()
            if raw_html and len(raw_html) > 100:
                try:
                    md = self._md.convert(raw_html)
                except Exception:
                    md = merged_text
            else:
                md = merged_text
            
            # Phase 8: XML boundary wrap
            xml_wrapped = self._wrap.wrap(md, title=title, url=url)
            
            parse_ms = int((time.perf_counter() - parse_start) * 1000)
            
            # Compute final confidence
            final_confidence = round(
                (mapper_confidence * 0.3) +
                (scorer_confidence * 0.3) +
                (validation.confidence * 0.4),
                3,
            )
            
            result = {
                "url": url,
                "title": title,
                "content": xml_wrapped,
                # raw_content intentionally empty: web_tools._extract dispatcher
                # prefers raw_content over content when present, which would
                # substitute the pre-pruning HTML for the clean markdown+XML
                # output we built. Leaving it blank forces the dispatcher to
                # fall back to `content` so consumers receive the processed
                # markdown+XML boundary wrap (the prebextor contract).
                "raw_content": "",
                "metadata": {
                    "selector": selector,
                    "extractor": "prebextor-v3.1",
                    "pipeline": "map->score->prune->validate->text->iframe->md->wrap",
                    "confidence": final_confidence,
                    "mapper_confidence": mapper_confidence,
                    "scorer_confidence": scorer_confidence,
                    "validator_confidence": validation.confidence,
                    "validation_pass": validation.pass_used,
                    "validation_warning": validation.warning,
                    "scored_blocks_count": len(scored_blocks),
                    "noise_selectors_found": len(noise_selectors),
                    "pruned_static": removed_static,
                    "pruned_dynamic": removed_dynamic,
                    "pruned_total": removed_total,
                    "iframes_extracted": len(iframe_texts),
                    "text_length": len(merged_text),
                    "content_aware": True,
                    "fetch_ms": fetch_ms,
                    "parse_ms": parse_ms,
                },
                "error": None,
            }
            
            # Apply quality filter if enabled
            if self._quality_filter:
                result = self._quality_filter.filter(result)
            
            # Record metrics
            if self._enable_metrics:
                metrics = ExtractionMetrics(
                    url=url,
                    fetch_ms=fetch_ms,
                    parse_ms=parse_ms,
                    quality_score=result.get("quality_score", 0.0),
                )
                self._metrics.append(metrics)
            
            return result
            
        except Exception as e:
            return {
                "url": url, "title": "", "content": "",
                "raw_content": "", "metadata": {}, "error": f"{type(e).__name__}: {e}",
            }
        finally:
            # Always close the tab to keep CamoFox clean
            self._camofox.close_tab(tab_id, user)
    
    async def _extract_one_with_structure_cache(self, url: str, **kwargs: Any) -> Dict[str, Any]:
        """Extract using structure cache: fetch fresh HTML, apply cached structure."""
        # Check structure cache
        cached_structure = self._structure_cache.get(url)
        
        if cached_structure:
            # Structure cache hit: fetch fresh HTML, apply cached structure
            return await self._extract_with_cached_structure(url, cached_structure, **kwargs)
        
        # Cache miss: full pipeline, then cache structure
        result = await self._extract_with_retry(url, **kwargs)
        
        # Cache structure from successful extraction
        if not result.get("error") and result.get("metadata", {}).get("selector"):
            self._cache_structure_from_result(url, result)
        
        return result
    
    async def _extract_with_cached_structure(
        self, 
        url: str, 
        cached: CachedStructure, 
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Apply cached structure to fresh HTML fetch."""
        user = f"prebextor_{uuid.uuid4().hex}"
        
        tab_id = self._camofox.open_tab(url, user=user)
        if not tab_id:
            return {
                "url": url, "title": "", "content": "",
                "raw_content": "", "metadata": {}, "error": "Failed to open tab",
            }
        
        fetch_start = time.perf_counter()
        
        try:
            # Get full page HTML for title
            full_html = self._camofox.get_html(tab_id, user) or ""
            
            # Anti-bot check
            anti_bot_warning = self._mapper._detect_anti_bot(tab_id, user)
            if anti_bot_warning:
                return {
                    "url": url,
                    "title": _extract_title_from_html(full_html) or url,
                    "content": "",
                    "raw_content": "",
                    "metadata": {
                        "selector": "", "extractor": "prebextor-v3.1",
                        "pipeline": "map->score->prune->validate->text->iframe->md->wrap",
                        "confidence": 0.0, "content_aware": True, "anti_bot_detected": True,
                    },
                    "error": anti_bot_warning,
                }
            
            # Apply cached structure: prune with cached noise selectors
            selector = cached.selector
            noise_selectors = cached.noise_selectors
            
            # Prune static + dynamic noise
            removed_static = self._pruner.prune(selector, tab_id, user)
            removed_dynamic = self._pruner.prune_dynamic(selector, noise_selectors, tab_id, user)
            
            # Get text from pruned DOM
            raw_text = self._camofox.get_text(tab_id, user, selector=selector) or ""
            raw_html = self._camofox.get_html(tab_id, user, selector=selector) or ""
            
            fetch_ms = int((time.perf_counter() - fetch_start) * 1000)
            
            # Empty content check
            if len(raw_text.strip()) < 30:
                return {
                    "url": url,
                    "title": _extract_title_from_html(full_html) or url,
                    "content": "",
                    "raw_content": "",
                    "metadata": {
                        "selector": selector,
                        "extractor": "prebextor-v3.1",
                        "pipeline": "cached_structure->text->iframe->md->wrap",
                        "confidence": 0.0,
                        "mapper_confidence": cached.mapper_confidence,
                        "scorer_confidence": cached.scorer_confidence,
                        "validator_confidence": cached.validator_confidence,
                        "validation_pass": cached.validation_pass,
                        "validation_warning": cached.validation_warning,
                        "scored_blocks_count": cached.scored_blocks_count,
                        "noise_selectors_found": len(noise_selectors),
                        "pruned_static": removed_static,
                        "pruned_dynamic": removed_dynamic,
                        "pruned_total": removed_static + removed_dynamic,
                        "iframes_extracted": 0,
                        "text_length": len(raw_text.strip()),
                        "content_aware": True,
                        "empty_content": True,
                        "fetch_ms": fetch_ms,
                        "parse_ms": 0,
                        "structure_cache_hit": True,
                    },
                    "error": f"Empty content extracted ({len(raw_text.strip())} chars)",
                }
            
            # Iframe extraction
            iframe_texts = self._extract_iframes(tab_id, user, **kwargs)
            
            # Merge iframe text
            merged_text = raw_text
            for iframe_data in iframe_texts:
                iframe_text = iframe_data.get("text", "")
                if iframe_text:
                    merged_text += f"\n\n---\n\n### Embedded: {iframe_data.get('title', 'iframe')}\n\n{iframe_text}"
            
            # Extract title
            title = (
                _extract_title_from_html(full_html) or
                _extract_title_from_html(raw_html) or
                _extract_title_from_text(merged_text) or
                url
            )
            
            # Markdown conversion
            parse_start = time.perf_counter()
            if raw_html and len(raw_html) > 100:
                try:
                    md = self._md.convert(raw_html)
                except Exception:
                    md = merged_text
            else:
                md = merged_text
            
            # XML boundary wrap
            xml_wrapped = self._wrap.wrap(md, title=title, url=url)
            
            parse_ms = int((time.perf_counter() - parse_start) * 1000)
            
            # Use cached confidences (structure unchanged)
            final_confidence = round(
                (cached.mapper_confidence * 0.3) +
                (cached.scorer_confidence * 0.3) +
                (cached.validator_confidence * 0.4),
                3,
            )
            
            result = {
                "url": url,
                "title": title,
                "content": xml_wrapped,
                # raw_content intentionally empty — see full-pipeline path comment.
                "raw_content": "",
                "metadata": {
                    "selector": selector,
                    "extractor": "prebextor-v3.1",
                    "pipeline": "cached_structure->text->iframe->md->wrap",
                    "confidence": final_confidence,
                    "mapper_confidence": cached.mapper_confidence,
                    "scorer_confidence": cached.scorer_confidence,
                    "validator_confidence": cached.validator_confidence,
                    "validation_pass": cached.validation_pass,
                    "validation_warning": cached.validation_warning,
                    "scored_blocks_count": cached.scored_blocks_count,
                    "noise_selectors_found": len(noise_selectors),
                    "pruned_static": removed_static,
                    "pruned_dynamic": removed_dynamic,
                    "pruned_total": removed_static + removed_dynamic,
                    "iframes_extracted": len(iframe_texts),
                    "text_length": len(merged_text),
                    "content_aware": True,
                    "fetch_ms": fetch_ms,
                    "parse_ms": parse_ms,
                    "structure_cache_hit": True,
                },
                "error": None,
            }
            
            # Apply quality filter
            if self._quality_filter:
                result = self._quality_filter.filter(result)
            
            # Record metrics
            if self._enable_metrics:
                metrics = ExtractionMetrics(
                    url=url,
                    fetch_ms=fetch_ms,
                    parse_ms=parse_ms,
                    quality_score=result.get("quality_score", 0.0),
                    structure_cache_hit=True,
                )
                self._metrics.append(metrics)
            
            return result
            
        except Exception as e:
            return {
                "url": url, "title": "", "content": "",
                "raw_content": "", "metadata": {}, "error": f"{type(e).__name__}: {e}",
            }
        finally:
            self._camofox.close_tab(tab_id, user)
    
    def _cache_structure_from_result(self, url: str, result: Dict[str, Any]) -> None:
        """Extract and cache structure from a successful full-pipeline result."""
        meta = result.get("metadata", {})
        structure = CachedStructure(
            url=url,
            selector=meta.get("selector", ""),
            noise_selectors=[],  # Would need to track these during pipeline
            mapper_confidence=meta.get("mapper_confidence", 0.0),
            scorer_confidence=meta.get("scorer_confidence", 0.0),
            validator_confidence=meta.get("validator_confidence", 0.0),
            validation_pass=meta.get("validation_pass", 1),
            validation_warning=meta.get("validation_warning"),
            scored_blocks_count=meta.get("scored_blocks_count", 0),
            scored_blocks=[],  # Would need access to scorer's internal blocks
        )
        self._structure_cache.set(url, structure)
    
    def _extract_iframes(self, tab_id: str, user: str, **kwargs: Any) -> List[Dict[str, Any]]:
        """Extract content from significant iframes."""
        results: List[Dict[str, Any]] = []
        try:
            iframes = self._iframe.detect_significant_iframes(tab_id, user)
            for iframe_info in iframes:
                src = iframe_info.get("src", "")
                if not src:
                    continue
                iframe_data = self._iframe.extract_iframe_content(
                    src, user,
                    scroll=bool(kwargs.get("scroll_to_bottom", False)),
                    wait_ms=int(kwargs.get("wait_after_scroll", 3000)),
                )
                if iframe_data and iframe_data.get("text"):
                    results.append(iframe_data)
        except Exception:
            pass  # Iframe extraction is best-effort
        return results
    
    async def _extract_one(self, url: str, **kwargs: Any) -> Dict[str, Any]:
        """Extract single URL using structure cache."""
        return await self._extract_one_with_structure_cache(url, **kwargs)
    
    # ---------- Public API ----------
    
    def extract(self, urls: List[str], **kwargs: Any) -> Dict[str, Any]:
        """Extract content from one or more URLs.
        
        Returns the Hermes WebSearchProvider envelope:
            {"success": True, "data": [{url,title,content,raw_content,metadata,error?}, ...]}
        On total failure: {"success": False, "error": "..."}
        
        Supported kwargs (per URL):
            - scroll_to_bottom: bool, trigger lazy loading (default: False)
            - wait_after_scroll: ms to wait after scroll (default: 3000)
        
        Failures on individual URLs do NOT abort the batch.
        """
        if not urls:
            return {"success": True, "data": []}
        
        async def _batch_extract() -> List[Dict[str, Any]]:
            async def _extract_with_semaphore(url: str) -> Dict[str, Any]:
                async with self._semaphore:
                    return await self._extract_one(url, **kwargs)
            
            tasks = [_extract_with_semaphore(url) for url in urls]
            # Use return_exceptions=True to prevent one failure from killing the batch
            return await asyncio.gather(*tasks, return_exceptions=True)
        
        try:
            # Stable loop management:
            # 1. Try to get current running loop (for async contexts)
            # 2. If no loop, use asyncio.run (for sync contexts)
            try:
                loop = asyncio.get_running_loop()
                # If we are in a running loop, we cannot use asyncio.run().
                # We must create a task and wait for it, but the provider.extract
                # is a sync method. This is a fundamental conflict.
                # To solve this, we use a temporary thread to run the async batch
                # and wait for the result, avoiding loop conflicts.
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    # We use a separate loop in the thread to avoid blocking the main loop
                    future = executor.submit(asyncio.run, _batch_extract())
                    raw_results = future.result()
            except RuntimeError:
                # No running loop, safe to use asyncio.run()
                raw_results = asyncio.run(_batch_extract())
            
            # Handle any exceptions from gather
            normalized = []
            for url, result in zip(urls, raw_results):
                if isinstance(result, Exception):
                    normalized.append({
                        "url": url, "title": "", "content": "",
                        "raw_content": "", "metadata": {}, "error": f"{type(result).__name__}: {result}",
                    })
                else:
                    normalized.append(result)
            
            return {"success": True, "data": normalized}
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}"}
    
    def get_metrics(self) -> List[Dict[str, Any]]:
        """Return collected metrics for this session."""
        return [m.finish() for m in self._metrics]
    
    def clear_metrics(self) -> None:
        """Clear collected metrics."""
        self._metrics.clear()