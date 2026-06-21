# Research: Hermes Agent Skills System (SLM Skill Frontmatter, Activation, Bundles)

## Context
File `research/hermes_skill_plugin_contract.md` sudah merangkum sisi *plugin*
Hermes (provider, manifest, envelope). Dokumen ini khusus sisi *skill* —
bagaimana Prebextor dibungkus dalam satu skill yang dapat meng-install
plugin-nya otomatis.

## Source of Truth
Halaman resmi: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills

## Lokasi Direktori Skill
- **Default (satu-satunya sumber kebenaran)**: `~/.hermes/skills/`
- Sub-direktori kategori: `~/.hermes/skills/<category>/<skill-name>/`
- Bundled skills dicopy ke `~/.hermes/skills/` saat fresh install
- Optional dirs lain via `skills.external_dirs` di config.yaml

Direktori layout per skill (resmi):
```
~/.hermes/skills/
└── <category>/
    └── <skill-name>/
        ├── SKILL.md            # Required
        ├── references/         # Optional: docs pendukung
        ├── templates/          # Optional: output formats
        ├── scripts/            # Optional: helper scripts
        └── assets/             # Optional: file pelengkap
```

## SKILL.md Frontmatter (Verifikasi)
Field WAJIB:
- `name: <slug>` — lowercase + hyphens, ≤64 char, **harus cocok dengan parent folder name**
- `description: <text>` — ≤1024 char; harus jelas mendeskripsikan kapan skill digunakan
  (loader pakai ini untuk aktivasi on-demand)

Field OPSIONAL:
- `version`, `author`
- `platforms: [macos, linux, windows]` — skill auto-hidden di OS yang tidak cocok
- `metadata.hermes.tags` — list of tags
- `metadata.hermes.category`
- `metadata.hermes.fallback_for_toolsets` / `requires_toolsets` — konditional activation
- `metadata.hermes.fallback_for_tools` / `requires_tools` — same, per-tool
- `metadata.hermes.config` — deklarasi config keys (akan dimintakan saat load)
- `required_environment_variables` — secret declaration (Hermes prompt on-demand
  hanya via local CLI; messaging surfaces tidak prompt)

## Progressive Disclosure (Load Pattern)
Hermes tidak memuat full body SKILL.md di setiap turn:
- Level 0: `skills_list()` → list flat (name + description only)
- Level 1: `skill_view(name)` → full content + metadata
- Level 2: `skill_view(name, file_path=...)` → specific reference/template

Implikasi untuk Prebextor Skill:
- `description` harus cukup deskriptif untuk agent *tahu kapan* memanggil skill.
- Body yang panjang disimpan di `references/`, di-load hanya saat skill dipakai.

## Activation Models
- **Always shown**: skill tanpa conditional field — selalu muncul di skill_index.
- **Conditional** (`fallback_for_toolsets`, `requires_toolsets`):
  muncul hanya saat toolsets tertentu available/tidak.
- Contoh resmi: built-in DuckDuckGo skill pakai
  `fallback_for_toolsets: [web]` → muncul hanya saat `web` toolset tidak
  tersedia (misalnya `FIRECRAWL_API_KEY` belum diset).

## Bundles (Slash command groups)
Bundle = file YAML di `~/.hermes/skill-bundles/<slug>.yaml`. Format:
```yaml
name: backend-dev
description: Backend feature work
skills:
  - github-code-review
  - test-driven-development
  - github-pr-workflow
instruction: |
  Always start by writing failing tests first.
```
Aturan: bundle **tidak install skills** — bundle hanya grouping reference.
Skills harus sudah ada di skills-dir dulu.

## Agent-Managed Skills (skill_manage tool)
Agent dapat memodifikasi skills via tool `skill_manage(action='create'|'patch'|'edit'|'delete'|'write_file'|'remove_file')`. Penting: ini adalah **procedural memory** agent untuk dipakai sendiri. Workflow: tulis saat setelah task kompleks 5+ tool calls selesai, atau saat ada koreksi user, atau saat discovery non-trivial workflow.

## Skill Output Mechanisms (untuk installer Prebextor)
- Setiap response yang berisi path absolut ke media file → auto-delivered via gateway (Telegram photo, dsb.).
- Directive `[[as_document]]` di akhir response → file dikirim sebagai document attachment, bukan photo bubble.
- Directive `[[audio_as_voice]]` → audio naik ke voice-message bubble (Telegram/WhatsApp).

## Hub / Distribution (untuk publish skill Prebextor ke publik)
- `hermes skills install <source>` dengan sumber:
  `official`, `skills-sh`, `well-known`, `github`, `clawhub`,
  `claude-marketplace`, `lobehub`, `browse-sh`, `url`.
- Trust levels mengontrol auto-apply.

## Trusted Setup (pra-load config)
- Skill dapat deklarasi env vars via `required_environment_variables`.
- Saat load, Hermes cek env; kalau hilang, prompt muncul hanya di **local CLI**
  (bukan messaging surface).
- Skills config keys (non-secret) disimpan di `config.yaml` di bawah skill-specific
  path (lihat `metadata.hermes.config`).

## Aplikasi ke Prebextor
1. Skill `prebextor-extractor` disimpan di
   `~/.hermes/skills/web-extraction/prebextor-extractor/SKILL.md`.
2. Frontmatter:
   - `name: prebextor-extractor`
   - `description`: jelaskan "install Prebextor plugin deterministic extraction backend ke Hermes",
     "support config edit", "verify Hermes boots".
3. Body berisi:
   - When to Use: "User bilang install prebextor / user mau pasang backend web_extract baru"
   - Procedure: step-by-step `install.sh` (copy plugin ke `~/.hermes/plugins/web/prebextor/`,
     patch `web.extract_backend = prebextor`).
   - Pitfalls: precision-extractor legacy ref harus OUT.
   - Verification: `hermes tools | grep prebextor` dan import test.

## Reference (verified URLs)
- Web Search Provider Plugins:
  https://hermes-agent.nousresearch.com/docs/developer-guide/web-search-provider-plugin
- Skills System:
  https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
- Web Search & Extract (config keys):
  https://hermes-agent.nousresearch.com/docs/user-guide/features/web-search
