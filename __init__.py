"""Prebextor — Deterministic Extraction Engine.

User plugin for Hermes Agent (deployed at ~/.hermes/plugins/web/prebextor/).

Pipeline v3.1 (per URL, structure-cache aware):
  open_tab -> StructuralMapper (anti-bot check + container discovery)
  -> ContentAwareScorer (text/link density scoring)
  -> SurgicalPruner (static + dynamic noise removal)
  -> ContentValidator (3-pass strict/relaxed/fallback)
  -> CamoFoxClient.get_text (innerText from pruned DOM)
  -> IframeExtractor (cross-origin embedded content)
  -> MarkdownConverter -> BoundaryWrapper (XML semantic tags)
  -> close_tab

Optimizations:
  - Parallel batch via asyncio.Semaphore (default 3 concurrent)
  - Structure Cache — caches pipeline decisions, NOT content. HTML always fresh.
  - Content Quality Filter (boilerplate removal, language, schema.org)
  - Retry with exponential backoff for transient failures
  - Structured metrics (ExtractionMetrics) for observability
"""

from __future__ import annotations

from pathlib import Path

from .tool_extract import (
    PREBEXTOR_EXTRACT_SCHEMA,
    prebextor_extract_handler,
    _check_available,
)

from .provider import PrebextorProvider

__version__ = "1.2.0"
__all__ = ["PrebextorProvider"]

# Skill that ships WITH this plugin. The path is resolved at register-time
# relative to this file so it works from any installed copy (project source,
# ~/.hermes/plugins/web/prebextor/, pip-installed, etc).
_EMBEDDED_SKILL_PATH = Path(__file__).parent / "skill_internal" / "SKILL.md"
_EMBEDDED_SKILL_NAME = "install"


def register(ctx) -> None:
    """Register Prebextor as BOTH a provider (for web.extract_backend config)
    and a standalone tool (for zero-config usage).

    Dual-mode:
    1. Provider — registered via web_search_registry for users setting
       web.extract_backend: prebextor
    2. Tool — registered via tool registry as 'prebextor_extract', works
       independently without any config.
    """
    # 1. Provider (for web.extract_backend: prebextor)
    # Pass optimization configs - Structure Cache enabled by default
    ctx.register_web_search_provider(PrebextorProvider(
        max_concurrent=3,
        timeout=30,
        cache_ttl_hours=168,  # 7 days for structure cache
        enable_quality_filter=True,
        enable_metrics=True,
    ))

    # 2. Standalone tool (zero-config, bypasses web_tools dispatcher)
    ctx.register_tool(
        name="prebextor_extract",
        toolset="web",
        schema=PREBEXTOR_EXTRACT_SCHEMA,
        handler=prebextor_extract_handler,
        check_fn=_check_available,
        is_async=True,
        emoji="📄",
        description="Prebextor extraction (deterministic, no API key needed)"
    )

    if _EMBEDDED_SKILL_PATH.exists():
        ctx.register_skill(
            name=_EMBEDDED_SKILL_NAME,
            path=_EMBEDDED_SKILL_PATH,
            description=(
                "Install, verify, and uninstall Prebextor (the plugin that "
                "ships this skill). Bundled inside the plugin so the "
                "install/remove procedure is portable."
            ),
        )