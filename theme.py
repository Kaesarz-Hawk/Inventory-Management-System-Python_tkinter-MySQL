"""
theme.py  -  the look of the whole application in ONE place.
Colours are (light, dark) pairs, so customtkinter switches theme automatically.
Also contains the reusable widgets: card, button, entry, StatCard, DataTable, toast.
"""
import functools
import os
import tkinter as tk
import tkinter.font as tkfont
import weakref
from tkinter import ttk

import customtkinter as ctk
from PIL import Image

import config
import lang

FONT_FAMILY = "Segoe UI"

# ------------------------------------------------------------------ colours
ACCENT, ACCENT_HOVER = "#4F46E5", "#4338CA"
SUCCESS, SUCCESS_HOVER = "#10B981", "#059669"
DANGER, DANGER_HOVER = "#EF4444", "#DC2626"
WARNING, WARNING_HOVER = "#F59E0B", "#D97706"
INFO = "#0EA5E9"
SLATE, SLATE_HOVER = ("#64748B", "#475569"), ("#475569", "#64748B")

BG = ("#EEF2F7", "#0B1220")
CARD = ("#FFFFFF", "#131C31")
CARD_ALT = ("#F8FAFC", "#0E1628")
BORDER = ("#E2E8F0", "#243049")
TEXT = ("#0F172A", "#E5E7EB")
MUTED = ("#64748B", "#94A3B8")
SIDEBAR, SIDEBAR_HOVER = "#0F172A", "#1E293B"


def resolve(color):
    """Pick the light/dark value of a colour pair (needed for raw Canvas / ttk widgets)."""
    if isinstance(color, (tuple, list)):
        return color[1 if ctk.get_appearance_mode() == "Dark" else 0]
    return color


@functools.lru_cache(maxsize=None)
def font(size=13, weight="normal"):
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


# ---------------------------------------------------------- small factories
def card(parent, **kw):
    return ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER, **kw)


def label(parent, text, size=13, weight="normal", muted=False, color=None, **kw):
    return ctk.CTkLabel(parent, text=lang.t(text), font=font(size, weight), text_color=color or (MUTED if muted else TEXT), **kw)


def button(parent, text, command=None, kind="primary", width=110, height=36, **kw):
    fg, hover = {"primary": (ACCENT, ACCENT_HOVER), "success": (SUCCESS, SUCCESS_HOVER),
                 "danger": (DANGER, DANGER_HOVER), "neutral": (SLATE, SLATE_HOVER),
                 "warning": (WARNING, WARNING_HOVER)}[kind]
    return ctk.CTkButton(parent, text=lang.t(text), command=command, fg_color=fg, hover_color=hover,
                         text_color="white", width=width, height=height, corner_radius=10,
                         font=font(13, "bold"), **kw)


def entry(parent, placeholder="", height=36, **kw):
    return ctk.CTkEntry(parent, placeholder_text=placeholder, height=height, corner_radius=8, border_width=1,
                        fg_color=CARD_ALT, border_color=BORDER, text_color=TEXT, font=font(13), **kw)


def combo(parent, values, height=36, **kw):
    return ctk.CTkComboBox(parent, values=values, state="readonly", height=height, corner_radius=8,
                           border_width=1, fg_color=CARD_ALT, border_color=BORDER, button_color=ACCENT,
                           button_hover_color=ACCENT_HOVER, text_color=TEXT, font=font(13),
                           dropdown_font=font(13), **kw)


def page_header(parent, title, subtitle=""):
    box = ctk.CTkFrame(parent, fg_color="transparent")
    label(box, title, 26, "bold").pack(anchor="w")   # label() translates the text
    if subtitle:
        label(box, subtitle, 13, muted=True).pack(anchor="w")
    return box


def load_image(name, max_w, max_h):
    """Load an image scaled to fit, keeping aspect ratio. Returns None if missing (never crashes)."""
    if not name:
        return None
    path = name if os.path.isabs(name) else os.path.join(config.IMAGE_DIR, name)
    if not os.path.exists(path):
        return None
    try:
        img = Image.open(path).convert("RGBA")
        img.thumbnail((max_w, max_h))
        return ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
    except Exception:
        return None


_BLANK = []


def set_label_image(lbl, pic, text=""):
    """Show a picture on a CTkLabel, or REMOVE it safely.
    (Passing image=None to a CTkLabel makes customtkinter crash later with 'image doesn't exist',
    so we swap in a transparent 1x1 picture instead.)"""
    if not _BLANK:
        _BLANK.append(ctk.CTkImage(Image.new("RGBA", (1, 1), (0, 0, 0, 0)), size=(1, 1)))
    lbl.configure(image=pic or _BLANK[0], text=text)


def toast(widget, text, kind="success"):
    """Small pop-up message in the bottom-right corner; disappears by itself."""
    root = widget.winfo_toplevel()
    color = {"success": SUCCESS, "error": DANGER, "info": ACCENT, "warning": WARNING}[kind]
    note = ctk.CTkLabel(root, text=f"   {text}   ", fg_color=color, text_color="white", corner_radius=10,
                        height=42, font=font(13, "bold"))
    note.place(relx=1.0, rely=1.0, x=-28, y=-48, anchor="se")
    note.lift()
    root.after(2600, note.destroy)


# --------------------------------------------------------------- stat card
class StatCard(ctk.CTkFrame):
    def __init__(self, parent, title, icon, color):
        super().__init__(parent, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER)
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=icon, width=46, height=46, corner_radius=14, fg_color=color,
                     text_color="white", font=font(20)).grid(row=0, column=0, rowspan=2, padx=(12, 10), pady=14)
        self.value = label(self, "0", 22, "bold")
        self.value.grid(row=0, column=1, sticky="sw", padx=(0, 10), pady=(14, 0))
        label(self, title, 12, muted=True).grid(row=1, column=1, sticky="nw", pady=(0, 14))

    def set(self, value):
        self.value.configure(text=str(value))


# -------------------------------------------------------------- data table
_tables = weakref.WeakSet()


def style_tables():
    """(Re)apply the table colours - called at start-up and whenever the theme is toggled."""
    s = ttk.Style()
    s.theme_use("clam")
    bg, fg = resolve(CARD), resolve(TEXT)
    head = resolve(("#F1F5F9", "#0E1628"))
    row_font = tkfont.Font(family=FONT_FAMILY, size=11)
    s.configure("IMS.Treeview", background=bg, fieldbackground=bg, foreground=fg, borderwidth=0,
                rowheight=row_font.metrics("linespace") + 16, font=(FONT_FAMILY, 11))
    s.configure("IMS.Treeview.Heading", background=head, foreground=resolve(MUTED), relief="flat",
                font=(FONT_FAMILY, 10, "bold"), padding=(8, 9), borderwidth=0)
    s.map("IMS.Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
    s.map("IMS.Treeview.Heading", background=[("active", head)])
    s.layout("IMS.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])


def refresh_tables():
    for table in list(_tables):
        try:
            table.recolor()
        except tk.TclError:
            pass


def _sort_key(value):
    if value is None:
        return (0, "")
    try:
        return (1, float(value))
    except (TypeError, ValueError):
        return (2, str(value).lower())


def _show(value):
    if value is None:
        return ""
    if isinstance(value, float) or value.__class__.__name__ == "Decimal":
        return f"{float(value):,.2f}"
    return str(value)


class DataTable(ctk.CTkFrame):
    """A nice-looking table. Keeps the ORIGINAL row data, so phone numbers keep their leading 0."""

    def __init__(self, parent, columns, on_select=None, on_double=None):
        super().__init__(parent, fg_color="transparent")
        self.columns = columns                    # [(heading, width), ...]
        self.on_select = on_select
        self.rows = {}                            # tree item id -> original row tuple
        self.extra = {}                           # tree item id -> extra tag
        self._descending = {}
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ids = [f"c{i}" for i in range(len(columns))]
        self.tree = ttk.Treeview(self, columns=ids, show="headings", style="IMS.Treeview", selectmode="browse", height=4)
        for i, (heading, width) in enumerate(columns):
            self.tree.heading(ids[i], text=heading, anchor="w", command=lambda i=i: self.sort_by(i))
            self.tree.column(ids[i], width=width, minwidth=60, anchor="w")
        vs = ctk.CTkScrollbar(self, command=self.tree.yview)
        hs = ctk.CTkScrollbar(self, orientation="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns", padx=(4, 0))
        hs.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        self.tree.bind("<<TreeviewSelect>>", self._selected)
        if on_double:
            self.tree.bind("<Double-1>", lambda e: on_double())
        self.recolor()
        _tables.add(self)

    def recolor(self):
        odd = resolve(("#F8FAFC", "#16213A"))
        self.tree.tag_configure("even", background=resolve(CARD))
        self.tree.tag_configure("odd", background=odd)
        self.tree.tag_configure("low", foreground="#EF4444")

    def load(self, rows, tag_fn=None):
        self.tree.delete(*self.tree.get_children())
        self.rows.clear()
        self.extra.clear()
        for i, row in enumerate(rows):
            extra = tag_fn(row) if tag_fn else None
            iid = self.tree.insert("", "end", values=[_show(v) for v in row],
                                   tags=("odd" if i % 2 else "even",) + ((extra,) if extra else ()))
            self.rows[iid] = row
            self.extra[iid] = extra

    def selected_row(self):
        sel = self.tree.selection()
        return self.rows.get(sel[0]) if sel else None

    def current_rows(self):
        return [self.rows[i] for i in self.tree.get_children()]

    def clear_selection(self):
        self.tree.selection_remove(self.tree.selection())

    def _selected(self, _event):
        if self.on_select:
            row = self.selected_row()
            if row:
                self.on_select(row)

    def sort_by(self, index):
        descending = self._descending.get(index, False)
        ordered = sorted(self.rows.items(), key=lambda kv: _sort_key(kv[1][index]), reverse=descending)
        for pos, (iid, _) in enumerate(ordered):
            self.tree.move(iid, "", pos)
            extra = self.extra.get(iid)
            self.tree.item(iid, tags=("odd" if pos % 2 else "even",) + ((extra,) if extra else ()))
        self._descending[index] = not descending
