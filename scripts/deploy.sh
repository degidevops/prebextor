#!/usr/bin/env bash
# deploy.sh — Deploy Prebextor plugin to Hermes Agent
# Usage: bash deploy.sh [source_path]
set -euo pipefail

SOURCE="${1:-$HOME/project/prebextor/prebextor}"
PLUGIN_DIR="$HOME/.hermes/plugins/web/prebextor"
CONFIG="$HOME/.hermes/config.yaml"

echo "=== Prebextor Deploy ==="

# 1. Validate source tree
if [ ! -d "$SOURCE" ]; then
    echo "FAIL: Source directory not found: $SOURCE"
    exit 1
fi

REQUIRED_FILES=("plugin.yaml" "__init__.py" "provider.py")
for f in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$SOURCE/$f" ]; then
        echo "FAIL: Required file missing: $SOURCE/$f"
        exit 1
    fi
done

REQUIRED_DIRS=("pipeline" "fetcher")
for d in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$SOURCE/$d" ]; then
        echo "FAIL: Required directory missing: $SOURCE/$d"
        exit 1
    fi
done

echo "[1/4] Source tree validated: $SOURCE"

# 2. Create plugin directory
mkdir -p "$PLUGIN_DIR"
echo "[2/4] Plugin directory created: $PLUGIN_DIR"

# 3. Copy real files (not symlinks)
cp -rL "$SOURCE"/* "$PLUGIN_DIR/"
echo "[3/4] Files copied (real files, no symlinks)"

# 4. Patch config.yaml
if [ -f "$CONFIG" ]; then
    cp "$CONFIG" "$CONFIG.bak.prebextor"
    if grep -q "extract_backend:" "$CONFIG"; then
        sed -i 's/extract_backend:.*/extract_backend: prebextor/' "$CONFIG"
    elif grep -q "^web:" "$CONFIG"; then
        sed -i '/^web:/a\  extract_backend: prebextor' "$CONFIG"
    else
        echo "" >> "$CONFIG"
        echo "web:" >> "$CONFIG"
        echo "  extract_backend: prebextor" >> "$CONFIG"
    fi
    echo "[4/4] Config patched: web.extract_backend = prebextor"
else
    mkdir -p "$(dirname "$CONFIG")"
    cat > "$CONFIG" <<'HERMES_CONFIG'
web:
  extract_backend: prebextor
HERMES_CONFIG
    echo "[4/4] Config created: $CONFIG"
fi

echo ""
echo "=== Deploy Complete ==="
echo "Plugin: $PLUGIN_DIR"
echo "Config: $CONFIG"
echo ""
echo "Verify: python3 $HOME/project/prebextor/scripts/verify.py"
