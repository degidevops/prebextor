# Fitur Utama CamoFox

CamoFox adalah sistem peramban (browser) yang dirancang khusus untuk kebutuhan otomatisasi AI dengan fokus pada *stealth* dan kemampuan interaksi tingkat lanjut.

### Fitur Utama:

1.  **Anti-Detection & Fingerprinting:**
    *   Menerapkan *fingerprinting* browser yang unik untuk setiap sesi atau pengguna.
    *   Mencegah deteksi otomatis sebagai bot oleh layanan keamanan seperti Cloudflare atau Akamai.

2.  **Manajemen Sesi & Tab:**
    *   Isolasi sesi per `userId` dan `sessionKey` untuk mencegah kebocoran data antar sesi.
    *   Manajemen tab yang dinamis (buka, tutup, navigasi).

3.  **Rendering & Interaksi:**
    *   Mendukung *full JS rendering* (penting untuk aplikasi SPA seperti React/Vue).
    *   Mampu melakukan interaksi seperti `scroll`, `hover`, `click`, dan `fill_form`.
    *   Mode *headless* dan *headed* yang bisa di-toggle untuk debugging atau memecahkan CAPTCHA.

4.  **Ekstraksi Data:**
    *   `snapshot`: Mengambil *accessibility tree* untuk ekstraksi konten yang token-efficient.
    *   `evaluate_js`: Mengeksekusi JS langsung di konteks halaman untuk ekstraksi data yang sangat presisi (*surgical extraction*).
    *   `get_page_html`: Mengambil DOM yang sudah di-render secara penuh.
    *   Ekstraksi resource (gambar, dokumen, link).

5.  **Waiting Mechanics:**
    *   `wait_for`: Menunggu DOM siap, network idle, atau framework selesai melakukan *hydration*.
    *   `wait_for_selector` / `wait_for_text`: Menunggu elemen atau teks tertentu muncul di DOM.

### Keunggulan untuk Agen:
CamoFox memposisikan dirinya bukan sekadar peramban, melainkan API server yang memungkinkan agen untuk "menguasai" peramban dengan perintah yang terstruktur, deterministik, dan dapat diulang.
