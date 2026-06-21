"""Prebextor — Deterministic Extraction Engine.

User plugin for Hermes Agent (deployed at ~/.hermes/plugins/web/prebextor/).

Pipeline (per atomic unit):
  open_tab -> StructuralMapper -> SurgicalPruner -> FidelityFetcher ->
  ZeroNoiseAssertionGate (HTML) -> MarkdownConverter -> BoundaryWrapper ->
  ZeroNoiseAssertionGate (XML) -> close_tab
"""

from __future__ import annotations

from .provider import PrebextorProvider

__version__ = "1.0.0"
__all__ = ["PrebextorProvider"]


def register(ctx) -> None:
    """Register the Prebextor provider with the plugin context.

    Mirrors the entry-point contract used by the bundled web-searxng and
    web-precision-extractor plugins: ctx.register_web_search_provider(...).
    """
    ctx.register_web_search_provider(PrebextorProvider())
