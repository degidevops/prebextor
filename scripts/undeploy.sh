#!/usr/bin/env bash
# undeploy.sh — Remove Prebextor plugin from Hermes Agent
set -euo pipefail

PLUGIN_DIR="$HOME/.hermes/plugins/web/prebextor"
CONFIG="$HOME/.hermes/config.yaml"

echo "=== Prebextor Undeploy ==="

if [ -d "$PLUGIN_DIR" ]; then
    rm -rf "$PLUGIN_DIR"
    echo "[1/2] Plugin directory removed: $PLUGIN_DIR"
else
    echo "[1/2] Plugin directory not found (already removed?)"
fi

if [ -f "$CONFIG.bak.prebextor" ]; then
    cp "$CONFIG.bak.prebextor" "$CONFIG"
    echo "[2/2] Config restored from backup"
elif [ -f "$CONFIG" ]; then
    sed -i '/extract_backend: prebextor/d' "$CONFIG"
    echo "[2/2] Config patched: removed extract_backend line"
else
    echo "[2/2] Config not found"
fi

echo "=== Undeploy Complete ==="
