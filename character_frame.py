import tkinter as tk
from tkinter import messagebox, filedialog
import json
import os
import re
import base64
import io

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from constants import (APP_VERSION, BG_DARK, BG_MID, BG_PANEL, BG_CARD,
                       ACCENT, GOLD, TEXT_MAIN, TEXT_DIM, DOT_EMPTY,
                       TAB_ACT, TAB_INACT, BORDER)
from data_loader import load_powers, format_description, migrate_char, empty_character
from ui_widgets import (DotRow, CheckBox, ScrollFrame,
                        section_label, card, _add_description_widget)


_DICE_COLOR = "#00cc44"
_MEGA_COLOR = "#cc3333"

# Matches any standard attribute or "power rating" / "Quantum" keyword
_ATTR_KW_RE = re.compile(
    r'\b(?:power\s+rating|quantum|strength|dexterity|stamina|perception|'
    r'intelligence|wits|appearance|manipulation|charisma)\b',
    re.IGNORECASE,
)


def _has_expr(text, power_name=None):
    """Return True when text has a (…) or […] group with a resolvable token."""
    for m in re.finditer(r'\(([^()]*)\)|\[([^\[\]]*)\]', text):
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        if _ATTR_KW_RE.search(inner):
            return True
        if power_name and re.search(r'\b' + re.escape(power_name) + r'\b',
                                    inner, re.IGNORECASE):
            return True
    return False


def _resolve_stat_rich(text, rating, quantum, power_name=None,
                       attr_vars=None, mega_vars=None):
    """Evaluate (…) / […] expressions; return list of (segment_text, tag).
    tag ∈ {'normal', 'dice', 'mega'}.
    'dice' = resolved number shown in green+underline (clickable future dice roller).
    'mega' = mega-attribute addendum shown in red, not underlined.
    attr_vars  — dict  UPPERCASE_NAME → tk.IntVar   (all standard attributes)
    mega_vars  — dict "Mega-Name"    → tk.IntVar   (mega-attribute dots)
    """
    attr_vars = attr_vars or {}
    mega_vars = mega_vars or {}

    # Build value lookup: lowercase key → current int value
    lookup = {"power rating": rating, "quantum": quantum}
    if power_name:
        lookup[power_name.lower()] = rating
    for k, v in attr_vars.items():
        lookup[k.lower()] = v.get()

    def _has_token(inner):
        il = inner.lower()
        for k in lookup:
            if k == "power rating":
                if re.search(r'power\s+rating', il):
                    return True
            elif re.search(r'\b' + re.escape(k) + r'\b', il):
                return True
        return False

    def _eval_inner(inner):
        """Substitute tokens, evaluate; return (num_str, mega_total) or (None, 0)."""
        mega_total = 0
        for mk, mv in mega_vars.items():
            base = mk[5:].lower()           # "Mega-Stamina" → "stamina"
            if re.search(r'\b' + re.escape(base) + r'\b', inner.lower()):
                mega_total += mv.get()
        ev = inner
        for k in sorted(lookup, key=len, reverse=True):
            vs = str(lookup[k])
            if k == "power rating":
                ev = re.sub(r'power\s+rating', vs, ev, flags=re.IGNORECASE)
            else:
                ev = re.sub(r'\b' + re.escape(k) + r'\b', vs, ev, flags=re.IGNORECASE)
        ev = re.sub(r'\s*[xX×]\s*', ' * ', ev)
        try:
            result = eval(ev)
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            return str(result), mega_total
        except Exception:
            return None, 0

    # Phase 1 — tokenise text into segments
    segs = []       # each entry is [tag, text], mutable for phase 2
    prev = 0
    for m in re.finditer(r'\(([^()]*)\)|\[([^\[\]]*)\]', text):
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        if m.start() > prev:
            segs.append(["normal", text[prev:m.start()]])
        if _has_token(inner):
            num_str, mega = _eval_inner(inner)
            if num_str is not None:
                segs.append(["dice", num_str])
                if mega > 0:
                    segs.append(["mega", f" ({mega})"])
            else:
                segs.append(["normal", m.group(0)])
        else:
            segs.append(["normal", m.group(0)])
        prev = m.end()
    if prev < len(text):
        segs.append(["normal", text[prev:]])

    # Phase 2 — merge a dice segment with any immediately-following arithmetic
    # so  ("12", dice) + (" + 40 km", normal) → ("52", dice) + (" km", normal)
    # and ("7",  dice) + (" + ",      normal) + ("12", dice) → ("19", dice)
    changed = True
    while changed:
        changed = False
        out = []
        i = 0
        while i < len(segs):
            tag, val = segs[i]
            if tag != "dice":
                out.append([tag, val])
                i += 1
                continue
            j, cur = i + 1, val
            while j < len(segs):
                nt, nv = segs[j]
                if nt == "mega":
                    break
                if nt == "normal":
                    # Case A: " op N…" immediately at start of next normal segment
                    ma = re.match(
                        r'^(\s*[+\-]\s*\d+(?:\.\d+)?|\s*[xX×*\/]\s*\d+(?:\.\d+)?)',
                        nv)
                    if ma:
                        arith = re.sub(r'[xX×]', '*', ma.group(1))
                        try:
                            nval = eval(cur + arith)
                            if isinstance(nval, float) and nval.is_integer():
                                nval = int(nval)
                            cur = str(nval)
                            rest = nv[len(ma.group(1)):]
                            if rest:
                                segs[j] = ["normal", rest]
                            else:
                                j += 1
                            changed = True
                            continue
                        except Exception:
                            pass
                    # Case B: pure operator segment + next dice segment
                    mb = re.match(r'^(\s*[+\-]\s*|\s*[xX×*\/]\s*)$', nv)
                    if mb and j + 1 < len(segs) and segs[j + 1][0] == "dice":
                        op = re.sub(r'[xX×]', '*', mb.group(1))
                        try:
                            nval = eval(cur + op + segs[j + 1][1])
                            if isinstance(nval, float) and nval.is_integer():
                                nval = int(nval)
                            cur = str(nval)
                            j += 2
                            changed = True
                            continue
                        except Exception:
                            pass
                    break
                break
            out.append(["dice", cur])
            if j < len(segs) and segs[j][0] == "mega":   # carry trailing mega tag
                out.append(segs[j])
                j += 1
            i = j
        segs = out

    return [(val, tag) for tag, val in segs]


def _find_expr_attr_vars(text, attr_vars, mega_vars):
    """Return IntVars for attributes (+ their mega versions) referenced inside
    (…) or […] groups in text.  Used to set up live-update traces."""
    result, seen = [], set()
    for m in re.finditer(r'\(([^()]*)\)|\[([^\[\]]*)\]', text):
        inner = (m.group(1) if m.group(1) is not None else m.group(2)).lower()
        for k, v in attr_vars.items():
            kl = k.lower()
            if kl in seen:
                continue
            if re.search(r'\b' + re.escape(kl) + r'\b', inner, re.IGNORECASE):
                result.append(v)
                seen.add(kl)
                mega_key = "Mega-" + k.capitalize()
                if mega_key in mega_vars:
                    result.append(mega_vars[mega_key])
    return result


def _configure_dice_tags(tw):
    """Configure 'dice' (green, underline, hand cursor) and 'mega' (red) tags."""
    tw.tag_configure("dice", foreground=_DICE_COLOR, underline=True)
    tw.tag_configure("mega", foreground=_MEGA_COLOR)
    tw.tag_bind("dice", "<Enter>", lambda e: tw.config(cursor="hand2"))
    tw.tag_bind("dice", "<Leave>", lambda e: tw.config(cursor=""))


# ─── Character Sheet Frame ────────────────────────────────────────────────────
class CharacterFrame(tk.Frame):
    def __init__(self, parent, cfg, on_title_change=None):
        super().__init__(parent, bg=BG_DARK)
        self.cfg = cfg
        self.char = empty_character(self.cfg)
        self._current_file = None
        self._dirty = False
        self._on_title_change = on_title_change
        self._preset_specs = self.cfg.get("ability_specialties", {})
        self._specialisations = {}
        self._custom_ability_frames = {}
        self._all_powers = load_powers()
        self._powers_by_id = {p["PowerID"]: p for p in self._all_powers}

        self._build_ui()
        self._load_char_to_ui()

    # ── Main UI skeleton ───────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()

        mid = tk.Frame(self, bg=BG_DARK)
        mid.pack(fill="both", expand=True, padx=6, pady=4)

        self._build_left_tabs(mid)
        self._build_center(mid)
        self._build_health_panel(mid)

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
            ("GAME NOTES",             "notes"),
            ("PORTRAIT",               "portrait"),
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
        self._tab_frames["attrs"]   = self._build_attrs_tab(self._center)
        self._tab_frames["advs"]    = self._build_advs_tab(self._center)
        self._tab_frames["combat"]  = self._build_combat_tab(self._center)
        self._tab_frames["powers"]  = self._build_powers_tab(self._center)
        self._tab_frames["notes"]   = self._build_notes_tab(self._center)
        self._tab_frames["portrait"] = self._build_portrait_tab(self._center)

        self._switch_tab("attrs")

    # ── ATTRIBUTES & ABILITIES tab ────────────────────────────────────────────
    def _build_attrs_tab(self, parent):
        sf = ScrollFrame(parent, bg=BG_DARK)
        inner = sf.inner

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

            tk.Label(col, text=group_name, font=("Arial", 10, "bold"),
                     bg=BG_PANEL, fg="white").pack(fill="x", pady=(0, 4))

            for attr in attrs:
                self._build_attr_block(col, attr)

        return sf

    def _build_attr_block(self, parent, attr):
        frame = card(parent)
        frame.pack(fill="x", pady=3)

        hdr = tk.Frame(frame, bg=BG_CARD)
        hdr.pack(fill="x", padx=6, pady=(4, 2))

        tk.Label(hdr, text=attr, font=("Arial", 9, "bold"),
                 bg=BG_CARD, fg=GOLD).pack(side="left")

        var = tk.IntVar(value=1)
        self._attr_vars[attr] = var
        var.trace_add("write", lambda *_: self._mark_dirty())

        right_cluster = tk.Frame(hdr, bg=BG_CARD)
        right_cluster.pack(side="right")

        dots = DotRow(right_cluster, max_dots=5, min_val=1, var=var, bg=BG_CARD)
        dots.pack(side="left")

        tk.Label(right_cluster, text=" —", font=("Arial", 9),
                 bg=BG_CARD, fg=TEXT_DIM).pack(side="left")

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

        if mega_name:
            if not hasattr(self, "_mega_attr_redraw"):
                self._mega_attr_redraw = {}
            self._mega_attr_redraw[mega_name] = _draw_mega
        _draw_mega()

        abilities = self.cfg["abilities"].get(attr, [])
        for skill in abilities:
            self._build_ability_row(frame, skill, BG_CARD)

        self._custom_ability_vars[attr] = []
        custom_container = tk.Frame(frame, bg=BG_CARD)
        custom_container.pack(fill="x", padx=6, pady=0)
        self._custom_ability_frames[attr] = custom_container

        add_btn = tk.Label(frame, text="+ Add Ability",
                           font=("Arial", 7, "bold"), bg=BG_CARD, fg=ACCENT,
                           cursor="hand2")
        add_btn.pack(anchor="w", padx=8, pady=(1, 3))
        add_btn.bind("<Button-1>", lambda e, a=attr: self._add_custom_ability(a))

    def _build_ability_row(self, parent, skill, bg_color):
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

        plus_lbl = tk.Label(top_row, text="+", font=("Arial", 8, "bold"),
                             bg=bg_color, fg=ACCENT, cursor="hand2")
        plus_lbl.pack(side="left", padx=(0, 4))

        inline_frame = tk.Frame(top_row, bg=bg_color)
        inline_frame.pack(side="left", fill="x", expand=True)

        self._spec_refresh_funcs = getattr(self, "_spec_refresh_funcs", {})

        def refresh_spec_tags():
            for w in inline_frame.winfo_children():
                w.destroy()

            entries = self._specialisations.get(skill, [])
            for entry in entries:
                s_name, s_var = entry
                row = tk.Frame(inline_frame, bg=bg_color)
                row.pack(fill="x", anchor="w")
                _make_spec_cb(row, s_name, s_var)

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

    def _add_custom_ability(self, attr, name="", val=0):
        container = self._custom_ability_frames[attr]
        name_var = tk.StringVar(value=name)
        val_var  = tk.IntVar(value=val)
        name_var.trace_add("write", lambda *_: self._mark_dirty())
        val_var.trace_add("write",  lambda *_: self._mark_dirty())

        row = tk.Frame(container, bg=BG_CARD)
        row.pack(fill="x", pady=1)

        entry_w = tk.Entry(row, textvariable=name_var, font=("Arial", 8),
                           bg=BG_MID, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                           relief="flat", width=14)
        entry_w.pack(side="left")
        DotRow(row, max_dots=5, min_val=0, var=val_var, bg=BG_CARD).pack(side="left", padx=4)

        x_lbl = tk.Label(row, text="×", font=("Arial", 9, "bold"),
                         bg=BG_CARD, fg=TEXT_DIM, cursor="hand2")
        x_lbl.pack(side="left", padx=(0, 2))

        entry_tuple = (name_var, val_var, row)
        self._custom_ability_vars[attr].append(entry_tuple)

        def _remove(r=row, a=attr, dirty=True):
            self._custom_ability_vars[a] = [
                e for e in self._custom_ability_vars[a] if e[2] is not r
            ]
            r.destroy()
            if dirty:
                self._mark_dirty()

        x_lbl.bind("<Button-1>", lambda e, fn=_remove: self.after(0, fn))
        entry_w.bind("<FocusOut>", lambda e: _remove(dirty=False) if not name_var.get().strip() else None)
        entry_w.bind("<Escape>",   lambda e: _remove(dirty=False))
        if not name:
            entry_w.focus_set()

    def _show_bg_menu(self, event):
        menu = tk.Menu(self, tearoff=0,
                       bg=BG_MID, fg=TEXT_MAIN, activebackground=ACCENT,
                       activeforeground="white", font=("Arial", 9))
        for bg_name in self.cfg.get("backgrounds", []):
            menu.add_command(label=bg_name,
                             command=lambda b=bg_name: self._add_background(name=b))
        menu.add_separator()
        menu.add_command(label="Custom…", command=lambda: self._add_background())
        menu.post(event.x_root, event.y_root)

    def _add_background(self, name="", val=0):
        name_var = tk.StringVar(value=name)
        val_var  = tk.IntVar(value=val)
        name_var.trace_add("write", lambda *_: self._mark_dirty())
        val_var.trace_add("write",  lambda *_: self._mark_dirty())

        row = tk.Frame(self._bg_container, bg=BG_CARD)
        row.pack(fill="x", pady=1)

        entry_w = tk.Entry(row, textvariable=name_var, font=("Arial", 8),
                           bg=BG_MID, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                           relief="flat", width=14)
        entry_w.pack(side="left", padx=(4, 0))
        DotRow(row, max_dots=5, min_val=0, var=val_var, bg=BG_CARD).pack(side="left", padx=4)

        x_lbl = tk.Label(row, text="×", font=("Arial", 9, "bold"),
                         bg=BG_CARD, fg=TEXT_DIM, cursor="hand2")
        x_lbl.pack(side="left", padx=(0, 2))

        entry_tuple = (name_var, val_var, row)
        self._bg_rows.append(entry_tuple)

        def _remove(r=row, dirty=True):
            self._bg_rows = [e for e in self._bg_rows if e[2] is not r]
            r.destroy()
            if dirty:
                self._mark_dirty()

        x_lbl.bind("<Button-1>", lambda e, fn=_remove: self.after(0, fn))
        entry_w.bind("<FocusOut>", lambda e: _remove(dirty=False) if not name_var.get().strip() else None)
        entry_w.bind("<Escape>",   lambda e: _remove(dirty=False))
        if not name:
            entry_w.focus_set()

    # ── ADVANTAGES tab ────────────────────────────────────────────────────────
    def _build_advs_tab(self, parent):
        sf = ScrollFrame(parent, bg=BG_DARK)
        inner = sf.inner

        cols = tk.Frame(inner, bg=BG_DARK)
        cols.pack(fill="both", expand=True, padx=4, pady=4)
        for c in range(3):
            cols.columnconfigure(c, weight=1)

        col0 = tk.Frame(cols, bg=BG_DARK)
        col0.grid(row=0, column=0, sticky="nsew", padx=4)

        section_label(col0, "BACKGROUNDS")
        self._bg_rows = []
        self._bg_container = tk.Frame(col0, bg=BG_DARK)
        self._bg_container.pack(fill="x", pady=0)

        add_bg_btn = tk.Label(col0, text="+ Add Background",
                              font=("Arial", 8, "bold"),
                              bg=BG_DARK, fg=ACCENT, cursor="hand2")
        add_bg_btn.pack(anchor="w", padx=8, pady=(1, 3))
        add_bg_btn.bind("<Button-1>", self._show_bg_menu)

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

        aber_hdr = tk.Frame(col0, bg=BG_DARK)
        aber_hdr.pack(fill="x", pady=(6, 0))
        section_label(aber_hdr, "ABERRATIONS")
        aber_add_btn = tk.Label(aber_hdr, text="+ Add",
                                font=("Arial", 8, "bold"), bg=BG_DARK, fg=ACCENT, cursor="hand2")
        aber_add_btn.pack(side="right", padx=6)
        aber_add_btn.bind("<Button-1>", self._show_aberration_picker)
        self._aberration_container = tk.Frame(col0, bg=BG_DARK)
        self._aberration_container.pack(fill="x", padx=2)
        self._aberration_cards = []

        section_label(col0, "QUANTUM")
        qf = card(col0)
        qf.pack(fill="x", pady=2, padx=2)
        tk.Label(qf, text="Quantum:", font=("Arial", 8),
                 bg=BG_CARD, fg=TEXT_MAIN).pack(side="left", padx=4)
        self._quantum_attr_var = tk.IntVar(value=1)
        self._quantum_attr_var.trace_add("write", lambda *_: self._mark_dirty())
        DotRow(qf, max_dots=10, min_val=1, var=self._quantum_attr_var, bg=BG_CARD).pack(side="left")

        col1 = tk.Frame(cols, bg=BG_DARK)
        col1.grid(row=0, column=1, sticky="nsew", padx=4)
        section_label(col1, "MEGA-ATTRIBUTES")
        self._mega_vars = {}
        self._mega_enhancements    = {}
        self._mega_enh_refresh     = {}
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

            inline_f  = tk.Frame(top_row, bg=BG_CARD)
            inline_f.pack(side="left", fill="x", expand=True)

            def _make_enh_cb(frame, name, bvar, bg=BG_CARD):
                tk.Checkbutton(frame, text=name, variable=bvar,
                               font=("Arial", 7, "italic"),
                               bg=bg, fg=GOLD,
                               selectcolor=BG_MID,
                               activebackground=bg, activeforeground=GOLD,
                               relief="flat", bd=0,
                               command=self._mark_dirty).pack(side="left", padx=(0, 4))

            def _refresh_enh(ma=ma, inf=inline_f):
                for w in inf.winfo_children(): w.destroy()
                entries = self._mega_enhancements.get(ma, [])
                for entry in entries:
                    r = tk.Frame(inf, bg=BG_CARD)
                    r.pack(fill="x", anchor="w")
                    _make_enh_cb(r, entry[0], entry[1])

            self._mega_enh_refresh[ma] = _refresh_enh

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

    # ── QUANTUM POWERS tab ───────────────────────────────────────────────────
    def _build_powers_tab(self, parent):
        sf = ScrollFrame(parent, bg=BG_DARK)
        inner = sf.inner

        top = tk.Frame(inner, bg=BG_DARK)
        top.pack(fill="x", padx=6, pady=(6, 2))
        section_label(top, "QUANTUM POWERS")
        add_btn = tk.Label(top, text="+ Add Power",
                           font=("Arial", 8, "bold"), bg=BG_DARK, fg=ACCENT, cursor="hand2")
        add_btn.pack(side="right", padx=8)
        add_btn.bind("<Button-1>", self._show_power_picker)
        mod_btn = tk.Label(top, text="+ Add Body Modification",
                           font=("Arial", 8, "bold"), bg=BG_DARK, fg=ACCENT, cursor="hand2")
        mod_btn.pack(side="right", padx=4)
        mod_btn.bind("<Button-1>", self._show_body_mod_picker)

        grid = tk.Frame(inner, bg=BG_DARK)
        grid.pack(fill="both", expand=True, padx=4, pady=4)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        self._powers_col_left  = tk.Frame(grid, bg=BG_DARK)
        self._powers_col_right = tk.Frame(grid, bg=BG_DARK)
        self._powers_col_left.grid(row=0, column=0, sticky="nsew", padx=2)
        self._powers_col_right.grid(row=0, column=1, sticky="nsew", padx=2)

        self._power_cards = []

        mod_section = tk.Frame(inner, bg=BG_DARK)
        mod_section.pack(fill="x", padx=4, pady=(8, 4))
        section_label(mod_section, "BODY MODIFICATIONS")
        self._body_mod_container = tk.Frame(inner, bg=BG_DARK)
        self._body_mod_container.pack(fill="x", padx=4, pady=(0, 4))
        self._body_mod_cards = []

        return sf

    def _show_power_picker(self, event=None):
        added_variant_sets: dict = {}
        for e in self._power_cards:
            added_variant_sets.setdefault(e["power_id"], set()).add(e.get("variant") or "")

        def _is_available(p):
            if p["PowerType"] == "Miscellaneous":
                return False
            pid = p["PowerID"]
            if p.get("AllowCustomVariant"):
                return True
            variants = p.get("Variants")
            if not variants:
                return pid not in added_variant_sets
            already = added_variant_sets.get(pid, set())
            return not all(v in already for v in variants)

        available = [p for p in self._all_powers if _is_available(p)]
        if not available:
            messagebox.showinfo("Powers", "All available powers have been added.")
            return

        win = tk.Toplevel(self, bg=BG_DARK)
        win.title("Add Quantum Power")
        win.geometry("320x420")
        win.grab_set()

        tk.Label(win, text="Select a Power", font=("Arial", 10, "bold"),
                 bg=BG_DARK, fg=ACCENT).pack(pady=(8, 4))

        frm = tk.Frame(win, bg=BG_DARK)
        frm.pack(fill="both", expand=True, padx=8)
        sb = tk.Scrollbar(frm)
        sb.pack(side="right", fill="y")
        lb = tk.Listbox(frm, yscrollcommand=sb.set, bg=BG_MID, fg=TEXT_MAIN,
                        selectbackground=ACCENT, font=("Arial", 9),
                        activestyle="none", relief="flat")
        lb.pack(side="left", fill="both", expand=True)
        sb.config(command=lb.yview)

        by_level = {}
        for p in available:
            by_level.setdefault(p.get("PowerLevel", "?"), []).append(p)

        index_map = {}
        i = 0
        for level in sorted(by_level.keys(), key=str):
            lb.insert("end", f"── Level {level} ──")
            lb.itemconfig(i, fg=GOLD, selectbackground=BG_DARK)
            index_map[i] = None
            i += 1
            for p in sorted(by_level[level], key=lambda x: x["PowerName"]):
                tag = " ★" if p["PowerType"] == "Mastery" else ""
                lb.insert("end", f"  {p['PowerName']}{tag}")
                index_map[i] = p["PowerID"]
                i += 1

        def _confirm():
            sel = lb.curselection()
            if not sel:
                return
            pid = index_map.get(sel[0])
            if not pid:
                return
            p = self._powers_by_id[pid]
            win.destroy()
            if p.get("Variants") or p.get("AllowCustomVariant"):
                self._show_variant_picker(p, on_chosen=lambda v: self._add_power_card(pid, variant=v))
            else:
                self._add_power_card(pid)

        lb.bind("<Double-Button-1>", lambda e: _confirm())
        tk.Button(win, text="Add", command=_confirm,
                  bg=ACCENT, fg="white", font=("Arial", 9, "bold"),
                  relief="flat", cursor="hand2").pack(pady=6)

    def _show_variant_picker(self, power_data, on_chosen):
        pid = power_data["PowerID"]
        already_used = {e.get("variant") or "" for e in self._power_cards if e["power_id"] == pid}
        remaining = [v for v in power_data.get("Variants", []) if v not in already_used]
        allow_custom = power_data.get("AllowCustomVariant", False)

        if not remaining and not allow_custom:
            return

        display_items = list(remaining)
        if allow_custom:
            display_items.append("Custom…")

        win = tk.Toplevel(self, bg=BG_DARK)
        win.title(f"Choose — {power_data['PowerName']}")
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text=f"Choose the form for\n{power_data['PowerName']}:",
                 font=("Arial", 10, "bold"), bg=BG_DARK, fg=ACCENT,
                 justify="center").pack(pady=(12, 6), padx=16)

        frm = tk.Frame(win, bg=BG_DARK)
        frm.pack(padx=12, pady=(0, 4))
        lb = tk.Listbox(frm, bg=BG_MID, fg=TEXT_MAIN, selectbackground=ACCENT,
                        selectforeground="white", font=("Arial", 10), activestyle="none",
                        relief="flat", width=22, height=min(len(display_items), 12))
        lb.pack()
        for v in display_items:
            lb.insert("end", f"  {v}")
        lb.selection_set(0)

        custom_frame = tk.Frame(win, bg=BG_DARK)
        tk.Label(custom_frame, text="Form name:", font=("Arial", 8),
                 bg=BG_DARK, fg=TEXT_DIM).pack(side="left")
        custom_var = tk.StringVar()
        custom_entry = tk.Entry(custom_frame, textvariable=custom_var, font=("Arial", 9),
                                bg=BG_CARD, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                                relief="flat", width=16)
        custom_entry.pack(side="left", padx=(4, 0))

        def _sync_custom(*_):
            sel = lb.curselection()
            is_custom = bool(sel) and display_items[sel[0]] == "Custom…"
            if is_custom:
                custom_frame.pack(padx=12, pady=(2, 0), fill="x")
                custom_entry.focus_set()
            else:
                custom_frame.pack_forget()
            win.update_idletasks()
            win.geometry(f"260x{win.winfo_reqheight()}")

        lb.bind("<<ListboxSelect>>", _sync_custom)

        def _confirm():
            sel = lb.curselection()
            if not sel:
                return
            if display_items[sel[0]] == "Custom…":
                chosen = custom_var.get().strip()
                if not chosen:
                    custom_entry.focus_set()
                    return
            else:
                chosen = display_items[sel[0]]
            win.destroy()
            on_chosen(chosen)

        lb.bind("<Double-Button-1>", lambda e: _confirm())
        custom_entry.bind("<Return>", lambda e: _confirm())
        win.bind("<Escape>", lambda e: win.destroy())

        btn_row = tk.Frame(win, bg=BG_DARK)
        btn_row.pack(pady=(4, 12))
        tk.Button(btn_row, text="Choose", command=_confirm, bg=ACCENT, fg="white",
                  font=("Arial", 9, "bold"), relief="flat", padx=12).pack(side="left", padx=4)
        tk.Button(btn_row, text="Cancel", command=win.destroy, bg=BG_MID, fg=TEXT_MAIN,
                  font=("Arial", 9), relief="flat", padx=12).pack(side="left", padx=4)

        win.update_idletasks()
        win.geometry(f"260x{win.winfo_reqheight()}")

    def _add_cost_row(self, parent, power_data, bg, prof_var=None):
        """Add a Cost: line. prof_var makes it live (learned = level, unlearned = 2×level)."""
        duration = str(power_data.get("Duration", "")).strip().lower()
        level_str = str(power_data.get("PowerLevel", "?"))

        r = tk.Frame(parent, bg=bg)
        r.pack(fill="x", padx=6, pady=(0, 1))
        tk.Label(r, text="Cost:", font=("Arial", 8, "bold"),
                 bg=bg, fg=TEXT_DIM, width=10, anchor="w").pack(side="left")

        cost_var = tk.StringVar()

        def _compute():
            if duration == "permanent":
                return "0 qp"
            try:
                lvl = int(level_str)
            except ValueError:
                return "?"
            if prof_var is None:
                return f"{lvl} qp"
            return f"{lvl} qp" if prof_var.get() else f"{lvl * 2} qp (unlearned)"

        if prof_var is not None:
            prof_var.trace_add("write", lambda *_: cost_var.set(_compute()))
        cost_var.set(_compute())

        tk.Label(r, textvariable=cost_var, font=("Arial", 8),
                 bg=bg, fg=TEXT_MAIN).pack(side="left")

    def _add_dice_pool_row(self, parent, dice_pool_str, rating_var, bg, label_width=13):
        """Add a Dice Pool: line with live-computed prefix and red mega indicator."""
        r = tk.Frame(parent, bg=bg)
        r.pack(fill="x", pady=0)
        tk.Label(r, text="Dice Pool:", font=("Arial", 8, "bold"),
                 bg=bg, fg=TEXT_DIM, width=label_width, anchor="w").pack(side="left")

        parts = re.split(r'\s*\+\s*', dice_pool_str, maxsplit=1)
        if len(parts) < 2:
            tk.Label(r, text=dice_pool_str, font=("Arial", 8),
                     bg=bg, fg=TEXT_MAIN, anchor="w").pack(side="left")
            return

        attr_raw = parts[0].strip()
        attr_upper = attr_raw.upper()

        if attr_upper == "QUANTUM":
            base_var = self._quantum_attr_var
            mega_var = None
        else:
            base_var = self._attr_vars.get(attr_upper)
            mega_key = "Mega-" + attr_raw.capitalize()
            mega_var = self._mega_vars.get(mega_key)

        if base_var is None:
            tk.Label(r, text=dice_pool_str, font=("Arial", 8),
                     bg=bg, fg=TEXT_MAIN, anchor="w").pack(side="left")
            return

        num_var  = tk.StringVar()
        mega_var2 = tk.StringVar()

        def _update(*_):
            total = base_var.get() + rating_var.get()
            num_var.set(str(total))
            if mega_var is not None:
                mv = mega_var.get()
                mega_var2.set(f" ({mv})" if mv > 0 else "")

        base_var.trace_add("write", _update)
        rating_var.trace_add("write", _update)
        if mega_var is not None:
            mega_var.trace_add("write", _update)
        _update()

        tk.Label(r, textvariable=num_var, font=("Arial", 8, "bold"),
                 bg=bg, fg=TEXT_MAIN).pack(side="left")
        if mega_var is not None:
            tk.Label(r, textvariable=mega_var2, font=("Arial", 8, "bold"),
                     bg=bg, fg="#cc3333").pack(side="left")
        tk.Label(r, text=f" - {dice_pool_str}", font=("Arial", 8),
                 bg=bg, fg=TEXT_MAIN, anchor="w",
                 wraplength=220, justify="left").pack(side="left")

    def _show_body_mod_picker(self, event=None):
        bm_power = next((p for p in self._all_powers if p["PowerID"] == "PWR065"), None)
        mods = bm_power.get("Modifications", []) if bm_power else []
        display_items = [m["name"] for m in mods] + ["Custom…"]

        win = tk.Toplevel(self, bg=BG_DARK)
        win.title("Add Body Modification")
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Choose a Body Modification:",
                 font=("Arial", 10, "bold"), bg=BG_DARK, fg=ACCENT).pack(pady=(12, 6), padx=16)

        frm = tk.Frame(win, bg=BG_DARK)
        frm.pack(padx=12, pady=(0, 4))
        lb = tk.Listbox(frm, bg=BG_MID, fg=TEXT_MAIN, selectbackground=ACCENT,
                        selectforeground="white", font=("Arial", 10), activestyle="none",
                        relief="flat", width=26, height=min(len(display_items), 12))
        lb.pack()
        for v in display_items:
            lb.insert("end", f"  {v}")
        lb.selection_set(0)

        desc_var = tk.StringVar()
        tk.Label(win, textvariable=desc_var, font=("Arial", 8), bg=BG_DARK, fg=TEXT_DIM,
                 wraplength=220, justify="left").pack(padx=12, pady=(0, 4), fill="x")

        custom_frame = tk.Frame(win, bg=BG_DARK)
        tk.Label(custom_frame, text="Name:", font=("Arial", 8),
                 bg=BG_DARK, fg=TEXT_DIM).pack(side="left")
        custom_var = tk.StringVar()
        custom_entry = tk.Entry(custom_frame, textvariable=custom_var, font=("Arial", 9),
                                bg=BG_CARD, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                                relief="flat", width=18)
        custom_entry.pack(side="left", padx=(4, 0))

        def _sync_desc(*_):
            sel = lb.curselection()
            if not sel:
                desc_var.set("")
                return
            chosen_name = display_items[sel[0]]
            m = next((x for x in mods if x["name"] == chosen_name), None)
            desc_var.set(f"{m['cost']} — {m['description']}" if m else "")
            if chosen_name == "Custom…":
                custom_frame.pack(padx=12, pady=(2, 0), fill="x")
                custom_entry.focus_set()
            else:
                custom_frame.pack_forget()
            win.update_idletasks()
            win.geometry(f"280x{win.winfo_reqheight()}")

        lb.bind("<<ListboxSelect>>", _sync_desc)

        def _confirm():
            sel = lb.curselection()
            if not sel:
                return
            chosen = display_items[sel[0]]
            if chosen == "Custom…":
                chosen = custom_var.get().strip()
                if not chosen:
                    custom_entry.focus_set()
                    return
            win.destroy()
            self._add_body_mod_card(chosen)

        lb.bind("<Double-Button-1>", lambda e: _confirm())
        custom_entry.bind("<Return>", lambda e: _confirm())
        win.bind("<Escape>", lambda e: win.destroy())

        btn_row = tk.Frame(win, bg=BG_DARK)
        btn_row.pack(pady=(4, 12))
        tk.Button(btn_row, text="Add", command=_confirm, bg=ACCENT, fg="white",
                  font=("Arial", 9, "bold"), relief="flat", padx=12).pack(side="left", padx=4)
        tk.Button(btn_row, text="Cancel", command=win.destroy, bg=BG_MID, fg=TEXT_MAIN,
                  font=("Arial", 9), relief="flat", padx=12).pack(side="left", padx=4)

        _sync_desc()
        win.update_idletasks()
        win.geometry(f"280x{win.winfo_reqheight()}")

    def _add_body_mod_card(self, name):
        outer = tk.Frame(self._body_mod_container, bg=BG_CARD,
                         highlightbackground=BORDER, highlightthickness=1)
        outer.pack(fill="x", pady=2, padx=2)

        hdr = tk.Frame(outer, bg=BG_PANEL)
        hdr.pack(fill="x")
        tk.Label(hdr, text=name, font=("Arial", 10, "bold"),
                 bg=BG_PANEL, fg=GOLD, anchor="w").pack(side="left", padx=6, pady=3)
        x_lbl = tk.Label(hdr, text="×", font=("Arial", 10, "bold"),
                         bg=BG_PANEL, fg=TEXT_DIM, cursor="hand2")
        x_lbl.pack(side="right", padx=6)

        entry = {"name": name, "frame": outer}
        self._body_mod_cards.append(entry)
        self._mark_dirty()

        def _remove():
            outer.destroy()
            self._body_mod_cards.remove(entry)
            self._mark_dirty()

        x_lbl.bind("<Button-1>", lambda e: _remove())

    def _show_aberration_picker(self, event=None):
        ab_cfg = self.cfg.get("aberrations", {})
        groups = [
            ("Low Taint (4–5)",     ab_cfg.get("low",             {}).get("list", [])),
            ("Medium Taint (6–7)",  ab_cfg.get("medium",          {}).get("list", [])),
            ("High Taint (8+)",     ab_cfg.get("high",            {}).get("list", [])),
            ("Mental Disorders",    ab_cfg.get("mental_disorders", {}).get("list", [])),
        ]

        # Build flat display list interleaved with non-selectable headers
        display_items = []   # each entry: (label_str, name_or_None)  None = header
        for group_name, items in groups:
            if not items:
                continue
            display_items.append((f"── {group_name} ──", None))
            for ab in items:
                display_items.append((ab["name"], ab["name"]))
        display_items.append(("── Custom ──", None))
        display_items.append(("Custom…", "Custom…"))

        desc_map = {}
        for _, items in groups:
            for ab in items:
                desc_map[ab["name"]] = ab.get("description", "")

        win = tk.Toplevel(self, bg=BG_DARK)
        win.title("Add Aberration")
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Choose an Aberration:",
                 font=("Arial", 10, "bold"), bg=BG_DARK, fg=ACCENT).pack(pady=(12, 6), padx=16)

        frm = tk.Frame(win, bg=BG_DARK)
        frm.pack(padx=12, pady=(0, 4))
        sb = tk.Scrollbar(frm, orient="vertical")
        lb = tk.Listbox(frm, bg=BG_MID, fg=TEXT_MAIN, selectbackground=ACCENT,
                        selectforeground="white", font=("Arial", 10), activestyle="none",
                        relief="flat", width=28, height=14,
                        yscrollcommand=sb.set)
        sb.config(command=lb.yview)
        lb.pack(side="left")
        sb.pack(side="left", fill="y")

        header_indices = set()
        for i, (label, name) in enumerate(display_items):
            if name is None:
                lb.insert("end", f"  {label}")
                lb.itemconfig(i, fg=GOLD, selectbackground=BG_MID, selectforeground=GOLD)
                header_indices.add(i)
            else:
                lb.insert("end", f"  {label}")

        # Select first real item
        first_real = next((i for i, (_, n) in enumerate(display_items) if n is not None), 0)
        lb.selection_set(first_real)
        lb.see(first_real)

        desc_var = tk.StringVar()
        tk.Label(win, textvariable=desc_var, font=("Arial", 8), bg=BG_DARK, fg=TEXT_DIM,
                 wraplength=240, justify="left").pack(padx=12, pady=(0, 4), fill="x")

        custom_frame = tk.Frame(win, bg=BG_DARK)
        tk.Label(custom_frame, text="Name:", font=("Arial", 8),
                 bg=BG_DARK, fg=TEXT_DIM).pack(side="left")
        custom_var = tk.StringVar()
        custom_entry = tk.Entry(custom_frame, textvariable=custom_var, font=("Arial", 9),
                                bg=BG_CARD, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                                relief="flat", width=20)
        custom_entry.pack(side="left", padx=(4, 0))

        def _sync(*_):
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            if idx in header_indices:
                desc_var.set("")
                custom_frame.pack_forget()
                return
            _, name = display_items[idx]
            desc_var.set(desc_map.get(name, ""))
            if name == "Custom…":
                custom_frame.pack(padx=12, pady=(2, 0), fill="x")
                custom_entry.focus_set()
            else:
                custom_frame.pack_forget()
            win.update_idletasks()
            win.geometry(f"300x{win.winfo_reqheight()}")

        lb.bind("<<ListboxSelect>>", _sync)

        def _confirm():
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            if idx in header_indices:
                return
            _, name = display_items[idx]
            if name == "Custom…":
                name = custom_var.get().strip()
                if not name:
                    custom_entry.focus_set()
                    return
            win.destroy()
            self._add_aberration_card(name)

        lb.bind("<Double-Button-1>", lambda e: _confirm())
        custom_entry.bind("<Return>", lambda e: _confirm())
        win.bind("<Escape>", lambda e: win.destroy())

        btn_row = tk.Frame(win, bg=BG_DARK)
        btn_row.pack(pady=(4, 12))
        tk.Button(btn_row, text="Add", command=_confirm, bg=ACCENT, fg="white",
                  font=("Arial", 9, "bold"), relief="flat", padx=12).pack(side="left", padx=4)
        tk.Button(btn_row, text="Cancel", command=win.destroy, bg=BG_MID, fg=TEXT_MAIN,
                  font=("Arial", 9), relief="flat", padx=12).pack(side="left", padx=4)

        _sync()
        win.update_idletasks()
        win.geometry(f"300x{win.winfo_reqheight()}")

    def _add_aberration_card(self, name):
        outer = tk.Frame(self._aberration_container, bg=BG_CARD,
                         highlightbackground=BORDER, highlightthickness=1)
        outer.pack(fill="x", pady=1, padx=2)

        hdr = tk.Frame(outer, bg=BG_PANEL)
        hdr.pack(fill="x")
        tk.Label(hdr, text=name, font=("Arial", 9, "bold"),
                 bg=BG_PANEL, fg=TEXT_MAIN, anchor="w").pack(side="left", padx=6, pady=2)
        x_lbl = tk.Label(hdr, text="×", font=("Arial", 9, "bold"),
                         bg=BG_PANEL, fg=TEXT_DIM, cursor="hand2")
        x_lbl.pack(side="right", padx=6)

        entry = {"name": name, "frame": outer}
        self._aberration_cards.append(entry)
        self._mark_dirty()

        def _remove():
            outer.destroy()
            self._aberration_cards.remove(entry)
            self._mark_dirty()

        x_lbl.bind("<Button-1>", lambda e: _remove())

    def _add_power_card(self, power_id, rating=1, techniques=None, extras_bought=None, variant=None):
        if techniques is None:
            techniques = []
        if extras_bought is None:
            extras_bought = []
        p = self._powers_by_id.get(power_id)
        if not p:
            return

        self.update_idletasks()
        col = (self._powers_col_left
               if self._powers_col_left.winfo_reqheight() <= self._powers_col_right.winfo_reqheight()
               else self._powers_col_right)

        outer = tk.Frame(col, bg=BG_CARD,
                         highlightbackground=BORDER, highlightthickness=1)
        outer.pack(fill="x", pady=3, padx=2)

        hdr = tk.Frame(outer, bg=BG_PANEL)
        hdr.pack(fill="x")
        _tmpl = p.get("VariantNameTemplate", "")
        display_name = _tmpl.format(variant=variant) if (_tmpl and variant) else p["PowerName"]
        tk.Label(hdr, text=display_name, font=("Arial", 10, "bold"),
                 bg=BG_PANEL, fg=GOLD, anchor="w").pack(side="left", padx=6, pady=4)
        x_lbl = tk.Label(hdr, text="×", font=("Arial", 10, "bold"),
                         bg=BG_PANEL, fg=TEXT_DIM, cursor="hand2")
        x_lbl.pack(side="right", padx=6)
        qmin = str(p.get("PwQuantMin", "")).strip()
        if qmin and qmin.lower() not in ("", "n/a"):
            tk.Label(hdr, text=f"Qmin: {qmin}", font=("Arial", 8),
                     bg=BG_PANEL, fg=TEXT_DIM).pack(side="right", padx=(0, 4))

        line2 = tk.Frame(outer, bg=BG_CARD)
        line2.pack(fill="x", padx=6, pady=(2, 0))
        tk.Label(line2, text="Rating:", font=("Arial", 9),
                 bg=BG_CARD, fg=TEXT_DIM).pack(side="left")
        rating_var = tk.IntVar(value=rating)
        rating_var.trace_add("write", lambda *_: self._mark_dirty())
        DotRow(line2, max_dots=5, min_val=1, var=rating_var, bg=BG_CARD).pack(side="left", padx=4)

        duration_str  = str(p.get("Duration", "")).strip().lower()
        level_str_p   = str(p.get("PowerLevel", "?"))
        cost_var_main = tk.StringVar()
        def _compute_main_cost():
            if duration_str == "permanent":
                return "0 qp"
            try:
                return f"{int(level_str_p)} qp"
            except ValueError:
                return "?"
        cost_var_main.set(_compute_main_cost())
        tk.Label(line2, textvariable=cost_var_main, font=("Arial", 8),
                 bg=BG_CARD, fg=TEXT_DIM).pack(side="right", padx=(0, 4))

        stats_frame = tk.Frame(outer, bg=BG_CARD)
        stats_frame.pack(fill="x", padx=6, pady=2)

        dice_pool = str(p.get("DicePool", "")).strip()
        if dice_pool and dice_pool.lower() not in ("", "n/a"):
            self._add_dice_pool_row(stats_frame, dice_pool, rating_var, BG_CARD)

        other_stat_fields = [
            ("Range",        "Range"),
            ("Area",         "Area"),
            ("Duration",     "Duration"),
            ("Multi-Action", "MultipleActions"),
            ("Effect",       "Effect"),
        ]
        power_name = p.get("PowerName", "")
        stat_traces = []
        for lbl, key in other_stat_fields:
            val = str(p.get(key, "")).strip()
            if not val or val.lower() in ("", "none", "n/a"):
                continue
            r = tk.Frame(stats_frame, bg=BG_CARD)
            r.pack(fill="x", pady=0)
            tk.Label(r, text=f"{lbl}:", font=("Arial", 8, "bold"),
                     bg=BG_CARD, fg=TEXT_DIM, width=13, anchor="w").pack(side="left")
            if _has_expr(val, power_name):
                cf = tk.Frame(r, bg=BG_CARD)
                cf.pack(side="left", fill="x", expand=True)
                xtra = _find_expr_attr_vars(val, self._attr_vars, self._mega_vars)
                def _upd_rich(*_, _cf=cf, _tmpl=val, _pn=power_name):
                    for w in _cf.winfo_children():
                        w.destroy()
                    for seg, tag in _resolve_stat_rich(
                            _tmpl, rating_var.get(), self._quantum_attr_var.get(),
                            _pn, self._attr_vars, self._mega_vars):
                        if tag == "dice":
                            tk.Label(_cf, text=seg, font=("Arial", 8, "underline"),
                                     bg=BG_CARD, fg=_DICE_COLOR,
                                     cursor="hand2", anchor="w").pack(side="left")
                        elif tag == "mega":
                            tk.Label(_cf, text=seg, font=("Arial", 8),
                                     bg=BG_CARD, fg=_MEGA_COLOR,
                                     anchor="w").pack(side="left")
                        else:
                            tk.Label(_cf, text=seg, font=("Arial", 8),
                                     bg=BG_CARD, fg=TEXT_MAIN,
                                     anchor="w").pack(side="left")
                tid_r = rating_var.trace_add("write", _upd_rich)
                tid_q = self._quantum_attr_var.trace_add("write", _upd_rich)
                stat_traces.append((rating_var, tid_r))
                stat_traces.append((self._quantum_attr_var, tid_q))
                for ev_v in xtra:
                    stat_traces.append((ev_v, ev_v.trace_add("write", _upd_rich)))
                _upd_rich()
            else:
                tk.Label(r, text=val, font=("Arial", 8),
                         bg=BG_CARD, fg=TEXT_MAIN, anchor="w",
                         wraplength=200, justify="left").pack(side="left", fill="x", expand=True)

        extras_str = str(p.get("Extras", "")).strip()
        extra_list = [e.strip() for e in extras_str.split(";")
                      if e.strip() and e.strip().lower() not in ("none", "n/a")]
        extra_vars = {n: tk.BooleanVar(value=(n in extras_bought)) for n in extra_list}

        if extra_list:
            extras_row = tk.Frame(stats_frame, bg=BG_CARD)
            extras_row.pack(fill="x", pady=0)
            tk.Label(extras_row, text="Extras:", font=("Arial", 8, "bold"),
                     bg=BG_CARD, fg=TEXT_DIM, width=13, anchor="w").pack(side="left")
            extras_inner = tk.Frame(extras_row, bg=BG_CARD)
            extras_inner.pack(side="left", fill="x", expand=True)

            def _refresh_extras():
                for w in extras_inner.winfo_children():
                    w.destroy()
                bought_names   = [n for n in extra_list if extra_vars[n].get()]
                unbought_names = [n for n in extra_list if not extra_vars[n].get()]
                if bought_names:
                    tk.Label(extras_inner, text=", ".join(bought_names),
                             font=("Arial", 8), bg=BG_CARD, fg=TEXT_MAIN,
                             anchor="w", wraplength=160, justify="left").pack(side="left")
                if unbought_names:
                    def _do_add():
                        avail = [n for n in extra_list if not extra_vars[n].get()]
                        if not avail:
                            return
                        if len(avail) == 1:
                            extra_vars[avail[0]].set(True)
                            self._mark_dirty()
                            _refresh_extras()
                        else:
                            m = tk.Menu(outer, tearoff=False, bg=BG_MID, fg=TEXT_MAIN,
                                        activebackground=ACCENT, activeforeground="white")
                            for n in avail:
                                def _cmd(name=n):
                                    extra_vars[name].set(True)
                                    self._mark_dirty()
                                    _refresh_extras()
                                m.add_command(label=n, command=_cmd)
                            m.post(self.winfo_pointerx(), self.winfo_pointery())
                    tk.Button(extras_inner, text="+", font=("Arial", 8, "bold"),
                              bg=BG_MID, fg=ACCENT, relief="flat", cursor="hand2",
                              command=_do_add).pack(side="left", padx=(4, 0))
                if bought_names:
                    def _do_remove():
                        active = [n for n in extra_list if extra_vars[n].get()]
                        if not active:
                            return
                        if len(active) == 1:
                            extra_vars[active[0]].set(False)
                            self._mark_dirty()
                            _refresh_extras()
                        else:
                            m = tk.Menu(outer, tearoff=False, bg=BG_MID, fg=TEXT_MAIN,
                                        activebackground=ACCENT, activeforeground="white")
                            for n in active:
                                def _cmd(name=n):
                                    extra_vars[name].set(False)
                                    self._mark_dirty()
                                    _refresh_extras()
                                m.add_command(label=n, command=_cmd)
                            m.post(self.winfo_pointerx(), self.winfo_pointery())
                    tk.Button(extras_inner, text="−", font=("Arial", 8, "bold"),
                              bg=BG_MID, fg=TEXT_DIM, relief="flat", cursor="hand2",
                              command=_do_remove).pack(side="left", padx=(2, 0))

            _refresh_extras()

        desc_text = format_description(p.get("Description", ""))
        if desc_text:
            tw = _add_description_widget(outer, desc_text)
            _configure_dice_tags(tw)
            if _has_expr(desc_text, power_name):
                xtra = _find_expr_attr_vars(desc_text, self._attr_vars, self._mega_vars)
                def _upd_desc(*_, _tw=tw, _tmpl=desc_text, _pn=power_name):
                    _tw.config(state="normal")
                    _tw.delete("1.0", "end")
                    for seg, tag in _resolve_stat_rich(
                            _tmpl, rating_var.get(), self._quantum_attr_var.get(),
                            _pn, self._attr_vars, self._mega_vars):
                        _tw.insert("end", seg, tag if tag != "normal" else ())
                    _tw.config(state="disabled")
                tid_r = rating_var.trace_add("write", _upd_desc)
                tid_q = self._quantum_attr_var.trace_add("write", _upd_desc)
                stat_traces.append((rating_var, tid_r))
                stat_traces.append((self._quantum_attr_var, tid_q))
                for ev_v in xtra:
                    stat_traces.append((ev_v, ev_v.trace_add("write", _upd_desc)))
                _upd_desc()

        tech_vars = {}
        if p["PowerType"] == "Mastery":
            sub_hdr = tk.Frame(outer, bg=BG_MID)
            sub_hdr.pack(fill="x", pady=(4, 0))
            tk.Label(sub_hdr, text="TECHNIQUES", font=("Arial", 7, "bold"),
                     bg=BG_MID, fg=ACCENT).pack(side="left", padx=6, pady=2)
            for sp in sorted(p.get("SubPowers", []), key=lambda x: x.get("ResolveOrder", 0)):
                proficient = sp["SubPowerID"] in techniques
                bv = self._add_sub_power_box(outer, sp, proficient,
                                             rating_var, p.get("PowerLevel", "?"),
                                             stat_traces=stat_traces,
                                             power_name=power_name)
                tech_vars[sp["SubPowerID"]] = bv

        entry = {
            "power_id":    power_id,
            "variant":     variant,
            "rating_var":  rating_var,
            "tech_vars":   tech_vars,
            "extra_vars":  extra_vars,
            "frame":       outer,
            "_stat_traces": stat_traces,
        }
        self._power_cards.append(entry)

        def _remove(e=entry, f=outer):
            for var, tid in e.get("_stat_traces", []):
                try:
                    var.trace_remove("write", tid)
                except Exception:
                    pass
            self._power_cards = [c for c in self._power_cards if c is not e]
            self.after(0, f.destroy)
            self._mark_dirty()

        x_lbl.bind("<Button-1>", lambda ev, fn=_remove: self.after(0, fn))
        self._mark_dirty()

    def _add_sub_power_box(self, parent, sp, proficient=False,
                           rating_var=None, power_level="?", stat_traces=None, power_name=None):
        box = tk.Frame(parent, bg=BG_MID,
                       highlightbackground=BORDER, highlightthickness=1)
        box.pack(fill="x", padx=4, pady=2)

        name_row = tk.Frame(box, bg=BG_MID)
        name_row.pack(fill="x", padx=4, pady=(3, 1))
        bv = tk.BooleanVar(value=proficient)
        bv.trace_add("write", lambda *_: self._mark_dirty())
        CheckBox(name_row, var=bv, bg=BG_MID).pack(side="left", padx=(0, 4))
        tk.Label(name_row, text=sp.get("SubPowerName", ""),
                 font=("Arial", 9, "bold"), bg=BG_MID, fg=TEXT_MAIN,
                 anchor="w").pack(side="left")

        sp_data_for_cost = {"PowerLevel": power_level,
                            "Duration": sp.get("Duration", "")}
        self._add_cost_row(box, sp_data_for_cost, BG_MID, prof_var=bv)

        stats = tk.Frame(box, bg=BG_MID)
        stats.pack(fill="x", padx=6, pady=1)

        dice_pool = str(sp.get("DicePool", "")).strip()
        if dice_pool and dice_pool.lower() not in ("", "n/a") and rating_var is not None:
            self._add_dice_pool_row(stats, dice_pool, rating_var, BG_MID, label_width=10)

        sub_stat_fields = [
            ("Range",    "Range"),
            ("Area",     "Area"),
            ("Duration", "Duration"),
        ]
        for lbl, key in sub_stat_fields:
            val = str(sp.get(key, "")).strip()
            if not val or val.lower() in ("", "n/a"):
                continue
            r = tk.Frame(stats, bg=BG_MID)
            r.pack(fill="x")
            tk.Label(r, text=f"{lbl}:", font=("Arial", 8, "bold"),
                     bg=BG_MID, fg=TEXT_DIM, width=10, anchor="w").pack(side="left")
            if _has_expr(val, power_name) and rating_var is not None and stat_traces is not None:
                cf = tk.Frame(r, bg=BG_MID)
                cf.pack(side="left", fill="x", expand=True)
                xtra = _find_expr_attr_vars(val, self._attr_vars, self._mega_vars)
                def _upd_rich(*_, _cf=cf, _tmpl=val, _pn=power_name):
                    for w in _cf.winfo_children():
                        w.destroy()
                    for seg, tag in _resolve_stat_rich(
                            _tmpl, rating_var.get(), self._quantum_attr_var.get(),
                            _pn, self._attr_vars, self._mega_vars):
                        if tag == "dice":
                            tk.Label(_cf, text=seg, font=("Arial", 8, "underline"),
                                     bg=BG_MID, fg=_DICE_COLOR,
                                     cursor="hand2", anchor="w").pack(side="left")
                        elif tag == "mega":
                            tk.Label(_cf, text=seg, font=("Arial", 8),
                                     bg=BG_MID, fg=_MEGA_COLOR,
                                     anchor="w").pack(side="left")
                        else:
                            tk.Label(_cf, text=seg, font=("Arial", 8),
                                     bg=BG_MID, fg=TEXT_MAIN,
                                     anchor="w").pack(side="left")
                tid_r = rating_var.trace_add("write", _upd_rich)
                tid_q = self._quantum_attr_var.trace_add("write", _upd_rich)
                stat_traces.append((rating_var, tid_r))
                stat_traces.append((self._quantum_attr_var, tid_q))
                for ev_v in xtra:
                    stat_traces.append((ev_v, ev_v.trace_add("write", _upd_rich)))
                _upd_rich()
            else:
                tk.Label(r, text=val, font=("Arial", 8),
                         bg=BG_MID, fg=TEXT_MAIN, anchor="w",
                         wraplength=180, justify="left").pack(side="left", fill="x", expand=True)

        desc_text = format_description(sp.get("Description", ""))
        if desc_text:
            tw = _add_description_widget(box, desc_text)
            _configure_dice_tags(tw)
            if _has_expr(desc_text, power_name) and rating_var is not None and stat_traces is not None:
                xtra = _find_expr_attr_vars(desc_text, self._attr_vars, self._mega_vars)
                def _upd_desc(*_, _tw=tw, _tmpl=desc_text, _pn=power_name):
                    _tw.config(state="normal")
                    _tw.delete("1.0", "end")
                    for seg, tag in _resolve_stat_rich(
                            _tmpl, rating_var.get(), self._quantum_attr_var.get(),
                            _pn, self._attr_vars, self._mega_vars):
                        _tw.insert("end", seg, tag if tag != "normal" else ())
                    _tw.config(state="disabled")
                tid_r = rating_var.trace_add("write", _upd_desc)
                tid_q = self._quantum_attr_var.trace_add("write", _upd_desc)
                stat_traces.append((rating_var, tid_r))
                stat_traces.append((self._quantum_attr_var, tid_q))
                for ev_v in xtra:
                    stat_traces.append((ev_v, ev_v.trace_add("write", _upd_desc)))
                _upd_desc()

        return bv

    # ── GAME NOTES tab ───────────────────────────────────────────────────────
    def _build_notes_tab(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        section_label(frame, "GAME NOTES")
        notes_card = tk.Frame(frame, bg=BG_CARD,
                              highlightbackground=BORDER, highlightthickness=1)
        notes_card.pack(fill="both", expand=True, padx=8, pady=4)
        self._notes_text = tk.Text(notes_card, font=("Arial", 9),
                                   bg=BG_MID, fg=TEXT_MAIN,
                                   insertbackground=TEXT_MAIN,
                                   relief="flat", wrap="word")
        vsb = tk.Scrollbar(notes_card, command=self._notes_text.yview)
        vsb.pack(side="right", fill="y")
        self._notes_text.configure(yscrollcommand=vsb.set)
        self._notes_text.pack(fill="both", expand=True, padx=4, pady=4)
        self._notes_text.bind("<<Modified>>", self._on_notes_change)
        return frame

    def _on_notes_change(self, e):
        self._mark_dirty()
        self._notes_text.edit_modified(False)

    # ── PORTRAIT tab ──────────────────────────────────────────────────────────
    PORTRAIT_W = 240
    PORTRAIT_H = 320

    def _build_portrait_tab(self, parent):
        frame = tk.Frame(parent, bg=BG_DARK)
        self._portrait_b64 = ""
        self._portrait_photo = None

        tk.Label(frame, text="CHARACTER PORTRAIT",
                 font=("Arial", 13, "bold"), bg=BG_DARK, fg=ACCENT).pack(pady=(18, 10))

        canvas = tk.Canvas(frame, width=self.PORTRAIT_W, height=self.PORTRAIT_H,
                           bg=BG_MID, highlightbackground=BORDER, highlightthickness=2)
        canvas.pack()
        self._portrait_canvas = canvas
        self._portrait_canvas_img_id = None

        self._draw_portrait_placeholder()

        btn_row = tk.Frame(frame, bg=BG_DARK)
        btn_row.pack(pady=12)

        def _btn(text, cmd):
            return tk.Button(btn_row, text=text, command=cmd,
                             bg=ACCENT, fg="white", relief="flat",
                             font=("Arial", 9, "bold"), padx=12, pady=4,
                             cursor="hand2")

        if PIL_AVAILABLE:
            _btn("Load Image…", self._load_portrait).pack(side="left", padx=6)
            _btn("Clear",       self._clear_portrait).pack(side="left", padx=6)
        else:
            tk.Label(frame,
                     text="Pillow is not installed.\nInstall it with:  pip install Pillow",
                     font=("Arial", 9), bg=BG_DARK, fg=TEXT_DIM,
                     justify="center").pack(pady=4)

        return frame

    def _draw_portrait_placeholder(self):
        c = self._portrait_canvas
        c.delete("all")
        self._portrait_canvas_img_id = None
        w, h = self.PORTRAIT_W, self.PORTRAIT_H
        c.create_line(0, 0, w, h, fill=BORDER, width=1)
        c.create_line(w, 0, 0, h, fill=BORDER, width=1)
        c.create_text(w // 2, h // 2, text="No Portrait",
                      fill=TEXT_DIM, font=("Arial", 11, "italic"))

    def _refresh_portrait(self):
        if not self._portrait_b64 or not PIL_AVAILABLE:
            self._draw_portrait_placeholder()
            return
        try:
            raw = base64.b64decode(self._portrait_b64)
            img = Image.open(io.BytesIO(raw))
            img.thumbnail((self.PORTRAIT_W, self.PORTRAIT_H), Image.LANCZOS)
            c = self._portrait_canvas
            c.delete("all")
            self._portrait_photo = ImageTk.PhotoImage(img)
            x = self.PORTRAIT_W // 2
            y = self.PORTRAIT_H // 2
            self._portrait_canvas_img_id = c.create_image(x, y, anchor="center",
                                                           image=self._portrait_photo)
        except Exception:
            self._draw_portrait_placeholder()

    def _load_portrait(self):
        path = filedialog.askopenfilename(
            title="Select Portrait Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff *.tif"),
                ("All files", "*.*"),
            ]
        )
        if not path:
            return
        try:
            img = Image.open(path).convert("RGB")
            img.thumbnail((300, 400), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            self._portrait_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            self._refresh_portrait()
            self._mark_dirty()
        except Exception as e:
            messagebox.showerror("Image Error", f"Could not load image:\n{e}")

    def _clear_portrait(self):
        self._portrait_b64 = ""
        self._portrait_photo = None
        self._draw_portrait_placeholder()
        self._mark_dirty()

    def _add_mega_enhancement(self, ma, name, refresh_func):
        if ma not in self._mega_enhancements:
            self._mega_enhancements[ma] = []
        if name not in [e[0] for e in self._mega_enhancements[ma]]:
            bv = tk.BooleanVar(value=False)
            bv.trace_add("write", lambda *_: self._mark_dirty())
            if ma == "Mega-Wits" and name == "Enhanced Initiative":
                bv.trace_add("write", self._recalc_initiative)
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
            count_checked = sum(1 for b in checks if b.get())
            var.set(count_checked)
            self._mark_dirty()

        for idx, bv in enumerate(checks):
            bv.trace_add("write", lambda *_, i=idx: on_check_click(i))

        return checks

    def _recalc_initiative(self, *_):
        dex  = self._attr_vars.get("DEXTERITY", tk.IntVar(value=0)).get()
        wits = self._attr_vars.get("WITS",      tk.IntVar(value=0)).get()
        base = dex + wits
        enh = any(
            name == "Enhanced Initiative" and bv.get()
            for name, bv in self._mega_enhancements.get("Mega-Wits", [])
        )
        self._initiative_var.set(f"{base} (+5)" if enh else str(base))

    def _recalc_movement(self, *_):
        dex = self._attr_vars.get("DEXTERITY", tk.IntVar(value=0)).get()
        self._move_vars["walk"].set("7")
        self._move_vars["run"].set(str(dex + 12))
        self._move_vars["sprint"].set(str(dex * 3 + 20))

    # ── COMBAT tab ─────────────────────────────────────────────────────────────
    def _build_combat_tab(self, parent):
        sf = ScrollFrame(parent, bg=BG_DARK)
        inner = sf.inner

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

        ims = tk.Frame(inner, bg=BG_DARK)
        ims.pack(fill="x", padx=4, pady=4)

        ini_f = card(ims)
        ini_f.pack(side="left", fill="both", expand=True, padx=2)
        tk.Label(ini_f, text="INITIATIVE", font=("Arial", 9, "bold"),
                 bg=BG_CARD, fg=GOLD).pack()
        self._initiative_var = tk.StringVar()
        tk.Label(ini_f, textvariable=self._initiative_var,
                 font=("Arial", 11, "bold"), bg=BG_CARD, fg=TEXT_MAIN).pack(padx=6, pady=4)
        self._attr_vars["DEXTERITY"].trace_add("write", self._recalc_initiative)
        self._attr_vars["WITS"].trace_add("write",      self._recalc_initiative)
        self._recalc_initiative()

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
            self._move_vars[key.lower()] = v
            tk.Label(mov_inner, textvariable=v, font=("Arial", 9, "bold"),
                     bg=BG_CARD, fg=TEXT_MAIN, width=4,
                     anchor="center").pack(side="left", padx=2, pady=4)
        self._attr_vars["DEXTERITY"].trace_add("write", self._recalc_movement)
        self._recalc_movement()

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

        return sf

    # ── Health panel (right side) ─────────────────────────────────────────────
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
    COLOR_EMPTY   = "#3a3a3a"

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

        leg = tk.Frame(hpanel, bg=BG_DARK)
        leg.pack(fill="x", padx=6, pady=(2, 0))
        tk.Label(leg, text="Lethal", font=("Arial", 7), bg=BG_DARK,
                 fg=TEXT_DIM).pack(side="right", padx=(1, 4))
        tk.Label(leg, text="■", font=("Arial", 9), bg=BG_DARK,
                 fg=self.COLOR_LETHAL).pack(side="right")
        tk.Label(leg, text="Bashing", font=("Arial", 7), bg=BG_DARK,
                 fg=TEXT_DIM).pack(side="right", padx=(1, 8))
        tk.Label(leg, text="■", font=("Arial", 9), bg=BG_DARK,
                 fg=self.COLOR_BASHING).pack(side="right")

        self._health_scroll = ScrollFrame(hpanel, bg=BG_DARK)
        self._health_scroll.pack(fill="both", expand=True)

        self._health_counts   = {s[0]: tk.IntVar(value=s[2])  for s in self.HEALTH_STATES}
        self._health_penalties= {s[0]: tk.IntVar(value=s[1])   for s in self.HEALTH_STATES}
        self._health_damage   = {}
        self._health_canvases = {}

        self._health_inner = self._health_scroll.inner
        self._rebuild_health_rows()

    def _all_health_boxes_ordered(self):
        result = []
        for state_label, _, _ in self.HEALTH_STATES:
            count = self._health_counts[state_label].get()
            for i in range(count):
                result.append((state_label, i))
        return result

    def _rebuild_health_rows(self):
        inner = self._health_inner
        for w in inner.winfo_children():
            w.destroy()
        self._health_canvases = {}

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

            pen_str = ("" if state_label in ("Incapacitated", "Dead")
                       else f"{penalty:+d}" if penalty != 0 else " 0")
            is_dead = (state_label == "Dead")

            for box_idx in range(count):
                row = tk.Frame(inner, bg=BG_DARK)
                row.pack(fill="x", padx=4, pady=1)

                tk.Label(row, text=state_label, font=("Arial", 8, "bold"),
                         bg=BG_DARK, fg=TEXT_MAIN, width=12, anchor="w").pack(side="left")
                tk.Label(row, text=pen_str, font=("Arial", 8, "bold"),
                         bg=BG_DARK, fg=ACCENT, width=3, anchor="e").pack(side="left")

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
                        x0, x1 = 1, bw + 1
                        fc = self.COLOR_BASHING if bval else self.COLOR_EMPTY
                        oc = "#ffcc88" if bval else BORDER
                        cv.create_rectangle(x0, y0, x1, y1, fill=fc, outline=oc, width=1)
                        x0b = bw + gap + 1; x1b = x0b + bw
                        fc2 = self.COLOR_LETHAL if lval else self.COLOR_EMPTY
                        oc2 = "#ff6644" if lval else BORDER
                        cv.create_rectangle(x0b, y0, x1b, y1, fill=fc2, outline=oc2, width=1)
                    else:
                        x0b = bw + gap + 1; x1b = x0b + bw
                        fc2 = self.COLOR_LETHAL if lval else self.COLOR_EMPTY
                        oc2 = "#ff6644" if lval else BORDER
                        cv.create_rectangle(1, y0, bw + 1, y1, fill=fc2, outline=oc2, width=1)

                bash_svars[box_idx].trace_add("write", lambda *_, d=_draw_box: d())
                leth_svars[box_idx].trace_add("write", lambda *_, d=_draw_box: d())

                def _on_click(event, sl=state_label, bi=box_idx,
                              dead=is_dead, bw=BOX_W, gap=GAP):
                    if dead or event.x < bw + gap:
                        col = "bashing" if not dead else "lethal"
                    else:
                        col = "lethal"
                    if event.num == 3:
                        svar_list = self._health_leth[sl] if col == "lethal" else self._health_bash[sl]
                        svar_list[bi].set("" if svar_list[bi].get() else col)
                        self._mark_dirty()
                        return
                    self._health_fill_up_to(sl, bi, col)
                    self._mark_dirty()

                cv.bind("<Button-1>", _on_click)
                cv.bind("<Button-3>", _on_click)
                _draw_box()

        hint = tk.Frame(inner, bg=BG_DARK)
        hint.pack(fill="x", padx=4, pady=(4, 2))
        tk.Label(hint, text="Click=fill up\nRight-click=toggle one\nShift=lethal col",
                 font=("Arial", 7), bg=BG_DARK, fg=TEXT_DIM, justify="left").pack(anchor="w")

    def _health_fill_up_to(self, target_state, target_box_idx, col):
        order = []
        for sl, _, _ in self.HEALTH_STATES:
            cnt = self._health_counts[sl].get()
            for bi in range(cnt):
                order.append((sl, bi))

        try:
            tgt_pos = order.index((target_state, target_box_idx))
        except ValueError:
            return

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

        for col, (txt, w) in enumerate([("State", 13), ("Boxes", 5), ("Penalty", 7)]):
            tk.Label(grid, text=txt, font=("Arial", 8, "bold"),
                     bg=BG_DARK, fg=GOLD, width=w, anchor="w").grid(
                     row=0, column=col, padx=(0, 6), pady=(0, 4), sticky="w")

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

        self._qp_dot_frame = tk.Frame(left_ctrl, bg=BG_PANEL)
        self._qp_dot_frame.pack(anchor="w", pady=(2, 0))
        self._qp_canvas = tk.Canvas(self._qp_dot_frame, bg=BG_PANEL,
                                    highlightthickness=0, height=20, width=390)
        self._qp_canvas.pack(side="left")
        self._qp_canvas.bind("<Button-1>", self._qp_canvas_click)
        self._qp_dots = []
        self._qp_updating = False

        sep1 = tk.Frame(bottom_row, bg=BORDER, width=1)
        sep1.pack(side="left", fill="y", padx=12)
        self._wp_bar = self._build_wp_bar(bottom_row)

        sep2 = tk.Frame(bottom_row, bg=BORDER, width=1)
        sep2.pack(side="left", fill="y", padx=12)
        self._taint_bar = self._build_taint_bar(bottom_row)

        sep3 = tk.Frame(bottom_row, bg=BORDER, width=1)
        sep3.pack(side="left", fill="y", padx=12)
        self._quantum_bar = self._build_quantum_attr_bar(bottom_row)

        self._refresh_qp_dots()

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
        DOT_S   = 14
        SPACING = 15
        W       = max_dots * SPACING + 4

        frame = tk.Frame(parent, bg=BG_PANEL)
        frame.pack(side="left")

        tk.Label(frame, text=label, font=("Arial", 9, "bold"),
                 bg=BG_PANEL, fg=color).pack(anchor="w")

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

    def _build_wp_bar(self, parent):
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
        cv = tk.Canvas(frame, bg=BG_PANEL, highlightthickness=0, height=36, width=W)
        cv.pack(anchor="w", pady=(2, 0))

        def refresh(*_):
            cv.delete("all")
            try:
                perm = self._taint_perm_var.get()
                temp = self._taint_temp_var.get()
            except Exception:
                return
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
            if event.y <= 18:
                self._taint_perm_var.set(idx - 1 if idx == perm else idx)
            else:
                temp = self._taint_temp_var.get()
                self._taint_temp_var.set(idx - 1 if idx == temp else idx)
            self._mark_dirty()

        self._taint_perm_var.trace_add("write", refresh)
        self._taint_temp_var.trace_add("write", refresh)
        cv.bind("<Button-1>", on_perm_click)
        refresh()
        return frame

    def _build_quantum_attr_bar(self, parent):
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

    def get_tab_title(self):
        name = self._hdr_vars.get("birth_name", tk.StringVar()).get() or "Unnamed"
        dirty = " *" if self._dirty else ""
        fname = f" [{os.path.basename(self._current_file)}]" if self._current_file else ""
        return f"{name}{fname}{dirty}"

    def _update_title(self):
        if self._on_title_change:
            self._on_title_change()

    def can_close(self):
        if not self._dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved changes",
            f"'{self.get_tab_title()}' has unsaved changes.\nSave before closing?"
        )
        if answer is None:
            return False
        if answer:
            self._save()
            return not self._dirty
        return True

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
        c["custom_abilities"] = {
            attr: [[nv.get(), vv.get()] for nv, vv, _ in entries if nv.get().strip()]
            for attr, entries in self._custom_ability_vars.items()
            if any(nv.get().strip() for nv, vv, _ in entries)
        }
        c["backgrounds"] = {
            nv.get(): vv.get()
            for nv, vv, _ in self._bg_rows
            if nv.get().strip()
        }
        c["powers"] = [
            {
                "PowerID":   entry["power_id"],
                "rating":    entry["rating_var"].get(),
                "techniques": [
                    spid for spid, bv in entry["tech_vars"].items() if bv.get()
                ],
                "extras": [
                    name for name, bv in entry.get("extra_vars", {}).items() if bv.get()
                ],
                **({"variant": entry["variant"]} if entry.get("variant") else {}),
            }
            for entry in self._power_cards
        ]
        c["body_modifications"] = [e["name"] for e in self._body_mod_cards]
        c["mega_attributes"] = {ma: v.get() for ma, v in self._mega_vars.items()}

        c["willpower_perm"]  = self._wp_perm_var.get()
        c["willpower_temp"]  = self._wp_temp_var.get()
        c["taint_perm"]      = self._taint_perm_var.get()
        c["taint_temp"]      = self._taint_temp_var.get()
        c["aberrations"]     = [e["name"] for e in self._aberration_cards]
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
        c["soak_bashing"] = self._soak_vars["bashing"].get()
        c["soak_lethal"]  = self._soak_vars["lethal"].get()
        c["game_notes"]   = self._notes_text.get("1.0", "end-1c")
        c["exp_total"]    = self._exp_total_var.get()
        c["exp_spent"]    = self._exp_spent_var.get()
        c["mega_enhancements"] = {
            ma: [[e[0], e[1].get()] for e in lst]
            for ma, lst in self._mega_enhancements.items()
        }
        c["portrait"]    = self._portrait_b64
        c["app_version"] = APP_VERSION
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
        self._specialisations.clear()
        for sk, entries in c.get("specialisations", {}).items():
            bvs = []
            for name, active in entries:
                bv = tk.BooleanVar(value=active)
                bv.trace_add("write", lambda *_: self._mark_dirty())
                bvs.append([name, bv])
            self._specialisations[sk] = bvs
        for sk, fn in getattr(self, "_spec_refresh_funcs", {}).items():
            fn()
        for attr, container in self._custom_ability_frames.items():
            for w in container.winfo_children():
                w.destroy()
            self._custom_ability_vars[attr] = []
        for attr, entries in c.get("custom_abilities", {}).items():
            if attr in self._custom_ability_frames:
                for item in entries:
                    name = item[0] if item else ""
                    val  = item[1] if len(item) > 1 else 0
                    self._add_custom_ability(attr, name=name, val=val)
        for w in self._bg_container.winfo_children():
            w.destroy()
        self._bg_rows = []
        for bg_name, bg_val in c.get("backgrounds", {}).items():
            self._add_background(name=bg_name, val=bg_val)
        for entry in self._power_cards:
            entry["frame"].destroy()
        self._power_cards = []
        for pw in c.get("powers", []):
            self._add_power_card(
                pw["PowerID"],
                rating=pw.get("rating", 1),
                techniques=pw.get("techniques", []),
                extras_bought=pw.get("extras", []),
                variant=pw.get("variant"),
            )
        for entry in self._body_mod_cards:
            entry["frame"].destroy()
        self._body_mod_cards = []
        for name in c.get("body_modifications", []):
            self._add_body_mod_card(name)
        for ma, var in self._mega_vars.items():
            var.set(c.get("mega_attributes", {}).get(ma, 0))

        self._wp_perm_var.set(c.get("willpower_perm", 5))
        self._wp_temp_var.set(c.get("willpower_temp", 5))
        self._taint_perm_var.set(c.get("taint_perm", 0))
        self._taint_temp_var.set(c.get("taint_temp", 0))
        for entry in self._aberration_cards:
            entry["frame"].destroy()
        self._aberration_cards = []
        for name in c.get("aberrations", []):
            self._add_aberration_card(name)
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
        self._soak_vars["bashing"].set(c.get("soak_bashing", ""))
        self._soak_vars["lethal"].set(c.get("soak_lethal", ""))
        self._notes_text.delete("1.0", "end")
        self._notes_text.insert("1.0", c.get("game_notes", ""))
        self._exp_total_var.set(c.get("exp_total", "0"))
        self._exp_spent_var.set(c.get("exp_spent", "0"))
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
        self._portrait_b64 = c.get("portrait", "")
        self._refresh_portrait()

    def _load_char_to_ui(self):
        self._apply_char(self.char)
        self._dirty = False
        self._update_title()

    # ── File operations ────────────────────────────────────────────────────────
    def _open_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data, migrated = migrate_char(data)
            self.char = data
            self._current_file = path
            self._load_char_to_ui()
            if migrated:
                self._mark_dirty()
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
