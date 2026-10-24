# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio v2.0 — Desktop GUI (Tkinter)
Giao dien desktop chay truc tiep tren Desktop nguoi dung.
FastAPI server chay trong thread nen de Extension giao tiep.
"""

import os
import sys
import json
import queue
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from typing import Optional

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Module path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    APP_NAME, APP_VERSION, API_HOST, API_PORT,
    CHROME_PATH, CHROME_USER_DATA_BASE, EXTENSION_DIR,
    DOLA_URL, OUTPUT_DIR, ACCOUNTS_STATE_FILE, DATA_DIR,
)
from account_manager import AccountManager, parse_via_cookie_string
from proxy_manager import ProxyManager
from job_manager import JobManager
from session_store import SessionStore
from worker_pool import WorkerPool

# ─── Colors & Style ──────────────────────────────────────────────────────────
BG = "#1a1a2e"
BG_CARD = "#16213e"
BG_INPUT = "#0f3460"
FG = "#e8e8e8"
FG_DIM = "#8899aa"
ACCENT = "#00d4ff"
ACCENT_HOVER = "#00bbdd"
GREEN = "#4ade80"
RED = "#f87171"
ORANGE = "#fb923c"
YELLOW = "#fbbf24"

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN GUI CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class SeedanceGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("960x680")
        self.root.minsize(800, 550)
        self.root.configure(bg=BG)

        # Icon
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        # Managers
        self.account_manager = AccountManager()
        self.proxy_manager = ProxyManager()
        self.job_manager = JobManager()
        self.session_store = SessionStore()
        self.worker_pool = WorkerPool(max_workers=10)
        self.current_job_id = None
        self.log_queue = queue.Queue()
        self.chrome_processes = {}  # account_name -> subprocess.Popen
        self.job_poll_running = False

        # Style
        self._setup_style()

        # Build UI
        self._build_header()
        self._build_notebook()
        self._build_status_bar()

        # Load data
        self.refresh_accounts()

        # Start API server in background
        self._start_api_server()

    # ─── Style ────────────────────────────────────────────────────────────

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background=BG, foreground=FG, fieldbackground=BG_INPUT)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG_CARD, foreground=FG, padding=[14, 6], font=("Segoe UI", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "#000")])
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=BG_CARD)
        style.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"), foreground=ACCENT)
        style.configure("Dim.TLabel", foreground=FG_DIM)
        style.configure("Green.TLabel", foreground=GREEN)
        style.configure("Red.TLabel", foreground=RED)
        style.configure("TButton", font=("Segoe UI", 10), padding=[10, 4])
        style.configure("Accent.TButton", background=ACCENT, foreground="#000")
        style.map("Accent.TButton", background=[("active", ACCENT_HOVER)])
        style.configure("Danger.TButton", background=RED, foreground="#fff")
        style.configure("TEntry", fieldbackground=BG_INPUT, foreground=FG, insertcolor=FG)
        style.configure("TCombobox", fieldbackground=BG_INPUT, foreground=FG)
        style.configure("Treeview", background=BG_CARD, foreground=FG, fieldbackground=BG_CARD,
                         rowheight=32, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=BG_INPUT, foreground=ACCENT, font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#000")])

    # ─── Header ───────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = ttk.Frame(self.root)
        hdr.pack(fill="x", padx=12, pady=(10, 4))

        ttk.Label(hdr, text=f"Seedance AI Video Studio", style="Title.TLabel").pack(side="left")
        ttk.Label(hdr, text=f"v{APP_VERSION}", style="Dim.TLabel").pack(side="left", padx=(6, 0))

        # Server status
        self.server_label = ttk.Label(hdr, text="API: Starting...", style="Dim.TLabel")
        self.server_label.pack(side="right")

    # ─── Notebook (Tabs) ──────────────────────────────────────────────────

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=6)

        self._build_tab_accounts()
        self._build_tab_create_video()
        self._build_tab_gallery()
        self._build_tab_proxy()
        self._build_tab_settings()

    # ═══ TAB: Accounts ════════════════════════════════════════════════════

    def _build_tab_accounts(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Tai khoan  ")

        # Toolbar
        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(toolbar, text="Quan ly tai khoan & Chrome Profile", style="Title.TLabel").pack(side="left")

        btn_frame = ttk.Frame(toolbar)
        btn_frame.pack(side="right")
        ttk.Button(btn_frame, text="+ Them Account", style="Accent.TButton",
                   command=self.add_account_dialog).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Import Hang Loat (VIA)",
                   command=self.bulk_import_dialog).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_accounts).pack(side="left", padx=2)

        # Table
        cols = ("name", "type", "session", "cookie", "status", "quota", "proxy")
        self.acc_tree = ttk.Treeview(tab, columns=cols, show="headings", height=10)
        self.acc_tree.heading("name", text="Ten Account")
        self.acc_tree.heading("type", text="Loai")
        self.acc_tree.heading("session", text="Session Dola (JSON)")
        self.acc_tree.heading("cookie", text="Cookie FB")
        self.acc_tree.heading("status", text="Trang thai")
        self.acc_tree.heading("quota", text="Quota")
        self.acc_tree.heading("proxy", text="Proxy")

        self.acc_tree.column("name", width=110)
        self.acc_tree.column("type", width=90)
        self.acc_tree.column("session", width=140)
        self.acc_tree.column("cookie", width=90)
        self.acc_tree.column("status", width=90)
        self.acc_tree.column("quota", width=70)
        self.acc_tree.column("proxy", width=140)

        self.acc_tree.pack(fill="both", expand=True, padx=8, pady=4)

        # Action buttons
        action_frame = ttk.Frame(tab)
        action_frame.pack(fill="x", padx=8, pady=(4, 8))

        ttk.Button(action_frame, text="🌐 Mo Chrome", style="Accent.TButton",
                   command=self.open_chrome_profile).pack(side="left", padx=2)
        ttk.Button(action_frame, text="💾 Luu Session Dola (5KB)",
                   command=self.extract_and_save_session_dialog).pack(side="left", padx=2)
        ttk.Button(action_frame, text="📋 Nap Cookie FB VIA",
                   command=self.inject_cookie_dialog).pack(side="left", padx=2)
        ttk.Button(action_frame, text="Xoa Account", style="Danger.TButton",
                   command=self.delete_account).pack(side="right", padx=2)

        # Info
        info = ttk.Label(tab, text="Quy trinh: Them Account -> Mo Chrome Login Dola -> Bam 'Luu Session Dola' -> Xong! (Dung luong chi 5KB/acc, khong ton o cung)",
                        style="Dim.TLabel", wraplength=900)
        info.pack(padx=8, pady=(0, 4))

    def refresh_accounts(self):
        """Reload account list from manager."""
        for item in self.acc_tree.get_children():
            self.acc_tree.delete(item)

        accounts = self.account_manager.get_all()
        for acc in accounts:
            name = acc["name"]
            has_cookie = "Co" if acc.get("fb_cookies", "").strip() else "Chua nap"
            
            # Check session status
            sess_info = self.session_store.get_session_info(name)
            if sess_info["saved"]:
                session_str = f"Da Luu ({sess_info['cookies_count']} cookies)"
            else:
                session_str = "Chua Luu"

            remaining = acc.get("quota_max", 4) - acc.get("quota_used", 0) - acc.get("quota_reserved", 0)
            quota_str = f"{remaining}/{acc.get('quota_max', 4)}"
            proxy_str = acc.get("proxy_direct") or acc.get("proxy_key") or acc.get("proxy", "")[:20] or "Pool"
            login_type = "Facebook" if acc.get("login_type") == "facebook" else "Google"
            status = acc.get("status", "active")

            self.acc_tree.insert("", "end", values=(
                name, login_type, session_str, has_cookie, status, quota_str, proxy_str
            ))

    def get_selected_account(self) -> Optional[str]:
        sel = self.acc_tree.selection()
        if not sel:
            messagebox.showwarning("Chon tai khoan", "Vui long chon 1 tai khoan trong bang truoc!")
            return None
        item = self.acc_tree.item(sel[0])
        return item["values"][0]

    def add_account_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Them tai khoan moi")
        dlg.geometry("420x350")
        dlg.configure(bg=BG)
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Them Tai Khoan Moi", style="Title.TLabel").pack(pady=(16, 8))

        frame = ttk.Frame(dlg)
        frame.pack(fill="x", padx=20)

        ttk.Label(frame, text="Ten Account:").grid(row=0, column=0, sticky="w", pady=4)
        name_entry = ttk.Entry(frame, width=30)
        name_entry.grid(row=0, column=1, pady=4, padx=(8, 0))
        name_entry.insert(0, f"fb{len(self.account_manager.accounts) + 1:02d}")

        ttk.Label(frame, text="Loai dang nhap:").grid(row=1, column=0, sticky="w", pady=4)
        type_var = tk.StringVar(value="facebook")
        type_cb = ttk.Combobox(frame, textvariable=type_var, values=["facebook", "google"], state="readonly", width=27)
        type_cb.grid(row=1, column=1, pady=4, padx=(8, 0))

        ttk.Label(frame, text="Cookie FB VIA:").grid(row=2, column=0, sticky="nw", pady=4)
        cookie_text = tk.Text(frame, width=30, height=4, bg=BG_INPUT, fg=FG, insertbackground=FG,
                             font=("Consolas", 9))
        cookie_text.grid(row=2, column=1, pady=4, padx=(8, 0))

        ttk.Label(frame, text="Proxy (tuy chon):").grid(row=3, column=0, sticky="w", pady=4)
        proxy_entry = ttk.Entry(frame, width=30)
        proxy_entry.grid(row=3, column=1, pady=4, padx=(8, 0))

        ttk.Label(frame, text="Quota toi da:").grid(row=4, column=0, sticky="w", pady=4)
        quota_var = tk.IntVar(value=4)
        quota_spin = ttk.Spinbox(frame, from_=1, to=20, textvariable=quota_var, width=8)
        quota_spin.grid(row=4, column=1, sticky="w", pady=4, padx=(8, 0))

        def do_add():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Loi", "Vui long nhap ten account!")
                return
            try:
                acc = self.account_manager.add_account(
                    name,
                    login_type=type_var.get(),
                    fb_cookies=cookie_text.get("1.0", "end").strip(),
                    proxy=proxy_entry.get().strip(),
                    quota_max=quota_var.get(),
                )
                self.refresh_accounts()
                self.log(f"Da them account: {name}")
                dlg.destroy()
            except ValueError as e:
                messagebox.showerror("Loi", str(e))

        ttk.Button(dlg, text="Tao Profile & Them Account", style="Accent.TButton",
                   command=do_add).pack(pady=16)

    def open_chrome_profile(self):
        name = self.get_selected_account()
        if not name:
            return

        chrome_path = CHROME_PATH
        if not chrome_path or not os.path.isfile(chrome_path):
            messagebox.showerror("Loi", "Khong tim thay Chrome! Cai dat Google Chrome truoc.")
            return

        # Close existing Chrome for this account
        if name in self.chrome_processes:
            proc = self.chrome_processes[name]
            if proc and proc.poll() is None:
                proc.terminate()
            del self.chrome_processes[name]

        profile_dir = os.path.join(CHROME_USER_DATA_BASE, name)
        os.makedirs(profile_dir, exist_ok=True)

        # Tính port debug cho account (cần cho "Luu Session Dola")
        from browser_manager import BrowserManager
        bm = BrowserManager()
        port = bm._get_port(name)

        # Kill bất kỳ Chrome nào đang dùng port này
        import psutil
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if "chrome" in (p.info["name"] or "").lower():
                    cmdline = " ".join(p.info["cmdline"] or [])
                    if f"--remote-debugging-port={port}" in cmdline:
                        p.kill()
            except Exception:
                pass

        # Build Chrome command
        cmd = [
            chrome_path,
            f"--remote-debugging-port={port}",
            f"--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={profile_dir}",
            "--profile-directory=Default",
            "--no-first-run",
            "--no-default-browser-check",
            "--lang=vi",
            "--window-position=100,80",
            "--window-size=1280,900",
        ]

        if os.path.isdir(EXTENSION_DIR):
            cmd.append(f"--load-extension={EXTENSION_DIR}")

        # Check if account has proxy
        acc = self.account_manager.get_account(name)
        if acc and acc.proxy:
            cmd.append(f"--proxy-server={acc.proxy}")

        cmd.append("https://www.facebook.com/")
        cmd.append(DOLA_URL)

        self.log(f"Dang mo Chrome Profile '{name}' (port={port}) kem Extension + Facebook/Dola...")

        try:
            proc = subprocess.Popen(cmd)
            self.chrome_processes[name] = proc
            self.log(f"Chrome da mo thanh cong! PID: {proc.pid}, Debug Port: {port}")
            self.log(f"  -> Login Dola xong, bam 'Luu Session Dola' de luu cookies")
        except Exception as e:
            messagebox.showerror("Loi mo Chrome", str(e))
            self.log(f"LOI: {e}")

    def inject_cookie_dialog(self):
        name = self.get_selected_account()
        if not name:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Nap Cookie FB VIA - {name}")
        dlg.geometry("500x300")
        dlg.configure(bg=BG)
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text=f"Nap Cookie Facebook VIA cho: {name}", style="Title.TLabel").pack(pady=(16, 8))

        ttk.Label(dlg, text="Dan chuoi Cookie (c_user=...; xs=...) hoac dong VIA (UID|Pass|2FA|Cookie):").pack(padx=20, anchor="w")

        cookie_text = tk.Text(dlg, width=55, height=6, bg=BG_INPUT, fg=FG, insertbackground=FG,
                             font=("Consolas", 9))
        cookie_text.pack(padx=20, pady=8)

        # Load existing cookie
        acc = self.account_manager.get_account(name)
        if acc and acc.fb_cookies:
            cookie_text.insert("1.0", acc.fb_cookies)

        status_label = ttk.Label(dlg, text="", style="Dim.TLabel")
        status_label.pack()

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(pady=8)

        def do_save():
            raw = cookie_text.get("1.0", "end").strip()
            if acc:
                acc.fb_cookies = raw
                self.account_manager.save()
            self.refresh_accounts()
            status_label.configure(text="Da luu Cookie!", style="Green.TLabel")
            self.log(f"Da luu Cookie FB cho account '{name}'")

        def do_save_and_open():
            do_save()
            dlg.destroy()
            # Select account in tree and open
            for item in self.acc_tree.get_children():
                if self.acc_tree.item(item)["values"][0] == name:
                    self.acc_tree.selection_set(item)
                    break
            self.open_chrome_profile()

        ttk.Button(btn_frame, text="Luu Cookie", command=do_save).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Luu & Mo Chrome", style="Accent.TButton",
                   command=do_save_and_open).pack(side="left", padx=4)

    def delete_account(self):
        name = self.get_selected_account()
        if not name:
            return
        if not messagebox.askyesno("Xac nhan", f"Xoa account '{name}'?\nProfile Chrome se duoc giu lai."):
            return

        # Close Chrome if running
        if name in self.chrome_processes:
            proc = self.chrome_processes[name]
            if proc and proc.poll() is None:
                proc.terminate()
            del self.chrome_processes[name]

        self.account_manager.delete_account(name)
        self.refresh_accounts()
        self.log(f"Da xoa account: {name}")

    def bulk_import_dialog(self):
        """Dialog nhập hàng loạt VIA cookies + tự động login Dola."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Import Hang Loat VIA Cookies -> Auto Login Dola")
        dlg.geometry("700x600")
        dlg.configure(bg=BG)
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Import Hang Loat VIA Cookies", style="Title.TLabel").pack(pady=(16, 4))
        ttk.Label(dlg, text="Dan danh sach VIA cookies (moi dong 1 account) hoac chon file .txt",
                  style="Dim.TLabel").pack(pady=(0, 8))

        # Text area for VIA cookies
        via_text = tk.Text(dlg, height=15, bg=BG_INPUT, fg=FG, insertbackground=FG,
                           font=("Consolas", 9), wrap="none")
        via_text.pack(fill="both", expand=True, padx=16, pady=4)
        via_text.insert("1.0", "# Dan VIA cookies vao day (moi dong 1 account):\n"
                                "# Format: uid|password|2fa|cookie_string\n"
                                "# Hoac chi can: cookie_string (c_user=...; xs=...)\n")

        # Options row
        opts = ttk.Frame(dlg)
        opts.pack(fill="x", padx=16, pady=4)

        ttk.Label(opts, text="So luong song song:").pack(side="left", padx=4)
        concurrent_var = tk.StringVar(value="5")
        ttk.Combobox(opts, textvariable=concurrent_var,
                     values=["1", "2", "3", "5", "10"],
                     state="readonly", width=4).pack(side="left", padx=4)

        # Progress
        progress_var = tk.DoubleVar(value=0)
        progress_bar = ttk.Progressbar(dlg, variable=progress_var, maximum=100)
        progress_bar.pack(fill="x", padx=16, pady=4)

        status_label = ttk.Label(dlg, text="San sang", style="Dim.TLabel")
        status_label.pack(pady=2)

        # Result log
        result_text = tk.Text(dlg, height=8, bg=BG_INPUT, fg=FG, insertbackground=FG,
                              font=("Consolas", 8), wrap="word", state="disabled")
        result_text.pack(fill="x", padx=16, pady=4)

        # Buttons
        btn_bar = ttk.Frame(dlg)
        btn_bar.pack(pady=8)

        def load_file():
            fp = filedialog.askopenfilename(
                title="Chon file VIA cookies",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
            if fp:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                via_text.delete("1.0", "end")
                via_text.insert("1.0", content)
                lines = [l for l in content.strip().split("\n") if l.strip() and not l.startswith("#")]
                status_label.configure(text=f"Da doc {len(lines)} dong tu file: {os.path.basename(fp)}")

        def start_import():
            raw = via_text.get("1.0", "end").strip()
            lines = [l for l in raw.split("\n") if l.strip() and not l.startswith("#")]
            if not lines:
                messagebox.showwarning("Trong", "Vui long dan VIA cookies hoac chon file .txt!")
                return

            num_concurrent = int(concurrent_var.get())
            total = len(lines)
            status_label.configure(text=f"Dang import {total} tai khoan ({num_concurrent} luong)...")
            result_text.configure(state="normal")
            result_text.delete("1.0", "end")
            result_text.configure(state="disabled")

            def on_progress(acc_name, msg, current, total_count):
                def update():
                    if total_count > 0:
                        progress_var.set(current / total_count * 100)
                    status_label.configure(text=f"[{current}/{total_count}] {acc_name}: {msg}")
                    result_text.configure(state="normal")
                    result_text.insert("end", f"[{current}/{total_count}] {acc_name}: {msg}\n")
                    result_text.see("end")
                    result_text.configure(state="disabled")
                dlg.after(0, update)

            def run():
                import asyncio
                from bulk_importer import BulkImporter

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                importer = BulkImporter(max_concurrent=num_concurrent)
                importer.set_progress_callback(on_progress)

                try:
                    results = loop.run_until_complete(importer.import_from_lines(lines))
                    summary = importer.get_summary()

                    def show_result():
                        progress_var.set(100)
                        ok = summary["success"]
                        fail = summary["failed"]
                        status_label.configure(
                            text=f"HOAN THANH: {ok} thanh cong, {fail} that bai (tong: {summary['total']})")
                        self.refresh_accounts()

                        if fail > 0:
                            result_text.configure(state="normal")
                            result_text.insert("end", "\n--- THAT BAI ---\n")
                            for r in summary["results"]:
                                if not r["success"]:
                                    result_text.insert("end", f"  {r['account']}: {r['error']}\n")
                            result_text.configure(state="disabled")

                        messagebox.showinfo("Hoan Thanh",
                            f"Da import xong!\n\n"
                            f"Thanh cong: {ok}\n"
                            f"That bai: {fail}\n"
                            f"Tong: {summary['total']}")
                    dlg.after(0, show_result)
                except Exception as e:
                    dlg.after(0, lambda: status_label.configure(text=f"LOI: {e}"))
                    dlg.after(0, lambda: messagebox.showerror("Loi", str(e)))
                finally:
                    loop.close()

            threading.Thread(target=run, daemon=True).start()

        ttk.Button(btn_bar, text="Chon File .txt", command=load_file).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="BAT DAU IMPORT", style="Accent.TButton",
                   command=start_import).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Dong", command=dlg.destroy).pack(side="left", padx=4)

    # ═══ TAB: Create Video ════════════════════════════════════════════════

    def _build_tab_create_video(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Tao Video  ")

        # Top section
        top = ttk.Frame(tab)
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="Tao Video tu Prompt", style="Title.TLabel").pack(anchor="w")

        # Account selector
        sel_frame = ttk.Frame(tab)
        sel_frame.pack(fill="x", padx=8)

        ttk.Label(sel_frame, text="Tai khoan:").pack(side="left")
        self.video_account_var = tk.StringVar()
        self.video_account_cb = ttk.Combobox(sel_frame, textvariable=self.video_account_var,
                                              state="readonly", width=20)
        self.video_account_cb.pack(side="left", padx=8)

        ttk.Button(sel_frame, text="Refresh", command=self._refresh_video_accounts).pack(side="left")

        # Prompt
        ttk.Label(tab, text="Prompt:").pack(padx=8, pady=(8, 2), anchor="w")
        self.prompt_text = tk.Text(tab, height=6, bg=BG_INPUT, fg=FG, insertbackground=FG,
                                   font=("Segoe UI", 10), wrap="word")
        self.prompt_text.pack(fill="x", padx=8)

        # Options row
        opts = ttk.Frame(tab)
        opts.pack(fill="x", padx=8, pady=8)

        ttk.Label(opts, text="Mode:").grid(row=0, column=0, padx=4)
        self.mode_var = tk.StringVar(value="standard")
        ttk.Combobox(opts, textvariable=self.mode_var, values=["standard", "fast"],
                     state="readonly", width=10).grid(row=0, column=1, padx=4)

        ttk.Label(opts, text="Ratio:").grid(row=0, column=2, padx=4)
        self.ratio_var = tk.StringVar(value="16:9")
        ttk.Combobox(opts, textvariable=self.ratio_var, values=["16:9", "9:16", "1:1"],
                     state="readonly", width=8).grid(row=0, column=3, padx=4)

        ttk.Label(opts, text="Model:").grid(row=0, column=4, padx=4)
        self.model_var = tk.StringVar(value="2.5")
        ttk.Combobox(opts, textvariable=self.model_var, values=["2.5", "2.0"],
                     state="readonly", width=8).grid(row=0, column=5, padx=4)

        ttk.Label(opts, text="Upscale:").grid(row=0, column=6, padx=4)
        self.upscale_var = tk.StringVar(value="4K")
        ttk.Combobox(opts, textvariable=self.upscale_var, values=["off", "2K", "4K"],
                     state="readonly", width=8).grid(row=0, column=7, padx=4)

        # Multi-thread Worker Option
        ttk.Label(opts, text="So luong Luong:").grid(row=0, column=8, padx=4)
        self.workers_var = tk.StringVar(value="5")
        ttk.Combobox(opts, textvariable=self.workers_var,
                     values=["1", "2", "3", "5", "10", "15", "20"],
                     state="readonly", width=4).grid(row=0, column=9, padx=4)

        # Create buttons
        btn_bar = ttk.Frame(tab)
        btn_bar.pack(pady=8)
        self.btn_create = ttk.Button(btn_bar, text="Tao Video (Don)", style="Accent.TButton",
                                      command=self.create_video)
        self.btn_create.pack(side="left", padx=4)

        self.btn_batch = ttk.Button(btn_bar, text="🚀 Chay Hang Loat (Da Luong)", style="Accent.TButton",
                                     command=self.create_batch_video)
        self.btn_batch.pack(side="left", padx=4)

        # Progress
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(tab, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", padx=8)

        self.job_status_label = ttk.Label(tab, text="San sang tao video (Ho tro 1-10 luong song song qua Cookie Pool)", style="Dim.TLabel")
        self.job_status_label.pack(pady=4)

        # Log console
        self.log_text = scrolledtext.ScrolledText(tab, height=8, bg="#0a0a15", fg="#00ff88",
                                                   insertbackground="#00ff88", font=("Consolas", 9),
                                                   state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=(4, 8))

    def _refresh_video_accounts(self):
        accounts = self.account_manager.get_all()
        names = [a["name"] for a in accounts]
        self.video_account_cb["values"] = names
        if names and not self.video_account_var.get():
            self.video_account_var.set(names[0])

    def create_video(self):
        prompt = self.prompt_text.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("Thieu prompt", "Vui long nhap prompt truoc!")
            return

        account_name = self.video_account_var.get()
        if not account_name:
            self._refresh_video_accounts()
            account_name = self.video_account_var.get()
            if not account_name:
                messagebox.showwarning("Thieu tai khoan", "Them tai khoan truoc!")
                return

        self.btn_create.configure(state="disabled")
        self.job_status_label.configure(text="Dang khoi tao...", style="TLabel")
        self.progress_var.set(10)
        self.log(f"Bat dau tao video voi account: {account_name}")

        # Run in background thread
        def run():
            try:
                import asyncio
                from browser_manager import BrowserManager
                from dola_automation import DolaAutomation
                from video_downloader import VideoDownloader

                bm = BrowserManager()
                da = DolaAutomation()
                vd = VideoDownloader()

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                acc = self.account_manager.get_account(account_name)
                proxy_url = acc.proxy if acc else ""

                mode = self.mode_var.get()
                ratio = self.ratio_var.get()
                model = self.model_var.get()
                upscale = self.upscale_var.get()

                job = self.job_manager.create_job(
                    prompt=prompt,
                    account_name=account_name,
                    aspect_ratio=ratio,
                    mode=mode,
                    model_version=model,
                    enable_upscale=upscale != "off",
                    upscale_target=upscale if upscale != "off" else "2K",
                )

                self.current_job_id = job.id
                self._update_status(f"Job {job.id} da tao. Dang ket noi Chrome...", 20)

                port = loop.run_until_complete(bm.launch_chrome(account_name, proxy_url=proxy_url, minimized=True))
                self._update_status("Chrome da ket noi. Dang mo Dola...", 30)

                browser = loop.run_until_complete(bm.connect_playwright(account_name))
                if not browser:
                    raise Exception("Không thể kết nối Playwright tới Chrome")
                page = loop.run_until_complete(bm.get_page(account_name))
                if not page:
                    raise Exception("Không có page nào mở trong Chrome")
                self._update_status("Dang gui prompt den Dola AI...", 40)

                video_url = loop.run_until_complete(da.execute_generation_flow(
                    page, prompt,
                    aspect_ratio=ratio,
                    model_version=model,
                    mode=mode,
                    duration_target=31,
                    progress_callback=lambda msg: self._update_status(msg, 50),
                ))

                if video_url:
                    self._update_status("Dang tai video goc tu Dola...", 70)
                    video_path = loop.run_until_complete(vd.download_video(video_url, output_filename=f"{job.id}.mp4"))

                    if video_path and os.path.exists(video_path):
                        final_path = video_path
                        # Thực hiện nâng cấp Upscale nếu bật (2K / 4K)
                        if upscale != "off":
                            self._update_status(f"Dang nang cap video len {upscale} bang FFmpeg...", 85)
                            upscaled_path = loop.run_until_complete(vd.upscale_video(video_path, target=upscale))
                            if upscaled_path and os.path.exists(upscaled_path):
                                final_path = upscaled_path

                        self.job_manager.update_job(job.id, status="completed", output_path=final_path, completed_at=time.time())
                        self._update_status(f"Hoan thanh! Video: {os.path.basename(final_path)}", 100)
                        self.log(f"Video ({upscale if upscale != 'off' else '1080p'}) da luu thanh cong: {final_path}")
                    else:
                        self.job_manager.update_job(job.id, status="failed", error="Khong tai duoc video", completed_at=time.time())
                        self._update_status("Loi tai video!", 0)
                else:
                    self.job_manager.update_job(job.id, status="failed", error="Khong tao duoc video", completed_at=time.time())
                    self._update_status("Loi: Khong tao duoc video tu Dola", 0)

                loop.run_until_complete(bm.close_chrome(account_name))
                loop.close()

            except Exception as e:
                self._update_status(f"Loi: {e}", 0)
                self.log(f"LOI: {e}")
            finally:
                self.root.after(0, lambda: self.btn_create.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def extract_and_save_session_dialog(self):
        """Trích xuất và lưu session Dola (Cookies + LocalStorage) từ Chrome đang mở."""
        name = self.get_selected_account()
        if not name:
            return

        def do_extract():
            try:
                import asyncio
                from browser_manager import BrowserManager
                from session_store import SessionStore
                
                bm = BrowserManager()
                ss = SessionStore()
                port = bm._get_port(name)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                pw = loop.run_until_complete(bm._ensure_playwright())
                browser = loop.run_until_complete(pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}"))
                ctx = browser.contexts[0]
                page = ctx.pages[0] if ctx.pages else loop.run_until_complete(ctx.new_page())

                cookies, ls = loop.run_until_complete(ss.extract_from_browser(ctx, page))
                ss.save_session(name, cookies, ls)

                # Mark in account
                acc = self.account_manager.get_account(name)
                if acc:
                    acc.dola_session_saved = True
                    self.account_manager.save()

                loop.run_until_complete(browser.close())
                loop.close()

                self.root.after(0, self.refresh_accounts)
                self.log(f"🎉 Da luu Dola Session cho '{name}' ({len(cookies)} cookies, ~5KB).")
                messagebox.showinfo("Thanh Cong", f"Da luu Session Dola cho account '{name}' thanh cong!\nBan co the dung account nay de tao video da luong.")
            except Exception as e:
                self.log(f"⚠️ Loi trich xuat session cho '{name}': {e}. Hay chac chan Chrome account dang mo.")
                messagebox.showwarning("Loi", f"Chua ket noi duoc Chrome '{name}'.\nHay bam '🌐 Mo Chrome' truoc, login Dola xong roi moi bam 'Luu Session'.")

        threading.Thread(target=do_extract, daemon=True).start()

    def create_batch_video(self):
        """Chạy tạo video hàng loạt đa luồng (1-10 workers)."""
        prompt = self.prompt_text.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("Thieu Prompt", "Vui long nhap Prompt tao video truoc!")
            return

        # Tìm tất cả accounts có session và còn quota
        avail_accounts = [
            a["name"] for a in self.account_manager.get_all()
            if self.session_store.has_session(a["name"]) and (a.get("quota_max", 4) - a.get("quota_used", 0) > 0)
        ]

        if not avail_accounts:
            # Nếu không có account nào có session, lấy tất cả active accounts
            avail_accounts = [
                a["name"] for a in self.account_manager.get_all()
                if (a.get("quota_max", 4) - a.get("quota_used", 0) > 0)
            ]

        if not avail_accounts:
            messagebox.showwarning("Het Quota", "Khong co account nao san sang / con quota de chay!")
            return

        num_workers = int(self.workers_var.get())
        num_workers = min(num_workers, len(avail_accounts))

        ratio = self.ratio_var.get()
        model = self.model_var.get()
        upscale = self.upscale_var.get()
        mode = self.mode_var.get()

        self.btn_batch.configure(state="disabled")
        self.btn_create.configure(state="disabled")
        self.log(f"🚀 Bat dau chay Da Luong: {len(avail_accounts)} accounts tren {num_workers} workers...")

        def run_batch():
            try:
                import asyncio
                from worker_pool import WorkerPool

                wp = WorkerPool(max_workers=num_workers)
                
                def on_prog(wid, jid, msg):
                    self.log(f"[Worker #{wid}] {msg}")
                    self._update_status(f"Worker #{wid}: {msg}", 50)

                def on_done(job):
                    if job.status == "completed":
                        self.log(f"✅ Job {job.id} ({job.account_name}) HOAN THANH -> {job.output_path}")
                        self.account_manager.deduct_quota(job.account_name, points=2 if job.duration_target >= 30 else 1)
                        self.root.after(0, self.refresh_accounts)
                    else:
                        self.log(f"❌ Job {job.id} ({job.account_name}) THAT BAI: {job.error}")

                wp.set_callbacks(on_progress=on_prog, on_job_done=on_done)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # Submit batch jobs
                for acc_name in avail_accounts:
                    wp.submit_job(
                        account_name=acc_name,
                        prompt=prompt,
                        aspect_ratio=ratio,
                        model_version=model,
                        mode=mode,
                        duration_target=31,
                        upscale=upscale,
                    )

                loop.run_until_complete(wp.start(num_workers))

                # Wait until all jobs done
                while True:
                    st = wp.get_status()
                    if st["active_jobs"] == 0 and st["queue_size"] == 0:
                        break
                    time.sleep(2)

                loop.run_until_complete(wp.stop())
                loop.close()

                self._update_status("Tat ca cac luong da hoan thanh!", 100)
                self.log("🎉 TOAN BO BATCH JOBS DA HOAN THANH!")
                messagebox.showinfo("Hoan Thanh", f"Da chay xong toan bo {len(avail_accounts)} video!")
            except Exception as e:
                self.log(f"LOI BATCH: {e}")
                self._update_status(f"Loi Batch: {e}", 0)
            finally:
                self.root.after(0, lambda: self.btn_batch.configure(state="normal"))
                self.root.after(0, lambda: self.btn_create.configure(state="normal"))

        threading.Thread(target=run_batch, daemon=True).start()

    def _update_status(self, text, progress):
        self.root.after(0, lambda: self.job_status_label.configure(text=text))
        self.root.after(0, lambda: self.progress_var.set(progress))
        self.log(text)

    # ═══ TAB: Gallery ═════════════════════════════════════════════════════

    def _build_tab_gallery(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Video Gallery  ")

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x", padx=8, pady=8)

        ttk.Label(toolbar, text="Video da tao", style="Title.TLabel").pack(side="left")
        ttk.Button(toolbar, text="Refresh", command=self.refresh_gallery).pack(side="right", padx=4)
        ttk.Button(toolbar, text="Mo thu muc Output",
                   command=lambda: os.startfile(OUTPUT_DIR)).pack(side="right", padx=4)

        cols = ("filename", "size", "date")
        self.gallery_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        self.gallery_tree.heading("filename", text="Ten file")
        self.gallery_tree.heading("size", text="Kich thuoc")
        self.gallery_tree.heading("date", text="Ngay tao")

        self.gallery_tree.column("filename", width=400)
        self.gallery_tree.column("size", width=100)
        self.gallery_tree.column("date", width=200)

        self.gallery_tree.pack(fill="both", expand=True, padx=8, pady=4)

        self.refresh_gallery()

    def refresh_gallery(self):
        for item in self.gallery_tree.get_children():
            self.gallery_tree.delete(item)

        if os.path.isdir(OUTPUT_DIR):
            files = sorted(
                [f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith((".mp4", ".webm", ".mkv"))],
                key=lambda f: os.path.getmtime(os.path.join(OUTPUT_DIR, f)),
                reverse=True
            )
            for f in files:
                fpath = os.path.join(OUTPUT_DIR, f)
                size_mb = os.path.getsize(fpath) / (1024 * 1024)
                mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(fpath)))
                self.gallery_tree.insert("", "end", values=(f, f"{size_mb:.1f} MB", mtime))

    # ═══ TAB: Proxy ═══════════════════════════════════════════════════════

    def _build_tab_proxy(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Proxy  ")

        ttk.Label(tab, text="Cau hinh Proxy Pool", style="Title.TLabel").pack(padx=8, pady=8, anchor="w")

        ttk.Label(tab, text="Danh sach API Key (1 key moi dong):").pack(padx=8, anchor="w")
        self.proxy_text = tk.Text(tab, height=6, bg=BG_INPUT, fg=FG, insertbackground=FG,
                                   font=("Consolas", 9))
        self.proxy_text.pack(fill="x", padx=8, pady=4)

        opts = ttk.Frame(tab)
        opts.pack(fill="x", padx=8)

        ttk.Label(opts, text="Nha mang:").grid(row=0, column=0, padx=4)
        self.carrier_var = tk.StringVar(value="random")
        ttk.Combobox(opts, textvariable=self.carrier_var,
                     values=["random", "viettel", "vinaphone", "mobifone"],
                     state="readonly", width=12).grid(row=0, column=1, padx=4)

        ttk.Label(opts, text="Tinh thanh:").grid(row=0, column=2, padx=4)
        self.province_var = tk.StringVar(value="0")
        ttk.Combobox(opts, textvariable=self.province_var,
                     values=["0", "1", "2", "3"],
                     state="readonly", width=8).grid(row=0, column=3, padx=4)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(pady=8)
        ttk.Button(btn_frame, text="Luu Proxy Pool", style="Accent.TButton",
                   command=self.save_proxy).pack(side="left", padx=4)

        # Load existing
        info = self.proxy_manager.get_pool_info()
        keys = info.get("proxies", [])
        if keys:
            self.proxy_text.insert("1.0", "\n".join(keys))
        self.carrier_var.set(info.get("5stars_carrier", "random"))
        self.province_var.set(str(info.get("5stars_province", "0")))

    def save_proxy(self):
        keys = [k.strip() for k in self.proxy_text.get("1.0", "end").strip().split("\n") if k.strip()]
        self.proxy_manager.update_pool(keys, self.carrier_var.get(), self.province_var.get())
        self.log("Da luu Proxy Pool!")
        messagebox.showinfo("OK", "Da luu cau hinh Proxy Pool!")

    # ═══ TAB: Settings ════════════════════════════════════════════════════

    def _build_tab_settings(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  Cai dat  ")

        ttk.Label(tab, text="Cai dat chung", style="Title.TLabel").pack(padx=8, pady=8, anchor="w")

        frame = ttk.Frame(tab)
        frame.pack(fill="x", padx=20, pady=4)

        ttk.Label(frame, text="Chrome:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Label(frame, text=CHROME_PATH or "Khong tim thay!",
                  style="Green.TLabel" if CHROME_PATH else "Red.TLabel").grid(row=0, column=1, sticky="w", pady=4, padx=8)

        ttk.Label(frame, text="Extension:").grid(row=1, column=0, sticky="w", pady=4)
        ext_ok = os.path.isdir(EXTENSION_DIR)
        ttk.Label(frame, text=EXTENSION_DIR if ext_ok else "Khong tim thay!",
                  style="Green.TLabel" if ext_ok else "Red.TLabel").grid(row=1, column=1, sticky="w", pady=4, padx=8)

        ttk.Label(frame, text="Output dir:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Label(frame, text=OUTPUT_DIR).grid(row=2, column=1, sticky="w", pady=4, padx=8)

        ttk.Label(frame, text="Data dir:").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Label(frame, text=DATA_DIR).grid(row=3, column=1, sticky="w", pady=4, padx=8)

        ttk.Label(frame, text="API Server:").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Label(frame, text=f"http://{API_HOST}:{API_PORT} (cho Extension)").grid(row=4, column=1, sticky="w", pady=4, padx=8)

        # Open folders
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(pady=16)
        ttk.Button(btn_frame, text="Mo thu muc Output",
                   command=lambda: os.startfile(OUTPUT_DIR)).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Mo thu muc Data",
                   command=lambda: os.startfile(DATA_DIR)).pack(side="left", padx=4)

    # ─── Status Bar ───────────────────────────────────────────────────────

    def _build_status_bar(self):
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=12, pady=(0, 6))

        ttk.Label(bar, text=f"Chrome: {'OK' if CHROME_PATH else 'NOT FOUND'}",
                  style="Green.TLabel" if CHROME_PATH else "Red.TLabel").pack(side="left", padx=8)

        ext_ok = os.path.isdir(EXTENSION_DIR)
        ttk.Label(bar, text=f"Extension: {'OK' if ext_ok else 'NOT FOUND'}",
                  style="Green.TLabel" if ext_ok else "Red.TLabel").pack(side="left", padx=8)

        accs = self.account_manager.get_all()
        ttk.Label(bar, text=f"Accounts: {len(accs)}", style="Dim.TLabel").pack(side="left", padx=8)

    # ─── Logging ──────────────────────────────────────────────────────────

    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        def do_log():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", f"[{timestamp}] {msg}\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after(0, do_log)

    # ─── API Server (Background Thread) ───────────────────────────────────

    def _start_api_server(self):
        """Start FastAPI server in background thread for Extension communication."""
        def run_server():
            try:
                import uvicorn
                uvicorn.run(
                    "api_server:app",
                    host=API_HOST,
                    port=API_PORT,
                    reload=False,
                    log_level="warning",
                    access_log=False,
                )
            except Exception as e:
                self.log(f"API Server error: {e}")

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        # Check server ready after 2s
        def check_server():
            try:
                import urllib.request
                urllib.request.urlopen(f"http://{API_HOST}:{API_PORT}/api/health", timeout=2)
                self.server_label.configure(text=f"API: :{API_PORT} OK", style="Green.TLabel")
                self.log(f"API Server dang chay tai http://{API_HOST}:{API_PORT}")
            except Exception:
                self.server_label.configure(text=f"API: :{API_PORT} ...", style="Dim.TLabel")
                self.root.after(2000, check_server)

        self.root.after(2000, check_server)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    app = SeedanceGUI(root)

    # Refresh video accounts on tab change
    def on_tab_change(event):
        tab = app.notebook.index(app.notebook.select())
        if tab == 1:  # Create Video tab
            app._refresh_video_accounts()
        elif tab == 2:  # Gallery tab
            app.refresh_gallery()

    app.notebook.bind("<<NotebookTabChanged>>", on_tab_change)

    root.mainloop()


if __name__ == "__main__":
    main()
