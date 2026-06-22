---
name: prebextor-install
description: "Install, verify, and uninstall Prebextor — the same procedure as the standalone skeleton, but bundled INSIDE the plugin so the lifecycle travels with the code itself. Opt-in via skill_view('prebextor:install')."
version: 3.2.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [web, extraction, deterministic, prebextor, plugin-installer]
    category: web-extraction
    requires_toolsets: [terminal]
---

# Prebextor — Plugin-Embedded Install Skill (opt-in)

This skill is shipped **inside** the Prebextor plugin (`prebextor/skill_internal/SKILL.md`)
and registered via `ctx.register_skill()` from the plugin's `register(ctx)` hook.

It is referenced as `prebextor:install` and is reachable only through
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
<plugin_root>/                     e.g. /home/degi/.hermes/plugins/web/prebextor/
├── __init__.py                    # register(ctx) — registers provider + THIS skill
├── provider.py                    # WebSearchProvider subclass
├── plugin.yaml                    # Manifest
├── pipeline/                      # Mapper, Pruner, QA, Transformer
├── fetcher/                       # CamoFox client
└── skill_internal/
    └── SKILL.md                   # ← you are here
```

The plugin also expects the full Prebextor source tree at
`/home/degi/project/prebextor/` for the canonical `scripts/deploy.sh`
installer. When deploying from pip/git, ship the project source alongside
the plugin or adapt the installer to read from the plugin's parent tree.

## Install procedure

1.  **Confirm source** at `/home/degi/project/prebextor/`. If missing,
    copy first (`git clone`, `tar`, `scp`).

2.  **Deploy via the canonical installer** (idempotent):
    ```bash
    bash /home/degi/project/prebextor/scripts/deploy.sh
    ```

3.  **Verify**:
    ```bash
    python3 /home/degi/project/prebextor/scripts/verify.py
    ```

4.  **Smoke-test** native `web_extract`:
    ```bash
    python3 /home/degi/project/prebextor/scripts/verify.py --test-extract
    ```
    Must print `<extraction_result>` envelope contract.

## Removal

```bash
bash /home/degi/project/prebextor/scripts/undeploy.sh
```

## Pitfalls (see canonical SKILL.md for full list)

*   `cp -rL` — no symlinks
*   `[3b] WARN` from `deploy.sh` is fatal (patch did not apply)
*   Per-profile `config.yaml` patching
*   `plugins.enabled` must list `web/prebextor`
*   Restart gateway after deploy

## Why two skills?

Two skill lifecycles, two audiences:

*   **Standalone** (`web-extraction/prebextor/`) — auto-listed, visible in
    every chat session's `<available_skills>` index. Targets end users who
    say "install prebextor".
*   **Embedded** (this one, `prebextor:install`) — opt-in via
    `skill_view()`, only resolvable when an agent already has the plugin
    loaded. Targets agents that want the install procedure BUNDLED with
    the plugin for portability.

Both call the same canonical installer. Neither reimplements the deploy
logic — they are procedures, not implementations.
