# Research: Hermes Agent Web-Search Provider Plugin Contract

## Source
Hermes Agent documentation, "Web Search Provider Plugins" developer guide:
- https://hermes-agent.nousresearch.com/docs/developer-guide/web-search-provider-plugin

## Why this exists
Prebextor must run **inside** Hermes Agent's plugin loader as a `web.extract_backend`. Until the contract is known exactly (not approximated from a co-located plugin), integration is guesswork. This file records the **authoritative** rules from Hermes docs.

## Plugin locations (Hermes scans three paths)
1. **Bundled**: `<repo>/plugins/web/<name>/` — auto-loaded, `kind: backend` always available.
2. **User**: `~/.hermes/plugins/web/<name>/` — opt-in via `plugins.enabled` list or `hermes plugins enable <name>`.
3. **Pip**: any package declaring an entry point under `hermes_agent.plugins`.

A `register(ctx)` function in the plugin's `__init__.py` is the single load-time hook:
- Bundled plugins: auto-called on every Hermes start.
- User plugins: only called when listed in `plugins.enabled` (or enabled by name).
- Pip plugins: registered via their entry-point descriptor.

## Directory structure (minimum)
```
plugins/web/my-backend/
├── __init__.py     # register() entry point
├── provider.py     # WebSearchProvider subclass
└── plugin.yaml     # Manifest with kind: backend and provides_web_providers
```
`brave_free/` and `ddgs/` are the smallest in-tree references; `firecrawl/` is the richest (multi-capability).

## plugin.yaml schema
```yaml
name: web-prebextor                  # display-ish; docs use "web-<id>"
version: 1.0.0
description: "Prebextor Deterministic Extraction Engine ..."
author: <name>
kind: backend                        # routes through backend-loading path
provides_web_providers:              # list of provider ids this plugin registers
  - prebextor
requires_env: []                     # optional; used by hermes plugins install wizard
```

`provides_web_providers` advertises the plugin to `hermes tools` even **before** `register()` runs.

## WebSearchProvider ABC — overridable surface
| Member | Required | Default | Purpose |
|---|---|---|---|
| `name` | ✅ | — | Stable id for `web.*_backend` config keys. Lowercase; hyphens permitted. |
| `display_name` | — | `name` | Label shown in `hermes tools`. |
| `is_available()` | ✅ | — | Cheap availability gate; **MUST NOT make network calls** (runs on every `hermes tools` paint). |
| `supports_search()` | — | `True` | Capability flag for `web_search` routing. |
| `supports_extract()` | — | `False` | Capability flag for `web_extract` routing. |
| `search(query, limit)` | conditional | raises | Required when `supports_search()` is `True`. |
| `extract(urls, **kwargs)` | conditional | raises | Required when `supports_extract()` is `True`. (Deep crawl is a mode of `extract()`, not a separate method.) |

## Search / Extract response shape (MUST follow)
Search success:
```json
{"success": true, "data": {"web": [
  {"title": "...", "url": "...", "description": "...", "position": 1}, ...
]}}
```
Extract success:
```json
{"success": true, "data": [
  {"url": "...", "title": "...", "content": "...", "raw_content": "...",
   "metadata": {...}, "error": "..."},
  ...
]}
```
`metadata` and `error` are optional per item. Batch failures must NOT abort the call — return per-URL `error` strings.

Failure (either capability):
```json
{"success": false, "error": "human-readable message"}
```

`search()` and `extract()` may be sync or `async def`; dispatcher detects via `inspect.iscoroutinefunction`.

## Routing
- `web.search_backend` (per-capability) → falls back to `web.backend`.
- `web.extract_backend` (per-capability) → falls back to `web.backend`.
- If neither per-capability nor `web.backend` set, Hermes auto-detects from env-key availability of the registered providers.
- Providers that don't advertise a capability are **not** matched for that tool — no "provider X failed" noise when paired with another extract backend.

## Discovery pipeline (the user's-eye view)
1. Hermes reads `web.extract_backend` (etc.).
2. Asks the registry for the provider with that name.
3. Checks `is_available()` AND the matching `supports_*()` flag.
4. Dispatches to `search()` / `extract()` (awaiting async).
5. JSON-serializes the envelope and hands it back to the LLM as the tool result.

## Pairing pattern: extract-only provider
Docs explicitly call out SearXNG's "pair me with an extract provider" pattern. This is the canonical deployment shape for Prebextor:
```yaml
web:
  search_backend: searxng
  extract_backend: prebextor
```
Prebextor adopts the extract-only shape: `supports_search() -> False`, `extract()` implemented, `search()` raises `NotImplementedError`.

## Lazy-installing optional dependencies
If a provider wraps a third-party Python package, the import must be deferred to `is_available()` / `search()` / `extract()` via `tools.lazy_deps.ensure(...)`. Gated by `security.allow_lazy_installs`. This is **not** needed for Prebextor (its dependencies are imported eagerly inside the plugin package).

## Pip packaging
```toml
[project.entry-points."hermes_agent.plugins"]
my-backend-web = "my_backend_web_package"
```
The named object must expose a top-level `register` function.

## Reference implementations cited by docs
- `plugins/web/brave_free/` — small, API-key-gated, search-only HTTP provider.
- `plugins/web/ddgs/` — no-key, lazy-installing SDK wrapper.
- `plugins/web/firecrawl/` — full multi-capability (search + extract + crawl).
- `plugins/web/searxng/` — self-hosted, URL-configured, no auth, search-only.
- `plugins/web/xai/` — LLM-backed via Grok's server-side search.
