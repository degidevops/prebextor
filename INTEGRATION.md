# Prebextor ↔ Hermes Agent Integration Notes

## Problem: `web_extract` tidak bisa menggunakan Prebextor meski sudah dikonfigurasi

### Gejala
- `web.extract_backend: prebextor` sudah diset di `config.yaml`
- Plugin Prebextor sudah ter-copy ke `~/.hermes/plugins/web/prebextor/`
- `verify.py` pass untuk import dan plugin copy
- Tapi `web_extract` error: *"SearXNG is a search-only backend and cannot extract URL content"*

### Root Cause
Dua masalah di `/home/degi/.hermes/hermes-agent/tools/web_tools.py`:

1. **`_LEGACY_WEB_BACKENDS` tidak include `prebextor`** → early-return di `_get_backend()` gagal, fallback ke auto-detect (SearXNG karena `SEARXNG_URL` ada)

2. **`_is_backend_available()` tidak call `_ensure_web_plugins_loaded()` sebelum cek registry** → plugin-registered providers (seperti prebextor) tidak ditemukan saat cek availability, return `False`

3. **Provider response normalization** → Prebextor mengembalikan *Hermes envelope* `{"success": true, "data": [...]}` tapi dispatcher expect *raw list* legacy format

---

## Fix Applied (2026-07-04)

### File: `/home/degi/.hermes/hermes-agent/tools/web_tools.py`

#### 1. Tambahkan `prebextor` ke `_LEGACY_WEB_BACKENDS` (line ~157)
```python
_LEGACY_WEB_BACKENDS = frozenset({
    "parallel", "firecrawl", "tavily", "exa", "searxng", 
    "brave-free", "ddgs", "xai", "prebextor"  # ← added
})
```

#### 2. Call `_ensure_web_plugins_loaded()` di awal `_is_backend_available()` (line ~310)
```python
def _is_backend_available(backend: str) -> bool:
    backend = (backend or "").lower().strip()
    # Ensure plugin discovery has run so the registry is populated.
    # This is critical for user-plugin backends like prebextor that register
    # via the plugin system rather than being built into Hermes-agent.
    _ensure_web_plugins_loaded()
    if backend not in _LEGACY_WEB_BACKENDS:
        registered = _registered_web_provider_available(backend)
        if registered is not None:
            return registered
    # ... rest unchanged
```

#### 3. Normalisasi response provider di `web_extract_tool()` (after line ~883)
```python
# Accept both shapes:
# 1. Envelope: {"success": True, "data": [dict, ...]}  (Prebextor, documented contract)
# 2. Raw list: [dict, dict, ...]                         (bundled providers, legacy)
if isinstance(results, dict):
    if results.get("success") is False:
        return json.dumps({"success": False, "error": ...})
    if "data" in results:
        extracted = results["data"]
        if isinstance(extracted, dict):
            extracted = [extracted]
        if not isinstance(extracted, list):
            return json.dumps({"success": False, "error": ...})
        results = extracted
    else:
        results = [results]
```

---

## Verification

```bash
# 1. Test provider langsung
python3 -c "
import sys; sys.path.insert(0, '/home/degi/.hermes/plugins/web')
from prebextor import PrebextorProvider
p = PrebextorProvider()
print(p.name, p.supports_extract(), p.is_available())
# Output: prebextor True True
"

# 2. Test registry resolution
python3 -c "
import sys; sys.path.insert(0, '/home/degi/.hermes/hermes-agent')
from hermes_cli.plugins import _ensure_plugins_discovered
_ensure_plugins_discovered()
from agent.web_search_registry import get_active_extract_provider
p = get_active_extract_provider()
print(p.name if p else 'None')
# Output: prebextor
"

# 3. Test end-to-end web_extract
python3 -c "
import asyncio, sys
sys.path.insert(0, '/home/degi/.hermes/hermes-agent')
from tools.web_tools import web_extract_tool
async def test():
    result = await web_extract_tool(['https://python.org'])
    print(result[:500])
asyncio.run(test())
# Output: JSON dengan results[0].content berisi markdown/html konten
"

# 4. Run verify script
python3 /home/degi/project/prebextor/.archive-v3/scripts/verify.py --test-extract
# Output: [10] PASS: Provider.extract() returns envelope
```

---

## Arquitecture Note

```
┌─────────────────────────────────────────────────────────────┐
│  Hermes Agent Core (tools/web_tools.py)                    │
│  ├── _get_extract_backend() → reads config                 │
│  ├── _is_backend_available() → checks registry             │
│  │   └── _ensure_web_plugins_loaded() ← KEY FIX            │
│  └── web_extract_tool() → dispatches to provider           │
│       └── normalize response (envelope ↔ raw list)         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Plugin System (hermes_cli/plugins.py)                     │
│  ├── _ensure_plugins_discovered()                          │
│  │   └── loads ~/.hermes/plugins/web/prebextor/__init__.py │
│  │       └── register(ctx) → ctx.register_web_search_provider()
│  └── agent/web_search_registry.register_provider()         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Prebextor Plugin (~/.hermes/plugins/web/prebextor/)       │
│  ├── plugin.yaml (kind: backend, provides_web_providers)   │
│  ├── __init__.py → register(ctx) → PrebextorProvider()    │
│  └── provider.py → WebSearchProvider.extract()             │
│       └── returns {"success": true, "data": [...]}         │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Principle

> **Core harus handle plugin discovery SEBELUM availability check.**
> 
> `_is_backend_available()` adalah *single chokepoint* untuk semua caller:
> - `_get_backend()` (auto-detect)
> - `_get_capability_backend()` (per-capability config)
> - `check_web_api_key()` (tool registry gate)
> - `web_extract_tool()` / `web_search_tool()` (dispatch)
> 
> Jadi **wajib** call `_ensure_web_plugins_loaded()` di awal fungsi ini.

---

## Related Files

| File | Role |
|------|------|
| `/home/degi/.hermes/hermes-agent/tools/web_tools.py` | **Fixed** - backend selection & dispatch |
| `/home/degi/.hermes/hermes-agent/agent/web_search_registry.py` | Registry implementation |
| `/home/degi/.hermes/hermes-agent/hermes_cli/plugins.py` | Plugin discovery & registration |
| `~/.hermes/plugins/web/prebextor/__init__.py` | Plugin entry point |
| `~/.hermes/plugins/web/prebextor/provider.py` | PrebextorProvider implementation |
| `/home/degi/project/prebextor/.archive-v3/scripts/deploy.sh` | Deploy script (copies plugin, patches config) |
| `/home/degi/project/prebextor/.archive-v3/scripts/verify.py` | Verification script |