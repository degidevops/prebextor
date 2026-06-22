---
name: prebextor
description: "Install and configure Prebextor as the deterministic web extraction backend for Hermes Agent. Use when the user wants to install, deploy, verify, or remove the Prebextor plugin. Handles real-file-copy deployment, config.yaml patching, and verification."
version: 2.1.0
platforms: [linux]
metadata:
  hermes:
    tags: [web, extraction, deterministic, prebextor]
    category: web-extraction
    requires_toolsets: [terminal]
    config:
      - key: web.extract_backend
        description: Prebextor extract backend id
        default: '"prebextor"'
---

# Prebextor — Deterministic Web Extraction Engine

## When to Use

- User says "install prebextor", "deploy prebextor", "setup prebextor extraction backend"
- User wants to activate Prebextor as `web_extract` backend in Hermes
- User wants to verify Prebextor plugin is working
- User wants to remove/uninstall Prebextor plugin

## Source Layout

```
~/project/prebextor/
├── SKILL.md                    # This file — skill + install procedure
├── prebextor/                  # Plugin source code (copy to ~/.hermes/plugins/web/prebextor/)
│   ├── __init__.py
│   ├── provider.py
│   ├── plugin.yaml
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── mapper.py
│   │   ├── pruner.py
│   │   ├── qa.py
│   │   └── transform.py
│   └── fetcher/
│       ├── __init__.py
│       └── camofox_client.py
├── patches/                    # Hermes-agent side fixes (apply-patches.sh)
│   ├── manifest.json
│   └── web_tools.py.patch
├── scripts/
│   ├── deploy.sh               # Copy plugin + apply patches + patch config
│   ├── undeploy.sh             # Revert patches + remove plugin + revert config
│   ├── apply-patches.sh        # Idempotent Hermes-agent patch apply
│   ├── verify.py               # Import + envelope schema check
│   └── test_patches.py         # Sandbox round-trip for the patch set
├── tests/
│   ├── __init__.py
│   ├── test_e2e_extract.py
│   └── test_envelope_schema.py
├── architecture/
│   ├── blueprint-v1.md
│   └── blueprint-v2.md
├── research/
│   └── ...
└── CHANGELOG.md                # Keep a Changelog format
```

## Procedure

### Deploy (Install)

1. Validate source tree exists at `~/project/prebextor/prebextor/`
2. Run `scripts/deploy.sh`:
   - Validates source tree
   - Copies real files to `~/.hermes/plugins/web/prebextor/`
   - **Invokes `apply-patches.sh`** — adds the Prebextor dispatch glue
     to the user's Hermes-agent `tools/web_tools.py`. Required for
     `web_extract` to route to Prebextor. Without this step, Hermes
     silently fails back to `searxng`.
   - Patches `~/.hermes/config.yaml` and the active profile's config
     (`extract_backend: prebextor`).
3. Run `scripts/verify.py` — confirms import, capabilities, envelope schema
4. (Optional) Run `scripts/test_patches.py` — runs the patch set against
   a sandboxed copy of the user's Hermes-agent; useful if upstream
   Hermes has moved and you suspect `deploy.sh` will refuse.

### Verify

1. Run `scripts/verify.py` — checks plugin shape + import
2. Run `scripts/test_patches.py` — checks patch shape + drift + round-trip
3. Expected: both print `ALL CHECKS PASSED`

### Undeploy (Remove)

1. Run `scripts/undeploy.sh` — restores patched files from
   `<target><backup_extension>`, removes marker + backup, then removes
   the plugin directory and reverts both root and profile configs.
2. Idempotent. Safe to run if the install was already half-cleaned.

## Pitfalls

- **Real files only**: Never use symlinks. Hermes plugin loader requires real files.
- **camofox must be installed**: `is_available()` checks `camofox --version`.
- **Do NOT touch precision-extractor**: Legacy plugin is unrelated.
- **Config backup**: deploy.sh creates `~/.hermes/config.yaml.bak.prebextor` before patching.
- **Hermes-agent patches live in `patches/`**: deploy.sh applies them to the
  user's Hermes-agent checkout on install. The patches are NOT committed to
  the user's Hermes-agent git history — they live entirely in this project,
  with `<target><backup_extension>` backups + `<target><marker_extension>`
  marker files in the user's Hermes-agent dir as the only on-disk signals.
- **Drift detection**: apply-patches.sh will refuse to install if the
  upstream Hermes-agent has moved (target SHA-256 != manifest baseline).
  Re-run `scripts/test_patches.py` after rebasing the patch on the
  new HEAD; touch the manifest with the new SHA-256 and CHANGELOG.
- **Patch is single-use**: `git apply` reports a conflict if you try to
  re-apply on top of an already-patched file. always-idempotent detection
  happens in apply-patches.sh via the `.prebextor-patched` marker + sentinel.
- **Do not edit upstream `tools/web_tools.py` by hand while patched** —
  apply-patches.sh's drift check will then refuse subsequent deploys.
  Either restore from `<target><backup_extension>` or undeploy and redeploy.

## Verification

```bash
# Plugin side
python3 ~/project/prebextor/scripts/verify.py

# Patch side
python3 ~/project/prebextor/scripts/test_patches.py

# End-to-end dispatch (after deploy.sh)
curl -fsSL https://example.com && echo "(sanity-check that HTTPS works from this host)"
python3 -c "import sys; sys.path.insert(0,'/home/degi/.hermes/hermes-agent'); import asyncio; from tools.web_tools import web_extract_tool; print(asyncio.run(web_extract_tool(['https://example.com'])))"
```
