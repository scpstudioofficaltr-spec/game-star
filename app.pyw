import os
import sys
import json
import math
import hashlib
import threading
import subprocess
import urllib.request
import urllib.error
import webbrowser
import secrets
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import datetime

try:
    from PIL import Image, ImageTk  # Opsiyonel: logoyu gerçek resim olarak göstermek için
    PIL_OK = True
except Exception:
    PIL_OK = False

# ======================= AYARLAR / SABİTLER =======================
APP_TITLE = "Game Star"
APP_VERSION = "2.1.0"

ICON_URL = "https://github.com/scpstudioofficaltr-spec/load-system-by-crgame/raw/refs/heads/main/icoimg"
ICON_NAME = "icoimg.ico"

APP_URL = "https://github.com/scpstudioofficaltr-spec/game-star/raw/refs/heads/main/main-app"
APP_NAME = "main-app.py"

REPO_URL = "https://github.com/scpstudioofficaltr-spec/game-star"
# !!! Vercel adresinle değiştir (sonunda / olmasın) !!!
SITE_URL = "https://sc-1-test.vercel.app"
CONFIG_NAME = "gamestar_config.json"

BG_DARK = "#1e1e1e"
BG_GRAY = "#2d2d2d"
BG_LIGHT = "#383838"
FG_WHITE = "#ffffff"
FG_MUTED = "#aaaaaa"
EXIT_BG = "#e74c3c"
ERROR = "#e74c3c"
OK_GREEN = "#4CAF50"

ACCENT_CHOICES = {
    "Yeşil": "#4CAF50",
    "Mavi": "#3498db",
    "Mor": "#9b59b6",
    "Turuncu": "#e67e22",
    "Kırmızı": "#e74c3c",
    "Turkuaz": "#1abc9c",
}

DEFAULT_CONFIG = {
    "fullscreen": True,
    "auto_update": True,
    "auto_launch": False,
    "close_after_launch": False,
    "accent": "#4CAF50",
    "games": [],
    "user": None,
    "session": None,
}


# ======================= YARDIMCI FONKSİYONLAR =======================
def download_file(url, path, progress=None, timeout=15):
    """Dosyayı .part olarak indirir, bitince yerine koyar. progress(0..1) çağrılır."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    path = Path(path)
    tmp = Path(str(path) + ".part")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(tmp, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress and total:
                    progress(min(done / total, 1.0))
    tmp.replace(path)


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def star_points(cx, cy, r_out, r_in):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        r = r_out if i % 2 == 0 else r_in
        pts += [cx + r * math.cos(ang), cy + r * math.sin(ang)]
    return pts


# ======================= ÖZEL BİLEŞENLER =======================
class ScrollFrame(tk.Frame):
    """Kaydırılabilir çerçeve. İçerik için .inner kullanın."""

    def __init__(self, parent, bg):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.vbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.win, width=e.width))
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vbar.pack(side="right", fill="y")
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def _bind_wheel(self, _e):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

    def _unbind_wheel(self, _e):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_wheel(self, e):
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")


class ProgressBar(tk.Canvas):
    def __init__(self, parent, width=420, height=10, bg=BG_GRAY, color=OK_GREEN, parent_bg=BG_DARK):
        super().__init__(parent, width=width, height=height, bg=parent_bg, highlightthickness=0)
        self.w, self.h, self.bg_c, self.color = width, height, bg, color
        self.create_rectangle(0, 0, width, height, fill=bg, outline="")
        self.bar = self.create_rectangle(0, 0, 0, height, fill=color, outline="")

    def set(self, value):
        self.coords(self.bar, 0, 0, self.w * max(0.0, min(1.0, value)), self.h)

    def set_color(self, color):
        self.itemconfig(self.bar, fill=color)


class Logo(tk.Canvas):
    """İkon dosyası varsa onu, yoksa çizilmiş yıldız logosunu gösterir."""

    def __init__(self, parent, size, bg, accent, icon_path=None):
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0)
        self._img = None
        shown = False
        if PIL_OK and icon_path and Path(icon_path).exists():
            try:
                img = Image.open(icon_path).convert("RGBA").resize((size, size))
                self._img = ImageTk.PhotoImage(img)
                self.create_image(size // 2, size // 2, image=self._img)
                shown = True
            except Exception:
                shown = False
        if not shown:
            c = size / 2
            self.create_oval(2, 2, size - 2, size - 2, fill=BG_GRAY, outline=accent, width=2)
            self.create_polygon(star_points(c, c + 1, size * 0.34, size * 0.14),
                                fill=accent, outline="")


def hover_button(parent, text, command, bg, fg=FG_WHITE, hover=None, font=("Segoe UI", 10, "bold"),
                 padx=16, pady=8):
    hover = hover or BG_LIGHT
    b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground=hover,
                  activeforeground=fg, relief="flat", bd=0, font=font, cursor="hand2",
                  padx=padx, pady=pady)
    b.bind("<Enter>", lambda e: b.config(bg=hover))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b


# ======================= GİRİŞ (GOOGLE / FIREBASE) =======================
class AuthClient:
    """Site üzerinden Google girişi. Tarayıcıyı açar, 127.0.0.1'de geri dönüşü bekler."""

    def __init__(self, site_url):
        self.site = site_url.rstrip("/")

    def _post(self, path, data, timeout=15):
        req = urllib.request.Request(
            self.site + path,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def login(self, timeout_sec=180):
        """Bloklar. Başarılıysa (user, session) döner, değilse Exception fırlatır."""
        if "YOUR-SITE" in self.site:
            raise Exception("SITE_URL ayarlanmamış. Launcher dosyasındaki SITE_URL'i Vercel adresinle değiştir.")

        state = secrets.token_urlsafe(24)
        result = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                u = urlparse(self.path)
                if u.path != "/callback":
                    self.send_response(404)
                    self.end_headers()
                    return
                q = parse_qs(u.query)
                result["code"] = (q.get("code") or [""])[0]
                result["state"] = (q.get("state") or [""])[0]
                body = (
                    "<html><head><meta charset='utf-8'><title>Game Star</title></head>"
                    "<body style='background:#1e1e1e;color:#fff;font-family:Segoe UI,sans-serif;"
                    "text-align:center;padding-top:20vh'><h2>Giriş başarılı ✔</h2>"
                    "<p style='color:#aaa'>Bu sekmeyi kapatıp Game Star'a dönebilirsin.</p></body></html>"
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        server.timeout = 1
        port = server.server_address[1]
        try:
            webbrowser.open(f"{self.site}/login?port={port}&state={state}")
            deadline = time.time() + timeout_sec
            while "code" not in result and time.time() < deadline:
                server.handle_request()
        finally:
            server.server_close()

        if "code" not in result:
            raise Exception("Giriş zaman aşımına uğradı.")
        if not secrets.compare_digest(result["state"], state):
            raise Exception("Güvenlik doğrulaması başarısız (state eşleşmedi).")

        data = self._post("/api/app-verify", {"code": result["code"], "state": state})
        if "user" not in data or "session" not in data:
            raise Exception(data.get("error", "Doğrulama başarısız"))
        return data["user"], data["session"]

    def restore(self, session):
        """Kayıtlı session geçerliyse kullanıcıyı döner, değilse None."""
        try:
            data = self._post("/api/app-me", {"session": session})
            return data.get("user")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return None
            raise


# ======================= ANA UYGULAMA =======================
class GameStarApp:
    NAV_ITEMS = [
        ("home", "🏠", "Ana Sayfa"),
        ("library", "🎮", "Kütüphane"),
        ("downloads", "⬇", "İndirmeler"),
        ("settings", "⚙", "Ayarlar"),
        ("about", "ℹ", "Hakkında"),
    ]

    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.configure(bg=BG_DARK)
        self.root.minsize(900, 600)
        self.root.withdraw()  # Hazır olana kadar gizle

        self.base_dir = Path(__file__).parent
        self.icon_path = self.base_dir / ICON_NAME
        self.app_path = self.base_dir / APP_NAME
        self.config_path = self.base_dir / CONFIG_NAME

        self.config = self.load_config()
        self.accent = self.config["accent"]
        self.is_fullscreen = self.config["fullscreen"]

        self.logs = []
        self.log_widget = None
        self.current_page = "home"
        self.nav_widgets = {}
        self.updating = False
        self.status_cards = {}
        self.auth = AuthClient(SITE_URL)
        self.login_busy = False
        self.user = self.config.get("user")

        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<Escape>", self.escape_pressed)
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)

        self.container = tk.Frame(self.root, bg=BG_DARK)
        self.container.pack(fill="both", expand=True)

        self.show_splash()
        self.root.deiconify()
        self.root.attributes("-fullscreen", self.is_fullscreen)
        threading.Thread(target=self.startup_process, daemon=True).start()

    # ---------- Config ----------
    def load_config(self):
        cfg = dict(DEFAULT_CONFIG)
        try:
            if self.config_path.exists():
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                cfg.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
        except Exception:
            pass
        return cfg

    def save_config(self):
        try:
            self.config_path.write_text(json.dumps(self.config, indent=2, ensure_ascii=False),
                                        encoding="utf-8")
        except Exception as e:
            self.log(f"Ayarlar kaydedilemedi: {e}", ERROR)

    # ---------- Log ----------
    def log(self, msg, color=None):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        self.logs.append((line, color))
        self.root.after(0, lambda: self._append_log(line, color))

    def _append_log(self, line, color):
        w = self.log_widget
        if w is None:
            return
        try:
            if not w.winfo_exists():
                return
            w.config(state="normal")
            tag = color or FG_WHITE
            w.tag_config(tag, foreground=tag)
            w.insert("end", line + "\n", tag)
            w.see("end")
            w.config(state="disabled")
        except tk.TclError:
            pass

    # ---------- Pencere kontrolleri ----------
    def toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes("-fullscreen", self.is_fullscreen)
        self.config["fullscreen"] = self.is_fullscreen
        self.save_config()
        return "break"

    def escape_pressed(self, event=None):
        if self.is_fullscreen:
            self.toggle_fullscreen()

    def quit_app(self):
        if messagebox.askyesno(APP_TITLE, "Uygulamadan çıkmak istiyor musun?"):
            self.root.destroy()

    def clear(self, widget):
        for w in widget.winfo_children():
            w.destroy()

    # ================= 1. AŞAMA: AÇILIŞ EKRANI =================
    def show_splash(self):
        self.clear(self.container)
        f = tk.Frame(self.container, bg=BG_DARK)
        f.pack(fill="both", expand=True)
        inner = tk.Frame(f, bg=BG_DARK)
        inner.place(relx=0.5, rely=0.5, anchor="center")

        self.splash_logo = Logo(inner, 120, BG_DARK, self.accent,
                                self.icon_path if self.icon_path.exists() else None)
        self.splash_logo.pack(pady=(0, 15))
        tk.Label(inner, text=APP_TITLE.upper(), bg=BG_DARK, fg=FG_WHITE,
                 font=("Segoe UI", 28, "bold")).pack()
        tk.Label(inner, text="Sistem Başlatılıyor...", bg=BG_DARK, fg=FG_MUTED,
                 font=("Segoe UI", 11)).pack(pady=(4, 20))
        self.splash_label = tk.Label(inner, text="Hazırlanıyor...", bg=BG_DARK, fg=FG_WHITE,
                                     font=("Segoe UI", 12, "bold"), justify="center")
        self.splash_label.pack(pady=(0, 10))
        self.splash_bar = ProgressBar(inner, color=self.accent)
        self.splash_bar.pack()

    def splash_update(self, text=None, progress=None, color=FG_WHITE):
        def _do():
            try:
                if text is not None:
                    self.splash_label.config(text=text, fg=color)
                if progress is not None:
                    self.splash_bar.set(progress)
                if color == ERROR:
                    self.splash_bar.set_color(ERROR)
            except tk.TclError:
                pass
        self.root.after(0, _do)

    def startup_process(self):
        # 1) Simge
        self.splash_update("Simge kontrol ediliyor...", 0.05)
        if not self.icon_path.exists() or self.icon_path.stat().st_size == 0:
            self.splash_update("Simge indiriliyor...", 0.10)
            try:
                download_file(ICON_URL, self.icon_path,
                              lambda p: self.splash_update(progress=0.10 + p * 0.20))
                self.log("Simge indirildi.", OK_GREEN)
            except Exception as e:
                self.log(f"Simge indirilemedi: {e}", ERROR)
                self.splash_update(f"Simge hatası (devam ediliyor):\n{e}", 0.30, ERROR)
        self.splash_update(progress=0.30)
        self.root.after(0, self.apply_window_icon)

        # 2) main-app
        if self.config["auto_update"]:
            self.splash_update("Uygulama güncelleniyor...", 0.35)
            try:
                self.sync_main_app(lambda p: self.splash_update(progress=0.35 + p * 0.55))
            except Exception as e:
                if self.app_path.exists():
                    self.log(f"Güncelleme başarısız, yerel sürüm kullanılacak: {e}", ERROR)
                else:
                    self.splash_update(f"Bağlantı Hatası:\n{e}", 0.9, ERROR)
                    self.log(f"main-app indirilemedi: {e}", ERROR)
        else:
            self.log("Otomatik güncelleme kapalı.")

        # 3) Kayıtlı oturum
        if self.config.get("session"):
            self.splash_update("Oturum kontrol ediliyor...", 0.95)
            try:
                user = self.auth.restore(self.config["session"])
                if user:
                    self.user = user
                    self.config["user"] = user
                    self.log(f"Oturum açık: {user.get('name') or user.get('email')}", OK_GREEN)
                else:
                    self.user = None
                    self.config["user"] = None
                    self.config["session"] = None
                    self.log("Oturum süresi dolmuş, tekrar giriş yap.")
                self.save_config()
            except Exception as e:
                self.log(f"Oturum doğrulanamadı (çevrimdışı olabilir): {e}", ERROR)

        self.splash_update("Arayüz hazırlanıyor...", 1.0)
        self.root.after(600, self.finish_startup)

    def apply_window_icon(self):
        try:
            self.root.iconbitmap(str(self.icon_path))
        except Exception:
            pass

    def finish_startup(self):
        self.build_main_ui()
        if self.config["auto_launch"] and self.app_path.exists():
            self.root.after(800, self.launch_main_app)

    # ================= main-app yönetimi =================
    def sync_main_app(self, progress=None):
        """main-app'i indirir; içerik değiştiyse günceller. True dönerse yeni sürüm vardı."""
        tmp_target = self.base_dir / (APP_NAME + ".new")
        download_file(APP_URL, tmp_target, progress)
        if tmp_target.stat().st_size < 100:
            tmp_target.unlink(missing_ok=True)
            raise Exception("İndirilen uygulama dosyası geçersiz veya boş.")
        changed = True
        if self.app_path.exists():
            changed = file_hash(tmp_target) != file_hash(self.app_path)
        if changed:
            tmp_target.replace(self.app_path)
            self.log("main-app güncellendi.", OK_GREEN)
        else:
            tmp_target.unlink(missing_ok=True)
            self.log("main-app zaten güncel.")
        return changed

    def launch_main_app(self):
        if not self.app_path.exists():
            messagebox.showwarning(APP_TITLE, "main-app bulunamadı. Önce İndirmeler sayfasından indir.")
            return
        try:
            python_exe = sys.executable
            if os.name == "nt":
                pw = python_exe.replace("python.exe", "pythonw.exe")
                if os.path.exists(pw):
                    python_exe = pw
            subprocess.Popen([python_exe, str(self.app_path)], cwd=str(self.base_dir))
            self.log("main-app başlatıldı.", OK_GREEN)
            if self.config["close_after_launch"]:
                self.root.destroy()
        except Exception as e:
            self.log(f"Çalıştırma hatası: {e}", ERROR)
            messagebox.showerror(APP_TITLE, f"Çalıştırma hatası:\n{e}")

    # ================= 2. AŞAMA: ANA ARAYÜZ =================
    def build_main_ui(self, page=None):
        self.clear(self.container)
        self.log_widget = None
        self.nav_widgets = {}

        # Sol menü
        self.sidebar = tk.Frame(self.container, bg=BG_GRAY, width=250)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Sağ taraf
        self.right = tk.Frame(self.container, bg=BG_DARK)
        self.right.pack(side="left", fill="both", expand=True)

        self.build_sidebar()
        self.build_header()
        self.content = tk.Frame(self.right, bg=BG_DARK)
        self.content.pack(fill="both", expand=True, padx=30, pady=(10, 25))

        self.show_page(page or self.current_page)
        self.tick_clock()

    def build_sidebar(self):
        top = tk.Frame(self.sidebar, bg=BG_GRAY)
        top.pack(fill="x", pady=(30, 25))
        Logo(top, 84, BG_GRAY, self.accent,
             self.icon_path if self.icon_path.exists() else None).pack()
        tk.Label(top, text=APP_TITLE.upper(), bg=BG_GRAY, fg=FG_WHITE,
                 font=("Segoe UI", 18, "bold")).pack(pady=(10, 0))
        tk.Label(top, text=f"v{APP_VERSION}", bg=BG_GRAY, fg=FG_MUTED,
                 font=("Segoe UI", 9)).pack()

        tk.Frame(self.sidebar, bg=BG_LIGHT, height=1).pack(fill="x", padx=20, pady=(0, 15))

        for key, icon, label in self.NAV_ITEMS:
            self.make_nav_item(key, icon, label)

        # Alt kısım
        bottom = tk.Frame(self.sidebar, bg=BG_GRAY)
        bottom.pack(side="bottom", fill="x", pady=20, padx=20)
        self.build_user_panel(bottom)
        hover_button(bottom, "▶  Uygulamayı Başlat", self.launch_main_app,
                     self.accent, hover=self.accent, pady=10).pack(fill="x", pady=(0, 8))
        hover_button(bottom, "✖  Çıkış", self.quit_app, EXIT_BG, hover="#c0392b",
                     pady=10).pack(fill="x")

    # ---------- Kullanıcı paneli / giriş ----------
    def welcome_text(self):
        if self.user:
            name = (self.user.get("name") or self.user.get("email") or "").split(" ")[0]
            return f"Hoş geldin, {name}! 👋"
        return "Hoş geldin! 👋"

    def build_user_panel(self, parent):
        panel = tk.Frame(parent, bg=BG_DARK, padx=12, pady=10)
        panel.pack(fill="x", pady=(0, 10))
        if self.user:
            name = self.user.get("name") or "Kullanıcı"
            email = self.user.get("email") or ""
            row = tk.Frame(panel, bg=BG_DARK)
            row.pack(fill="x")
            av = tk.Canvas(row, width=38, height=38, bg=BG_DARK, highlightthickness=0)
            av.create_oval(1, 1, 37, 37, fill=self.accent, outline="")
            av.create_text(19, 19, text=name[:1].upper(), fill="white", font=("Segoe UI", 14, "bold"))
            av.pack(side="left", padx=(0, 10))
            info = tk.Frame(row, bg=BG_DARK)
            info.pack(side="left", fill="x", expand=True)
            tk.Label(info, text=name[:22], bg=BG_DARK, fg=FG_WHITE, font=("Segoe UI", 10, "bold"),
                     anchor="w").pack(fill="x")
            tk.Label(info, text=email[:26], bg=BG_DARK, fg=FG_MUTED, font=("Segoe UI", 8),
                     anchor="w").pack(fill="x")
            hover_button(panel, "Oturumu Kapat", self.logout, BG_GRAY, font=("Segoe UI", 9),
                         pady=4).pack(fill="x", pady=(8, 0))
        else:
            tk.Label(panel, text="Giriş yapılmadı", bg=BG_DARK, fg=FG_MUTED,
                     font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))
            self.login_btn = hover_button(panel, "Giriş Yap (Google / GitHub)", self.login_clicked,
                                          FG_WHITE, fg="#222222", hover="#e8e8e8", pady=8)
            self.login_btn.pack(fill="x")

    def login_clicked(self):
        if self.login_busy:
            return
        self.login_busy = True
        try:
            self.login_btn.config(text="Tarayıcıda giriş yap...", state="disabled")
        except Exception:
            pass
        self.log("Giriş başlatıldı, tarayıcı açılıyor...")

        def work():
            try:
                user, session = self.auth.login()
                self.root.after(0, lambda: self.login_ok(user, session))
            except Exception as e:
                self.root.after(0, lambda: self.login_fail(e))

        threading.Thread(target=work, daemon=True).start()

    def login_ok(self, user, session):
        self.login_busy = False
        self.user = user
        self.config["user"] = user
        self.config["session"] = session
        self.save_config()
        self.log(f"Giriş yapıldı: {user.get('name') or user.get('email')}", OK_GREEN)
        self.root.deiconify()
        self.root.lift()
        self.build_main_ui(self.current_page)

    def login_fail(self, err):
        self.login_busy = False
        self.log(f"Giriş başarısız: {err}", ERROR)
        self.build_main_ui(self.current_page)
        messagebox.showerror(APP_TITLE, f"Giriş başarısız:\n{err}")

    def logout(self):
        if messagebox.askyesno(APP_TITLE, "Oturumu kapatmak istiyor musun?"):
            self.user = None
            self.config["user"] = None
            self.config["session"] = None
            self.save_config()
            self.log("Oturum kapatıldı.")
            self.build_main_ui(self.current_page)

    def make_nav_item(self, key, icon, label):
        row = tk.Frame(self.sidebar, bg=BG_GRAY, cursor="hand2")
        row.pack(fill="x", pady=2)
        bar = tk.Frame(row, bg=BG_GRAY, width=4)
        bar.pack(side="left", fill="y")
        lbl = tk.Label(row, text=f"  {icon}   {label}", bg=BG_GRAY, fg=FG_MUTED,
                       font=("Segoe UI", 12), anchor="w", padx=14, pady=11, cursor="hand2")
        lbl.pack(side="left", fill="x", expand=True)
        self.nav_widgets[key] = (row, bar, lbl)

        def enter(_e):
            if self.current_page != key:
                for w in (row, lbl):
                    w.config(bg=BG_LIGHT)

        def leave(_e):
            if self.current_page != key:
                for w in (row, lbl):
                    w.config(bg=BG_GRAY)

        for w in (row, lbl):
            w.bind("<Enter>", enter)
            w.bind("<Leave>", leave)
            w.bind("<Button-1>", lambda e, k=key: self.show_page(k))

    def refresh_nav(self):
        for key, (row, bar, lbl) in self.nav_widgets.items():
            active = key == self.current_page
            bg = BG_LIGHT if active else BG_GRAY
            row.config(bg=bg)
            lbl.config(bg=bg, fg=FG_WHITE if active else FG_MUTED,
                       font=("Segoe UI", 12, "bold" if active else "normal"))
            bar.config(bg=self.accent if active else bg)

    def build_header(self):
        header = tk.Frame(self.right, bg=BG_DARK)
        header.pack(fill="x", padx=30, pady=(25, 0))
        self.title_label = tk.Label(header, text="", bg=BG_DARK, fg=FG_WHITE,
                                    font=("Segoe UI", 24, "bold"))
        self.title_label.pack(side="left")

        right = tk.Frame(header, bg=BG_DARK)
        right.pack(side="right")
        self.clock_label = tk.Label(right, text="", bg=BG_DARK, fg=FG_MUTED, font=("Segoe UI", 11))
        self.clock_label.pack(side="left", padx=(0, 15))
        tk.Button(right, text="⛶", command=self.toggle_fullscreen, bg=BG_GRAY, fg=FG_WHITE,
                  relief="flat", bd=0, font=("Segoe UI", 12), cursor="hand2",
                  width=3).pack(side="left", padx=(0, 6))
        tk.Button(right, text="✖", command=self.quit_app, bg=EXIT_BG, fg="white",
                  activebackground="#c0392b", activeforeground="white", relief="flat", bd=0,
                  font=("Segoe UI", 12, "bold"), cursor="hand2", width=3).pack(side="left")

        tk.Frame(self.right, bg=BG_LIGHT, height=1).pack(fill="x", padx=30, pady=(15, 0))

    def tick_clock(self):
        try:
            self.clock_label.config(text=datetime.now().strftime("%d.%m.%Y  %H:%M:%S"))
            self.root.after(1000, self.tick_clock)
        except tk.TclError:
            pass

    # ---------- Sayfa yönetimi ----------
    def show_page(self, key):
        self.current_page = key
        self.log_widget = None
        self.clear(self.content)
        titles = {k: l for k, _i, l in self.NAV_ITEMS}
        self.title_label.config(text=titles.get(key, ""))
        self.refresh_nav()
        {
            "home": self.page_home,
            "library": self.page_library,
            "downloads": self.page_downloads,
            "settings": self.page_settings,
            "about": self.page_about,
        }[key]()

    def card(self, parent, title, value, sub="", value_color=None):
        c = tk.Frame(parent, bg=BG_GRAY, padx=20, pady=16)
        tk.Label(c, text=title, bg=BG_GRAY, fg=FG_MUTED, font=("Segoe UI", 10)).pack(anchor="w")
        v = tk.Label(c, text=value, bg=BG_GRAY, fg=value_color or FG_WHITE,
                     font=("Segoe UI", 20, "bold"))
        v.pack(anchor="w", pady=(4, 0))
        if sub:
            tk.Label(c, text=sub, bg=BG_GRAY, fg=FG_MUTED, font=("Segoe UI", 9)).pack(anchor="w")
        return c

    def section_label(self, parent, text):
        tk.Label(parent, text=text, bg=BG_DARK, fg=FG_WHITE,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(22, 8))

    # ---------- SAYFA: ANA SAYFA ----------
    def page_home(self):
        tk.Label(self.content, text=self.welcome_text(), bg=BG_DARK, fg=FG_WHITE,
                 font=("Segoe UI", 18)).pack(anchor="w", pady=(15, 0))
        tk.Label(self.content, text="Oyunlarını yönet, uygulamanı güncelle ve tek tıkla başlat.",
                 bg=BG_DARK, fg=FG_MUTED, font=("Segoe UI", 11)).pack(anchor="w", pady=(2, 15))

        row = tk.Frame(self.content, bg=BG_DARK)
        row.pack(fill="x")
        for i in range(3):
            row.columnconfigure(i, weight=1, uniform="c")

        installed = self.app_path.exists()
        size = human_size(self.app_path.stat().st_size) if installed else "-"
        mtime = (datetime.fromtimestamp(self.app_path.stat().st_mtime).strftime("%d.%m.%Y %H:%M")
                 if installed else "Henüz indirilmedi")

        self.card(row, "Uygulama Durumu", "Hazır ✔" if installed else "Eksik ✖",
                  f"main-app • {size}", OK_GREEN if installed else ERROR
                  ).grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.card(row, "Kütüphane", f"{len(self.config['games'])} oyun",
                  "Eklenen oyun sayısı").grid(row=0, column=1, sticky="nsew", padx=5)
        self.card(row, "Son Güncelleme", mtime.split(" ")[0], mtime
                  ).grid(row=0, column=2, sticky="nsew", padx=(10, 0))

        self.section_label(self.content, "Hızlı İşlemler")
        actions = tk.Frame(self.content, bg=BG_DARK)
        actions.pack(anchor="w")
        hover_button(actions, "▶  Uygulamayı Başlat", self.launch_main_app, self.accent,
                     hover=self.accent, pady=12, padx=22).pack(side="left", padx=(0, 10))
        hover_button(actions, "🎮  Kütüphaneyi Aç", lambda: self.show_page("library"), BG_GRAY,
                     pady=12, padx=22).pack(side="left", padx=(0, 10))
        hover_button(actions, "⬇  Güncelle", lambda: self.show_page("downloads"), BG_GRAY,
                     pady=12, padx=22).pack(side="left")

        self.section_label(self.content, "Son Etkinlikler")
        box = tk.Frame(self.content, bg=BG_GRAY, padx=16, pady=12)
        box.pack(fill="x")
        recent = self.logs[-5:] or [("Henüz bir etkinlik yok.", None)]
        for line, color in recent:
            tk.Label(box, text=line, bg=BG_GRAY, fg=color or FG_MUTED, font=("Consolas", 10),
                     anchor="w").pack(fill="x")

    # ---------- SAYFA: KÜTÜPHANE ----------
    def page_library(self):
        bar = tk.Frame(self.content, bg=BG_DARK)
        bar.pack(fill="x", pady=(15, 10))
        tk.Label(bar, text="Eklediğin oyunlar ve programlar", bg=BG_DARK, fg=FG_MUTED,
                 font=("Segoe UI", 11)).pack(side="left")
        hover_button(bar, "＋  Oyun Ekle", self.add_game, self.accent, hover=self.accent
                     ).pack(side="right")

        self.lib_scroll = ScrollFrame(self.content, BG_DARK)
        self.lib_scroll.pack(fill="both", expand=True)
        self.render_games()

    def render_games(self):
        inner = self.lib_scroll.inner
        self.clear(inner)
        games = self.config["games"]
        if not games:
            tk.Label(inner, text="Kütüphane boş.\n'Oyun Ekle' ile bir .exe / .py / .bat seç.",
                     bg=BG_DARK, fg=FG_MUTED, font=("Segoe UI", 12), justify="left"
                     ).pack(anchor="w", pady=30)
            return
        for idx, g in enumerate(games):
            row = tk.Frame(inner, bg=BG_GRAY, padx=16, pady=12)
            row.pack(fill="x", pady=4)
            Logo(row, 40, BG_GRAY, self.accent).pack(side="left", padx=(0, 14))
            info = tk.Frame(row, bg=BG_GRAY)
            info.pack(side="left", fill="x", expand=True)
            tk.Label(info, text=g["name"], bg=BG_GRAY, fg=FG_WHITE,
                     font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x")
            exists = Path(g["path"]).exists()
            tk.Label(info, text=g["path"] + ("" if exists else "  (dosya bulunamadı)"),
                     bg=BG_GRAY, fg=FG_MUTED if exists else ERROR, font=("Segoe UI", 9),
                     anchor="w").pack(fill="x")
            hover_button(row, "▶ Oyna", lambda i=idx: self.launch_game(i), self.accent,
                         hover=self.accent, pady=6).pack(side="right", padx=(8, 0))
            hover_button(row, "🗑", lambda i=idx: self.remove_game(i), BG_LIGHT,
                         hover=EXIT_BG, pady=6, padx=10).pack(side="right")

    def add_game(self):
        path = filedialog.askopenfilename(
            title="Oyun / program seç",
            filetypes=[("Çalıştırılabilir", "*.exe *.py *.bat *.cmd *.sh *.lnk"), ("Tümü", "*.*")])
        if not path:
            return
        name = Path(path).stem.replace("_", " ").replace("-", " ").title()
        self.config["games"].append({"name": name, "path": path})
        self.save_config()
        self.log(f"Kütüphaneye eklendi: {name}")
        self.render_games()

    def remove_game(self, idx):
        g = self.config["games"][idx]
        if messagebox.askyesno(APP_TITLE, f"'{g['name']}' kütüphaneden kaldırılsın mı?\n(Dosya silinmez.)"):
            del self.config["games"][idx]
            self.save_config()
            self.log(f"Kütüphaneden kaldırıldı: {g['name']}")
            self.render_games()

    def launch_game(self, idx):
        g = self.config["games"][idx]
        p = Path(g["path"])
        if not p.exists():
            messagebox.showerror(APP_TITLE, "Dosya bulunamadı:\n" + g["path"])
            return
        try:
            if p.suffix.lower() == ".py":
                subprocess.Popen([sys.executable, str(p)], cwd=str(p.parent))
            elif os.name == "nt":
                os.startfile(str(p))  # type: ignore[attr-defined]
            else:
                subprocess.Popen([str(p)], cwd=str(p.parent))
            self.log(f"Başlatıldı: {g['name']}", OK_GREEN)
        except Exception as e:
            self.log(f"{g['name']} başlatılamadı: {e}", ERROR)
            messagebox.showerror(APP_TITLE, f"Başlatılamadı:\n{e}")

    # ---------- SAYFA: İNDİRMELER ----------
    def page_downloads(self):
        top = tk.Frame(self.content, bg=BG_GRAY, padx=22, pady=18)
        top.pack(fill="x", pady=(15, 0))
        tk.Label(top, text="main-app", bg=BG_GRAY, fg=FG_WHITE,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w")
        installed = self.app_path.exists()
        info = (f"Yüklü • {human_size(self.app_path.stat().st_size)}" if installed
                else "Henüz indirilmedi")
        self.dl_status = tk.Label(top, text=info, bg=BG_GRAY,
                                  fg=OK_GREEN if installed else ERROR, font=("Segoe UI", 10))
        self.dl_status.pack(anchor="w", pady=(2, 12))
        self.dl_bar = ProgressBar(top, width=520, color=self.accent, parent_bg=BG_GRAY)
        self.dl_bar.pack(anchor="w", pady=(0, 14))
        btns = tk.Frame(top, bg=BG_GRAY)
        btns.pack(anchor="w")
        hover_button(btns, "⬇  Güncellemeleri Kontrol Et", self.manual_update, self.accent,
                     hover=self.accent).pack(side="left", padx=(0, 8))
        hover_button(btns, "🔗  GitHub'ı Aç", lambda: webbrowser.open(REPO_URL), BG_LIGHT
                     ).pack(side="left")

        self.section_label(self.content, "İşlem Günlüğü")
        wrap = tk.Frame(self.content, bg=BG_GRAY)
        wrap.pack(fill="both", expand=True)
        txt = tk.Text(wrap, bg=BG_GRAY, fg=FG_WHITE, font=("Consolas", 10), relief="flat", bd=0,
                      padx=12, pady=10, state="disabled", wrap="word")
        sb = tk.Scrollbar(wrap, command=txt.yview)
        txt.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        self.log_widget = txt
        for line, color in self.logs:
            self._append_log(line, color)

    def manual_update(self):
        if self.updating:
            return
        self.updating = True
        self.dl_bar.set(0)
        self.log("Güncelleme kontrol ediliyor...")

        def work():
            try:
                changed = self.sync_main_app(lambda p: self.root.after(0, lambda: self._dl_progress(p)))
                msg = "Yeni sürüm indirildi." if changed else "Zaten güncel."
                self.root.after(0, lambda: self._dl_done(msg, OK_GREEN))
            except Exception as e:
                self.log(f"Güncelleme hatası: {e}", ERROR)
                self.root.after(0, lambda: self._dl_done(f"Hata: {e}", ERROR))

        threading.Thread(target=work, daemon=True).start()

    def _dl_progress(self, p):
        try:
            self.dl_bar.set(p)
        except tk.TclError:
            pass

    def _dl_done(self, msg, color):
        self.updating = False
        try:
            self.dl_bar.set(1 if color == OK_GREEN else 0)
            self.dl_status.config(text=msg, fg=color)
        except tk.TclError:
            pass

    # ---------- SAYFA: AYARLAR ----------
    def page_settings(self):
        sf = ScrollFrame(self.content, BG_DARK)
        sf.pack(fill="both", expand=True)
        box = sf.inner

        def toggle(key, title, desc):
            row = tk.Frame(box, bg=BG_GRAY, padx=18, pady=12)
            row.pack(fill="x", pady=4)
            txt = tk.Frame(row, bg=BG_GRAY)
            txt.pack(side="left", fill="x", expand=True)
            tk.Label(txt, text=title, bg=BG_GRAY, fg=FG_WHITE, font=("Segoe UI", 12, "bold"),
                     anchor="w").pack(fill="x")
            tk.Label(txt, text=desc, bg=BG_GRAY, fg=FG_MUTED, font=("Segoe UI", 9),
                     anchor="w").pack(fill="x")
            var = tk.BooleanVar(value=self.config[key])

            def on_change():
                self.config[key] = var.get()
                self.save_config()
                if key == "fullscreen":
                    self.is_fullscreen = var.get()
                    self.root.attributes("-fullscreen", self.is_fullscreen)

            tk.Checkbutton(row, variable=var, command=on_change, bg=BG_GRAY, activebackground=BG_GRAY,
                           selectcolor=BG_DARK, fg=self.accent, bd=0, highlightthickness=0
                           ).pack(side="right")

        self.section_label(box, "Genel")
        toggle("fullscreen", "Tam ekran", "Açılışta tam ekran kullan (F11 ile de değişir).")
        toggle("auto_update", "Otomatik güncelleme", "Açılışta main-app'i GitHub'dan güncelle.")
        toggle("auto_launch", "Açılışta main-app'i başlat", "Hazır olunca main-app otomatik çalışsın.")
        toggle("close_after_launch", "Başlatınca launcher'ı kapat", "main-app açılınca bu pencere kapansın.")

        self.section_label(box, "Vurgu Rengi")
        colors = tk.Frame(box, bg=BG_DARK)
        colors.pack(anchor="w")
        for name, hexc in ACCENT_CHOICES.items():
            b = tk.Button(colors, text=name, bg=hexc, fg="white", activebackground=hexc,
                          relief="flat", bd=0, font=("Segoe UI", 10, "bold"), cursor="hand2",
                          padx=14, pady=8, command=lambda h=hexc: self.set_accent(h))
            b.pack(side="left", padx=(0, 8))

        self.section_label(box, "Bakım")
        maint = tk.Frame(box, bg=BG_DARK)
        maint.pack(anchor="w")
        hover_button(maint, "Günlüğü Temizle", self.clear_logs, BG_GRAY).pack(side="left", padx=(0, 8))
        hover_button(maint, "Ayarları Sıfırla", self.reset_config, EXIT_BG, hover="#c0392b"
                     ).pack(side="left")

    def set_accent(self, color):
        self.accent = color
        self.config["accent"] = color
        self.save_config()
        self.build_main_ui("settings")

    def clear_logs(self):
        self.logs.clear()
        messagebox.showinfo(APP_TITLE, "Günlük temizlendi.")

    def reset_config(self):
        if messagebox.askyesno(APP_TITLE, "Tüm ayarlar (oyun listesi dahil) sıfırlansın mı?"):
            self.config = dict(DEFAULT_CONFIG)
            self.config["games"] = []
            self.accent = self.config["accent"]
            self.save_config()
            self.build_main_ui("settings")

    # ---------- SAYFA: HAKKINDA ----------
    def page_about(self):
        c = tk.Frame(self.content, bg=BG_GRAY, padx=30, pady=26)
        c.pack(fill="x", pady=(15, 0))
        Logo(c, 90, BG_GRAY, self.accent,
             self.icon_path if self.icon_path.exists() else None).pack(side="left", padx=(0, 24))
        t = tk.Frame(c, bg=BG_GRAY)
        t.pack(side="left")
        tk.Label(t, text=APP_TITLE, bg=BG_GRAY, fg=FG_WHITE, font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(t, text=f"Sürüm {APP_VERSION}", bg=BG_GRAY, fg=FG_MUTED, font=("Segoe UI", 11)).pack(anchor="w")
        tk.Label(t, text="Oyun ve uygulama başlatıcı • Python / Tkinter", bg=BG_GRAY, fg=FG_MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(6, 0))
        hover_button(t, "🔗  GitHub", lambda: webbrowser.open(REPO_URL), self.accent,
                     hover=self.accent).pack(anchor="w", pady=(12, 0))

        self.section_label(self.content, "Klavye Kısayolları")
        keys = tk.Frame(self.content, bg=BG_GRAY, padx=22, pady=14)
        keys.pack(fill="x")
        for k, d in (("F11", "Tam ekranı aç / kapat"), ("ESC", "Tam ekrandan çık")):
            r = tk.Frame(keys, bg=BG_GRAY)
            r.pack(fill="x", pady=3)
            tk.Label(r, text=k, bg=BG_LIGHT, fg=FG_WHITE, font=("Consolas", 10, "bold"),
                     padx=10, pady=3).pack(side="left")
            tk.Label(r, text=d, bg=BG_GRAY, fg=FG_MUTED, font=("Segoe UI", 10)).pack(side="left", padx=12)

        if not PIL_OK:
            tk.Label(self.content, text="İpucu: Logoyu gerçek resim olarak görmek için  pip install pillow",
                     bg=BG_DARK, fg=FG_MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(18, 0))


# ======================= BAŞLAT =======================
if __name__ == "__main__":
    root = tk.Tk()
    app = GameStarApp(root)
    root.mainloop()
