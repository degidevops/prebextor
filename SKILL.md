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
├── scripts/
│   ├── deploy.sh               # Copy plugin + patch config
│   ├── undeploy.sh             # Remove plugin + revert config
│   └── verify.py               # Import + envelope schema check
├── tests/
│   ├── __init__.py
│   ├── test_e2e_extract.py
│   └── test_envelope_schema.py
├── architecture/
│   ├── blueprint-v1.md
│   └── blueprint-v2.md
└── research/
    └── ...
```

## Procedure

### Deploy (Install)

1. Validate source tree exists at `~/project/prebextor/prebextor/`
2. Run `scripts/deploy.sh` — copies real files to `~/.hermes/plugins/web/prebextor/` and patches config
3. Run `scripts/verify.py` — confirms import, capabilities, envelope schema

### Verify

1. Run `scripts/verify.py` — checks all assertions
2. Expected: `ALL CHECKS PASSED`

### Undeploy (Remove)

1. Run `scripts/undeploy.sh` — removes plugin dir and reverts config

## Pitfalls

- **Real files only**: Never use symlinks. Hermes plugin loader requires real files.
- **camofox must be installed**: `is_available()` checks `camofox --version`.
- **Do NOT touch precision-extractor**: Legacy plugin is unrelated.
- **Config backup**: deploy.sh creates `~/.hermes/config.yaml.bak.prebextor` before patching.

## Verification

```bash
python3 ~/project/prebextor/scripts/verify.py
```
