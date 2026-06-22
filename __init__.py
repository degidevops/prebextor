"""Prebextor — Deterministic Extraction Engine.

User plugin for Hermes Agent (deployed at ~/.hermes/plugins/web/prebextor/).

Pipeline (per atomic unit):
  open_tab -> StructuralMapper -> SurgicalPruner -> FidelityFetcher ->
  ZeroNoiseAssertionGate (HTML) -> MarkdownConverter -> BoundaryWrapper ->
  ZeroNoiseAssertionGate (XML) -> close_tab
"""

from __future__ import annotations

from pathlib import Path

from .provider import PrebextorProvider

__version__ = "1.0.1"
__all__ = ["PrebextorProvider"]


# Skill that ships WITH this plugin. The path is resolved at register-time
# relative to this file so it works from any installed copy (project source,
# ~/.hermes/plugins/web/prebextor/, pip-installed, etc).
_EMBEDDED_SKILL_PATH = Path(__file__).parent / "skill_internal" / "SKILL.md"
_EMBEDDED_SKILL_NAME = "install"


def register(ctx) -> None:
    """Register the Prebextor provider with the plugin context.

    Also self-registers an opt-in internal skill referencing this plugin's own
    install procedure. This complements the standalone per-profile skill that
    ships at ``~/.hermes/profiles/<active>/skills/web-extraction/prebextor/``
    (which is auto-listed in the system prompt). The internal skill is only
    reachable via ``skill_view('prebextor:install')``; it documents the same
    install/verify/uninstall sequence for agents that want the procedure
    bundled with the plugin itself rather than with the profile.
    """
    ctx.register_web_search_provider(PrebextorProvider())

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
