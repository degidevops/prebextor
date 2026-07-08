#!/usr/bin/env bash
# Deploy prebextor plugin to Hermes — ONLY the runtime files.
# Excludes: .venv, .git, tests, caches, egg-info, docs, pycache.
#
# IMPORTANT: The Hermes plugin loader expects the plugin ROOT directory to
# contain __init__.py + plugin.yaml directly. In this repo the plugin package
# lives under ./prebextor/ — so we copy the CONTENTS of ./prebextor/ into the
# destination, NOT the ./prebextor/ folder itself (that would double-nest and
# the loader would never find register()).
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)/prebextor"
DEST="${1:-$HOME/.hermes/plugins/prebextor}"

echo "Deploy -> $DEST"

mkdir -p "$DEST"

# 1. the entire prebextor/ package contents, with junk stripped
rsync -a --delete \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.mypy_cache/' \
  --exclude='.ruff_cache/' \
  "$SRC/" "$DEST/"

echo "Done. Deployed size:"
du -sh "$DEST"
