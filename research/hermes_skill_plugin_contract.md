# Research: Hermes Agent Skill + Plugin Integration Contract

## Context
Riset dilakukan pada 2026-06-21 untuk memvalidasi struktur resmi *plugin* `web_extract`/`web_search` backend dan *skill* wrapper di Hermes Agent. Tujuan: menghilangkan preseden yang salah (mirror dari `precision-extractor` lokal) dan menyusun ulang dokumentasi Prebextor sehingga satu skill dapat membungkus deployment plugin dengan benar.

## Source of Truth (Halaman resmi Hermes Agent)
1. **Plugin contract**: https://hermes-agent.nousresearch.com/docs/developer-guide/web-search-provider-plugin
2. **Skills system**: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
3. **Capabilities rubric** (di halaman pertama): SearXNG didokumentasikan sebagai *search-only* dengan workflow resmi "pair me with an extract provider". Ini meng-confirm bahwa pairing SearXNG + Prebextor adalah desain yang sesuai standar Hermes Agent, bukan improvisasi.

## Plugin Installation Paths (3 Jalur Resmi)
Hermes Agent scan lokasi plugin web-search di **3 tempat**:

| Lokasi | Mode aktivasi |
| :--- | :--- |
| **Bundled**: `<repo>/plugins/web/<name>/` | Auto-loaded, `kind: backend` |
| **User**: `~/.hermes/plugins/web/<name>/` | Opt-in via `plugins.enabled` atau `hermes plugins enable <name>` |
| **Pip**: package dengan entry point `hermes_agent.plugins` | Didaftarkan di `pyproject.toml` |

**Keputusan untuk Prebextor**: pakai jalur **User** (`~/.hermes/plugins/web/prebextor/`) karena Prebextor adalah plugin *milik pengguna*, bukan bundled core.

## Directory Structure (Wajib, Minimum)
```
plugins/web/prebextor/
├── __init__.py      # Entry: def register(ctx)
├── provider.py      # Subclass agent.web_search_provider.WebSearchProvider
└── plugin.yaml      # Manifest: kind: backend + provides_web_providers
```
Diperbolehkan juga `@-references/`, `@-templates/`, `@-scripts/`, `@-assets/` di dalam skill (bukan plugin). Plugin **hanya** butuh 3 file itu.

## `plugin.yaml` Schema (Valid)
```yaml
name: web-prebextor
version: 1.0.0
description: "Prebextor Deterministic Extraction Engine — ..."
author: degi
kind: backend
provides_web_providers:
  - prebextor
```
Field **wajib**: `name`, `kind: backend`, `provides_web_providers`. Field opsional: `version`, `author`, `description`, `requires_env`.

## `WebSearchProvider` ABC Contract (Wajib Diimplement)
Subclass `agent.web_search_provider.WebSearchProvider`:

| Member | Required? | Default | Purpose |
| :--- | :--- | :--- | :--- |
| `name` (property, str) | ✅ | — | Stable id for `web.*_backend` config. Lowercase, hyphen-allowed, no spaces. |
| `display_name` | — | `name` | Label di `hermes tools`. |
| `is_available() -> bool` | ✅ | — | **Cheap availability gate** — env var/optional deps. **TIDAK boleh network call** (dipanggil tiap `hermes tools` paint). |
| `supports_search() -> bool` | — | `True` | Capability flag untuk `web_search` routing. |
| `supports_extract() -> bool` | — | `False` | Capability flag untuk `web_extract` routing. |
| `search(query, limit)` | if supports_search | raises | Required ketika `supports_search() == True`. |
| `extract(urls, **kwargs)` | if supports_extract | raises | Required ketika `supports_extract() == True`. Sync atau `async def` (dispatcher deteksi via `inspect.iscoroutinefunction`). |

## Response Envelope (Wajib Pada Block Panggil)
Dispatcher di `tools/web_tools.py` **menolak** response yang tidak mengikuti envelope. Format fixed:

**Search success**:
```json
{"success": true, "data": {"web": [{"title", "url", "description", "position"}, ...]}}
```

**Extract success**:
```json
{"success": true, "data": [
  {"url", "title", "content", "raw_content", "metadata?", "error?"},
  ...
]}
```

**Failure** (apapun capability):
```json
{"success": false, "error": "human-readable message"}
```

## Routing Config Keys (`~/.hermes/config.yaml` & `<profile>/config.yaml`)
| Capability | Key | Falls back to |
| :--- | :--- | :--- |
| `web_search` | `web.search_backend` | `web.backend` |
| `web_extract` | `web.extract_backend` | `web.backend` |
| Deep-crawl (mode of `extract`) | `web.extract_backend` | `web.backend` |

**Konfigurasi final Prebextor** (sudah di-set sesi sebelumnya):
- `web.search_backend = 'searxng'` (root + dave profile)
- `web.extract_backend = 'prebextor'` (akan di-patch dari skill installer)
- `web.backend = ""` (kosong, biar per-capability overrides dipakai)

## Skill System (Loader Prebextor)
**Lokasi skill di Hermes:**
- **Primary**: `~/.hermes/skills/<category>/<skill-name>/SKILL.md`
- User-managed, agent-managed (`skill_manage`), bundled (di-seed otomatis dari repo), hub-installed (`hermes skills install`)
- Bisa ditambah lewat `skills.external_dirs` di config → scan external folder (shared, multi-agent)

**SKILL.md format (valid):**
```yaml
---
name: prebextor-extractor      # lowercase-hyphens, ≤64 chars
description: Install and configure Prebextor ...   # ≤1024 chars
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [web, extraction, deterministic, zero-noise]
    category: web-extraction
    config:                       # optional: settings di config.yaml
      - key: web.extract_backend
        description: "Prebextor backend id"
        default: '"prebextor"'
---
# Body proceeded: When to Use / Procedure / Pitfalls / Verification
```

**Skill loading**: 3-level progressive disclosure:
- Level 0: `skills_list()` — small index
- Level 1: `skill_view(name)` — full content
- Level 2: `skill_view(name, path)` — specific reference file

**Skill directory structure (recommended):**
```
~/.hermes/skills/web-extraction/prebextor-extractor/
├── SKILL.md
├── references/        # additional docs
├── templates/         # output formats
├── scripts/           # helper scripts
└── assets/            # supplementary files
```

## Pitfalls & Lessons Learned
- **Envelope strictness**: `extract()` yang mengembalikan `List[Dict]` langsung **TIDAK akan diproses dispatcher**. Wajib `{"success": True, "data": [...]}` atau `{"success": False, "error": "..."}`. Ini bugs utama hasil edit Prebextor sebelumnya.
- **`is_available()` cheap contract**: method ini dipanggil berkali-kali (tiap `hermes tools` paint). Jangan network-call, jangan subprocess yang lama. Cukup cek env var / import.
- **Per-capability vs global**: `web.backend` adalah fallback untuk search **dan** extract. Saat `web.search_backend` dan `web.extract_backend` keduanya di-set, per-capability menang. SearXNG resmi dipair dengan extract provider terpisah (kami cocokkan dengan Prebextor).
- **`kind: backend`** wajib — bukan `standalone`. Field ini yang me-route loader ke path backend plugin yang benar.
- **Plugin user (`~/.hermes/plugins/`) optically independent dari profile**: walaupun Anda aktif di profile `dave`, plugin user-plugin loaded oleh Hermes core (bukan dimuat ke profile tertentu). Karena itu `~/.hermes/plugins/` (root) adalah target install yang benar.

## Verification Steps (untuk Skill + Plugin)
1. Cek `~/.hermes/plugins/web/prebextor/` ber-isi 3 file wajib: `__init__.py`, `provider.py`, `plugin.yaml`.
2. Cek `~/.hermes/config.yaml` dan `~/.hermes/profiles/dave/config.yaml` keduanya berisi `web.extract_backend: "prebextor"`.
3. Jalankan `hermes tools | grep prebextor` → nama provider muncul di daftar.
4. Test pemanggilan: dari Python shell, `import` plugin via `path/ke/dir/plugins/web/prebextor` lalu Instantiate provider dan panggil `extract(["https://example.com"])` — return harus match envelope sukses.
5. Restart Hermes Agent (`hermes restart` atau equivalent) jika perubahan config baru terdeteksi.

## Ringkasan (Apa yang Berubah dari Preseden Salah)
| Topik | Preseden lama (salah) | Riset resmi (benar) |
| :--- | :--- | :--- |
| `plugin.yaml` kind | `standalone` | `backend` |
| Response envelope `extract` | `List[Dict]` langsung | `{"success": true, "data": [...]}` |
| Lokasi plugin user | `~/.hermes/<profile>/plugins/web/` | `~/.hermes/plugins/web/` |
| `is_available()` impl | network-call (subprocess `camofox --version`) | cheap gate (env-only) |
| Config key | `web.backend` saja | `web.extract_backend` + `web.search_backend` |
| `cp -RL` di installer | asumsi hard-link-safe | `-R` (no -L) untuk copy file nyata |

---
*Maintained by Hermes Agent (Dave). Verified against official Hermes Agent documentation on 2026-06-21.*
