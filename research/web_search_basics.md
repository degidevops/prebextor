# Cara Kerja web_search di Hermes Agent

Hermes Agent menggunakan arsitektur modular untuk `web_search`, yang dirancang untuk menjadi fleksibel dan dapat dikonfigurasi melalui plugin.

### Alur Kerja Utama:

1.  **Input Query:** Agen menerima prompt pengguna yang memicu kebutuhan akan informasi eksternal.
2.  **Orkestrasi:** Hermes memeriksa konfigurasi `web.search_backend` untuk menentukan penyedia (provider) mana yang aktif.
3.  **Delegasi ke Provider:** Query diteruskan ke *Search Provider* yang terdaftar (misal: SearXNG, Google, atau provider khusus lainnya).
4.  **Eksekusi Pencarian:** Provider menjalankan query ke mesin pencari target, menangani otentikasi (jika ada), dan format query (seperti penggunaan operator `site:`, `intitle:`, dll).
5.  **Normalisasi Hasil:** Apapun format asli dari mesin pencari, hasil pencarian dikonversi oleh provider ke format data internal Hermes yang seragam, biasanya berupa list dari objek (dictionary) yang berisi:
    *   `url`: URL sumber.
    *   `title`: Judul halaman.
    *   `description`: Cuplikan (snippet) informasi.
6.  **Injeksi Konteks:** Hasil yang sudah dinormalisasi dikembalikan ke *context window* LLM agar dapat digunakan untuk proses penalaran (reasoning) lebih lanjut.

### Karakteristik Utama:
- **Modular:** Mudah mengganti backend pencarian tanpa mengubah kode agen.
- **Provider-Agnostic:** Hermes tidak peduli mesin pencari apa yang digunakan, selama provider mengikuti kontrak internal.
- **Berbasis Konteks:** Hasil pencarian dioptimalkan agar relevan dan ringkas untuk dikonsumsi oleh LLM.
