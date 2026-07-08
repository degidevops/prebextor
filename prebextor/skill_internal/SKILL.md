---
name: prebextor-install
description: "Install, verify, and uninstall Prebextor — the procedure is bundled INSIDE the plugin so the install lifecycle travels with the code itself. Opt-in via skill_view('prebextor:install')."
version: 1.2.2
platforms: [linux, macos]
metadata:
  hermes:
    tags: [web, extraction, deterministic, prebextor, plugin-installer]
    category: web-extraction
    requires_toolsets: [terminal]
---

# Prebextor — Plugin-Embedded Install Skill (opt-in)

This skill ships **inside** the Prebextor plugin (`prebextor/skill_internal/SKILL.md`)
and is registered via `ctx.register_skill()` from the plugin's `register(ctx)` hook.

It is referenced as `prebextor:install` and reachable only through
`skill_view('prebextor:install')` calls. It does **NOT** appear in the
system prompt's `<available_skills>` index.

**Prefer the standalone sibling** at
`~/.hermes/profiles/<active>/skills/web-extraction/prebextor/` for
user-facing installs — that one IS auto-listed.

Use this embedded skill when:

*   The plugin is being delivered via pip, git, or tar and the agent has
    no `~/.hermes/skills/web-extraction/prebextor/` directory yet.
*   You want the install procedure to travel with the plugin source
    (one artifact = one installable unit).
*   The agent is exploring the plugin via `skill_view('prebextor:install')`
    after the plugin loaded successfully.

## Source layout (when bundled with plugin)

```
<plugin_root>/                     e.g. ~/.hermes/plugins/prebextor/
├── __init__.py                    # register(ctx) — registers provider + tool + THIS skill
├── provider.py                    # WebSearchProvider subclass + StructureCache + Metrics
├── tool_extract.py                # prebextor_extract standalone tool handler
├── plugin.yaml                    # Manifest
├── pipeline/                      # Mapper, Scorer, Pruner, Validator, Transformer, Iframe
├── fetcher/                       # CamoFox client
└── skill_internal/
    └── SKILL.md                   # ← you are here
```

When deployed via the Hermes plugin system, install directly via the
`hermes plugins install` workflow. The plugin's `register(ctx)` hook is
the single entry point — it registers the provider (`PrebextorProvider`),
the standalone tool (`prebextor_extract`), and this install skill.

## Install procedure

1.  **Install via Hermes CLI** (preferred) — pass the **sub-folder path** so
    the installer clones only `prebextor/` as the plugin root:
    ```bash
    hermes plugins install https://github.com/degidevops/prebextor/tree/main/prebextor
    hermes plugins enable prebextor
    # restart gateway from a shell OUTSIDE the running gateway
    ```
    Do NOT use `hermes plugins install degidevops/prebextor` (whole repo) —
    the repo root has no `__init__.py`, so `register()` never runs and the
    `prebextor_extract` tool won't appear.

2.  **Confirm source** is at the plugin install path
    (`~/.hermes/plugins/prebextor/`) with `__init__.py` + `plugin.yaml` at
    that root.

3.  **Verify** the plugin loaded:
    ```bash
    hermes plugins list
    # Should show: prebextor (enabled)

    python3 -c "
    import sys; sys.path.insert(0, '$HOME/.hermes/plugins')
    from prebextor import PrebextorProvider
    p = PrebextorProvider()
    print(p.name, p.supports_extract(), p.is_available())
    "
    # Output: prebextor True [True if CamoFox CLI available]
    ```

4.  **Verify the tool** is registered:
    ```bash
    hermes tools list | grep prebextor
    # Should show: web.prebextor_extract
    ```

5.  **Smoke-test** native extraction:
    ```bash
    python3 -c "
    import sys; sys.path.insert(0, '$HOME/.hermes/plugins')
    from prebextor import PrebextorProvider
    p = PrebextorProvider()
    r = p.extract(['https://example.com'])
    print(r['success'], len(r.get('data', [])))
    "
    ```
    Must print a successful envelope contract.

## Optional: web.extract_backend config

To route `web_extract` (the standard Hermes tool) through Prebextor:
```bash
hermes config set web.extract_backend prebextor
```
Then restart Hermes (or `/reset` in chat). The standalone `prebextor_extract`
tool bypasses this config — it works independently.

## Removal

```bash
# Remove plugin
rm -rf ~/.hermes/plugins/prebextor/

# Revert config if you set it
hermes config set web.extract_backend searxng   # or your previous backend
```

## Pitfalls

*   `cp -rL` (resolve symlinks) — never `cp -r` with dangling symlinks.
*   `plugins.enabled` must list `web/prebextor` if your Hermes version uses
    an explicit plugin allowlist.
*   Restart gateway/CLI after deploy — plugin manifest reads happen at startup.
*   CamoFox CLI must be installed and on `PATH` for `is_available()` to return
    True. Without it, the provider registers but extraction returns errors.
*   Optional Hermes core patches described in `INTEGRATION.md` are **not**
    required for the standalone `prebextor_extract` tool — they only affect
    the `web.extract_backend: prebextor` route through `web_tools`.

## Why two skills?

Two skill lifecycles, two audiences:

*   **Standalone** (`web-extraction/prebextor/`) — auto-listed, visible in
    every chat session's `<available_skills>` index. Targets end users who
    say "install prebextor".
*   **Embedded** (this one, `prebextor:install`) — opt-in via
    `skill_view()`, only resolvable when an agent already has the plugin
    loaded. Targets agents that want the install procedure BUNDLED with
    the plugin for portability.
