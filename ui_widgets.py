import tkinter as tk

from constants import (BG_DARK, BG_MID, BG_CARD, BG_PANEL, ACCENT, BORDER,
                       TEXT_MAIN, TEXT_DIM, DOT_FULL, DOT_EMPTY)


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


def _add_description_widget(parent, text):
    frame = tk.Frame(parent, bg=BG_DARK)
    frame.pack(fill="x", padx=4, pady=(4, 4))
    sb = tk.Scrollbar(frame)
    sb.pack(side="right", fill="y")
    tw = tk.Text(frame, height=6, wrap="word",
                 font=("Arial", 9), bg=BG_DARK, fg=TEXT_MAIN,
                 relief="flat", yscrollcommand=sb.set, state="normal",
                 padx=4, pady=2)
    tw.insert("1.0", text)
    tw.config(state="disabled")
    tw.pack(side="left", fill="x", expand=True)
    sb.config(command=tw.yview)
