import os
import sys
import threading
import urllib.request
import tkinter as tk
from pathlib import Path
import subprocess

# Simge URL'si
ICON_URL = "https://github.com/scpstudioofficaltr-spec/load-system-by-crgame/raw/refs/heads/main/icoimg"
ICON_NAME = "icoimg.ico"

# Yeni Uygulama Bağlantısı
APP_URL = "https://github.com/scpstudioofficaltr-spec/game-star/raw/refs/heads/main/main-app"
APP_NAME = "main-app.py"  # Uzantısız olduğu için .py olarak kaydediyoruz

# Siyah / Gri Tema Renkleri
BG_DARK  = "#1e1e1e"
BG_GRAY  = "#2d2d2d"
FG_WHITE = "#ffffff"
FG_MUTED = "#aaaaaa"
ACCENT   = "#4CAF50"
EXIT_BG  = "#e74c3c"
ERROR    = "#e74c3c"

class GameStarApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Game Star")
        
        # Pencereyi başlangıçta gizle
        self.root.withdraw()
        
        # Tam ekran ayarları
        self.is_fullscreen = True
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg=BG_DARK)
        
        # Klavye kısayolları (F11: Tam ekran, ESC: Çıkış)
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        
        # Dosya yolları
        self.base_dir = Path(__file__).parent
        self.icon_path = self.base_dir / ICON_NAME
        self.app_path = self.base_dir / APP_NAME

        # Çıkış Butonu
        self.exit_btn = tk.Button(self.root, text="✖", command=self.root.destroy,
                                  bg=EXIT_BG, fg="white", activebackground="#c0392b", activeforeground="white",
                                  relief="flat", bd=0, font=("Segoe UI", 12, "bold"), cursor="hand2",
                                  width=3)
        self.exit_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        # Ana çerçeve
        self.container = tk.Frame(root, bg=BG_DARK)
        self.container.pack(fill="both", expand=True)

        self.show_loading_screen()
        threading.Thread(target=self.startup_process, daemon=True).start()

    def toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes("-fullscreen", self.is_fullscreen)
        return "break"

    # ---------- 1. AŞAMA: LOADING EKRANI ----------
    def show_loading_screen(self):
        for w in self.container.winfo_children():
            w.pack_forget()

        self.loading_frame = tk.Frame(self.container, bg=BG_DARK)
        self.loading_frame.pack(fill="both", expand=True)

        tk.Label(self.loading_frame, text="Sistem Başlatılıyor...", 
                 bg=BG_DARK, fg=FG_MUTED, font=("Segoe UI", 12)).pack(pady=(150, 10))
        
        self.loading_label = tk.Label(self.loading_frame, text="Simge kontrol ediliyor...", 
                                      bg=BG_DARK, fg=FG_WHITE, font=("Segoe UI", 14, "bold"), justify="center")
        self.loading_label.pack()

    def update_loading_text(self, text, color=FG_WHITE):
        self.root.after(0, lambda: self.loading_label.config(text=text, fg=color))

    # ---------- BAŞLANGIÇ İŞLEMLERİ ----------
    def startup_process(self):
        # 1. Simge Kontrolü
        if not self.icon_path.exists() or self.icon_path.stat().st_size == 0:
            self.update_loading_text("Simge indiriliyor...")
            try:
                self.download_file(ICON_URL, self.icon_path)
            except Exception as e:
                self.update_loading_text(f"Simge Hatası:\n{e}", ERROR)
                self.root.after(3000, self.root.destroy)
                return

        self.root.after(0, lambda: self.root.iconbitmap(str(self.icon_path)))
        
        # 2. Uygulama (main-app) Kontrolü ve İndirilmesi
        self.update_loading_text("Uygulama bağlantısı kuruluyor...")
        try:
            # Dosyayı her zaman güncel çekmek için indiriyoruz
            self.download_file(APP_URL, self.app_path)
            if not self.app_path.exists() or self.app_path.stat().st_size < 100:
                raise Exception("İndirilen uygulama dosyası geçersiz veya boş.")
        except Exception as e:
            self.update_loading_text(f"Bağlantı Hatası:\n{e}", ERROR)
            return

        self.update_loading_text("Uygulama başlatılıyor...")
        self.root.after(1000, self.launch_main_app)

    def download_file(self, url, path):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp, open(path, "wb") as f:
            f.write(resp.read())

    # ---------- 2. AŞAMA: UYGULAMAYI ÇALIŞTIR ----------
    def launch_main_app(self):
        try:
            # Pythonw kullanarak konsol açılmasını engelle
            python_exe = sys.executable.replace("python.exe", "pythonw.exe")
            if not os.path.exists(python_exe):
                python_exe = sys.executable
            
            # Yeni uygulamayı arka planda çalıştır
            subprocess.Popen([python_exe, str(self.app_path)], cwd=str(self.base_dir))
            
            # Kendi penceresini (launcher'ı) kapat
            self.root.destroy()
            
        except Exception as e:
            self.update_loading_text(f"Çalıştırma Hatası:\n{e}", ERROR)

if __name__ == "__main__":
    root = tk.Tk()
    app = GameStarApp(root)
    root.mainloop()
