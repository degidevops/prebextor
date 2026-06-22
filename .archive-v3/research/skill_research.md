# Research: Hermes Agent Skill System (for plugin-deploying skills)

## Source
Hermes Agent documentation, "Skills System":
- https://hermes-agent.nousresearch.com/docs/user-guide/features/skills

## Why this exists
Prebextor must be **deployed via a skill**, not by a one-off `cp` command. A skill is a token-efficient, declarative knowledge bundle that the agent can load on demand; embedding the install procedure in a skill turns deployment into an agent action (`/prebextor-extractor install`) and keeps the procedure reusable and auditable.

## Skill location
- Default: `~/.hermes/skills/`.
- Category subdirs permitted: `~/.hermes/skills/web-extraction/<name>/SKILL.md`.
- External dirs supported via `skills.external_dirs` in config.

## SKILL.md schema (authoritative)

```yaml
---
name: prebextor-extractor            # lowercase-hyphens, ≤ 64 chars, matches folder name
description: <≤ 1024 chars, explains both WHAT and WHEN to use>
version: 1.0.0
platforms: [linux]                    # optional; hidden elsewhere
metadata:
  hermes:
    tags: [web, extraction, deterministic]
    category: web-extraction
    fallback_for_toolsets: [web]      # optional: show only when these are missing
    requires_toolsets: [terminal]     # optional: show only when these are present
    config:                            # optional config keys
      - key: web.extract_backend
        description: Prebextor extract backend id
        default: '"prebextor"'
required_environment_variables:       # optional: secure setup on load
  - name: SOME_TOKEN
    prompt: Prompt displayed to user
    help: Where to get it
    required_for: full functionality
---

# Skill Title

## When to Use
The trigger conditions that activate this skill.

## Procedure
1. Step one
2. Step two

## Pitfalls
- Known failure modes and their fixes.

## Verification
How to confirm the skill ran successfully.
```

## Loading patterns (progressive disclosure)
- `skills_list()` → `[name, description, category]` (~3k tokens).
- `skill_view(name)` → full content + metadata.
- `skill_view(name, path)` → specific reference file.

The agent only loads full content when needed.

## Distributing a skill
- On-disk: copy `SKILL.md` (+ `scripts/`, `references/`) into `~/.hermes/skills/<cat>/<name>/`.
- `hermes skills install <url | tap>` for hub installs.
- `hermes bundles create ...` to group skills under one slash command.

## Auto-activation
A skill without conditional fields is always listed. Fields `fallback_for_toolsets`, `requires_toolsets`, etc. gate visibility per session; the *built-in duckduckgo-search* skill uses `fallback_for_toolsets: [web]` so it only appears when no paid web backend is configured. Sample pattern for `prebextor-extractor`:
```yaml
metadata:
  hermes:
    fallback_for_toolsets: [web]      # show only when web toolset is missing
```

(Since this skill *creates* the web tool by installing the backend, gating on `fallback_for_toolsets: [web]` makes the skill self-discoverable only when needed — but if it is not itself a `web` tool, alternative gating expressions exist. Use `requires_tools` to ensure `terminal` is present.)

## Secure setup on load
`required_environment_variables` lets a skill declare secrets without disappearing from discovery. The CLI prompts only locally; messaging surfaces tell the user to use `hermes setup` or `~/.hermes/.env`. Once set, declared env vars are passed through to `execute_code` and `terminal` sandboxes.

## Why SKILL.md is required for deployment
The skill body is the canonical place to encode Prebextor's install procedure:
- Validate source tree at `~/project/prebextor/prebextor/`.
- Reject if `plugin.yaml`, `__init__.py`, `provider.py`, `pipeline/`, `fetcher/` are missing.
- Copy (real files, no symlinks) into `~/.hermes/plugins/web/prebextor/`.
- Patch `~/.hermes/config.yaml` so `web.extract_backend = prebextor`.
- Run a verification import + capability probe.
- Emit a final summary line.

The same body remains the source of truth for `hermes skills ...` invocations and for any tool calls the agent decides to make after loading the skill.
