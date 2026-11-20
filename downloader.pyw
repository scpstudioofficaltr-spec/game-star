import os
import sys
import ctypes
import threading
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

# DÜZELTİLDİ: GitHub linkleri "raw.githubusercontent.com" formatına çevrildi.
# (github.com/.../raw/refs/heads/main/... formatı bazen 404 verir veya HTML döner)
FILES = [
    ("app.pyw", "https://raw.githubusercontent.com/scpstudioofficaltr-spec/game-star/main/app.pyw"),
    ("icoimg.ico", "https://raw.githubusercontent.com/scpstudioofficaltr-spec/load-system-by-crgame/main/icoimg"),
]

SUBFOLDER = "Game Star"

# Beyaz / sade palet
BG       = "#ffffff"
FG       = "#222222"
MUTED    = "#777777"
BORDER   = "#e0e0e0"
GREEN    = "#2ecc71"
GREEN_DK = "#27ae60"
GRAY_BTN = "#f2f2f2"


def create_shortcut_windows(shortcut_path: Path, target: Path, arguments: str,
                            workdir: Path, icon: Path, description: str):
    """PowerShell/ekran açmadan, ctypes ile .lnk oluşturur."""
    CLSID_ShellLink = ctypes.c_buffer(
        b"\x01\x14\x02\x00\x00\x00\x00\x00\xC0\x00\x00\x00\x00\x00\x00\x46"
    )
    IID_IShellLinkW = ctypes.c_buffer(
        b"\xF9\x14\x02\x00\x00\x00\x00\x00\xC0\x00\x00\x00\x00\x00\x00\x46"
    )
    IID_IPersistFile = ctypes.c_buffer(
        b"\x0B\x01\x00\x00\x00\x00\x00\x00\xC0\x00\x00\x00\x00\x00\x00\x46"
    )

    ole32 = ctypes.windll.ole32
    ole32.CoInitialize(None)

    shell_link = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(
        ctypes.byref(CLSID_ShellLink), None, 1,
        ctypes.byref(IID_IShellLinkW), ctypes.byref(shell_link)
    )
    if hr != 0:
        raise RuntimeError(f"CoCreateInstance başarısız (0x{hr & 0xFFFFFFFF:08X})")

    try:
        vtable = ctypes.cast(shell_link, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents

        SetPath = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p)(vtable[20])
        SetPath(shell_link, str(target))

        SetArguments = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p)(vtable[11])
        SetArguments(shell_link, arguments)

        SetWorkingDirectory = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p)(vtable[9])
        SetWorkingDirectory(shell_link, str(workdir))

        if icon.exists():
            SetIconLocation = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int)(vtable[17])
            SetIconLocation(shell_link, str(icon), 0)

        SetDescription = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p)(vtable[7])
        SetDescription(shell_link, description)

        QueryInterface = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                            ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(vtable[0])
        persist = ctypes.c_void_p()
        hr = QueryInterface(shell_link, ctypes.byref(IID_IPersistFile), ctypes.byref(persist))
        if hr != 0:
            raise RuntimeError(f"QueryInterface(IPersistFile) başarısız (0x{hr & 0xFFFFFFFF:08X})")

        try:
            pvtable = ctypes.cast(persist, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            Save = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int)(pvtable[6])
            hr = Save(persist, str(shortcut_path), 1)
            if hr != 0:
                raise RuntimeError(f"IPersistFile::Save başarısız (0x{hr & 0xFFFFFFFF:08X})")
        finally:
            Release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(pvtable[2])
            Release(persist)
    finally:
        vtable2 = ctypes.cast(shell_link, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        Release2 = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable2[2])
        Release2(shell_link)


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Game Star — Kurulum")
        self.root.geometry("380x200")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        self.created_items = []
        self.parent_dir = None
        self.install_dir = None
        self.path_var = tk.StringVar()

        self.container = tk.Frame(root, bg=BG)
        self.container.pack(fill="both", expand=True)

        self.screen1 = self._build_screen1(self.container)
        self.screen2 = self._build_screen2(self.container)

        self.show_screen(self.screen1)

    # ---------- EKRAN 1: Klasör seçimi ----------
    def _build_screen1(self, parent):
        frame = tk.Frame(parent, bg=BG)

        tk.Label(frame, text="Kurulum Konumu", bg=BG, fg=FG,
                 font=("Segoe UI", 11, "bold")).pack(pady=(20, 10))

        row = tk.Frame(frame, bg=BG)
        row.pack(fill="x", padx=24)

        entry = tk.Entry(
            row, textvariable=self.path_var, state="readonly",
            bg=BG, fg=FG, readonlybackground=BG,
            relief="solid", bd=1, highlightthickness=0,
            font=("Segoe UI", 9)
        )
        entry.pack(side="left", fill="x", expand=True, ipady=5)

        tk.Button(
            row, text="Gözat", command=self.browse_folder,
            bg=GRAY_BTN, fg=FG, activebackground=BORDER,
            relief="solid", bd=1, highlightthickness=0,
            font=("Segoe UI", 9), cursor="hand2", padx=10
        ).pack(side="left", padx=(6, 0), ipady=2)

        self.info_label = tk.Label(frame, text="", bg=BG, fg=MUTED,
                                   font=("Segoe UI", 8))
        self.info_label.pack(pady=(8, 0))

        tk.Button(
            frame, text="Devam", command=self.go_to_download,
            bg=GREEN, fg="white", activebackground=GREEN_DK, activeforeground="white",
            relief="flat", bd=0, font=("Segoe UI", 10, "bold"), cursor="hand2"
        ).pack(fill="x", padx=24, pady=(12, 0), ipady=6)

        return frame

    # ---------- EKRAN 2: İndirme ----------
    def _build_screen2(self, parent):
        frame = tk.Frame(parent, bg=BG)

        tk.Label(frame, text="İndiriliyor...", bg=BG, fg=FG,
                 font=("Segoe UI", 11, "bold")).pack(pady=(25, 5))

        self.folder_label = tk.Label(frame, text="", bg=BG, fg=MUTED,
                                     font=("Segoe UI", 8), wraplength=320)
        self.folder_label.pack(pady=(0, 15))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Green.Horizontal.TProgressbar",
                        troughcolor="#f2f2f2", background=GREEN,
                        bordercolor=BG, lightcolor=GREEN, darkcolor=GREEN)

        self.progress = ttk.Progressbar(frame, orient="horizontal",
                                        mode="determinate",
                                        style="Green.Horizontal.TProgressbar")
        self.progress.pack(fill="x", padx=24)

        info_row = tk.Frame(frame, bg=BG)
        info_row.pack(fill="x", padx=24, pady=(6, 0))

        self.status_label = tk.Label(info_row, text="Hazır", bg=BG, fg=MUTED,
                                     font=("Segoe UI", 8))
        self.status_label.pack(side="left")

        self.percent_label = tk.Label(info_row, text="%0", bg=BG, fg=GREEN,
                                      font=("Segoe UI", 10, "bold"))
        self.percent_label.pack(side="right")

        return frame

    # ---------- Ekran geçişleri ----------
    def show_screen(self, screen):
        for w in self.container.winfo_children():
            w.pack_forget()
        screen.pack(fill="both", expand=True)

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Üst klasörü seçin")
        if folder:
            self.parent_dir = Path(folder)
            self.install_dir = self.parent_dir / SUBFOLDER
            self.path_var.set(str(self.parent_dir))
            self.info_label.config(text=f"Şuraya kurulacak: {SUBFOLDER}")

    def go_to_download(self):
        if not self.parent_dir:
            messagebox.showwarning("Klasör Seçilmedi", "Lütfen önce bir klasör seçin.")
            return
        self.folder_label.config(text=str(self.install_dir))
        self.show_screen(self.screen2)
        threading.Thread(target=self.download_task, daemon=True).start()

    # ---------- İndirme iş akışı ----------
    def download_task(self):
        base_dir = self.install_dir

        if not base_dir.exists():
            try:
                base_dir.mkdir(parents=True, exist_ok=True)
                self.created_items.append(base_dir)
            except Exception as e:
                self.fail_and_cleanup(f"Klasör oluşturulamadı: {e}")
                return

        total_files = len(FILES)
        for idx, (filename, url) in enumerate(FILES):
            filepath = base_dir / filename
            try:
                self.root.after(0, lambda f=filename: self.status_label.config(
                    text=f"İndiriliyor: {f}"))
                existed_before = filepath.exists()
                
                self.download_and_verify(url, filepath, filename, idx, total_files)
                
                if not existed_before:
                    self.created_items.append(filepath)
            except Exception as e:
                self.fail_and_cleanup(str(e))
                return

        self.root.after(0, lambda: self.status_label.config(text="Kısayol oluşturuluyor..."))
        try:
            shortcut_path = self.create_desktop_shortcut(base_dir)
            self.created_items.append(shortcut_path)
        except Exception as e:
            self.fail_and_cleanup(f"Kısayol oluşturulamadı: {e}")
            return

        self.root.after(0, lambda: self.progress.config(value=100))
        self.root.after(0, lambda: self.percent_label.config(text="%100"))
        self.root.after(0, lambda: self.status_label.config(text="Tamamlandı"))
        
        self.root.after(0, lambda: self.finish_and_launch(shortcut_path))

    def download_and_verify(self, url, filepath, filename, file_index, total_files):
        # DÜZELTİLDİ: GitHub raw linklerine önbellek önleyici (cache-buster) eklendi
        if "raw.githubusercontent.com" in url:
            sep = "&" if "?" in url else "?"
            url = url + sep + "t=" + str(int(time.time()))

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(filepath, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        overall = ((file_index + downloaded / total_size) / total_files) * 100
                        self.root.after(0, lambda v=overall: self.update_progress(v))
        
        if not filepath.exists() or filepath.stat().st_size == 0:
            raise RuntimeError(f"Sistem Error: '{filename}' dosyası boş indirildi.")
            
        if filepath.stat().st_size < 5000:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if "404: Not Found" in content or "Not Found" in content or "GitHub" in content and "raw" not in content:
                    raise RuntimeError(f"Sistem Error: '{filename}' GitHub üzerinde bulunamadı (404).")

    def update_progress(self, value):
        self.progress["value"] = value
        self.percent_label.config(text=f"%{int(value)}")

    def create_desktop_shortcut(self, base_dir):
        desktop = Path(os.path.expanduser("~/Desktop"))
        shortcut_path = desktop / "Game Star.lnk"
        target = base_dir / "app.pyw"
        icon_path = base_dir / "icoimg.ico"

        pythonw = Path(sys.executable).with_name("pythonw.exe")
        if not pythonw.exists():
            pythonw = Path(sys.executable)

        create_shortcut_windows(
            shortcut_path=shortcut_path,
            target=pythonw,
            arguments=f'"{target}"',
            workdir=base_dir,
            icon=icon_path,
            description="Game Star Başlatıcı",
        )
        return shortcut_path

    def finish_and_launch(self, shortcut_path):
        messagebox.showinfo("Başarılı", f"Kurulum başarıyla tamamlandı.\n\nKlasör: {self.install_dir}\n\nUygulama başlatılıyor...")
        
        # Pencereyi yok et
        self.root.destroy()
        
        # Pencere kapandıktan hemen sonra kısayolu arka planda çalıştır (kilitlenmeyi önler)
        def launch():
            import time
            time.sleep(0.5) # Pencere tamamen kapanana kadar milisaniyelik bekleme
            os.startfile(str(shortcut_path))
        
        threading.Thread(target=launch, daemon=False).start()

    # ---------- Hata + temizlik ----------
    def fail_and_cleanup(self, message):
        removed = []
        for item in reversed(self.created_items):
            try:
                if item.is_dir():
                    for sub in item.rglob("*"):
                        if sub.is_file():
                            sub.unlink()
                    for sub in sorted(item.rglob("*"), reverse=True):
                        if sub.is_dir():
                            sub.rmdir()
                    item.rmdir()
                elif item.is_file():
                    item.unlink()
                removed.append(item.name)
            except Exception:
                pass
        self.created_items.clear()

        cleanup_msg = ""
        if removed:
            cleanup_msg = "\n\nOtomatik silinenler:\n- " + "\n- ".join(removed)

        self.root.after(0, lambda: messagebox.showerror("Sistem Error", message + cleanup_msg))
        self.root.after(0, lambda: self.status_label.config(text="Hata oluştu"))
        self.root.after(0, lambda: self.progress.config(value=0))
        self.root.after(0, lambda: self.percent_label.config(text="%0"))
        self.root.after(0, lambda: self.show_screen(self.screen1))


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
