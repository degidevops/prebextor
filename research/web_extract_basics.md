# Cara Kerja `web_extract` di Hermes Agent

`web_extract` bukan merupakan sebuah alat tunggal dengan fungsi statis, melainkan sebuah **antarmuka (interface)** yang menghubungkan Hermes Agent dengan berbagai **Provider** (penyedia layanan ekstraksi).

Berikut adalah dasar-dasar cara kerja sistem ini:

## 1. Arsitektur Plugin
Hermes menggunakan sistem plugin untuk menangani permintaan ekstraksi. Saat Anda memanggil `web_extract`, Hermes tidak melakukan ekstraksi sendiri, melainkan mendelegasikan tugas tersebut kepada plugin yang terdaftar.

## 2. Kontrak Provider (`WebSearchProvider`)
Agar sebuah kode bisa berfungsi sebagai `web_extract`, ia harus memenuhi kontrak `WebSearchProvider`. Kontrak ini mewajibkan implementasi beberapa metode kunci, terutama:

- `supports_extract()`: Harus mengembalikan `True` agar Hermes tahu plugin ini bisa digunakan untuk ekstraksi.
- `extract(urls: List[str], **kwargs)`: Metode utama yang menerima daftar URL dan argumen tambahan (seperti pengaturan *scroll* atau *schema*).

## 3. Alur Eksekusi (The Request Flow)
Saat `web_extract` dipanggil:

1.  **Pengiriman Permintaan**: Hermes menerima perintah ekstraksi dengan satu atau lebih URL.
2.  **Routing**: Hermes mencari plugin yang memiliki `supports_extract()` bernilai `True`.
3.  **Eksekusi Provider**:
    - **Fetching**: Provider mengambil konten (misalnya menggunakan CamoFox untuk *stealth browsing*).
    - **Sanitasi**: Konten mentah dibersihkan dari "noise" (script, iklan, navigasi).
    - **Transformasi**: Konten diubah menjadi format yang diharapkan (biasanya Markdown atau JSON terstruktur).
4.  **Pengembalian Hasil**: Provider mengembalikan daftar *dictionary* yang berisi `url`, `title`, `content` (Markdown), `raw_content` (HTML bersih), dan `error` (jika terjadi kegagalan).

## 4. Prinsip Desain
Agar sistem ini bekerja optimal bagi pengguna seperti Anda, setiap provider harus:
- **Stateless**: Tidak menyimpan sesi antar-permintaan untuk menjaga isolasi.
- **Deterministik**: Input yang sama harus menghasilkan output yang konsisten.
- **Robust**: Harus memiliki penanganan *error* (gagal di satu URL tidak boleh menggagalkan seluruh proses).

---
*Dokumen ini merupakan ringkasan dasar sebagai referensi penelitian untuk pembangunan proyek Prebextor.*
