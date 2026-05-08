import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from constants import (APP_VERSION, BG_DARK, BG_MID, ACCENT, TEXT_MAIN,
                       TAB_ACT, TAB_INACT)
from data_loader import load_config, save_config
from character_frame import CharacterFrame


# ─── Main Application Window ──────────────────────────────────────────────────
class AberrantApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.title("Aberrant Character Sheet")
        self.configure(bg=BG_DARK)
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        win_w = self.cfg.get("window_width", 1300)
        win_h = self.cfg.get("window_height", 900)
        x = (sw - win_w) // 2
        y = (sh - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.minsize(1100, 600)

        self._build_menu()
        self._build_notebook()
        self._new_tab()
        self.protocol("WM_DELETE_WINDOW", self._quit)

    # ── Menu ──────────────────────────────────────────────────────────────────
    def _build_menu(self):
        mb = tk.Menu(self, bg=BG_MID, fg=TEXT_MAIN,
                     activebackground=ACCENT, activeforeground="white",
                     tearoff=False)
        self.config(menu=mb)

        file_menu = tk.Menu(mb, bg=BG_MID, fg=TEXT_MAIN,
                            activebackground=ACCENT, activeforeground="white",
                            tearoff=False)
        mb.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Tab",   accelerator="Ctrl+N", command=self._new_tab)
        file_menu.add_command(label="Open…",     accelerator="Ctrl+O", command=self._open_tab)
        file_menu.add_separator()
        file_menu.add_command(label="Save",      accelerator="Ctrl+S",
                              command=lambda: self._active()._save() if self._active() else None)
        file_menu.add_command(label="Save As…",  accelerator="Ctrl+Shift+S",
                              command=lambda: self._active()._save_as() if self._active() else None)
        file_menu.add_separator()
        file_menu.add_command(label="Close Tab", accelerator="Ctrl+W", command=self._close_tab)
        file_menu.add_separator()
        file_menu.add_command(label="Quit",      accelerator="Ctrl+Q", command=self._quit)

        settings_menu = tk.Menu(mb, bg=BG_MID, fg=TEXT_MAIN,
                                activebackground=ACCENT, activeforeground="white",
                                tearoff=False)
        mb.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Window Size…", command=self._open_settings)

        about_menu = tk.Menu(mb, bg=BG_MID, fg=TEXT_MAIN,
                             activebackground=ACCENT, activeforeground="white",
                             tearoff=False)
        mb.add_cascade(label="About", menu=about_menu)
        about_menu.add_command(label="Help",    command=self._help)
        about_menu.add_command(label="Version", command=self._version)

        self.bind_all("<Control-n>", lambda e: self._new_tab())
        self.bind_all("<Control-o>", lambda e: self._open_tab())
        self.bind_all("<Control-s>", lambda e: self._active()._save() if self._active() else None)
        self.bind_all("<Control-S>", lambda e: self._active()._save_as() if self._active() else None)
        self.bind_all("<Control-w>", lambda e: self._close_tab())
        self.bind_all("<Control-q>", lambda e: self._quit())

    # ── Notebook ───────────────────────────────────────────────────────────────
    def _build_notebook(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook",     background=BG_DARK, borderwidth=0)
        style.configure("TNotebook.Tab", background=TAB_INACT, foreground=TEXT_MAIN,
                        padding=[12, 4], font=("Arial", 9, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", TAB_ACT)],
                  foreground=[("selected", "white")])
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=4, pady=(2, 4))
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _active(self):
        tab_id = self._notebook.select()
        return self._notebook.nametowidget(tab_id) if tab_id else None

    def _new_tab(self):
        frame = CharacterFrame(self._notebook, self.cfg,
                               on_title_change=self._refresh_tab_titles)
        self._notebook.add(frame, text=frame.get_tab_title())
        self._notebook.select(frame)

    def _open_tab(self):
        path = filedialog.askopenfilename(
            title="Open Character",
            filetypes=[("Aberrant character", "*.abe"), ("All files", "*.*")]
        )
        if not path:
            return
        frame = CharacterFrame(self._notebook, self.cfg,
                               on_title_change=self._refresh_tab_titles)
        self._notebook.add(frame, text=frame.get_tab_title())
        self._notebook.select(frame)
        frame._open_file(path)

    def _close_tab(self):
        frame = self._active()
        if not frame:
            return
        if not frame.can_close():
            return
        self._notebook.forget(frame)
        frame.destroy()
        if not self._notebook.tabs():
            self._new_tab()

    def _refresh_tab_titles(self):
        for tab_id in self._notebook.tabs():
            frame = self._notebook.nametowidget(tab_id)
            self._notebook.tab(tab_id, text=frame.get_tab_title())
        self._update_window_title()

    def _update_window_title(self):
        frame = self._active()
        if frame and frame._current_file:
            self.title(f"Aberrant — {os.path.basename(frame._current_file)}")
        else:
            self.title("Aberrant Character Sheet")

    def _on_tab_changed(self, _event):
        self._update_window_title()

    def _quit(self):
        for tab_id in list(self._notebook.tabs()):
            frame = self._notebook.nametowidget(tab_id)
            self._notebook.select(frame)
            if not frame.can_close():
                return
        self.destroy()

    # ── Settings ───────────────────────────────────────────────────────────────
    def _open_settings(self):
        win = tk.Toplevel(self, bg=BG_DARK)
        win.title("Settings — Window Size")
        win.geometry("280x160")
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Window Resolution", font=("Arial", 11, "bold"),
                 bg=BG_DARK, fg=ACCENT).pack(pady=(14, 6))

        row = tk.Frame(win, bg=BG_DARK)
        row.pack()
        tk.Label(row, text="Width:", bg=BG_DARK, fg=TEXT_MAIN,
                 font=("Arial", 9)).grid(row=0, column=0, padx=6, pady=4, sticky="e")
        w_var = tk.IntVar(value=self.cfg.get("window_width", 1300))
        tk.Spinbox(row, from_=800, to=7680, increment=10, textvariable=w_var,
                   width=7, bg=BG_MID, fg=TEXT_MAIN, buttonbackground=BG_MID,
                   font=("Arial", 9)).grid(row=0, column=1, padx=6)
        tk.Label(row, text="Height:", bg=BG_DARK, fg=TEXT_MAIN,
                 font=("Arial", 9)).grid(row=1, column=0, padx=6, pady=4, sticky="e")
        h_var = tk.IntVar(value=self.cfg.get("window_height", 900))
        tk.Spinbox(row, from_=600, to=4320, increment=10, textvariable=h_var,
                   width=7, bg=BG_MID, fg=TEXT_MAIN, buttonbackground=BG_MID,
                   font=("Arial", 9)).grid(row=1, column=1, padx=6)

        def _apply():
            try:
                w, h = int(w_var.get()), int(h_var.get())
            except (ValueError, tk.TclError):
                messagebox.showerror("Invalid", "Width and height must be integers.", parent=win)
                return
            self.cfg["window_width"] = w
            self.cfg["window_height"] = h
            save_config(self.cfg)
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
            win.destroy()

        tk.Button(win, text="Apply", command=_apply,
                  bg=ACCENT, fg="white", relief="flat",
                  font=("Arial", 9, "bold"), width=10).pack(pady=12)

    # ── About ──────────────────────────────────────────────────────────────────
    def _help(self):
        win = tk.Toplevel(self, bg=BG_DARK)
        win.title("Help")
        win.geometry("500x420")
        win.resizable(False, False)
        tk.Label(win, text="ABERRANT CHARACTER SHEET — HELP",
                 font=("Arial", 12, "bold"), bg=BG_DARK, fg=ACCENT).pack(pady=12)
        help_text = (
            "NAVIGATION\n"
            "  Use the left-side tabs to switch between sections:\n"
            "  • Attributes & Abilities — core stats and skills\n"
            "  • Advantages — backgrounds, mega-attributes, powers\n"
            "  • Combat — attacks, armor, initiative, movement\n\n"
            "DOTS\n"
            "  Click a dot to set the rating. Click the same dot\n"
            "  again to lower it. Attributes start at 1.\n\n"
            "SPECIALTIES\n"
            "  The small checkbox next to an ability dot row marks a specialty.\n\n"
            "HEALTH\n"
            "  Check boxes on the right to track wounds.\n\n"
            "QUANTUM POOL\n"
            "  Set Max and Current using the spinboxes, or click dots directly.\n\n"
            "MULTIPLE CHARACTERS\n"
            "  File → New Tab (Ctrl+N) opens a fresh character.\n"
            "  File → Open (Ctrl+O) loads a file into a new tab.\n"
            "  File → Close Tab (Ctrl+W) closes the current tab.\n\n"
            "FILES\n"
            "  Characters are saved as .abe files (JSON format).\n"
            "  Use File → Save / Save As to save your character.\n"
        )
        txt = tk.Text(win, font=("Arial", 9), bg=BG_MID, fg=TEXT_MAIN,
                      relief="flat", wrap="word", padx=12, pady=8)
        txt.insert("1.0", help_text)
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True, padx=12, pady=8)
        tk.Button(win, text="Close", command=win.destroy,
                  bg=ACCENT, fg="white", relief="flat",
                  font=("Arial", 9, "bold")).pack(pady=8)

    def _version(self):
        messagebox.showinfo("Version",
                            f"Aberrant Character Sheet\nVersion {APP_VERSION}\n\n"
                            "Based on the Aberrant RPG system\nby White Wolf Publishing.")
