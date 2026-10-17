# 🤖 Panduan Penggunaan JARVIS untuk Pemula (How-To-Use)

Selamat datang di **JARVIS**! Panduan ini dirancang khusus bagi pengguna baru untuk memahami cara menjalankan, mengoperasikan, dan memaksimalkan seluruh kemampuan JARVIS di laptop/PC Windows 11 Anda.

---

## 🌟 1. Apa itu JARVIS?

JARVIS bukan sekadar *chatbot* biasa yang hanya bisa membalas teks. JARVIS adalah **Asisten AI Komputer Mandiri & Proaktif (Modern Hacker Terminal HUD v2.5)** yang:
- **Cepat & Proaktif ala Omi Desktop**: Berjalan senyap di System Tray dengan waktu respon kilat sub-detik (< 300ms via mode Turbo) dan siap dipanggil seketika via **Win + Alt + J**.
- **Mode Dual-Engine Fleksibel**:
  - `⚡ TURBO (Groq Free Cloud)`: Respon instan tanpa membebani RAM/CPU laptop, tidak memerlukan Ollama saat terhubung internet.
  - `🔒 OFFLINE (Ollama Lokal)`: 100% lokal dan privat di komputer tanpa internet via model `qwen3:8b`.
  - *(Dapat diubah dengan 1-klik pada header aplikasi!)*
- **One-Click Workspace Janitor**: Mampu memindai dan merapikan folder **Downloads** dan **Desktop** yang berantakan ke subfolder teratur dalam 1 klik.
- **Todo & Scratchpad Cerdas**: Mencatat tugas dan deadline dari obrolan atau teks secara otomatis (*"catat todo: bayar listrik"*).
- **Proactive Awareness (Ambient Health)**: Mengingatkan istirahat mata & peregangan setelah 45 menit fokus, serta mendeteksi penumpukan file sampah.
- **Dapat Mengontrol Komputer Nyata**: Membuka aplikasi, memutar musik, mencari file, mengeklik elemen layar, mengunci Windows, dan mengambil tangkapan layar.

---

## 🚀 2. Cara Menjalankan (Sangat Mudah — 1 Klik!)

Anda **tidak perlu** mengetik perintah rumit di terminal setiap kali ingin menggunakan JARVIS:

### Opsi 1: Klik Ganda `run_gui.bat` (Rekomendasi Utama)
Cukup klik ganda file **`run_gui.bat`** di folder JARVIS.
- Jendela **Modern Hacker Terminal HUD** akan langsung muncul di tengah layar.
- Ikon JARVIS akan aktif di **System Tray** (dekat jam Windows di kanan bawah).
- Saat ditutup (klik tombol silang), JARVIS **tetap siaga di latar belakang**. Tekan **`Win + Alt + J`** kapan saja untuk memunculkannya kembali!

### Opsi 2: Dari Terminal / Developer Mode
Jika Anda ingin melihat log debug lengkap di terminal:
```powershell
.\.venv\Scripts\Activate.ps1
python -m app.main
```

---

## 🕹️ 3. Empat Tab Produktivitas Utama

JARVIS Terminal HUD dilengkapi dengan 4 panel kerja khusus:

1. **`>_ CONSOLE`**:
   - Terminal interaktif dengan prompt `JARVIS ❯ _`.
   - Streaming jawaban AI super cepat, riwayat perintah dengan tombol panah **ATAS / BAWAH**, tombol chip cepat, dan tombol mikrofon *Push-to-Talk*.
2. **`📝 TODO & NOTES`**:
   - Tempat mencatat daftar tugas dan pengingat harian.
   - Ketik tugas di kolom atas atau katakan *"Jarvis, catat todo: kirim laporan besok jam 3"*.
   - Centang kotak untuk menandai selesai atau hapus tugas dengan satu klik.
3. **`🧹 JANITOR`**:
   - Pembersih folder **Downloads** atau **Desktop**.
   - Klik **Scan Folder** untuk melihat rincian file yang tercecer (Dokumen, Gambar, Installer, Arsip, dll).
   - Klik **✨ RAPIKAN SEKARANG** untuk memindahkan file ke subfoldernya masing-masing secara aman tanpa ada file yang terhapus.
4. **`⚡ PROACTIVE STREAM`**:
   - Feed pemantau ritme kerja Anda ala Omi Desktop.
   - Menghitung durasi fokus sesi aktif dan memberi peringatan istirahat jika sudah > 45 menit.
   - Memberi tahu jika folder Downloads sudah menumpuk lebih dari 20 file tercecer.

---

## 🎙️ 4. Cara Berinteraksi & Kontrol Suara

1. **Shortcut Menampilkan / Menyembunyikan HUD (`Win + Alt + J` atau `Ctrl + Shift + J`)**:
   - Tekan kombinasi tombol ini dari aplikasi apa pun untuk instan menampilkan/menyembunyikan Terminal JARVIS.
2. **Shortcut Menyuruh JARVIS Berhenti Bicara (`Esc`)**:
   - Tekan tombol **`Esc`** kapan saja saat JARVIS sedang berbicara atau mengetik untuk menghentikannya seketika.
   - Atau klik tombol merah **`[⏹️ STOP (Esc)]`** yang muncul di samping input bar.
   - Bisa juga ketik atau ucapkan: *"diam"*, *"stop bicara"*, *"berhenti ngomong"*, *"cukup"*.
3. **Mengetik di Prompt Console (`JARVIS ❯`)**:
   - Ketik pertanyaan atau perintah, lalu tekan **ENTER**.
4. **Tombol Mikrofon (Push-to-Talk)**:
   - Klik ikon **🎙️** di sebelah kanan input bar. Status akan berubah menjadi merah (🔴 merekam). Bicaralah dengan santai, lalu klik sekali lagi untuk selesai.
5. **Panggilan Kata Kunci (*Wake Word* "Hey Jarvis")**:
   - Jika tombol `[🎙️ WAKE: ON]` aktif di header, cukup panggil *"Hey Jarvis"* dari mana saja, dan JARVIS akan merespons seketika.

---

## 🛠️ 5. Katalog Kemampuan & Contoh Perintah

JARVIS memahami bahasa Indonesia kasual, formal, maupun bahasa Inggris:

### A. Kontrol Aplikasi & Komputer (Cepat < 1 Detik)
JARVIS langsung mengeksekusi perintah ini tanpa jeda:
- *"Buka Chrome"*
- *"Buka VS Code"*
- *"Buka Spotify"*
- *"Buka Notepad"*
- *"Tutup Notepad"*
- *"Ambil screenshot"* (Tangkapan layar otomatis tersimpan di folder Screenshots)
- *"Kunci komputer"* (Mengunci layar Windows secara aman)
- *"Cek baterai"* (Menampilkan persentase daya dan status charger)
- *"Cek info sistem"* atau *"Cek spesifikasi"* (Menampilkan spesifikasi prosesor, RAM terpakai, dan sisa SSD instan)

### B. Musik, Video & Suara (Bebas Judul Negatif)
- *"Putar lagu Lofi"*
- *"Play lagu jangan pergi"* (Kata 'jangan' pada judul lagu tidak akan membatalkan pemutaran)
- *"Jeda musik"* atau *"Pause lagu"*
- *"Lanjutkan musik"* atau *"Play lagi"*
- *"Naikkan volume"* atau *"Kecilkan suara 20%"*
- *"Mute volume"*

### C. Todo Cerdas & Pengingat Waktu Otomatis
- *"Catat todo: jam 14.20 beli makanan"*
  - JARVIS otomatis mencatat tugas sebagai **'beli makanan'** dengan waktu **14:20**.
  - Saat jam 14:20 tiba, JARVIS secara proaktif mengingatkan Anda melalui suara dan notifikasi!
- *"Tambah tugas: selesaikan laporan besok pagi"*

### D. Pencarian Web & Konteks Multi-Turn
- *"search band naif di google"* -> membuka tab browser Google dengan kata kunci bersih 'band naif'.
- *"search band naif"* -> menampilkan ringkasan berita serta daftar sumber artikel (1, 2, 3).
- *"buka sumber 1"* -> membuka tautan sumber ke-1 di browser.
- *"sumber 2"* -> melanjutkan membuka sumber ke-2 secara cerdas tanpa kehilangan konteks.

### C. Workspace Janitor (Pembersih File Otomatis)
Merapikan file yang menumpuk di folder unduhan atau desktop dalam hitungan detik:
- *"Rapikan folder Downloads"* ➔ Otomatis mengelompokkan file lepas ke subfolder Documents, Images, Installers, Archives, Media, Code.
- *"Rapikan desktop"* ➔ Merapikan ikon file yang tercecer di layar desktop.

### D. Todo & Scratchpad Cerdas
Mencatat tugas dan deadline tanpa membuka aplikasi to-do list terpisah:
- *"Catat todo: kirim email revisi jam 3 sore"*
- *"Tolong catat tugas: selesaikan laporan akhir"*
- *"Todo beli susu dan kopi"*
- *(Tugas langsung muncul di tab `📝 TODO & NOTES` dan tersimpan permanen)*

### E. Manajemen File & Folder Dasar
- *"Buka folder Downloads"*
- *"Buka folder Dokumen"*
- *"Buat folder bernama Tugas Akhir di Desktop"*

### D. Memori & Profil Pribadi (Pengingat Permanen)
JARVIS memiliki memori SQLite lokal. Anda bisa mengajarinya fakta-fakta tentang Anda:
- *"Ingat bahwa nama saya Alex."*
- *"Ingat bahwa browser favorit saya adalah Google Chrome."*
- *"Ingat bahwa saya seorang software engineer yang menyukai kopi hitam."*
- *"Siapa nama saya?"* ➔ JARVIS: *"Nama Anda adalah Alex, sir."*
- *"Apa saja yang kamu ingat tentang aku?"* ➔ Menampilkan daftar memori yang tersimpan.
- *"Lupakan catatan tentang browser favorit."*

### E. Membaca Layar & Diagnostik Error (Screen Intelligence)
Ketika Anda bingung dengan tampilan di layar atau mendapati pesan error:
- *"Baca layar"* ➔ JARVIS membaca teks dan tombol-tombol yang sedang tampil di layar Anda.
- *"Layarku kok error gini ya"* ➔ JARVIS otomatis menganalisis jendela aktif untuk mencari kode error atau kotak dialog kegagalan dan memberikan solusi.
- *"Klik tombol Simpan di layar"* ➔ JARVIS mencari tombol "Simpan" via OCR dan mengarahkan kursor mouse untuk mengekliknya secara otomatis.

### F. Open Interpreter (Kekuatan Python & PowerShell Dinamis)
Jika Anda meminta tugas perhitungan, analisa data, atau otomasi Windows yang tidak ada di tool bawaan, JARVIS akan **menulis dan menjalankan kode script sendiri secara otomatis**:
- *"Hitung akar kuadrat dari 144 dikalikan 25."* (Dijalankan via Python)
- *"Cek daftar 5 proses yang memakan CPU tertinggi saat ini."* (Dijalankan via PowerShell)
- *"Buatkan file teks di desktop berisi jadwal belajar mingguan."*
- **Fitur Self-Healing**: Jika kode yang dijalankan mengalami kendala/error, JARVIS akan membaca pesan error tersebut dan otomatis memperbaiki kodenya pada langkah berikutnya tanpa menyuruh Anda mengulang perintah!

### G. Inisiatif Mandiri (Proactive Agent)
Anda tidak perlu selalu memerintah. Di latar belakang, JARVIS peka terhadap kondisi:
- **Sapaan Awal**: Saat aplikasi dinyalakan, JARVIS dapat menyapa ramah sesuai nama di memori Anda.
- **Pengingat Istirahat**: Jika Anda bekerja di editor kode atau aplikasi kerja dalam waktu lama tanpa jeda, JARVIS dapat menyarankan istirahat singkat secara halus.
- **Deteksi Kendala**: Jika muncul jendela crash/error di layar, JARVIS akan berinisiatif menawarkan bantuan.
- *(Catatan: JARVIS tidak akan pernah memotong pembicaraan saat Anda sedang berbicara).*

---

## 🛡️ 5. Sistem Keamanan & Konfirmasi Pengguna

Keamanan data komputer Anda adalah prioritas utama:
1. **Tidak Ada Perintah Destruktif Liar**: JARVIS tidak mengizinkan eksekusi bebas tanpa filter.
2. **Proteksi Kode Berbahaya (Safety Guard)**: Kode yang mencoba menghapus folder secara rekursif (`shutil.rmtree`, `Remove-Item -Recurse`), memformat drive (`Format-Volume`), memodifikasi file `System32`, atau mematikan paksa Windows (`shutdown`) akan **DIBLOKIR OTOMATIS**.
3. **Konfirmasi Eksplisit**: Jika suatu tindakan berisiko (misalnya menghapus file permanen), JARVIS akan meminta konfirmasi terlebih dahulu kepada Anda sebelum melanjutkannya.

---

## 💡 6. Tips & Trik untuk Hasil Terbaik

1. **Gunakan Bahasa yang Alami**:
   Tidak perlu memakai format perintah kaku. Bicaralah seperti kepada asisten pribadi manusia:
   - *"Tolong dong bukain youtube terus cari video tutorial python."*
2. **Perintah Bersambung**:
   JARVIS mendukung instruksi multi-langkah:
   - *"Buka Chrome lalu putar musik jazz santai."*
3. **Mengatur Suara (TTS) & Menghentikan Ucapan (Emergency Stop)**:
   - Tekan tombol **`Esc`** kapan saja di keyboard untuk langsung memotong/menghentikan suara JARVIS secara instan tanpa menutup aplikasi.
   - Ketik `/stop` atau gunakan perintah *"diam"* / *"berhenti bicara"* untuk menghentikan pembacaan suara.
   - Klik ikon speaker di jendela utama atau ketik `/tts` untuk beralih mode senyap.
4. **Cheatsheet HUD Lengkap (`/cheat`)**:
   - Ketik **`/cheat`** (atau klik tombol pill **`📜 /cheat`** di bawah kolom prompt) untuk menampilkan lembar sontekan perintah interaktif lengkap (Web, Media, Todo, Windows, Screen Vision, dll).
   - Perintah `/cheat` ditampilkan secara **100% senyap tanpa suara (silent mode)** agar Anda leluasa membaca tanpa terdistraksi audio.
5. **Bantuan Perintah Terminal Lainnya**:
   - Ketik `/help` untuk ringkasan bantuan cepat, atau `/status` untuk memeriksa status engine (Groq Turbo / Ollama Lokal).

---

## ❓ 7. Tanya Jawab & Pemecahan Masalah (FAQ)

### Q: Muncul pesan "Ollama is offline" atau "Connection refused"
**Solusi**: Pastikan aplikasi Ollama di Windows sudah berjalan (cek ikon Ollama di taskbar kanan bawah dekat jam). Jika belum aktif, buka Start Menu dan jalankan aplikasi **Ollama**.

### Q: Mikrofon tidak merespons suara saya
**Solusi**:
1. Pastikan mikrofon laptop/headset Anda sudah terpilih sebagai *Default Input Device* di Windows Settings.
2. Pastikan izin akses mikrofon (*Microphone Privacy Settings*) di Windows 11 diaktifkan untuk aplikasi desktop.

### Q: JARVIS berbicara dengan suara bahasa Inggris padahal saya tanya bahasa Indonesia?
**Solusi**: JARVIS dirancang mendeteksi bahasa input Anda. Cukup sapa kembali dengan bahasa Indonesia (*"Halo Jarvis"*), maka ia akan otomatis beralih menggunakan suara bahasa Indonesia.

### Q: Apakah JARVIS memerlukan koneksi internet?
**Solusi**: Sebagian besar fitur inti (membuka aplikasi, kontrol desktop, suara Whisper, suara Piper TTS, ReAct reasoning, Open Interpreter, dan memori) berjalan **100% offline tanpa internet**. Internet hanya diperlukan saat Anda meminta pencarian web Google atau streaming YouTube.

---

## 📱 8. Kontrol Jarak Jauh dari Smartphone (PocketDesk Remote Integration)

Anda dapat mengontrol laptop dan berbicara langsung dengan JARVIS dari smartphone (Android / iOS) melalui browser tanpa perlu menginstall aplikasi tambahan di HP!

### Cara Menggunakan:
1. **Nyalakan Remote Server**:
   - Cukup katakan ke JARVIS di laptop: *"Jarvis, nyalakan remote"* atau ketik `nyalakan remote`.
   - JARVIS akan meluncurkan PocketDesk Remote dan memberikan alamat URL lokal (misalnya: `http://192.168.1.x:8000/remote`).
2. **Buka di Smartphone**:
   - Pastikan smartphone dan laptop terhubung ke jaringan Wi-Fi yang sama.
   - Pindai QR Code dari layar laptop atau ketik URL tersebut di Google Chrome / Safari smartphone Anda.
3. **Buka Deck JARVIS di Smartphone**:
   - Ketuk tombol **`🤖 JARVIS`** di bottom dock atau di header remote.
   - Deck asisten pintar JARVIS akan muncul seketika dengan status indikator hijau (`ONLINE`).
4. **Instruksi Suara dari HP (Push-to-Talk)**:
   - Tahan tombol mikrofon bulat cyan di HP untuk bicara (misalnya: *"Buka Chrome"*, *"Putar lagu Yellow Coldplay"*, *"Catat todo bayar tagihan"*).
   - Suara Anda direkam secara lokal dalam format PCM 16kHz WAV dan ditranskripsi oleh engine Whisper JARVIS di laptop (100% privat & offline).
5. **Memilih Output Suara (Speaker Laptop vs HP)**:
   - Tekan toggle **`[ 🔊 Laptop ]`** jika ingin suara balasan JARVIS dibacakan dari speaker laptop.
   - Tekan toggle **`[ 📱 HP ]`** jika ingin suara balasan JARVIS langsung terdengar keluar dari speaker smartphone Anda!
6. **Nyalakan JARVIS dari HP**:
   - Jika JARVIS di laptop sedang tertutup/offline, deck JARVIS di HP akan menampilkan tombol merah **`[ ⚡ Nyalakan ]`** untuk membangunkan JARVIS di laptop secara remote.

---

*Selamat bekerja lebih produktif bersama JARVIS — Asisten AI Windows Pribadi Anda!* 🚀
