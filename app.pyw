import os
import sys
import threading
import urllib.request
import tkinter as tk
from pathlib import Path

# Simge URL'si (Eğer klasörde yoksa buradan çekilecek)
ICON_URL = "https://github.com/scpstudioofficaltr-spec/load-system-by-crgame/raw/refs/heads/main/icoimg"
ICON_NAME = "icoimg.ico"

# Siyah / Gri Tema Renkleri
BG_DARK  = "#1e1e1e"
BG_GRAY  = "#2d2d2d"
FG_WHITE = "#ffffff"
FG_MUTED = "#aaaaaa"
ACCENT   = "#4CAF50"
EXIT_BG  = "#e74c3c"

class GameStarApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Game Star")
        
        # Pencereyi başlangıçta gizle (Küçük açılma efektini engellemek için)
        self.root.withdraw()
        
        # Tam ekran ayarları
        self.is_fullscreen = True
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg=BG_DARK)
        
        # Tam ekranın en önde açılmasını sağla
        self.root.attributes("-topmost", True)
        self.root.after(100, lambda: self.root.attributes("-topmost", False)) # Bir süre sonra özelliği kaldır
        
        # Klavye kısayolları (F11: Tam ekran, ESC: Çıkış)
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        
        # Dosya yolları
        self.base_dir = Path(__file__).parent
        self.icon_path = self.base_dir / ICON_NAME

        # Çıkış Butonu (Sağ Üst Köşe)
        self.exit_btn = tk.Button(self.root, text="✖", command=self.root.destroy,
                                  bg=EXIT_BG, fg="white", activebackground="#c0392b", activeforeground="white",
                                  relief="flat", bd=0, font=("Segoe UI", 12, "bold"), cursor="hand2",
                                  width=3)
        self.exit_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        # Ana çerçeve
        self.container = tk.Frame(root, bg=BG_DARK)
        self.container.pack(fill="both", expand=True)

        # İlk açılışta Loading Ekranını göster
        self.show_loading_screen()
        
        # Simge kontrolünü arka planda başlat
        threading.Thread(target=self.check_and_download_icon, daemon=True).start()

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
                                      bg=BG_DARK, fg=FG_WHITE, font=("Segoe UI", 14, "bold"))
        self.loading_label.pack()

    def update_loading_text(self, text):
        self.root.after(0, lambda: self.loading_label.config(text=text))

    # ---------- SİMGE KONTROLÜ VE İNDİRME ----------
    def check_and_download_icon(self):
        if not self.icon_path.exists() or self.icon_path.stat().st_size == 0:
            self.update_loading_text("Simge bulunamadı, indiriliyor...")
            try:
                req = urllib.request.Request(ICON_URL, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp, open(self.icon_path, "wb") as f:
                    f.write(resp.read())
                
                if not self.icon_path.exists() or self.icon_path.stat().st_size == 0:
                    raise Exception("İndirilen simge dosyası geçersiz.")
                
                self.update_loading_text("Simge başarıyla indirildi.")
            except Exception as e:
                self.update_loading_text(f"Hata: Simge indirilemedi.\n{e}")
                self.root.after(3000, self.root.destroy)
                return
        else:
            self.update_loading_text("Simge hazır.")
        
        self.root.after(0, self.apply_icon)

    def apply_icon(self):
        try:
            self.root.iconbitmap(str(self.icon_path))
        except Exception:
            pass 
        
        # Kısa bir bekleme sonrası ana ekrana geç
        self.root.after(1000, self.show_main_screen)

    # ---------- 2. AŞAMA: ANA EKRAN ----------
    def show_main_screen(self):
        for w in self.container.winfo_children():
            w.pack_forget()

        main_frame = tk.Frame(self.container, bg=BG_DARK)
        main_frame.pack(fill="both", expand=True)

        card = tk.Frame(main_frame, bg=BG_GRAY, bd=0)
        card.place(relx=0.5, rely=0.5, anchor="center", width=400, height=200)

        self.anim_label = tk.Label(card, text="⠋", bg=BG_GRAY, fg=ACCENT, 
                                   font=("Segoe UI", 28, "bold"))
        self.anim_label.pack(pady=(40, 10))

        self.main_status = tk.Label(card, text="Bağlantı kuruluyor...", 
                                    bg=BG_GRAY, fg=FG_WHITE, font=("Segoe UI", 12))
        self.main_status.pack()

        self.animate_loading(0)
        self.root.after(3000, self.show_to_be_continued)
        
        # Pencereyi şimdi göster (böylece tam ekran ayarları çoktan yapılmış olur)
        self.root.deiconify()

    def animate_loading(self, index):
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        if hasattr(self, 'anim_label') and self.anim_label.winfo_exists():
            self.anim_label.config(text=frames[index % len(frames)])
            self.root.after(100, self.animate_loading, index + 1)

    def show_to_be_continued(self):
        if hasattr(self, 'main_status') and self.main_status.winfo_exists():
            self.anim_label.config(text="🍿")
            self.main_status.config(text="To be continued...", fg=ACCENT, font=("Segoe UI", 14, "bold"))


if __name__ == "__main__":
    root = tk.Tk()
    app = GameStarApp(root)
    root.mainloop()
