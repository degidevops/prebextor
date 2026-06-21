# Changelog

All notable changes to the Prebextor project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] — 2026-06-21

### Added
- **`prebextor-extractor` Skill** — Hermes skill for one-command plugin deployment:
  - `SKILL.md` with frontmatter (name, description, version 2.0.0, metadata with tags/category/config)
  - `scripts/deploy.sh` — validates source tree, copies real files to `~/.hermes/plugins/web/prebextor/`, patches config.yaml
  - `scripts/undeploy.sh` — removes plugin dir, reverts config
  - `scripts/verify.py` — 11-point verification (import, instantiation, capabilities, envelope schema)
  - `references/plugin-layout.md` — plugin folder structure (Appendix A from blueprint-v2)
  - `references/troubleshooting.md` — common issues and fixes
- **E2E test suite** (`tests/`):
  - `test_e2e_extract.py` — 32 assertions against real website (example.com), validates full pipeline
  - `test_envelope_schema.py` — 41 assertions for Hermes envelope contract compliance (mock + real)
- **Density fallback improvement** — StructuralMapper density threshold lowered from 500 to 100 chars, added `tagName` fallback for elements without id/class

### Changed
- **`extract()` return shape** — now returns Hermes envelope `{"success": True, "data": [...]}` instead of raw `List[Dict]` (breaking change)
- **`_extract_one()` success return** — now includes `"error": None` key for consistent per-URL shape
- **`provider.py` return annotation** — `extract()` annotated as `Dict[str, Any]` (was `List[Dict[str, Any]]`)

### Fixed
- **StructuralMapper density fallback** — now returns `best.tagName.toLowerCase()` instead of `null` when element has no id/class (fixes extraction on simple pages like example.com)

---

## [1.0.0] — 2026-06-21

### Added
- **Git repository initialized** with `.gitignore` (Python artifacts, venv, env files).
- **`CHANGELOG.md`** — structured changelog (Keep a Changelog 1.1.0 format).
- **`blueprint-v2.md`** — architecture blueprint with Hermes Agent Integration Layer.
- **`PLAN-v2.md`** — implementation plan with Layer 0 (plugin integration) + Sprint 5 (deployment).
- **Plugin source code** (`prebextor/` package):
  - `provider.py`, `__init__.py`, `plugin.yaml`
  - `pipeline/` — mapper, pruner, transform, qa
  - `fetcher/` — camofox_client
- **Initial release** of Prebextor Deterministic Extraction Engine.
- **Architecture blueprint v1** (`architecture/blueprint-v1.md`).
- **PLAN.md** — original atomic unit catalog.
- **Research documents** (`research/`) — CamoFox, extraction pipeline, LLM formats, Hermes contracts.

---

[2.0.0]: https://github.com/degi/prebextor/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/degi/prebextor/releases/tag/v1.0.0
