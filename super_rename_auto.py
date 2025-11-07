# Super Rename – Ultimate AutoUpdate Edition
# Credit: Nakano Tabasa
# Features:
# - Drag & Drop
# - Delete key to remove from list
# - Icon / Type / Size / No.
# - Sorting by clicking headers
# - Preview & Apply rename with pattern (Isekai EP01 -> EP02...)
# - Auto-detect episode number from filenames
# - Dark / Light theme toggle (saved in settings file)
# - Check for update online and Auto Update (download zip and replace files)
# - About & Update Log
#
# Usage: put this file where you run app. Update JSON (version) should point to a zip with updated files,
# or to an installer exe in the zip when running as frozen exe.

import os
import re
import sys
import json
import shutil
import tempfile
import zipfile
import urllib.request
import subprocess
import platform
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Optional DnD support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    USE_DND = True
except Exception:
    TkinterDnD = None
    DND_FILES = None
    USE_DND = False

APP_TITLE = "Super Rename – Ultimate AutoUpdate Edition"
VERSION = "v1.2.0"
CREDIT = "Developed by Nakano Tabasa ❤️"

# URL to version.json (change to your raw GitHub URL)
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/example/superrename_update/main/version.json"
# Example of version.json content:
# {
#   "latest_version": "v1.2.1",
#   "download_url": "https://example.com/SuperRename_v1.2.1.zip",
#   "notes": "Auto-detect, Dark mode, Auto-update"
# }

# Settings filename (to save theme preference)
SETTINGS_FILE = "super_rename_settings.json"


class SuperRenameApp:
    def __init__(self, root):
        self.root = root
        root.title(f"{APP_TITLE} — {VERSION}")
        root.geometry("1040x700")
        root.minsize(900, 500)
        root.resizable(True, True)

        # state
        self.file_list = []          # list of tuples (path, name)
        self.preview_list = []       # list of tuples (oldname, newname)
        self.pattern = tk.StringVar(value="Isekai EP01")
        self.sort_column = None
        self.sort_reverse = False
        self.settings = {"theme": "light"}  # theme: light or dark

        # load saved settings
        self.load_settings()

        # menubar
        self.create_menu()

        # top buttons
        top = ttk.Frame(root, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="Add Files", command=self.add_files).pack(side="left")
        ttk.Button(top, text="Clear List", command=self.clear_list).pack(side="left", padx=6)
        ttk.Button(top, text="Preview Rename", command=self.preview_rename).pack(side="left", padx=6)
        ttk.Button(top, text="Apply Rename", command=self.apply_rename).pack(side="left", padx=6)

        ttk.Label(top, text="Pattern (e.g. Isekai EP01):").pack(side="left", padx=(20, 6))
        ttk.Entry(top, textvariable=self.pattern, width=30).pack(side="left")
        ttk.Button(top, text="Auto-detect start", command=self.auto_detect_episode).pack(side="left", padx=6)

        # theme toggle
        self.theme_btn = ttk.Button(top, text="Toggle Theme", command=self.toggle_theme)
        self.theme_btn.pack(side="right")
        ttk.Label(top, text=CREDIT).pack(side="right", padx=(0,10))

        # treeview
        frame = ttk.Frame(root, padding=8)
        frame.pack(fill="both", expand=True)

        columns = ("icon", "no", "original", "type", "size", "new")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("icon", text="")
        self.tree.heading("no", text="No.", command=lambda: self.sort_by("no"))
        self.tree.heading("original", text="Original File", command=lambda: self.sort_by("original"))
        self.tree.heading("type", text="Type", command=lambda: self.sort_by("type"))
        self.tree.heading("size", text="Size", command=lambda: self.sort_by("size"))
        self.tree.heading("new", text="Preview New Name", command=lambda: self.sort_by("new"))

        self.tree.column("icon", width=30, anchor="center")
        self.tree.column("no", width=40, anchor="center")
        self.tree.column("original", width=360, anchor="w")
        self.tree.column("type", width=100, anchor="center")
        self.tree.column("size", width=80, anchor="e")
        self.tree.column("new", width=360, anchor="w")

        self.tree.pack(fill="both", expand=True, side="left")
        self.tree.bind("<Double-1>", self.open_file_location)  # double click -> open folder

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        # footer
        footer = ttk.Frame(root, padding=8)
        footer.pack(fill="x")
        self.status = ttk.Label(footer, text=f"Ready. {CREDIT}")
        self.status.pack(side="left")

        # key bindings
        self.root.bind("<Delete>", self.delete_selected)
        self.root.bind("<Control-s>", lambda e: self.save_settings())

        # DnD
        if USE_DND and TkinterDnD is not None:
            try:
                self.tree.drop_target_register(DND_FILES)
                self.tree.dnd_bind("<<Drop>>", self.handle_drop)
            except Exception:
                pass
            try:
                self.root.drop_target_register(DND_FILES)
                self.root.dnd_bind("<<Drop>>", self.handle_drop)
            except Exception:
                pass
            self.status.config(text=f"Ready. Drag & Drop enabled ✅ — {CREDIT}")
        else:
            self.status.config(text=f"Ready. Drag & Drop not available ❌ — {CREDIT}")

        # Apply theme initially
        self.apply_theme()

    # ---------- Menu ----------
    def create_menu(self):
        menubar = tk.Menu(self.root)

        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Add Files", command=self.add_files)
        filemenu.add_command(label="Clear List", command=self.clear_list)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About / ผู้พัฒนา", command=self.show_about)
        helpmenu.add_command(label="Update Log / บันทึกการอัปเดต", command=self.show_log)
        helpmenu.add_separator()
        helpmenu.add_command(label="Check for Update", command=self.check_for_update)
        helpmenu.add_command(label="Auto Update (Download & Apply)", command=self.auto_update)
        menubar.add_cascade(label="Help", menu=helpmenu)

        self.root.config(menu=menubar)

    def show_about(self):
        msg = (
            f"{APP_TITLE} {VERSION}\n\n"
            "โปรแกรมเปลี่ยนชื่อไฟล์เป็นชุด สำหรับชื่อซีรีส์/ตอน\n"
            "ฟีเจอร์: Drag&Drop, Auto-detect episode, Dark/Light mode, Auto Update\n\n"
            f"ผู้พัฒนา: Nakano Tabasa\n"
        )
        messagebox.showinfo("About – Nakano Tabasa", msg)

    def show_log(self):
        log = (
            "📜 Super Rename – Update Log\n"
            "----------------------------------------\n"
            "v1.0.1 – ระบบเปลี่ยนชื่อพื้นฐาน\n"
            "v1.0.2 – เพิ่ม Drag & Drop\n"
            "v1.0.3 – เพิ่ม Delete ลบไฟล์จากรายการ\n"
            "v1.0.4 – เพิ่มไอคอน, ประเภท, ขนาดไฟล์\n"
            "v1.0.5 – เพิ่ม Sorting + เมนู About\n"
            "v1.1.0 – เพิ่ม Check for Update\n"
            "v1.2.0 – เพิ่ม Auto Update, Auto-detect episode, Dark/Light theme\n\n"
            "ผู้พัฒนา: Nakano Tabasa"
        )
        messagebox.showinfo("Update Log", log)

    # ---------- Files handling ----------
    def add_files(self):
        paths = filedialog.askopenfilenames(title="Select files to rename")
        self._add_files_internal(paths)

    def _add_files_internal(self, paths):
        if not paths:
            return
        added = 0
        for p in paths:
            if os.path.isfile(p) and p not in [x[0] for x in self.file_list]:
                self.file_list.append((p, os.path.basename(p)))
                added += 1
        if added:
            self.refresh_table()
            self.status.config(text=f"Added {added} files.")

    def handle_drop(self, event):
        try:
            paths = self.root.tk.splitlist(event.data)
        except Exception:
            paths = [event.data]
        self._add_files_internal(paths)

    def clear_list(self):
        self.file_list.clear()
        self.preview_list.clear()
        self.refresh_table()
        self.status.config(text="Cleared list.")

    def delete_selected(self, event=None):
        selected = self.tree.selection()
        if not selected:
            return
        names_to_remove = [self.tree.item(i)["values"][2] for i in selected]  # original file name at index 2
        before = len(self.file_list)
        self.file_list = [f for f in self.file_list if f[1] not in names_to_remove]
        self.preview_list = []
        self.refresh_table()
        self.status.config(text=f"Removed {before - len(self.file_list)} file(s).")

    def refresh_table(self, preview=False):
        self.tree.delete(*self.tree.get_children())
        if preview and self.preview_list:
            display_list = self.preview_list
        else:
            display_list = [(name, "", os.path.splitext(name)[1][1:], self._get_size(path)) for path, name in self.file_list]

        for idx, data in enumerate(display_list, start=1):
            if preview:
                old, new = data
                path = [p for p, n in self.file_list if n == old][0]
                ftype = os.path.splitext(old)[1][1:]
                fsize = self._get_size(path)
                self.tree.insert("", "end", values=(self._get_icon(ftype), idx, old, ftype.upper(), fsize, new))
            else:
                name, _, ftype, fsize = data
                self.tree.insert("", "end", values=(self._get_icon(ftype), idx, name, ftype.upper(), fsize, ""))

        self.status.config(text=f"Files: {len(self.file_list)}")

    # ---------- Sorting ----------
    def sort_by(self, column):
        if not self.tree.get_children():
            return
        col_map = {"no": 1, "original": 2, "type": 3, "size": 4, "new": 5}
        col_index = col_map.get(column)
        if not col_index:
            return
        self.sort_reverse = not self.sort_reverse if self.sort_column == column else False
        self.sort_column = column
        items = [(self.tree.set(k, col_index), k) for k in self.tree.get_children("")]

        if column == "size":
            def parse_size(s):
                try:
                    val, unit = s.split()
                    val = float(val)
                    factor = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}
                    return val * factor.get(unit, 1)
                except Exception:
                    return 0
            items.sort(key=lambda t: parse_size(t[0]), reverse=self.sort_reverse)
        elif column == "no":
            items.sort(key=lambda t: int(t[0]), reverse=self.sort_reverse)
        else:
            items.sort(key=lambda t: t[0].lower(), reverse=self.sort_reverse)

        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)

        # refresh No. column
        for i, k in enumerate(self.tree.get_children(""), start=1):
            vals = list(self.tree.item(k, "values"))
            vals[1] = i
            self.tree.item(k, values=vals)

    # ---------- Rename features ----------
    def preview_rename(self):
        if not self.file_list:
            messagebox.showwarning(APP_TITLE, "ยังไม่ได้เลือกไฟล์เลยนะ~")
            return
        pattern = self.pattern.get().strip()
        if not pattern:
            messagebox.showwarning(APP_TITLE, "กรุณาใส่ชื่อ pattern ก่อน เช่น Isekai EP01")
            return
        base, num = self.split_pattern(pattern)
        if num is None:
            messagebox.showwarning(APP_TITLE, "รูปแบบ pattern ต้องมีตัวเลขตอนท้าย เช่น EP01, 001, etc.")
            return
        self.preview_list = []
        start_num = int(num)
        pad_len = len(num)
        for i, (path, name) in enumerate(self.file_list):
            ext = os.path.splitext(name)[1]
            new_name = f"{base}{str(start_num + i).zfill(pad_len)}{ext}"
            self.preview_list.append((name, new_name))
        self.refresh_table(preview=True)
        self.status.config(text=f"Preview ready for {len(self.preview_list)} files.")

    def split_pattern(self, pattern):
        m = re.search(r"(\d+)$", pattern)
        if not m:
            return pattern, None
        base = pattern[: m.start()]
        num = m.group(1)
        return base, num

    def apply_rename(self):
        if not self.preview_list:
            messagebox.showinfo(APP_TITLE, "ยังไม่มี preview ให้เปลี่ยนชื่อ")
            return
        sample = "\n".join([f"{old} → {new}" for old, new in self.preview_list[:10]])
        if len(self.preview_list) > 10:
            sample += f"\n... (รวมทั้งหมด {len(self.preview_list)} ไฟล์)"
        confirm = messagebox.askyesno(APP_TITLE, f"ยืนยันจะเปลี่ยนชื่อไฟล์ทั้งหมด?\n\n{sample}")
        if not confirm:
            return
        success, failed = 0, []
        for (path, old_name), (_, new_name) in zip(self.file_list, self.preview_list):
            folder = os.path.dirname(path)
            new_path = os.path.join(folder, new_name)
            try:
                if os.path.exists(new_path):
                    failed.append((old_name, "มีไฟล์ชื่อนี้อยู่แล้ว"))
                    continue
                os.rename(path, new_path)
                success += 1
            except Exception as e:
                failed.append((old_name, str(e)))
        msg = f"เปลี่ยนชื่อสำเร็จ {success} ไฟล์"
        if failed:
            msg += f"\n\nล้มเหลว {len(failed)} ไฟล์:\n"
            msg += "\n".join([f"{f[0]}: {f[1]}" for f in failed[:10]])
        messagebox.showinfo(APP_TITLE, msg)
        self.file_list.clear()
        self.preview_list.clear()
        self.refresh_table()
        self.status.config(text="Rename complete.")

    # ---------- Auto-detect episode ----------
    def auto_detect_episode(self):
        """Scan filenames to find highest episode number and prefill pattern"""
        if not self.file_list:
            messagebox.showwarning(APP_TITLE, "กรุณาเพิ่มไฟล์ก่อน เพื่อให้ระบบตรวจหาเลขตอน")
            return
        nums = []
        pad = 2
        # try to find patterns like EP01, E01, 01, S01E02 etc.
        for path, name in self.file_list:
            # search EP or E or just numbers
            m = re.search(r"[Ee][Pp]?0*([0-9]+)", name)
            if m:
                nums.append(int(m.group(1)))
                pad = max(pad, len(m.group(1)))
                continue
            m2 = re.search(r"(\d{1,4})(?=\D*$)", name)  # number near end
            if m2:
                nums.append(int(m2.group(1)))
                pad = max(pad, len(m2.group(1)))
        if not nums:
            messagebox.showinfo("Auto-detect", "ไม่พบเลขตอนในชื่อไฟล์ ลองตั้งชื่อไฟล์ให้มีเลขตอน (เช่น EP01) แล้วลองอีกครั้ง")
            return
        highest = max(nums)
        start = highest + 1
        base_guess = re.sub(r"(\d+)(\.\w+)?$", "", self.file_list[0][1])  # not perfect but a guess
        # We'll be conservative: use user-provided base if exists; otherwise ask to input base
        # Suggest pattern: take first file name without trailing number and extension
        first_name = self.file_list[0][1]
        base_match = re.sub(r"(\d+)(\.\w+)?$", "", first_name)
        # create pattern using start-1 as likely last existing: set pattern to base + (start-1) padded
        suggestion = f"{base_match}{str(start).zfill(pad)}"
        # Ask user to accept suggestion or edit
        res = messagebox.askyesno("Auto-detect", f"พบเลขตอนสูงสุด {highest}\nแนะนำเริ่มที่: {suggestion}\n\nกด Yes เพื่อใช้คำแนะนำ (จะใส่ลงในช่อง Pattern)")
        if res:
            self.pattern.set(suggestion)
            self.status.config(text=f"Auto-detect set start = {start}")
        else:
            self.status.config(text="Auto-detect canceled")

    # ---------- Helpers ----------
    def _get_icon(self, ftype):
        ftype = ftype.lower()
        if ftype in ("jpg", "jpeg", "png", "gif", "bmp", "webp"):
            return "🖼️"
        elif ftype in ("mp3", "wav", "ogg", "flac", "m4a"):
            return "🎵"
        elif ftype in ("mp4", "mkv", "avi", "mov", "wmv"):
            return "🎬"
        elif ftype in ("txt", "doc", "docx", "pdf"):
            return "📄"
        else:
            return "📦"

    def _get_size(self, path):
        try:
            size = os.path.getsize(path)
            for unit in ["B", "KB", "MB", "GB"]:
                if size < 1024:
                    return f"{size:.1f} {unit}"
                size /= 1024
            return f"{size:.1f} TB"
        except Exception:
            return "-"

    def open_file_location(self, event):
        """Double-click: open folder containing file and select it (Windows only)"""
        item = self.tree.identify_row(event.y)
        if not item:
            return
        name = self.tree.item(item)["values"][2]
        # find path
        matched = [p for p, n in self.file_list if n == name]
        if not matched:
            return
        path = matched[0]
        folder = os.path.dirname(path)
        try:
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer /select,"{path}"')
            else:
                # try open folder
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            messagebox.showwarning("Open", f"ไม่สามารถเปิดโฟลเดอร์ได้: {e}")

    # ---------- Theme (Dark / Light) ----------
    def apply_theme(self):
        style = ttk.Style()
        # use default theme engine
        try:
            style.theme_use("clam")
        except Exception:
            pass
        # Basic color adjustments
        if self.settings.get("theme", "light") == "dark":
            bg = "#222222"
            fg = "#eeeeee"
            rowbg = "#2b2b2b"
            style.configure(".", background=bg, foreground=fg)
            style.configure("Treeview", background=rowbg, fieldbackground=rowbg, foreground=fg)
            style.map("Treeview", background=[("selected", "#555555")], foreground=[("selected", "white")])
            self.root.configure(bg=bg)
        else:
            bg = None
            fg = None
            style.configure("Treeview", background="white", fieldbackground="white", foreground="black")
            try:
                self.root.configure(bg=self.root.cget("bg"))
            except Exception:
                pass

    def toggle_theme(self):
        cur = self.settings.get("theme", "light")
        self.settings["theme"] = "dark" if cur == "light" else "light"
        self.apply_theme()
        self.save_settings()
        self.status.config(text=f"Theme set to {self.settings['theme']}")

    def load_settings(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    self.settings = json.load(f)
        except Exception:
            self.settings = {"theme": "light"}

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            self.status.config(text="Settings saved.")
        except Exception as e:
            self.status.config(text=f"Save settings failed: {e}")

    # ---------- Update functions ----------
    def check_for_update(self):
        """Check remote version.json and show info"""
        try:
            with urllib.request.urlopen(UPDATE_CHECK_URL, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            latest = data.get("latest_version", "")
            notes = data.get("notes", "")
            download = data.get("download_url", "")
            if latest and latest != VERSION:
                msg = f"พบเวอร์ชันใหม่: {latest}\n\n{notes}\n\nดาวน์โหลด: {download}"
                messagebox.showinfo("Update Available", msg)
            else:
                messagebox.showinfo("No Update", "คุณใช้เวอร์ชันล่าสุดแล้ว ❤️")
        except Exception as e:
            messagebox.showwarning("Update Check Failed", f"ไม่สามารถตรวจสอบอัปเดตได้:\n{e}")

    def auto_update(self):
        """Download zip from update JSON and try to apply update automatically.
        Behavior:
         - If running as script (.py): extract and copy files over current script directory (best-effort).
         - If running as frozen exe: prefer to run 'installer.exe' inside downloaded zip if present.
        """
        if not messagebox.askyesno("Auto Update", "ต้องการดาวน์โหลดและติดตั้งเวอร์ชันใหม่หรือไม่? (แอปจะปิดเมื่ออัปเดตสำเร็จ)"):
            return
        # fetch JSON
        try:
            with urllib.request.urlopen(UPDATE_CHECK_URL, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            messagebox.showwarning("Update", f"ไม่สามารถดึงข้อมูลเวอร์ชันได้: {e}")
            return
        latest = data.get("latest_version", "")
        download = data.get("download_url", "")
        notes = data.get("notes", "")
        if not download:
            messagebox.showwarning("Update", "ไฟล์อัปเดตไม่มี URL ดาวน์โหลด")
            return
        if latest == VERSION:
            if not messagebox.askyesno("Update", "เวอร์ชันตรงกัน (ไม่มีการอัปเดต) แต่ต้องการดาวน์โหลดใหม่หรือไม่?"):
                return
        # download zip
        tmpdir = tempfile.mkdtemp(prefix="super_rename_update_")
        try:
            self.status.config(text="Downloading update...")
            self.root.update_idletasks()
            zip_path = os.path.join(tmpdir, "update.zip")
            urllib.request.urlretrieve(download, zip_path)
            # extract
            self.status.config(text="Extracting update...")
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(tmpdir)
            # find files to copy
            extracted_dir = tmpdir
            # if zip contains single folder, use it
            entries = os.listdir(tmpdir)
            if len(entries) == 1 and os.path.isdir(os.path.join(tmpdir, entries[0])):
                extracted_dir = os.path.join(tmpdir, entries[0])

            app_dir = os.path.abspath(os.path.dirname(sys.argv[0]))  # where current script/exe sits

            # If frozen exe, try to run installer if present
            if getattr(sys, "frozen", False):
                # look for installer exe
                installers = [f for f in os.listdir(extracted_dir) if f.lower().endswith(".exe")]
                if installers:
                    installer_path = os.path.join(extracted_dir, installers[0])
                    try:
                        messagebox.showinfo("Update", f"ดาวน์โหลดเสร็จแล้ว จะรันตัวติดตั้ง: {installers[0]}")
                        subprocess.Popen([installer_path], shell=True)
                        self.root.quit()
                        return
                    except Exception as e:
                        messagebox.showwarning("Update", f"ไม่สามารถรันตัวติดตั้งได้: {e}\nจะพยายามคัดลอกไฟล์แทน")
                else:
                    # no installer; cannot overwrite running exe. Ask user to manually replace
                    messagebox.showinfo("Update", f"ไม่มีตัวติดตั้งอัตโนมัติในแพ็กเกจ กรุณแตกไฟล์ในโฟลเดอร์ {extracted_dir} แล้วปิดโปรแกรมเพื่อนำไฟล์ไปแทนด้วยตนเอง.")
                    return

            # Not frozen: running as .py, try to copy files over (best-effort)
            self.status.config(text="Applying update (copying files)...")
            # copy all files from extracted_dir to app_dir (overwrite)
            for root_dir, dirs, files in os.walk(extracted_dir):
                rel = os.path.relpath(root_dir, extracted_dir)
                target_dir = os.path.join(app_dir, rel) if rel != "." else app_dir
                if not os.path.exists(target_dir):
                    os.makedirs(target_dir, exist_ok=True)
                for fname in files:
                    src = os.path.join(root_dir, fname)
                    dst = os.path.join(target_dir, fname)
                    try:
                        # don't overwrite user settings
                        if os.path.abspath(dst) == os.path.abspath(SETTINGS_FILE):
                            continue
                        shutil.copy2(src, dst)
                    except Exception as e:
                        print("Copy failed:", src, dst, e)
            messagebox.showinfo("Update", f"อัปเดตเสร็จแล้วเป็น {latest}\nโปรดปิดและเปิดโปรแกรมใหม่")
            self.root.quit()
        except Exception as e:
            messagebox.showwarning("Update Failed", f"อัปเดตล้มเหลว: {e}")
        finally:
            try:
                shutil.rmtree(tmpdir)
            except Exception:
                pass

def main():
    root = TkinterDnD.Tk() if USE_DND and TkinterDnD is not None else tk.Tk()
    style = ttk.Style()
    for theme in ("vista", "clam", "alt"):
        try:
            style.theme_use(theme)
            break
        except Exception:
            pass
    app = SuperRenameApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
