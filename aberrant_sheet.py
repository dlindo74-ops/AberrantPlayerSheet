#!/usr/bin/env python3
"""
Aberrant Character Sheet Application
RPG character sheet manager for the Aberrant game system.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import sys

APP_VERSION = "1.0.0"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aberrant_config.json")

# ─── Colour palette ───────────────────────────────────────────────────────────
BG_DARK   = "#2a2a2a"
BG_MID    = "#3a3a3a"
BG_PANEL  = "#2a1a00"
BG_CARD   = "#333333"
ACCENT    = "#ff8c00"
GOLD      = "#ffd700"
TEXT_MAIN = "#f0e0c0"
TEXT_DIM  = "#997755"
DOT_FULL  = "#ff8c00"
DOT_EMPTY = "#5a4020"
TAB_ACT   = "#ff8c00"
TAB_INACT = "#3d2800"
BORDER    = "#4a3010"


def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        messagebox.showerror("Config Error", f"Cannot load config:\n{e}")
        sys.exit(1)


def empty_character(cfg):
    """Return a blank character dict matching the config structure."""
    char = {
        "birth_name": "", "nova_name": "", "series": "",
        "eruption": "", "nature": "", "allegiance": "",
        "attributes": {a: 1 for group in [cfg["physical_attributes"],
                                          cfg["mental_attributes"],
                                          cfg["social_attributes"]] for a in group},
        "abilities": {},
        "ability_specialties": {},
        "custom_abilities": {a: ["", ""] for a in
                             cfg["physical_attributes"] + cfg["mental_attributes"] + cfg["social_attributes"]},
        "backgrounds": {bg: 0 for bg in cfg.get("backgrounds", [])},
        "mega_attributes": {ma: 0 for ma in cfg["mega_attributes"]},
        "willpower_perm": 5, "willpower_temp": 5,
        "taint_perm": 0, "taint_temp": 0,
        "aberrations": "",
        "quantum": 1,
        "quantum_pool_max": 20, "quantum_pool_current": 0,
        "attacks": [{"name": "", "acc": "", "dmg": "", "rof": "", "ft": ""} for _ in range(cfg["num_attack_rows"])],
        "armors":  [{"name": "", "b": "", "l": "", "bulk": "", "ft": ""} for _ in range(cfg["num_armor_rows"])],
        "initiative": "", "walk": "", "run": "", "sprint": "",
        "soak_bashing": "", "soak_lethal": "",
        "description": "",
        "experience": ""
    }
    for attr, skills in cfg["abilities"].items():
        for skill in skills:
            char["abilities"][skill] = 0
            char["ability_specialties"][skill] = False
    return char


# ─── Dot widget ───────────────────────────────────────────────────────────────
class DotRow(tk.Frame):
    """A row of clickable dot widgets representing a 1-5 (or 0-5) rating."""

    def __init__(self, parent, max_dots=5, min_val=0, var=None, size=12,
                 on_change=None, **kwargs):
        super().__init__(parent, bg=kwargs.pop("bg", BG_CARD), **kwargs)
        self.max_dots = max_dots
        self.min_val = min_val
        self.on_change = on_change
        self.size = size
        self.var = var if var is not None else tk.IntVar(value=min_val)
        self._dots = []
        for i in range(1, max_dots + 1):
            c = tk.Canvas(self, width=size, height=size,
                          bg=self["bg"], highlightthickness=0, cursor="hand2")
            c.grid(row=0, column=i - 1, padx=1)
            c.bind("<Button-1>", lambda e, idx=i: self._click(idx))
            self._dots.append(c)
        self.var.trace_add("write", lambda *_: self._redraw())
        self._redraw()

    def _click(self, idx):
        current = self.var.get()
        # Click same dot again → go down one (but not below min)
        new_val = self.min_val if idx == current else idx
        if idx < current:
            new_val = idx
        self.var.set(new_val)
        if self.on_change:
            self.on_change(new_val)

    def _redraw(self):
        val = self.var.get()
        for i, c in enumerate(self._dots):
            filled = (i + 1) <= val
            c.delete("all")
            color = DOT_FULL if filled else DOT_EMPTY
            pad = 2
            c.create_oval(pad, pad, self.size - pad, self.size - pad,
                          fill=color, outline=ACCENT if filled else BORDER, width=1)


# ─── Check-box widget ─────────────────────────────────────────────────────────
class CheckBox(tk.Canvas):
    def __init__(self, parent, var=None, size=14, **kwargs):
        bg = kwargs.pop("bg", BG_CARD)
        super().__init__(parent, width=size, height=size,
                         bg=bg, highlightthickness=0, cursor="hand2", **kwargs)
        self.size = size
        self.var = var if var is not None else tk.BooleanVar(value=False)
        self.var.trace_add("write", lambda *_: self._redraw())
        self.bind("<Button-1>", lambda e: self.var.set(not self.var.get()))
        self._redraw()

    def _redraw(self):
        self.delete("all")
        p = 2
        s = self.size
        checked = self.var.get()
        fill = ACCENT if checked else DOT_EMPTY
        self.create_rectangle(p, p, s - p, s - p,
                              fill=fill, outline=ACCENT if checked else BORDER)
        if checked:
            self.create_line(p + 2, s // 2, s // 2, s - p - 2, fill="white", width=2)
            self.create_line(s // 2, s - p - 2, s - p - 2, p + 2, fill="white", width=2)


# ─── Scrollable frame helper ──────────────────────────────────────────────────
class ScrollFrame(tk.Frame):
    def __init__(self, parent, **kwargs):
        bg = kwargs.pop("bg", BG_MID)
        super().__init__(parent, bg=bg, **kwargs)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.inner.bind("<MouseWheel>", self._on_mousewheel)

    def _on_frame_configure(self, e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, e):
        self.canvas.itemconfig(self._win, width=e.width)

    def _on_mousewheel(self, e):
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")


# ─── Section label helper ─────────────────────────────────────────────────────
def section_label(parent, text, bg=BG_PANEL):
    f = tk.Frame(parent, bg=ACCENT, pady=1)
    f.pack(fill="x", pady=(8, 2))
    tk.Label(f, text=text, font=("Arial", 9, "bold"),
             bg=ACCENT, fg="white").pack(fill="x", padx=4, pady=2)
    return f


def card(parent, **kwargs):
    return tk.Frame(parent, bg=BG_CARD,
                    highlightbackground=BORDER, highlightthickness=1,
                    **kwargs)


# ─── Main Application ─────────────────────────────────────────────────────────
class AberrantApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.char = empty_character(self.cfg)
        self._current_file = None
        self._dirty = False
        # loaded from config in _build_attrs_tab after config is available
        self._preset_specs = self.cfg.get("ability_specialties", {})
        # runtime: skill -> list of [name_str, active_BoolVar]
        self._specialisations = {}

        self.title("Aberrant Character Sheet")
        self.configure(bg=BG_DARK)
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        win_w = min(1280, sw)
        win_h = int(sh * 0.95)
        x = (sw - win_w) // 2
        y = (sh - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.minsize(1100, 600)

        self._build_menu()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._quit)

        # Populate widgets from blank char
        self._load_char_to_ui()

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
        file_menu.add_command(label="New",     accelerator="Ctrl+N", command=self._new)
        file_menu.add_command(label="Open…",   accelerator="Ctrl+O", command=self._open)
        file_menu.add_separator()
        file_menu.add_command(label="Save",    accelerator="Ctrl+S", command=self._save)
        file_menu.add_command(label="Save As…",accelerator="Ctrl+Shift+S", command=self._save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Quit",    accelerator="Ctrl+Q", command=self._quit)

        about_menu = tk.Menu(mb, bg=BG_MID, fg=TEXT_MAIN,
                             activebackground=ACCENT, activeforeground="white",
                             tearoff=False)
        mb.add_cascade(label="About", menu=about_menu)
        about_menu.add_command(label="Help",    command=self._help)
        about_menu.add_command(label="Version", command=self._version)

        self.bind_all("<Control-n>", lambda e: self._new())
        self.bind_all("<Control-o>", lambda e: self._open())
        self.bind_all("<Control-s>", lambda e: self._save())
        self.bind_all("<Control-S>", lambda e: self._save_as())
        self.bind_all("<Control-q>", lambda e: self._quit())

    # ── Main UI skeleton ───────────────────────────────────────────────────────
    def _build_ui(self):
        # Top header (always visible)
        self._build_header()

        # Middle row: left tabs | center content | right health
        mid = tk.Frame(self, bg=BG_DARK)
        mid.pack(fill="both", expand=True, padx=6, pady=4)

        self._build_left_tabs(mid)
        self._build_center(mid)
        self._build_health_panel(mid)

        # Bottom quantum pool
        self._build_quantum_pool()

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=BG_PANEL,
                       highlightbackground=ACCENT, highlightthickness=2)
        hdr.pack(fill="x", padx=6, pady=(6, 0))

        tk.Label(hdr, text="ABERRANT CHARACTER SHEET",
                 font=("Arial", 14, "bold"),
                 bg=BG_PANEL, fg=ACCENT).grid(row=0, column=0, columnspan=6,
                                               pady=(6, 4))

        fields = [
            ("Birth Name:", "birth_name"), ("Eruption:", "eruption"),
            ("Nova Name:",  "nova_name"),  ("Nature:",   "nature"),
            ("Series:",     "series"),     ("Allegiance:", "allegiance"),
        ]
        self._hdr_vars = {}
        for i, (lbl, key) in enumerate(fields):
            r, c = divmod(i, 2)
            col_base = c * 3
            tk.Label(hdr, text=lbl, font=("Arial", 9, "bold"),
                     bg=BG_PANEL, fg=GOLD).grid(row=r + 1, column=col_base,
                                                 sticky="e", padx=(10, 2), pady=2)
            var = tk.StringVar()
            self._hdr_vars[key] = var
            var.trace_add("write", lambda *_, k=key: self._mark_dirty())
            e = tk.Entry(hdr, textvariable=var, font=("Arial", 9),
                         bg=BG_CARD, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                         relief="flat", bd=2, width=22)
            e.grid(row=r + 1, column=col_base + 1, sticky="ew", padx=(0, 8), pady=2)

        for c in range(6):
            hdr.columnconfigure(c, weight=1 if c % 3 == 1 else 0)

    # ── Left tab strip ────────────────────────────────────────────────────────
    def _build_left_tabs(self, parent):
        self._tab_frame = tk.Frame(parent, bg=BG_DARK, width=180)
        self._tab_frame.pack(side="left", fill="y", padx=(0, 4))
        self._tab_frame.pack_propagate(False)

        self._tab_buttons = {}
        tabs = [
            ("ATTRIBUTES\n& ABILITIES", "attrs"),
            ("ADVANTAGES",              "advs"),
            ("COMBAT",                  "combat"),
            ("QUANTUM\nPOWERS",        "powers"),
        ]
        for label, key in tabs:
            btn = tk.Button(self._tab_frame, text=label,
                            font=("Arial", 10, "bold"),
                            bg=TAB_INACT, fg=TEXT_MAIN,
                            activebackground=TAB_ACT, activeforeground="white",
                            relief="flat", bd=0, cursor="hand2",
                            wraplength=160, justify="center",
                            pady=14,
                            command=lambda k=key: self._switch_tab(k))
            btn.pack(fill="x", pady=2, padx=2)
            self._tab_buttons[key] = btn

        self._active_tab = None

    def _switch_tab(self, key):
        if self._active_tab == key:
            return
        self._active_tab = key
        for k, btn in self._tab_buttons.items():
            btn.config(bg=TAB_ACT if k == key else TAB_INACT)
        # Show the right frame
        for k, frame in self._tab_frames.items():
            if k == key:
                frame.pack(side="left", fill="both", expand=True)
            else:
                frame.pack_forget()

    # ── Center content ─────────────────────────────────────────────────────────
    def _build_center(self, parent):
        self._center = tk.Frame(parent, bg=BG_DARK)
        self._center.pack(side="left", fill="both", expand=True)

        self._tab_frames = {}
        self._tab_frames["attrs"]  = self._build_attrs_tab(self._center)
        self._tab_frames["advs"]   = self._build_advs_tab(self._center)
        self._tab_frames["combat"] = self._build_combat_tab(self._center)
        self._tab_frames["powers"] = self._build_powers_tab(self._center)

        # Show first tab
        self._switch_tab("attrs")

    # ── ATTRIBUTES & ABILITIES tab ────────────────────────────────────────────
    def _build_attrs_tab(self, parent):
        sf = ScrollFrame(parent, bg=BG_DARK)
        inner = sf.inner

        # Three columns: Physical | Mental | Social
        cols_frame = tk.Frame(inner, bg=BG_DARK)
        cols_frame.pack(fill="both", expand=True, padx=4, pady=4)

        groups = [
            ("PHYSICAL", self.cfg["physical_attributes"]),
            ("MENTAL",   self.cfg["mental_attributes"]),
            ("SOCIAL",   self.cfg["social_attributes"]),
        ]

        self._attr_vars   = {}
        self._ability_vars = {}
        self._spec_vars    = {}
        self._custom_ability_vars = {}

        for col_idx, (group_name, attrs) in enumerate(groups):
            col = tk.Frame(cols_frame, bg=BG_DARK)
            col.grid(row=0, column=col_idx, sticky="nsew", padx=4)
            cols_frame.columnconfigure(col_idx, weight=1)

            # Group header
            tk.Label(col, text=group_name, font=("Arial", 10, "bold"),
                     bg=BG_PANEL, fg="white").pack(fill="x", pady=(0, 4))

            for attr in attrs:
                self._build_attr_block(col, attr)

        return sf

    def _build_attr_block(self, parent, attr):
        frame = card(parent)
        frame.pack(fill="x", pady=3)

        # Attribute header row: label | [centered: attr dots — mega dots] |
        hdr = tk.Frame(frame, bg=BG_CARD)
        hdr.pack(fill="x", padx=6, pady=(4, 2))

        tk.Label(hdr, text=attr, font=("Arial", 9, "bold"),
                 bg=BG_CARD, fg=GOLD).pack(side="left")

        var = tk.IntVar(value=1)
        self._attr_vars[attr] = var
        var.trace_add("write", lambda *_: self._mark_dirty())

        # Right cluster: attr dots — mega dots (linked from advantages tab)
        right_cluster = tk.Frame(hdr, bg=BG_CARD)
        right_cluster.pack(side="right")

        dots = DotRow(right_cluster, max_dots=5, min_val=1, var=var, bg=BG_CARD)
        dots.pack(side="left")

        tk.Label(right_cluster, text=" —", font=("Arial", 9),
                 bg=BG_CARD, fg=TEXT_DIM).pack(side="left")

        # Mega-attribute canvas: live-linked to _mega_vars
        mega_name = {
            "STRENGTH": "Mega-Strength", "DEXTERITY": "Mega-Dexterity",
            "STAMINA": "Mega-Stamina", "PERCEPTION": "Mega-Perception",
            "INTELLIGENCE": "Mega-Intelligence", "WITS": "Mega-Wits",
            "APPEARANCE": "Mega-Appearance", "MANIPULATION": "Mega-Manipulation",
            "CHARISMA": "Mega-Charisma",
        }.get(attr, None)

        DOT_S = 11; PAD = 1
        mega_cv = tk.Canvas(right_cluster, bg=BG_CARD, highlightthickness=0,
                            height=DOT_S + 4, width=5 * (DOT_S + PAD * 2) + 4)
        mega_cv.pack(side="left", padx=(2, 0))

        def _draw_mega(cv=mega_cv, mn=mega_name, ds=DOT_S, p=PAD):
            cv.delete("all")
            mega_vars = getattr(self, '_mega_vars', {})
            val = mega_vars.get(mn, tk.IntVar(value=0)).get() if mn else 0
            for i in range(5):
                xc = 2 + i * (ds + p * 2) + ds // 2
                x0, y0 = xc - ds // 2, 2
                x1, y1 = xc + ds // 2, ds + 2
                filled = (i + 1) <= val
                fc = "#cc2200" if filled else DOT_EMPTY
                oc = "#ff4422" if filled else BORDER
                cv.create_oval(x0, y0, x1, y1, fill=fc, outline=oc, width=1)

        # Store draw func keyed by mega_name for later refresh
        if mega_name:
            if not hasattr(self, "_mega_attr_redraw"):
                self._mega_attr_redraw = {}
            self._mega_attr_redraw[mega_name] = _draw_mega
        _draw_mega()

        # Abilities under this attribute
        abilities = self.cfg["abilities"].get(attr, [])
        for skill in abilities:
            self._build_ability_row(frame, skill, BG_CARD)

        # Two custom ability slots per attribute
        for slot_idx in range(2):
            self._build_custom_ability_row(frame, attr, slot_idx)

    def _build_ability_row(self, parent, skill, bg_color):
        # Outer container: top row + optional overflow rows
        outer = tk.Frame(parent, bg=bg_color)
        outer.pack(fill="x", padx=6, pady=1)

        top_row = tk.Frame(outer, bg=bg_color)
        top_row.pack(fill="x")

        tk.Label(top_row, text=skill, font=("Arial", 8),
                 bg=bg_color, fg=TEXT_MAIN, width=14, anchor="w").pack(side="left")

        var = tk.IntVar(value=0)
        self._ability_vars[skill] = var
        var.trace_add("write", lambda *_: self._mark_dirty())
        dots = DotRow(top_row, max_dots=5, min_val=0, var=var, bg=bg_color)
        dots.pack(side="left", padx=(0, 2))

        spec = tk.BooleanVar(value=False)
        self._spec_vars[skill] = spec
        spec.trace_add("write", lambda *_: self._mark_dirty())
        cb = CheckBox(top_row, var=spec, bg=bg_color)
        cb.pack(side="left", padx=(0, 2))

        # + button
        plus_lbl = tk.Label(top_row, text="+", font=("Arial", 8, "bold"),
                             bg=bg_color, fg=ACCENT, cursor="hand2")
        plus_lbl.pack(side="left", padx=(0, 4))

        # Inline spec area (to the right of +, same row for first; overflow below)
        inline_frame = tk.Frame(top_row, bg=bg_color)
        inline_frame.pack(side="left", fill="x", expand=True)

        overflow_frame = tk.Frame(outer, bg=bg_color)
        # overflow not packed until needed

        self._spec_refresh_funcs = getattr(self, "_spec_refresh_funcs", {})

        def refresh_spec_tags():
            for w in inline_frame.winfo_children():
                w.destroy()
            for w in overflow_frame.winfo_children():
                w.destroy()
            overflow_frame.pack_forget()

            entries = self._specialisations.get(skill, [])
            if not entries:
                return

            # First spec inline
            first = entries[0]
            s_name, s_var = first
            _make_spec_cb(inline_frame, s_name, s_var)

            # Remaining specs in overflow rows (one per row)
            if len(entries) > 1:
                overflow_frame.pack(fill="x", padx=0)
                for entry in entries[1:]:
                    s_name2, s_var2 = entry
                    row2 = tk.Frame(overflow_frame, bg=bg_color)
                    row2.pack(fill="x")
                    # indent to align under inline
                    tk.Label(row2, text="", width=22, bg=bg_color).pack(side="left")
                    _make_spec_cb(row2, s_name2, s_var2)

        def _make_spec_cb(frame, name, bvar):
            tk.Checkbutton(frame, text=name,
                           variable=bvar,
                           font=("Arial", 7, "italic"),
                           bg=bg_color, fg=GOLD,
                           selectcolor=BG_MID,
                           activebackground=bg_color,
                           activeforeground=GOLD,
                           relief="flat", bd=0,
                           command=self._mark_dirty).pack(side="left", padx=(0, 4))

        self._spec_refresh_funcs[skill] = refresh_spec_tags

        def open_spec_menu(event, sk=skill):
            menu = tk.Menu(self, tearoff=False,
                           bg=BG_MID, fg=TEXT_MAIN,
                           activebackground=ACCENT, activeforeground="white")
            presets = self._preset_specs.get(sk, [])
            existing_names = [e[0] for e in self._specialisations.get(sk, [])]
            if presets:
                for p in presets:
                    if p not in existing_names:
                        menu.add_command(
                            label=f"Add: {p}",
                            command=lambda n=p, s=sk: self._add_specialisation(s, n, refresh_spec_tags)
                        )
                menu.add_separator()
            menu.add_command(
                label="Add custom…",
                command=lambda s=sk: self._add_custom_spec(s, refresh_spec_tags)
            )
            if existing_names:
                menu.add_separator()
                for nm in existing_names:
                    menu.add_command(
                        label=f"Remove: {nm}",
                        command=lambda n=nm, s=sk: self._remove_specialisation(s, n, refresh_spec_tags)
                    )
            menu.tk_popup(event.x_root, event.y_root)

        plus_lbl.bind("<Button-1>", open_spec_menu)
        refresh_spec_tags()

    def _add_specialisation(self, skill, name, refresh_func):
        if skill not in self._specialisations:
            self._specialisations[skill] = []
        names = [e[0] for e in self._specialisations[skill]]
        if name not in names:
            bv = tk.BooleanVar(value=False)
            bv.trace_add("write", lambda *_: self._mark_dirty())
            self._specialisations[skill].append([name, bv])
            self._mark_dirty()
        refresh_func()

    def _add_custom_spec(self, skill, refresh_func):
        win = tk.Toplevel(self, bg=BG_DARK)
        win.title("Add Specialisation")
        win.geometry("280x110")
        win.resizable(False, False)
        win.grab_set()
        tk.Label(win, text=f"Specialisation for {skill}:",
                 font=("Arial", 9), bg=BG_DARK, fg=TEXT_MAIN).pack(pady=(12, 4))
        entry_var = tk.StringVar()
        e = tk.Entry(win, textvariable=entry_var, font=("Arial", 9),
                     bg=BG_CARD, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                     relief="flat", width=24)
        e.pack(padx=16)
        e.focus_set()
        def confirm():
            name = entry_var.get().strip()
            if name:
                self._add_specialisation(skill, name, refresh_func)
            win.destroy()
        e.bind("<Return>", lambda _: confirm())
        tk.Button(win, text="Add", command=confirm,
                  bg=ACCENT, fg="white", relief="flat",
                  font=("Arial", 9, "bold")).pack(pady=8)

    def _remove_specialisation(self, skill, name, refresh_func):
        if skill in self._specialisations:
            self._specialisations[skill] = [
                e for e in self._specialisations[skill] if e[0] != name
            ]
            self._mark_dirty()
        refresh_func()

    def _build_custom_ability_row(self, parent, attr, slot_idx):
        row = tk.Frame(parent, bg=BG_CARD)
        row.pack(fill="x", padx=6, pady=1)

        key = f"{attr}__custom_{slot_idx}"
        name_var = tk.StringVar()
        val_var  = tk.IntVar(value=0)
        self._custom_ability_vars[key] = (name_var, val_var)
        name_var.trace_add("write", lambda *_: self._mark_dirty())
        val_var.trace_add("write",  lambda *_: self._mark_dirty())

        e = tk.Entry(row, textvariable=name_var, font=("Arial", 8),
                     bg=BG_MID, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                     relief="flat", width=14)
        e.pack(side="left")

        dots = DotRow(row, max_dots=5, min_val=0, var=val_var, bg=BG_CARD)
        dots.pack(side="left", padx=4)

    # ── ADVANTAGES tab ────────────────────────────────────────────────────────
    def _build_advs_tab(self, parent):
        sf = ScrollFrame(parent, bg=BG_DARK)
        inner = sf.inner

        cols = tk.Frame(inner, bg=BG_DARK)
        cols.pack(fill="both", expand=True, padx=4, pady=4)
        for c in range(3):
            cols.columnconfigure(c, weight=1)

        # ── Column 0: Backgrounds, Willpower, Taint, Quantum ──
        col0 = tk.Frame(cols, bg=BG_DARK)
        col0.grid(row=0, column=0, sticky="nsew", padx=4)

        section_label(col0, "BACKGROUNDS")
        self._bg_vars = {}   # name -> IntVar
        for bg_name in self.cfg.get("backgrounds", []):
            row = card(col0)
            row.pack(fill="x", pady=2)
            vv = tk.IntVar(value=0)
            vv.trace_add("write", lambda *_: self._mark_dirty())
            self._bg_vars[bg_name] = vv
            tk.Label(row, text=bg_name, font=("Arial", 8),
                     bg=BG_CARD, fg=TEXT_MAIN, width=12, anchor="w").pack(side="left", padx=4, pady=3)
            DotRow(row, max_dots=5, var=vv, bg=BG_CARD).pack(side="left")

        # Willpower
        section_label(col0, "WILLPOWER")
        wp_frame = card(col0)
        wp_frame.pack(fill="x", pady=2, padx=2)
        tk.Label(wp_frame, text="Permanent:", font=("Arial", 8),
                 bg=BG_CARD, fg=TEXT_MAIN).pack(side="left", padx=4)
        self._wp_perm_var = tk.IntVar(value=5)
        self._wp_perm_var.trace_add("write", lambda *_: self._mark_dirty())
        DotRow(wp_frame, max_dots=10, min_val=1, var=self._wp_perm_var, bg=BG_CARD).pack(side="left")

        wp2 = card(col0)
        wp2.pack(fill="x", pady=2, padx=2)
        tk.Label(wp2, text="Temporary:", font=("Arial", 8),
                 bg=BG_CARD, fg=TEXT_MAIN).pack(side="left", padx=4)
        self._wp_temp_var = tk.IntVar(value=5)
        self._wp_temp_var.trace_add("write", lambda *_: self._mark_dirty())
        self._wp_temp_checks = self._build_dot_checks(wp2, 10, self._wp_temp_var)

        # Taint
        section_label(col0, "TAINT")
        t1 = card(col0)
        t1.pack(fill="x", pady=2, padx=2)
        tk.Label(t1, text="Permanent:", font=("Arial", 8),
                 bg=BG_CARD, fg=TEXT_MAIN).pack(side="left", padx=4)
        self._taint_perm_var = tk.IntVar(value=0)
        self._taint_perm_var.trace_add("write", lambda *_: self._mark_dirty())
        DotRow(t1, max_dots=10, min_val=0, var=self._taint_perm_var, bg=BG_CARD).pack(side="left")

        t2 = card(col0)
        t2.pack(fill="x", pady=2, padx=2)
        tk.Label(t2, text="Temporary:", font=("Arial", 8),
                 bg=BG_CARD, fg=TEXT_MAIN).pack(side="left", padx=4)
        self._taint_temp_var = tk.IntVar(value=0)
        self._taint_temp_var.trace_add("write", lambda *_: self._mark_dirty())
        self._build_dot_checks(t2, 10, self._taint_temp_var)

        # Aberrations
        section_label(col0, "ABERRATIONS")
        aber_frame = card(col0)
        aber_frame.pack(fill="x", pady=2, padx=2)
        self._aberr_var = tk.StringVar()
        self._aberr_var.trace_add("write", lambda *_: self._mark_dirty())
        tk.Entry(aber_frame, textvariable=self._aberr_var,
                 font=("Arial", 8), bg=BG_MID, fg=TEXT_MAIN,
                 insertbackground=TEXT_MAIN, relief="flat").pack(fill="x", padx=4, pady=3)

        # Quantum attribute
        section_label(col0, "QUANTUM")
        qf = card(col0)
        qf.pack(fill="x", pady=2, padx=2)
        tk.Label(qf, text="Quantum:", font=("Arial", 8),
                 bg=BG_CARD, fg=TEXT_MAIN).pack(side="left", padx=4)
        self._quantum_attr_var = tk.IntVar(value=1)
        self._quantum_attr_var.trace_add("write", lambda *_: self._mark_dirty())
        DotRow(qf, max_dots=10, min_val=1, var=self._quantum_attr_var, bg=BG_CARD).pack(side="left")

        # ── Column 1: Mega-Attributes ──
        col1 = tk.Frame(cols, bg=BG_DARK)
        col1.grid(row=0, column=1, sticky="nsew", padx=4)
        section_label(col1, "MEGA-ATTRIBUTES")
        self._mega_vars = {}
        self._mega_enhancements    = {}   # ma -> [[name, BoolVar], ...]
        self._mega_enh_refresh     = {}   # ma -> refresh_func
        preset_enhs = self.cfg.get("mega_attribute_enhancements", {})

        for ma in self.cfg["mega_attributes"]:
            outer = card(col1)
            outer.pack(fill="x", pady=2)

            top_row = tk.Frame(outer, bg=BG_CARD)
            top_row.pack(fill="x")

            tk.Label(top_row, text=ma, font=("Arial", 8),
                     bg=BG_CARD, fg=TEXT_MAIN, width=18, anchor="w").pack(side="left", padx=4, pady=3)

            v = tk.IntVar(value=0)
            v.trace_add("write", lambda *_: self._mark_dirty())
            self._mega_vars[ma] = v
            DotRow(top_row, max_dots=5, var=v, bg=BG_CARD).pack(side="left", padx=2)

            # Enhancement inline display
            inline_f  = tk.Frame(top_row, bg=BG_CARD)
            inline_f.pack(side="left", fill="x", expand=True)
            overflow_f = tk.Frame(outer, bg=BG_CARD)

            def _make_enh_cb(frame, name, bvar, bg=BG_CARD):
                tk.Checkbutton(frame, text=name, variable=bvar,
                               font=("Arial", 7, "italic"),
                               bg=bg, fg=GOLD,
                               selectcolor=BG_MID,
                               activebackground=bg, activeforeground=GOLD,
                               relief="flat", bd=0,
                               command=self._mark_dirty).pack(side="left", padx=(0, 4))

            def _refresh_enh(ma=ma, inf=inline_f, ovf=overflow_f):
                for w in inf.winfo_children(): w.destroy()
                for w in ovf.winfo_children(): w.destroy()
                ovf.pack_forget()
                entries = self._mega_enhancements.get(ma, [])
                if not entries: return
                _make_enh_cb(inf, entries[0][0], entries[0][1])
                if len(entries) > 1:
                    ovf.pack(fill="x", padx=0)
                    for entry in entries[1:]:
                        r2 = tk.Frame(ovf, bg=BG_CARD)
                        r2.pack(fill="x")
                        tk.Label(r2, text="", width=24, bg=BG_CARD).pack(side="left")
                        _make_enh_cb(r2, entry[0], entry[1])

            self._mega_enh_refresh[ma] = _refresh_enh
            # Redraw attr tab mega-dots whenever this var changes
            def _on_mega_change(*_, _mn=ma):
                fn = getattr(self, '_mega_attr_redraw', {}).get(_mn)
                if fn: fn()
            v.trace_add('write', _on_mega_change)

            def _open_enh_menu(event, _ma=ma, _rf=_refresh_enh):
                menu = tk.Menu(self, tearoff=False,
                               bg=BG_MID, fg=TEXT_MAIN,
                               activebackground=ACCENT, activeforeground="white")
                presets   = preset_enhs.get(_ma, [])
                existing  = [e[0] for e in self._mega_enhancements.get(_ma, [])]
                if presets:
                    for p in presets:
                        if p not in existing:
                            menu.add_command(
                                label=f"Add: {p}",
                                command=lambda n=p, m=_ma, r=_rf:
                                    self._add_mega_enhancement(m, n, r))
                    menu.add_separator()
                menu.add_command(label="Add custom…",
                                 command=lambda m=_ma, r=_rf:
                                     self._add_custom_mega_enh(m, r))
                if existing:
                    menu.add_separator()
                    for nm in existing:
                        menu.add_command(
                            label=f"Remove: {nm}",
                            command=lambda n=nm, m=_ma, r=_rf:
                                self._remove_mega_enhancement(m, n, r))
                menu.tk_popup(event.x_root, event.y_root)

            plus = tk.Label(top_row, text="+", font=("Arial", 8, "bold"),
                            bg=BG_CARD, fg=ACCENT, cursor="hand2")
            plus.pack(side="left", padx=(0, 4))
            plus.bind("<Button-1>", _open_enh_menu)
            _refresh_enh()

        return sf

    # ── QUANTUM POWERS tab (blank for now) ───────────────────────────────────
    def _build_powers_tab(self, parent):
        sf = ScrollFrame(parent, bg=BG_DARK)
        inner = sf.inner
        tk.Label(inner, text="QUANTUM POWERS",
                 font=("Arial", 14, "bold"), bg=BG_DARK, fg=ACCENT).pack(pady=(30, 8))
        tk.Label(inner, text="This section will be developed in a future update.",
                 font=("Arial", 10), bg=BG_DARK, fg=TEXT_DIM).pack()
        return sf

    def _add_mega_enhancement(self, ma, name, refresh_func):
        if ma not in self._mega_enhancements:
            self._mega_enhancements[ma] = []
        if name not in [e[0] for e in self._mega_enhancements[ma]]:
            bv = tk.BooleanVar(value=False)
            bv.trace_add("write", lambda *_: self._mark_dirty())
            self._mega_enhancements[ma].append([name, bv])
            self._mark_dirty()
        refresh_func()

    def _add_custom_mega_enh(self, ma, refresh_func):
        win = tk.Toplevel(self, bg=BG_DARK)
        win.title("Add Enhancement")
        win.geometry("280x110")
        win.resizable(False, False)
        win.grab_set()
        tk.Label(win, text=f"Enhancement for {ma}:",
                 font=("Arial", 9), bg=BG_DARK, fg=TEXT_MAIN).pack(pady=(12, 4))
        ev = tk.StringVar()
        e = tk.Entry(win, textvariable=ev, font=("Arial", 9),
                     bg=BG_CARD, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                     relief="flat", width=24)
        e.pack(padx=16)
        e.focus_set()
        def confirm():
            name = ev.get().strip()
            if name:
                self._add_mega_enhancement(ma, name, refresh_func)
            win.destroy()
        e.bind("<Return>", lambda _: confirm())
        tk.Button(win, text="Add", command=confirm,
                  bg=ACCENT, fg="white", relief="flat",
                  font=("Arial", 9, "bold")).pack(pady=8)

    def _remove_mega_enhancement(self, ma, name, refresh_func):
        if ma in self._mega_enhancements:
            self._mega_enhancements[ma] = [
                e for e in self._mega_enhancements[ma] if e[0] != name]
            self._mark_dirty()
        refresh_func()

    def _build_dot_checks(self, parent, count, var):
        """Row of square checkboxes that track how many are checked (for temp pools)."""
        checks = []
        f = tk.Frame(parent, bg=BG_CARD)
        f.pack(side="left", padx=4, pady=3)
        for i in range(1, count + 1):
            bv = tk.BooleanVar(value=False)
            cb = CheckBox(f, var=bv, bg=BG_CARD)
            cb.grid(row=0, column=i - 1, padx=1)
            checks.append(bv)

        def sync_checks(*_):
            val = var.get()
            for idx, bv in enumerate(checks):
                bv.set(idx < val)

        var.trace_add("write", sync_checks)
        sync_checks()

        def on_check_click(idx):
            # Count how many are checked
            count_checked = sum(1 for b in checks if b.get())
            var.set(count_checked)
            self._mark_dirty()

        for idx, bv in enumerate(checks):
            bv.trace_add("write", lambda *_, i=idx: on_check_click(i))

        return checks

    # ── COMBAT tab ─────────────────────────────────────────────────────────────
    def _build_combat_tab(self, parent):
        sf = ScrollFrame(parent, bg=BG_DARK)
        inner = sf.inner

        # Attack table
        section_label(inner, "ATTACK")
        atk_frame = card(inner)
        atk_frame.pack(fill="x", padx=4, pady=4)

        headers = ["Name", "ACC", "DMG", "ROF", "FT"]
        widths   = [18, 5, 6, 5, 5]
        for c, (h, w) in enumerate(zip(headers, widths)):
            tk.Label(atk_frame, text=h, font=("Arial", 8, "bold"),
                     bg=BG_CARD, fg=GOLD, width=w).grid(row=0, column=c, padx=2, pady=2)

        self._attack_vars = []
        for r in range(self.cfg["num_attack_rows"]):
            row_vars = {}
            for c, (key, w) in enumerate(zip(["name", "acc", "dmg", "rof", "ft"], widths)):
                v = tk.StringVar()
                v.trace_add("write", lambda *_: self._mark_dirty())
                row_vars[key] = v
                e = tk.Entry(atk_frame, textvariable=v, font=("Arial", 8),
                             bg=BG_MID, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                             relief="flat", width=w)
                e.grid(row=r + 1, column=c, padx=2, pady=1)
            self._attack_vars.append(row_vars)

        # Armor table
        section_label(inner, "ARMOR")
        arm_frame = card(inner)
        arm_frame.pack(fill="x", padx=4, pady=4)

        arm_headers = ["Name", "B", "L", "BULK", "FT"]
        arm_widths   = [18, 5, 5, 6, 5]
        for c, (h, w) in enumerate(zip(arm_headers, arm_widths)):
            tk.Label(arm_frame, text=h, font=("Arial", 8, "bold"),
                     bg=BG_CARD, fg=GOLD, width=w).grid(row=0, column=c, padx=2, pady=2)

        self._armor_vars = []
        for r in range(self.cfg["num_armor_rows"]):
            row_vars = {}
            for c, (key, w) in enumerate(zip(["name", "b", "l", "bulk", "ft"], arm_widths)):
                v = tk.StringVar()
                v.trace_add("write", lambda *_: self._mark_dirty())
                row_vars[key] = v
                e = tk.Entry(arm_frame, textvariable=v, font=("Arial", 8),
                             bg=BG_MID, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                             relief="flat", width=w)
                e.grid(row=r + 1, column=c, padx=2, pady=1)
            self._armor_vars.append(row_vars)

        # Initiative / Movement / Soak
        ims = tk.Frame(inner, bg=BG_DARK)
        ims.pack(fill="x", padx=4, pady=4)

        # Initiative
        ini_f = card(ims)
        ini_f.pack(side="left", fill="both", expand=True, padx=2)
        tk.Label(ini_f, text="INITIATIVE", font=("Arial", 9, "bold"),
                 bg=BG_CARD, fg=GOLD).pack()
        self._initiative_var = tk.StringVar()
        self._initiative_var.trace_add("write", lambda *_: self._mark_dirty())
        tk.Entry(ini_f, textvariable=self._initiative_var, font=("Arial", 9),
                 bg=BG_MID, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                 relief="flat", width=10, justify="center").pack(padx=6, pady=4)

        # Movement
        mov_f = card(ims)
        mov_f.pack(side="left", fill="both", expand=True, padx=2)
        tk.Label(mov_f, text="MOVEMENT", font=("Arial", 9, "bold"),
                 bg=BG_CARD, fg=GOLD).pack()
        mov_inner = tk.Frame(mov_f, bg=BG_CARD)
        mov_inner.pack()
        self._move_vars = {}
        for key in ["Walk", "Run", "Sprint"]:
            tk.Label(mov_inner, text=key, font=("Arial", 7),
                     bg=BG_CARD, fg=TEXT_DIM).pack(side="left", padx=2)
            v = tk.StringVar()
            v.trace_add("write", lambda *_: self._mark_dirty())
            self._move_vars[key.lower()] = v
            tk.Entry(mov_inner, textvariable=v, font=("Arial", 8),
                     bg=BG_MID, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                     relief="flat", width=5).pack(side="left", padx=2, pady=4)

        # Soak
        soak_f = card(ims)
        soak_f.pack(side="left", fill="both", expand=True, padx=2)
        tk.Label(soak_f, text="SOAK", font=("Arial", 9, "bold"),
                 bg=BG_CARD, fg=GOLD).pack()
        soak_inner = tk.Frame(soak_f, bg=BG_CARD)
        soak_inner.pack()
        self._soak_vars = {}
        for key in ["Bashing", "Lethal"]:
            tk.Label(soak_inner, text=key, font=("Arial", 7),
                     bg=BG_CARD, fg=TEXT_DIM).pack(side="left", padx=2)
            v = tk.StringVar()
            v.trace_add("write", lambda *_: self._mark_dirty())
            self._soak_vars[key.lower()] = v
            tk.Entry(soak_inner, textvariable=v, font=("Arial", 8),
                     bg=BG_MID, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                     relief="flat", width=6).pack(side="left", padx=2, pady=4)

        # Description + Experience
        de_frame = tk.Frame(inner, bg=BG_DARK)
        de_frame.pack(fill="x", padx=4, pady=4)

        section_label(de_frame, "DESCRIPTION")
        desc_card = card(de_frame)
        desc_card.pack(fill="x", pady=2)
        self._desc_text = tk.Text(desc_card, font=("Arial", 8), height=6,
                                  bg=BG_MID, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                                  relief="flat", wrap="word")
        self._desc_text.pack(fill="both", padx=4, pady=4)
        self._desc_text.bind("<<Modified>>", self._on_desc_change)

        exp_row = tk.Frame(de_frame, bg=BG_DARK)
        exp_row.pack(fill="x", pady=4)
        tk.Label(exp_row, text="EXPERIENCE:", font=("Arial", 9, "bold"),
                 bg=BG_DARK, fg=GOLD).pack(side="left", padx=4)
        self._exp_var = tk.StringVar()
        self._exp_var.trace_add("write", lambda *_: self._mark_dirty())
        tk.Entry(exp_row, textvariable=self._exp_var, font=("Arial", 9),
                 bg=BG_MID, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                 relief="flat", width=20).pack(side="left", padx=4)

        return sf

    def _on_desc_change(self, e):
        self._mark_dirty()
        self._desc_text.edit_modified(False)

    # ── Health panel (right side) ─────────────────────────────────────────────
    # (label, default_penalty, default_count)
    HEALTH_STATES = [
        ("Bruised",        0,  1),
        ("Hurt",          -1,  1),
        ("Injured",       -1,  1),
        ("Wounded",       -2,  1),
        ("Maimed",        -3,  1),
        ("Crippled",      -4,  1),
        ("Incapacitated",  0,  1),
        ("Dead",           0,  1),
    ]
    COLOR_BASHING = "#ff9944"
    COLOR_LETHAL  = "#cc2200"
    COLOR_EMPTY   = "#3a3a3a"   # matches BG_CARD-ish

    def _build_health_panel(self, parent):
        hpanel = tk.Frame(parent, bg=BG_DARK, width=220)
        hpanel.pack(side="right", fill="y", padx=(4, 0))
        hpanel.pack_propagate(False)

        hdr = tk.Frame(hpanel, bg=BG_PANEL)
        hdr.pack(fill="x")
        tk.Label(hdr, text="HEALTH", font=("Arial", 10, "bold"),
                 bg=BG_PANEL, fg="white").pack(side="left", padx=6, pady=3)
        gear = tk.Label(hdr, text="⚙", font=("Arial", 10),
                        bg=BG_PANEL, fg=TEXT_DIM, cursor="hand2")
        gear.pack(side="right", padx=6)
        gear.bind("<Button-1>", lambda e: self._open_health_config())

        # Legend
        leg = tk.Frame(hpanel, bg=BG_DARK)
        leg.pack(fill="x", padx=6, pady=(2, 0))
        tk.Label(leg, text="■", font=("Arial", 9), bg=BG_DARK,
                 fg=self.COLOR_BASHING).pack(side="left")
        tk.Label(leg, text="Bashing", font=("Arial", 7), bg=BG_DARK,
                 fg=TEXT_DIM).pack(side="left", padx=(1, 8))
        tk.Label(leg, text="■", font=("Arial", 9), bg=BG_DARK,
                 fg=self.COLOR_LETHAL).pack(side="left")
        tk.Label(leg, text="Lethal", font=("Arial", 7), bg=BG_DARK,
                 fg=TEXT_DIM).pack(side="left", padx=(1, 0))

        self._health_scroll = ScrollFrame(hpanel, bg=BG_DARK)
        self._health_scroll.pack(fill="both", expand=True)

        # Per-state: count of boxes and penalty modifier
        self._health_counts   = {s[0]: tk.IntVar(value=s[2])  for s in self.HEALTH_STATES}
        self._health_penalties= {s[0]: tk.IntVar(value=s[1])   for s in self.HEALTH_STATES}
        # damage: state -> list of StringVar, each "" | "bashing" | "lethal"
        self._health_damage   = {}
        # canvas widgets per state for redraw
        self._health_canvases = {}

        self._health_inner = self._health_scroll.inner
        self._rebuild_health_rows()

    # ── flat ordered list of all boxes for fill-to-top logic ─────────────────
    def _all_health_boxes_ordered(self):
        """Return flat list of (state, idx) in order Bruised→Dead."""
        result = []
        for state_label, _, _ in self.HEALTH_STATES:
            count = self._health_counts[state_label].get()
            for i in range(count):
                result.append((state_label, i))
        return result

    def _rebuild_health_rows(self):
        """One row per health state. Each row shows the state label, penalty,
        an orange bashing box and a red lethal box. Dead has only the red box.
        Clicking a box fills it AND all boxes above it (same column) up to the top."""
        inner = self._health_inner
        for w in inner.winfo_children():
            w.destroy()
        self._health_canvases = {}

        # Preserve existing damage
        saved_bash = {k: [sv.get() for sv in lst]
                      for k, lst in getattr(self, "_health_bash", {}).items()}
        saved_leth = {k: [sv.get() for sv in lst]
                      for k, lst in getattr(self, "_health_leth", {}).items()}
        self._health_bash = {}
        self._health_leth = {}

        BOX_W = 14; GAP = 2

        active_states = [(sl, pen) for (sl, _, _) in self.HEALTH_STATES
                         for pen in [self._health_penalties[sl].get()]
                         if self._health_counts[sl].get() > 0]

        for state_label, penalty in active_states:
            count = self._health_counts[state_label].get()

            # Restore or init damage StringVars
            old_b = saved_bash.get(state_label, [])
            old_l = saved_leth.get(state_label, [])
            bash_svars = []
            leth_svars = []
            for i in range(count):
                bsv = tk.StringVar(value=old_b[i] if i < len(old_b) else "")
                lsv = tk.StringVar(value=old_l[i] if i < len(old_l) else "")
                bash_svars.append(bsv)
                leth_svars.append(lsv)
            self._health_bash[state_label] = bash_svars
            self._health_leth[state_label] = leth_svars

            # --- Build row(s): one per box, repeating the state label ---
            pen_str = f"{penalty:+d}" if penalty != 0 else " 0"
            is_dead = (state_label == "Dead")

            for box_idx in range(count):
                row = tk.Frame(inner, bg=BG_DARK)
                row.pack(fill="x", padx=4, pady=1)

                # State label only on first box of the state
                lbl_text = state_label if box_idx == 0 else ""
                tk.Label(row, text=lbl_text, font=("Arial", 8, "bold"),
                         bg=BG_DARK, fg=TEXT_MAIN, width=12, anchor="w").pack(side="left")
                tk.Label(row, text=pen_str if box_idx == 0 else "",
                         font=("Arial", 8, "bold"),
                         bg=BG_DARK, fg=ACCENT, width=3, anchor="e").pack(side="left")

                # Canvas: for Dead only red box; others orange + red
                n_cols = 1 if is_dead else 2
                cv_w = n_cols * (BOX_W + GAP) + 2
                cv = tk.Canvas(row, bg=BG_DARK, highlightthickness=0,
                               width=cv_w, height=BOX_W + 4)
                cv.pack(side="right", padx=(0, 4))

                def _draw_box(cv=cv, sl=state_label, bi=box_idx,
                              dead=is_dead, bw=BOX_W, gap=GAP):
                    cv.delete("all")
                    bval = self._health_bash[sl][bi].get() if sl in self._health_bash else ""
                    lval = self._health_leth[sl][bi].get() if sl in self._health_leth else ""
                    y0, y1 = 2, bw + 2

                    if not dead:
                        # Orange bashing box (col 0)
                        x0, x1 = 1, bw + 1
                        fc = self.COLOR_BASHING if bval else self.COLOR_EMPTY
                        oc = "#ffcc88" if bval else BORDER
                        cv.create_rectangle(x0, y0, x1, y1, fill=fc, outline=oc, width=1)
                        # Red lethal box (col 1) – aligned with red boxes
                        x0b = bw + gap + 1; x1b = x0b + bw
                        fc2 = self.COLOR_LETHAL if lval else self.COLOR_EMPTY
                        oc2 = "#ff6644" if lval else BORDER
                        cv.create_rectangle(x0b, y0, x1b, y1, fill=fc2, outline=oc2, width=1)
                    else:
                        # Dead: only red, aligned at col 1 position (same x as lethal column above)
                        x0b = bw + gap + 1; x1b = x0b + bw
                        fc2 = self.COLOR_LETHAL if lval else self.COLOR_EMPTY
                        oc2 = "#ff6644" if lval else BORDER
                        # Shift canvas to align: draw at offset 0 but pack right
                        cv.create_rectangle(1, y0, bw + 1, y1, fill=fc2, outline=oc2, width=1)

                bash_svars[box_idx].trace_add("write", lambda *_, d=_draw_box: d())
                leth_svars[box_idx].trace_add("write", lambda *_, d=_draw_box: d())

                def _on_click(event, sl=state_label, bi=box_idx,
                              dead=is_dead, bw=BOX_W, gap=GAP):
                    # Determine which column was clicked
                    if dead or event.x < bw + gap:
                        col = "bashing" if not dead else "lethal"
                    else:
                        col = "lethal"
                    # Override: right-click toggles only this box
                    if event.num == 3:
                        svar_list = self._health_leth[sl] if col == "lethal" else self._health_bash[sl]
                        svar_list[bi].set("" if svar_list[bi].get() else col)
                        self._mark_dirty()
                        return
                    # Left-click: fill this box + all boxes above in same column
                    # "Above" = earlier boxes in this state + boxes of states earlier in order
                    self._health_fill_up_to(sl, bi, col)
                    self._mark_dirty()

                cv.bind("<Button-1>", _on_click)
                cv.bind("<Button-3>", _on_click)
                _draw_box()

        # Hint
        hint = tk.Frame(inner, bg=BG_DARK)
        hint.pack(fill="x", padx=4, pady=(4, 2))
        tk.Label(hint, text="Click=fill up  Right-click=toggle one  Shift=lethal col",
                 font=("Arial", 7), bg=BG_DARK, fg=TEXT_DIM).pack(anchor="w")

    def _health_fill_up_to(self, target_state, target_box_idx, col):
        """Fill all boxes in `col` from the very first state down to target_state/target_box_idx.
        If they're all already filled, clear them instead (toggle off)."""
        # Build ordered flat list of (state, box_idx) active entries
        order = []
        for sl, _, _ in self.HEALTH_STATES:
            cnt = self._health_counts[sl].get()
            for bi in range(cnt):
                order.append((sl, bi))

        # Find target position
        try:
            tgt_pos = order.index((target_state, target_box_idx))
        except ValueError:
            return

        # Check if all boxes up to and including target are already filled
        bash_dict = self._health_bash
        leth_dict = self._health_leth
        def get_svar(sl, bi, c):
            d = leth_dict if c == "lethal" else bash_dict
            if sl in d and bi < len(d[sl]):
                return d[sl][bi]
            return None

        all_filled = all(
            (sv := get_svar(sl, bi, col)) and sv.get()
            for sl, bi in order[:tgt_pos + 1]
        )

        for sl, bi in order[:tgt_pos + 1]:
            sv = get_svar(sl, bi, col)
            if sv is not None:
                sv.set("" if all_filled else col)

    def _open_health_config(self):
        win = tk.Toplevel(self, bg=BG_DARK)
        win.title("Configure Health Levels")
        win.geometry("340x360")
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Health Level Configuration",
                 font=("Arial", 10, "bold"), bg=BG_DARK, fg=ACCENT).pack(pady=(10, 2))
        tk.Label(win, text="Boxes = number of health boxes. Penalty = dice modifier.",
                 font=("Arial", 8), bg=BG_DARK, fg=TEXT_DIM).pack(pady=(0, 6))

        grid = tk.Frame(win, bg=BG_DARK)
        grid.pack(padx=14, pady=4, fill="x")

        # Headers
        for col, (txt, w) in enumerate([("State", 13), ("Boxes", 5), ("Penalty", 7)]):
            tk.Label(grid, text=txt, font=("Arial", 8, "bold"),
                     bg=BG_DARK, fg=GOLD, width=w, anchor="w").grid(
                     row=0, column=col, padx=(0, 6), pady=(0, 4), sticky="w")

        # Local copies so we don't mutate live vars until Apply
        tmp_counts   = {s[0]: tk.IntVar(value=self._health_counts[s[0]].get())
                        for s in self.HEALTH_STATES}
        tmp_penalties= {s[0]: tk.IntVar(value=self._health_penalties[s[0]].get())
                        for s in self.HEALTH_STATES}

        for i, (state_label, _, _) in enumerate(self.HEALTH_STATES):
            r = i + 1
            tk.Label(grid, text=state_label, font=("Arial", 9),
                     bg=BG_DARK, fg=TEXT_MAIN, width=13, anchor="w").grid(
                     row=r, column=0, pady=3, sticky="w")
            tk.Spinbox(grid, from_=0, to=20,
                       textvariable=tmp_counts[state_label],
                       font=("Arial", 9), width=4,
                       bg=BG_CARD, fg=TEXT_MAIN,
                       buttonbackground=BG_MID).grid(row=r, column=1, padx=(0, 6))
            tk.Spinbox(grid, from_=-10, to=0,
                       textvariable=tmp_penalties[state_label],
                       font=("Arial", 9), width=4,
                       bg=BG_CARD, fg=TEXT_MAIN,
                       buttonbackground=BG_MID).grid(row=r, column=2)

        def apply_and_close():
            for s in self.HEALTH_STATES:
                sl = s[0]
                self._health_counts[sl].set(tmp_counts[sl].get())
                self._health_penalties[sl].set(tmp_penalties[sl].get())
            self._rebuild_health_rows()
            self._mark_dirty()
            win.destroy()

        tk.Button(win, text="Apply", command=apply_and_close,
                  bg=ACCENT, fg="white", relief="flat",
                  font=("Arial", 9, "bold")).pack(pady=10)

    # ── Quantum pool + stat bars (bottom) ────────────────────────────────────
    def _build_quantum_pool(self):
        qp_frame = tk.Frame(self, bg=BG_PANEL,
                            highlightbackground=ACCENT, highlightthickness=1)
        qp_frame.pack(fill="x", padx=6, pady=(4, 6))

        bottom_row = tk.Frame(qp_frame, bg=BG_PANEL)
        bottom_row.pack(fill="x", padx=8, pady=(4, 4))

        # ── QUANTUM POOL (left) ──────────────────────────────────────────────
        left_ctrl = tk.Frame(bottom_row, bg=BG_PANEL)
        left_ctrl.pack(side="left")

        tk.Label(left_ctrl, text="QUANTUM POOL",
                 font=("Arial", 10, "bold"), bg=BG_PANEL, fg=ACCENT).pack(anchor="w")

        spinbox_row = tk.Frame(left_ctrl, bg=BG_PANEL)
        spinbox_row.pack(anchor="w")

        tk.Label(spinbox_row, text="Max:", font=("Arial", 8),
                 bg=BG_PANEL, fg=TEXT_DIM).pack(side="left")
        self._qp_max_var = tk.IntVar(value=20)
        self._qp_max_var.trace_add("write", lambda *_: self._on_qp_max_changed())
        tk.Spinbox(spinbox_row, from_=1, to=34, textvariable=self._qp_max_var,
                   font=("Arial", 8), width=4,
                   bg=BG_CARD, fg=TEXT_MAIN, buttonbackground=BG_MID).pack(side="left", padx=(2, 8))

        tk.Label(spinbox_row, text="Quantum Used:", font=("Arial", 8),
                 bg=BG_PANEL, fg=TEXT_DIM).pack(side="left")
        self._qp_cur_var = tk.IntVar(value=0)
        self._qp_cur_var.trace_add("write", lambda *_: self._on_qp_cur_changed())
        self._qp_spinbox = tk.Spinbox(spinbox_row, from_=0, to=34,
                                       textvariable=self._qp_cur_var,
                                       font=("Arial", 8), width=4,
                                       bg=BG_CARD, fg=TEXT_MAIN, buttonbackground=BG_MID)
        self._qp_spinbox.pack(side="left", padx=(2, 0))

        # Dot canvas for quantum pool
        self._qp_dot_frame = tk.Frame(left_ctrl, bg=BG_PANEL)
        self._qp_dot_frame.pack(anchor="w", pady=(2, 0))
        self._qp_canvas = tk.Canvas(self._qp_dot_frame, bg=BG_PANEL,
                                    highlightthickness=0, height=20, width=390)
        self._qp_canvas.pack(side="left")
        self._qp_canvas.bind("<Button-1>", self._qp_canvas_click)
        self._qp_dots = []
        self._qp_updating = False

        # ── WILLPOWER (right section) ────────────────────────────────────────
        sep1 = tk.Frame(bottom_row, bg=BORDER, width=1)
        sep1.pack(side="left", fill="y", padx=12)

        self._wp_bar = self._build_wp_bar(bottom_row)

        # ── TAINT (right section) ─ shares vars with Advantages tab ───────────
        sep2 = tk.Frame(bottom_row, bg=BORDER, width=1)
        sep2.pack(side="left", fill="y", padx=12)

        self._taint_bar = self._build_taint_bar(bottom_row)

        # ── QUANTUM ATTRIBUTE (right section) ───────────────────────────────
        sep3 = tk.Frame(bottom_row, bg=BORDER, width=1)
        sep3.pack(side="left", fill="y", padx=12)

        self._quantum_bar = self._build_quantum_attr_bar(bottom_row)

        self._refresh_qp_dots()

        # ── EXPERIENCE (far right) ──────────────────────────────────────────
        sep4 = tk.Frame(bottom_row, bg=BORDER, width=1)
        sep4.pack(side="left", fill="y", padx=12)
        exp_ctrl = tk.Frame(bottom_row, bg=BG_PANEL)
        exp_ctrl.pack(side="left")
        tk.Label(exp_ctrl, text="EXPERIENCE", font=("Arial", 9, "bold"),
                 bg=BG_PANEL, fg=GOLD).pack(anchor="w")
        exp_row2 = tk.Frame(exp_ctrl, bg=BG_PANEL)
        exp_row2.pack(anchor="w")
        tk.Label(exp_row2, text="Total:", font=("Arial", 8),
                 bg=BG_PANEL, fg=TEXT_DIM).pack(side="left")
        self._exp_total_var = tk.StringVar(value="0")
        self._exp_total_var.trace_add("write", lambda *_: self._mark_dirty())
        tk.Entry(exp_row2, textvariable=self._exp_total_var,
                 font=("Arial", 9), width=5,
                 bg=BG_CARD, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                 relief="flat", justify="center").pack(side="left", padx=(3, 8))
        tk.Label(exp_row2, text="Spent:", font=("Arial", 8),
                 bg=BG_PANEL, fg=TEXT_DIM).pack(side="left")
        self._exp_spent_var = tk.StringVar(value="0")
        self._exp_spent_var.trace_add("write", lambda *_: self._mark_dirty())
        tk.Entry(exp_row2, textvariable=self._exp_spent_var,
                 font=("Arial", 9), width=5,
                 bg=BG_CARD, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                 relief="flat", justify="center").pack(side="left", padx=(3, 0))

    def _build_stat_bar(self, parent, label, max_dots, min_val, used,
                        perm_var_name, used_var_name, canvas_name,
                        updating_name, color, fixed_max=None):
        """Generic permanent-dots + optional used-counter bar widget."""
        DOT_S   = 14
        SPACING = 15
        W       = max_dots * SPACING + 4

        frame = tk.Frame(parent, bg=BG_PANEL)
        frame.pack(side="left")

        tk.Label(frame, text=label, font=("Arial", 9, "bold"),
                 bg=BG_PANEL, fg=color).pack(anchor="w")

        # Permanent / rating spinbox row
        ctrl = tk.Frame(frame, bg=BG_PANEL)
        ctrl.pack(anchor="w")

        perm_var = tk.IntVar(value=min_val if min_val > 0 else 0)
        setattr(self, perm_var_name, perm_var)

        updating_flag = [False]
        setattr(self, updating_name, updating_flag)

        fm = fixed_max if fixed_max else max_dots
        tk.Label(ctrl, text="Rating:" if not used else "Permanent:",
                 font=("Arial", 8), bg=BG_PANEL, fg=TEXT_DIM).pack(side="left")
        tk.Spinbox(ctrl, from_=min_val, to=fm, textvariable=perm_var,
                   font=("Arial", 8), width=3,
                   bg=BG_CARD, fg=TEXT_MAIN, buttonbackground=BG_MID).pack(side="left", padx=(2, 6))

        used_var = None
        if used:
            used_var = tk.IntVar(value=0)
            setattr(self, used_var_name, used_var)
            tk.Label(ctrl, text="Used:", font=("Arial", 8),
                     bg=BG_PANEL, fg=TEXT_DIM).pack(side="left")
            tk.Spinbox(ctrl, from_=0, to=fm, textvariable=used_var,
                       font=("Arial", 8), width=3,
                       bg=BG_CARD, fg=TEXT_MAIN, buttonbackground=BG_MID).pack(side="left", padx=(2, 0))

        # Canvas
        cv = tk.Canvas(frame, bg=BG_PANEL, highlightthickness=0,
                       height=20, width=W)
        cv.pack(anchor="w", pady=(2, 0))
        setattr(self, canvas_name, cv)

        def refresh(*_):
            if updating_flag[0]:
                return
            cv.delete("all")
            try:
                perm = perm_var.get()
                cur  = used_var.get() if used_var else 0
            except Exception:
                return

            # Bar showing permanent level
            if perm > 0:
                bar_x2 = 2 + (perm - 1) * SPACING + DOT_S
                cv.create_line(2, 2, bar_x2, 2, fill=GOLD, width=2)

            for i in range(max_dots):
                xc = 2 + i * SPACING + DOT_S // 2
                x0, y0 = xc - DOT_S // 2, 5
                x1, y1 = xc + DOT_S // 2, 5 + DOT_S

                in_perm = (i + 1) <= perm
                filled  = (i + 1) <= cur if used else in_perm

                if in_perm:
                    fill_c = color if filled else DOT_EMPTY
                    out_c  = GOLD  if filled else color
                else:
                    fill_c = BG_DARK
                    out_c  = BORDER
                cv.create_oval(x0, y0, x1, y1, fill=fill_c, outline=out_c, width=1)

        def on_click(event):
            if updating_flag[0]:
                return
            try:
                perm = perm_var.get()
                cur  = used_var.get() if used_var else perm_var.get()
            except Exception:
                return

            idx = (event.x - 2) // SPACING + 1
            idx = max(1, min(max_dots, idx))

            if used and used_var:
                if idx > perm:
                    return
                new_val = idx - 1 if idx == cur else idx
                updating_flag[0] = True
                used_var.set(new_val)
                updating_flag[0] = False
            else:
                # Attribute-style: click sets rating
                new_val = (min_val if min_val > 0 else 0) if idx == perm else idx
                if idx < perm:
                    new_val = idx
                updating_flag[0] = True
                perm_var.set(new_val)
                updating_flag[0] = False
            refresh()
            self._mark_dirty()

        perm_var.trace_add("write", refresh)
        if used_var:
            used_var.trace_add("write", refresh)
        cv.bind("<Button-1>", on_click)
        refresh()
        return frame

    # ── Shared-var bottom bar widgets ────────────────────────────────────────

    def _build_wp_bar(self, parent):
        """Willpower bar – shares _wp_perm_var / _wp_temp_var with Advantages tab."""
        DOT_S = 14; SPACING = 15; W = 10 * SPACING + 4
        frame = tk.Frame(parent, bg=BG_PANEL)
        frame.pack(side="left")
        tk.Label(frame, text="WILLPOWER", font=("Arial", 9, "bold"),
                 bg=BG_PANEL, fg=GOLD).pack(anchor="w")
        ctrl = tk.Frame(frame, bg=BG_PANEL)
        ctrl.pack(anchor="w")
        tk.Label(ctrl, text="Permanent:", font=("Arial", 8),
                 bg=BG_PANEL, fg=TEXT_DIM).pack(side="left")
        tk.Spinbox(ctrl, from_=1, to=10, textvariable=self._wp_perm_var,
                   font=("Arial", 8), width=3,
                   bg=BG_CARD, fg=TEXT_MAIN, buttonbackground=BG_MID).pack(side="left", padx=(2, 6))
        tk.Label(ctrl, text="Used:", font=("Arial", 8),
                 bg=BG_PANEL, fg=TEXT_DIM).pack(side="left")
        tk.Spinbox(ctrl, from_=0, to=10, textvariable=self._wp_temp_var,
                   font=("Arial", 8), width=3,
                   bg=BG_CARD, fg=TEXT_MAIN, buttonbackground=BG_MID).pack(side="left", padx=(2, 0))
        cv = tk.Canvas(frame, bg=BG_PANEL, highlightthickness=0, height=20, width=W)
        cv.pack(anchor="w", pady=(2, 0))

        def refresh(*_):
            cv.delete("all")
            try:
                perm = self._wp_perm_var.get()
                used = self._wp_temp_var.get()
            except Exception:
                return
            if perm > 0:
                cv.create_line(2, 2, 2 + (perm-1)*SPACING + DOT_S, 2, fill=GOLD, width=2)
            for i in range(10):
                xc = 2 + i*SPACING + DOT_S//2
                x0, y0 = xc - DOT_S//2, 5
                x1, y1 = xc + DOT_S//2, 5 + DOT_S
                in_p = (i+1) <= perm
                filled = (i+1) <= used
                if in_p:
                    fc = GOLD if filled else DOT_EMPTY
                    oc = "#ffffff" if filled else GOLD
                else:
                    fc, oc = BG_DARK, BORDER
                cv.create_oval(x0, y0, x1, y1, fill=fc, outline=oc, width=1)

        def on_click(event):
            try:
                perm = self._wp_perm_var.get()
                used = self._wp_temp_var.get()
            except Exception:
                return
            idx = (event.x - 2) // SPACING + 1
            idx = max(1, min(10, idx))
            if idx > perm:
                return
            self._wp_temp_var.set(idx - 1 if idx == used else idx)
            self._mark_dirty()

        self._wp_perm_var.trace_add("write", refresh)
        self._wp_temp_var.trace_add("write", refresh)
        cv.bind("<Button-1>", on_click)
        refresh()
        return frame

    def _build_taint_bar(self, parent):
        """Taint bar – shares _taint_perm_var / _taint_temp_var with Advantages tab.
        Permanent = dots (0-10). Temporary = filled squares (0-10), like the tab."""
        DOT_S = 14; SPACING = 15; W = 10 * SPACING + 4
        frame = tk.Frame(parent, bg=BG_PANEL)
        frame.pack(side="left")
        tk.Label(frame, text="TAINT", font=("Arial", 9, "bold"),
                 bg=BG_PANEL, fg="#cc4400").pack(anchor="w")
        ctrl = tk.Frame(frame, bg=BG_PANEL)
        ctrl.pack(anchor="w")
        tk.Label(ctrl, text="Permanent:", font=("Arial", 8),
                 bg=BG_PANEL, fg=TEXT_DIM).pack(side="left")
        tk.Spinbox(ctrl, from_=0, to=10, textvariable=self._taint_perm_var,
                   font=("Arial", 8), width=3,
                   bg=BG_CARD, fg=TEXT_MAIN, buttonbackground=BG_MID).pack(side="left", padx=(2, 6))
        tk.Label(ctrl, text="Temporary:", font=("Arial", 8),
                 bg=BG_PANEL, fg=TEXT_DIM).pack(side="left")
        tk.Spinbox(ctrl, from_=0, to=10, textvariable=self._taint_temp_var,
                   font=("Arial", 8), width=3,
                   bg=BG_CARD, fg=TEXT_MAIN, buttonbackground=BG_MID).pack(side="left", padx=(2, 0))
        # Two-row canvas: top = perm dots, bottom = temp squares
        cv = tk.Canvas(frame, bg=BG_PANEL, highlightthickness=0, height=36, width=W)
        cv.pack(anchor="w", pady=(2, 0))

        def refresh(*_):
            cv.delete("all")
            try:
                perm = self._taint_perm_var.get()
                temp = self._taint_temp_var.get()
            except Exception:
                return
            # Row 1 – permanent dots (circles)
            if perm > 0:
                cv.create_line(2, 2, 2 + (perm-1)*SPACING + DOT_S, 2, fill="#cc4400", width=2)
            for i in range(10):
                xc = 2 + i*SPACING + DOT_S//2
                x0, y0 = xc - DOT_S//2, 4
                x1, y1 = xc + DOT_S//2, 4 + DOT_S
                in_p = (i+1) <= perm
                fc = "#cc4400" if in_p else BG_DARK
                oc = "#ff6622" if in_p else BORDER
                cv.create_oval(x0, y0, x1, y1, fill=fc, outline=oc, width=1)
            # Row 2 – temporary squares
            for i in range(10):
                xc = 2 + i*SPACING + DOT_S//2
                x0, y0 = xc - DOT_S//2, 20
                x1, y1 = xc + DOT_S//2, 20 + DOT_S
                filled = (i+1) <= temp
                fc = "#cc4400" if filled else DOT_EMPTY
                oc = "#ff6622" if filled else BORDER
                cv.create_rectangle(x0, y0, x1, y1, fill=fc, outline=oc, width=1)

        def on_perm_click(event):
            try:
                perm = self._taint_perm_var.get()
            except Exception:
                return
            idx = (event.x - 2) // SPACING + 1
            idx = max(0, min(10, idx))
            if event.y <= 18:  # top row = permanent
                self._taint_perm_var.set(idx - 1 if idx == perm else idx)
            else:              # bottom row = temporary
                temp = self._taint_temp_var.get()
                self._taint_temp_var.set(idx - 1 if idx == temp else idx)
            self._mark_dirty()

        self._taint_perm_var.trace_add("write", refresh)
        self._taint_temp_var.trace_add("write", refresh)
        cv.bind("<Button-1>", on_perm_click)
        refresh()
        return frame

    def _build_quantum_attr_bar(self, parent):
        """Quantum attribute bar – shares _quantum_attr_var with Advantages tab."""
        DOT_S = 14; SPACING = 15; W = 10 * SPACING + 4
        frame = tk.Frame(parent, bg=BG_PANEL)
        frame.pack(side="left")
        tk.Label(frame, text="QUANTUM", font=("Arial", 9, "bold"),
                 bg=BG_PANEL, fg=ACCENT).pack(anchor="w")
        ctrl = tk.Frame(frame, bg=BG_PANEL)
        ctrl.pack(anchor="w")
        tk.Label(ctrl, text="Rating:", font=("Arial", 8),
                 bg=BG_PANEL, fg=TEXT_DIM).pack(side="left")
        tk.Spinbox(ctrl, from_=1, to=10, textvariable=self._quantum_attr_var,
                   font=("Arial", 8), width=3,
                   bg=BG_CARD, fg=TEXT_MAIN, buttonbackground=BG_MID).pack(side="left", padx=(2, 0))
        cv = tk.Canvas(frame, bg=BG_PANEL, highlightthickness=0, height=20, width=W)
        cv.pack(anchor="w", pady=(2, 0))

        def refresh(*_):
            cv.delete("all")
            try:
                val = self._quantum_attr_var.get()
            except Exception:
                return
            if val > 0:
                cv.create_line(2, 2, 2 + (val-1)*SPACING + DOT_S, 2, fill=GOLD, width=2)
            for i in range(10):
                xc = 2 + i*SPACING + DOT_S//2
                x0, y0 = xc - DOT_S//2, 5
                x1, y1 = xc + DOT_S//2, 5 + DOT_S
                filled = (i+1) <= val
                fc = ACCENT if filled else DOT_EMPTY
                oc = GOLD   if filled else ACCENT
                cv.create_oval(x0, y0, x1, y1, fill=fc, outline=oc, width=1)

        def on_click(event):
            try:
                val = self._quantum_attr_var.get()
            except Exception:
                return
            idx = (event.x - 2) // SPACING + 1
            idx = max(1, min(10, idx))
            self._quantum_attr_var.set(1 if idx == val else idx)
            self._mark_dirty()

        self._quantum_attr_var.trace_add("write", refresh)
        cv.bind("<Button-1>", on_click)
        refresh()
        return frame

    def _on_qp_max_changed(self):
        if not hasattr(self, "_qp_dot_frame"):
            return
        self._refresh_qp_dots()
        self._mark_dirty()

    def _on_qp_cur_changed(self):
        if not hasattr(self, "_qp_dot_frame") or self._qp_updating:
            return
        self._refresh_qp_dots()
        self._mark_dirty()

    def _refresh_qp_dots(self):
        if not hasattr(self, "_qp_dot_frame"):
            return
        try:
            max_val = self._qp_max_var.get()
            cur_val = self._qp_cur_var.get()
        except Exception:
            return

        c = self._qp_canvas
        c.delete("all")
        self._qp_dots.clear()

        total    = 34
        dot_size = 11
        spacing  = 11
        y_center = 10
        x_start  = 4

        if max_val > 0:
            bar_x1 = x_start
            bar_x2 = x_start + (max_val - 1) * spacing + dot_size
            c.create_line(bar_x1, 2, bar_x2, 2, fill=GOLD, width=2)

        for i in range(total):
            xc = x_start + i * spacing + dot_size // 2
            x0 = xc - dot_size // 2
            y0 = y_center - dot_size // 2 + 2
            x1 = xc + dot_size // 2
            y1 = y_center + dot_size // 2 + 2

            in_max = (i + 1) <= max_val
            filled = (i + 1) <= cur_val

            if in_max:
                fill    = ACCENT if filled else DOT_EMPTY
                outline = GOLD   if filled else ACCENT
            else:
                fill    = BG_DARK
                outline = BORDER

            c.create_oval(x0, y0, x1, y1, fill=fill, outline=outline, width=1)
            self._qp_dots.append(xc)

    def _qp_canvas_click(self, event):
        if self._qp_updating:
            return
        try:
            max_val = self._qp_max_var.get()
            cur_val = self._qp_cur_var.get()
        except Exception:
            return
        dot_size = 11
        spacing  = 11
        x_start  = 4
        idx = (event.x - x_start) // spacing + 1
        idx = max(1, min(34, idx))
        if idx > max_val:
            return
        new_val = idx - 1 if idx == cur_val else idx
        self._qp_updating = True
        self._qp_cur_var.set(new_val)
        self._qp_updating = False
        self._refresh_qp_dots()
        self._mark_dirty()

    # ── Dirty tracking ─────────────────────────────────────────────────────────
    def _mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            self._update_title()

    def _update_title(self):
        name = self._hdr_vars.get("birth_name", tk.StringVar()).get() or "Unnamed"
        dirty = " *" if self._dirty else ""
        fname = f" — {os.path.basename(self._current_file)}" if self._current_file else ""
        self.title(f"Aberrant — {name}{fname}{dirty}")

    # ── Serialise / Deserialise ────────────────────────────────────────────────
    def _collect_char(self):
        c = {}
        for key, var in self._hdr_vars.items():
            c[key] = var.get()
        c["attributes"] = {a: v.get() for a, v in self._attr_vars.items()}
        c["abilities"]  = {s: v.get() for s, v in self._ability_vars.items()}
        c["ability_specialties"] = {s: v.get() for s, v in self._spec_vars.items()}
        c["specialisations"] = {
            sk: [[e[0], e[1].get()] for e in entries]
            for sk, entries in self._specialisations.items()
        }
        c["custom_abilities"] = {k: [nv.get(), vv.get()]
                                  for k, (nv, vv) in self._custom_ability_vars.items()}
        c["backgrounds"] = {k: v.get() for k, v in self._bg_vars.items()}
        c["mega_attributes"] = {ma: v.get() for ma, v in self._mega_vars.items()}

        c["willpower_perm"]  = self._wp_perm_var.get()
        c["willpower_temp"]  = self._wp_temp_var.get()
        c["taint_perm"]      = self._taint_perm_var.get()
        c["taint_temp"]      = self._taint_temp_var.get()
        c["aberrations"]     = self._aberr_var.get()
        c["quantum"]         = self._quantum_attr_var.get()
        c["quantum_pool_max"]     = self._qp_max_var.get()
        c["quantum_pool_current"] = self._qp_cur_var.get()
        c["health_counts"]    = {k: v.get() for k, v in self._health_counts.items()}
        c["health_penalties"] = {k: v.get() for k, v in self._health_penalties.items()}
        c["health_bash"]      = {k: [sv.get() for sv in lst]
                                  for k, lst in getattr(self, "_health_bash", {}).items()}
        c["health_leth"]      = {k: [sv.get() for sv in lst]
                                  for k, lst in getattr(self, "_health_leth", {}).items()}
        c["attacks"] = [{k: v.get() for k, v in row.items()} for row in self._attack_vars]
        c["armors"]  = [{k: v.get() for k, v in row.items()} for row in self._armor_vars]
        c["initiative"]   = self._initiative_var.get()
        c["walk"]         = self._move_vars["walk"].get()
        c["run"]          = self._move_vars["run"].get()
        c["sprint"]       = self._move_vars["sprint"].get()
        c["soak_bashing"] = self._soak_vars["bashing"].get()
        c["soak_lethal"]  = self._soak_vars["lethal"].get()
        c["description"]  = self._desc_text.get("1.0", "end-1c")
        c["experience"]   = self._exp_var.get()
        c["exp_total"]    = self._exp_total_var.get()
        c["exp_spent"]    = self._exp_spent_var.get()
        c["mega_enhancements"] = {
            ma: [[e[0], e[1].get()] for e in lst]
            for ma, lst in self._mega_enhancements.items()
        }
        return c

    def _apply_char(self, c):
        for key, var in self._hdr_vars.items():
            var.set(c.get(key, ""))
        for a, var in self._attr_vars.items():
            var.set(c.get("attributes", {}).get(a, 1))
        for s, var in self._ability_vars.items():
            var.set(c.get("abilities", {}).get(s, 0))
        for s, var in self._spec_vars.items():
            var.set(c.get("ability_specialties", {}).get(s, False))
        # Restore specialisations
        self._specialisations.clear()
        for sk, entries in c.get("specialisations", {}).items():
            bvs = []
            for name, active in entries:
                bv = tk.BooleanVar(value=active)
                bv.trace_add("write", lambda *_: self._mark_dirty())
                bvs.append([name, bv])
            self._specialisations[sk] = bvs
        # Refresh all spec tag displays
        for sk, fn in getattr(self, "_spec_refresh_funcs", {}).items():
            fn()
        for k, (nv, vv) in self._custom_ability_vars.items():
            data = c.get("custom_abilities", {}).get(k, ["", 0])
            nv.set(data[0])
            vv.set(data[1])
        for k, v in self._bg_vars.items():
            v.set(c.get("backgrounds", {}).get(k, 0))
        for ma, var in self._mega_vars.items():
            var.set(c.get("mega_attributes", {}).get(ma, 0))

        self._wp_perm_var.set(c.get("willpower_perm", 5))
        self._wp_temp_var.set(c.get("willpower_temp", 5))
        self._taint_perm_var.set(c.get("taint_perm", 0))
        self._taint_temp_var.set(c.get("taint_temp", 0))
        self._aberr_var.set(c.get("aberrations", ""))
        self._quantum_attr_var.set(c.get("quantum", 1))
        self._qp_max_var.set(c.get("quantum_pool_max", 20))
        self._qp_cur_var.set(c.get("quantum_pool_current", 0))
        self._refresh_qp_dots()
        for k, v in c.get("health_counts", {}).items():
            if k in self._health_counts:
                self._health_counts[k].set(v)
        for k, v in c.get("health_penalties", {}).items():
            if k in self._health_penalties:
                self._health_penalties[k].set(v)
        self._rebuild_health_rows()
        for k, vals in c.get("health_bash", {}).items():
            if k in self._health_bash:
                for j, sv in enumerate(self._health_bash[k]):
                    if j < len(vals): sv.set(vals[j])
        for k, vals in c.get("health_leth", {}).items():
            if k in self._health_leth:
                for j, sv in enumerate(self._health_leth[k]):
                    if j < len(vals): sv.set(vals[j])
        for i, row in enumerate(self._attack_vars):
            atk = c.get("attacks", [{}] * 5)
            entry = atk[i] if i < len(atk) else {}
            for k, v in row.items():
                v.set(entry.get(k, ""))
        for i, row in enumerate(self._armor_vars):
            arm = c.get("armors", [{}] * 5)
            entry = arm[i] if i < len(arm) else {}
            for k, v in row.items():
                v.set(entry.get(k, ""))
        self._initiative_var.set(c.get("initiative", ""))
        self._move_vars["walk"].set(c.get("walk", ""))
        self._move_vars["run"].set(c.get("run", ""))
        self._move_vars["sprint"].set(c.get("sprint", ""))
        self._soak_vars["bashing"].set(c.get("soak_bashing", ""))
        self._soak_vars["lethal"].set(c.get("soak_lethal", ""))
        self._desc_text.delete("1.0", "end")
        self._desc_text.insert("1.0", c.get("description", ""))
        self._exp_var.set(c.get("experience", ""))
        self._exp_total_var.set(c.get("exp_total", "0"))
        self._exp_spent_var.set(c.get("exp_spent", "0"))
        # Restore mega enhancements
        self._mega_enhancements.clear()
        for ma, entries in c.get("mega_enhancements", {}).items():
            bvs = []
            for name, active in entries:
                bv = tk.BooleanVar(value=active)
                bv.trace_add("write", lambda *_: self._mark_dirty())
                bvs.append([name, bv])
            self._mega_enhancements[ma] = bvs
        for ma, fn in self._mega_enh_refresh.items():
            fn()

    def _load_char_to_ui(self):
        self._apply_char(self.char)
        self._dirty = False
        self._update_title()

    # ── File operations ────────────────────────────────────────────────────────
    def _new(self):
        if self._dirty:
            if not messagebox.askyesno("Unsaved changes",
                                       "Discard unsaved changes and create a new character?"):
                return
        self.char = empty_character(self.cfg)
        self._current_file = None
        self._load_char_to_ui()

    def _open(self):
        if self._dirty:
            if not messagebox.askyesno("Unsaved changes",
                                       "Discard unsaved changes and open a file?"):
                return
        path = filedialog.askopenfilename(
            title="Open Character",
            filetypes=[("Aberrant character", "*.abe"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.char = data
            self._current_file = path
            self._load_char_to_ui()
        except Exception as e:
            messagebox.showerror("Open Error", f"Could not open file:\n{e}")

    def _save(self):
        if self._current_file:
            self._write_file(self._current_file)
        else:
            self._save_as()

    def _save_as(self):
        path = filedialog.asksaveasfilename(
            title="Save Character As",
            defaultextension=".abe",
            filetypes=[("Aberrant character", "*.abe"), ("All files", "*.*")]
        )
        if not path:
            return
        self._write_file(path)
        self._current_file = path

    def _write_file(self, path):
        try:
            data = self._collect_char()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self._dirty = False
            self._update_title()
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save file:\n{e}")

    def _quit(self):
        if self._dirty:
            answer = messagebox.askyesnocancel(
                "Unsaved changes",
                "You have unsaved changes.\nSave before quitting?"
            )
            if answer is None:    # Cancel
                return
            if answer:            # Yes → save first
                self._save()
                if self._dirty:   # Save was cancelled
                    return
        self.destroy()

    # ── About menu ─────────────────────────────────────────────────────────────
    def _help(self):
        win = tk.Toplevel(self, bg=BG_DARK)
        win.title("Help")
        win.geometry("500x400")
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


if __name__ == "__main__":
    app = AberrantApp()
    app.mainloop()
