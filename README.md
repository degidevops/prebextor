# Prebextor: Deterministic Extraction Engine

## 1. Core Architecture
Prebextor adalah backend provider deterministik untuk `web_search` dan `web_extract` di Hermes Agent. Engine ini memindahkan *content-awareness* ke sisi peramban (CamoFox) untuk menjamin data yang bersih (Zero-Noise) dan efisien secara token.

- **Output Format**: **Markdown** yang dibungkus dengan **Semantic XML-style boundary tags** (`<extraction_result>`, `<main_body>`, dll). Ini menjamin presisi batas konten tanpa mengorbankan keterbacaan Markdown bagi LLM.
- **Determinisme**: Seluruh pipeline (Mapping -> Pruning -> Fetching -> QA) bersifat *stateless* dan berbasis aturan (Rule-Based), bukan heuristik probabilitas.

## 2. Integration with Hermes Agent
Prebextor diintegrasikan sebagai **Backend Provider** melalui sistem plugin Hermes.

### Contract Compliance
Provider harus mengimplementasikan kontrak `WebSearchProvider` (dari Hermes Agent core):
- `supports_extract()`: Mengembalikan `True`.
- `extract(urls: List[str], **kwargs)`: Pipeline deterministik internal.
- `search(query: str, **kwargs)`: Orchestration via SearXNG.

### Plugin Registration
1. Prebextor harus terdaftar di `~/.hermes/plugins/web/` (atau direktori plugin Hermes yang sesuai).
2. Konfigurasi `web.search_backend` di Hermes harus merujuk ke provider Prebextor.
3. Prebextor menggunakan `PrebextorProvider` yang menginisiasi pipeline secara *on-demand* setiap kali ada request dari Hermes.

## 3. Installation Guide
1. **Dependencies**: Pastikan `markdownify`, `beautifulsoup4` terinstal di environment Hermes.
2. **Plugin Injection**: Salin (atau symlink) direktori `/home/degi/project/prebextor/prebextor/` ke direktori plugin Hermes (misal: `~/.hermes/plugins/web/prebextor/`).
3. **Verification**: Jalankan `hermes tools list` atau perintah verifikasi plugin untuk memastikan `PrebextorProvider` dimuat.

## 4. Operational Sequence (The Deterministic Pipeline)
Setiap request `web_extract` melalui Prebextor mengikuti alur kaku:
1. **Mapping**: `StructuralMapper` (Determining container via DOM hierarchy).
2. **Pruning**: `SurgicalPruner` (JavaScript-side noise removal).
3. **Fetching**: `FidelityFetcher` (Raw HTML retrieval).
4. **HTML QA**: `ZeroNoiseAssertionGate` (Assert clean HTML structure).
5. **Transformation**: `MarkdownConverter` (Hierarchy-preserving Markdown).
6. **Boundary Wrapping**: `BoundaryWrapper` (Semantic XML tagging).
7. **Final QA**: `ZeroNoiseAssertionGate` (Assert XML boundary integrity).

---
*Maintained by Hermes Agent (Dave).*
