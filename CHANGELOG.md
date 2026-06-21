# Changelog

All notable changes to the Prebextor project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **Git repository initialized** with `.gitignore` (Python artifacts, venv, env files).
- **`CHANGELOG.md`** — structured changelog (Keep a Changelog 1.1.0 format) to track all changes across versions.
- **`blueprint-v2.md`** — new architecture blueprint adding Hermes Agent Integration Layer:
  - Plugin contract (`WebSearchProvider` ABC compliance)
  - `plugin.yaml` manifest (`kind: backend`, `provides_web_providers: [prebextor]`)
  - `__init__.py` entry point with `register(ctx)`
  - Skill packaging (`prebextor-extractor` skill)
  - Response envelope specification (`{"success", "data"|"error"}`)
  - Verification & QA test matrix for plugin lifecycle
- **`PLAN-v2.md`** — updated implementation plan aligned with blueprint-v2:
  - Atomic units now include Hermes Plugin Layer (Layer 0)
  - Sprint-based roadmap with plugin deployment tasks
  - Verification checklist for plugin discovery and real-domain extraction
- **Plugin source code** (`prebextor/` package):
  - `provider.py` — `PrebextorProvider(WebSearchProvider)` with `supports_search()=False`, `supports_extract()=True`
  - `__init__.py` — `register(ctx)` entry point
  - `plugin.yaml` — Hermes plugin manifest
  - `pipeline/mapper.py` — StructuralMapper (hierarchy-based container detection)
  - `pipeline/pruner.py` — SurgicalPruner (client-side noise removal)
  - `pipeline/transform.py` — MarkdownConverter + BoundaryWrapper (semantic XML)
  - `pipeline/qa.py` — ZeroNoiseAssertionGate (two-pass QA)
  - `fetcher/camofox_client.py` — CamoFox CLI subprocess wrapper

### Changed
- **`extract()` return shape** now returns Hermes envelope `{"success": True, "data": [...]}` instead of raw `List[Dict]` — breaking change for any consumer expecting the old format.

### Removed
- (none in this cycle)

### Fixed
- (none in this cycle)

### Security
- (none in this cycle)

---

## [1.0.0] — 2026-06-21

### Added
- **Initial release** of Prebextor Deterministic Extraction Engine.
- **Architecture blueprint v1** (`architecture/blueprint-v1.md`) — core mandates and atomic unit catalog.
- **PLAN.md** — implementation roadmap with 5 atomic layers (Integration, Lifecycle, Pipeline, Transformation, QA).
- **Research documents** (`research/`) — CamoFox capabilities, extraction pipeline, LLM-optimal formats, web search basics, Firecrawl analysis, Hermes skill/plugin contract.
- **Extraction pipeline** — Mapping → Pruning → Fetching → QA → Markdown → Boundary Wrap → Final QA.
- **CamoFox integration** — browser-driven DOM extraction with chunked retrieval for >1MB pages.

---

[Unreleased]: https://github.com/degi/prebextor/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/degi/prebextor/releases/tag/v1.0.0
