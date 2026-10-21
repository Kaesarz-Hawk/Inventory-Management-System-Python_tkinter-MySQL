"""
base_page.py  -  ONE generic CRUD screen, reused by Employees, Suppliers, Categories and Products.

Each of those screens is just a small subclass that says WHICH table, WHICH fields and WHICH query.
This is OOP inheritance: the Create / Read / Update / Delete logic is written once, here.
"""
import customtkinter as ctk
from mysql.connector import Error

import config
import theme
import utils
from db import db
from theme import DataTable, button, card, combo, entry, label


class CrudPage(ctk.CTkFrame):
    # ---- the subclass fills these in ----
    TITLE = SUBTITLE = TABLE = ITEM = ""
    ADMIN_ONLY = False
    FIELDS = []              # form fields (see employee.py for the format)
    LIST_SQL = ""            # SELECT ... that returns: id, then one column per visible field, then EXTRA columns
    ORDER_BY = "ORDER BY 1 DESC"
    SEARCH = {}              # {"label": "sql column"}  -> the "Search by" box
    EXTRA_COLUMNS = []       # [("Heading", width)] for computed columns shown after the fields
    NAME_FIELD = "name"      # field used in the activity log text
    FORM_IMAGE = None        # optional picture under the form

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.widgets = {}        # field key -> input widget
        self.lookups = {}        # field key -> {display name: id}   (for drop-downs filled from the DB)
        self.image_previews = {} # field key -> image preview label
        self.selected_id = None
        self._job = None
        self.build()

    # =============================================================== layout
    def build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        head.grid_columnconfigure(0, weight=1)
        theme.page_header(head, self.TITLE, self.SUBTITLE).grid(row=0, column=0, sticky="w")
        bar = ctk.CTkFrame(head, fg_color="transparent")
        bar.grid(row=0, column=1, sticky="e")
        self.search_by = combo(bar, ["All"] + list(self.SEARCH), width=140)
        self.search_by.set("All")
        self.search_by.pack(side="left", padx=(0, 8))
        self.search_entry = entry(bar, f"Search {self.TITLE.lower()}...", width=260)
        self.search_entry.pack(side="left")
        self.search_entry.bind("<KeyRelease>", self.search_later)
        button(bar, "Clear", self.clear_search, "neutral", 70).pack(side="left", padx=(8, 0))

        self.build_form()
        self.build_table()
        self.bind_all_escape()

    def bind_all_escape(self):
        self.bind("<Escape>", lambda e: self.clear())

    def build_form(self):
        form = card(self, width=410)
        form.grid(row=1, column=0, sticky="ns", padx=(0, 14))
        form.grid_propagate(False)
        form.grid_columnconfigure(0, weight=1)
        form.grid_rowconfigure(1, weight=1)
        label(form, f"{self.ITEM.title()} Details", 16, "bold").grid(row=0, column=0, sticky="w", padx=20, pady=(16, 0))

        scroll = ctk.CTkScrollableFrame(form, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 4))
        for f in self.FIELDS:
            label(scroll, f["label"] + (" *" if f.get("required") else ""), 12, "bold", muted=True).pack(anchor="w", padx=10, pady=(8, 2))
            kind = f["kind"]
            if kind == "combo":
                w = combo(scroll, f.get("values", ["Select"]))
            elif kind == "textarea":
                w = ctk.CTkTextbox(scroll, height=72, border_width=1, corner_radius=8, fg_color=theme.CARD_ALT,
                                   border_color=theme.BORDER, text_color=theme.TEXT, font=theme.font(13))
            elif kind == "image":
                row_f = ctk.CTkFrame(scroll, fg_color="transparent")
                row_f.pack(fill="x", padx=10, pady=(2, 4))
                w = entry(row_f, placeholder=f.get("placeholder", "Optional image path"), height=34)
                w.pack(side="left", fill="x", expand=True, padx=(0, 6))
                button(row_f, "Browse", lambda k=f["key"]: self._pick_img(k), "neutral", width=70, height=34).pack(side="right")
                prev = label(scroll, "No image selected", 11, muted=True)
                prev.pack(anchor="w", padx=14, pady=(0, 4))
                self.image_previews[f["key"]] = prev
            else:
                w = entry(scroll, f.get("placeholder", ""), **({"show": "•"} if kind == "password" else {}))
            if kind != "image":
                w.pack(fill="x", padx=10)
            self.widgets[f["key"]] = w
        self.reset_form_widgets()

        buttons = ctk.CTkFrame(form, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="ew", padx=14, pady=(6, 14))
        buttons.grid_columnconfigure((0, 1), weight=1, uniform="b")
        button(buttons, "Save", self.add, "primary", width=10).grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        button(buttons, "Update", self.update, "success", width=10).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        button(buttons, "Delete", self.delete, "danger", width=10).grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        button(buttons, "Clear", self.clear, "neutral", width=10).grid(row=1, column=1, sticky="ew", padx=4, pady=4)

        if self.FORM_IMAGE:
            pic = theme.load_image(self.FORM_IMAGE, 360, 190)
            if pic:
                ctk.CTkLabel(form, text="", image=pic).grid(row=3, column=0, pady=(0, 14))

    def _pick_img(self, key):
        import os, shutil, time
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(), title="Select Product Picture",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif")])
        if path:
            os.makedirs(config.PRODUCT_IMG_DIR, exist_ok=True)
            safe_name = f"prod_{int(time.time())}_{os.path.basename(path).replace(' ', '_')}"
            dest = os.path.join(config.PRODUCT_IMG_DIR, safe_name)
            try:
                shutil.copy2(path, dest)
                self.write({"key": key, "kind": "image"}, dest)
            except Exception as e:
                utils.error(self, f"Could not save image: {e}")

    def build_table(self):
        box = card(self)
        box.grid(row=1, column=1, sticky="nsew")
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(box, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))
        label(top, f"All {self.TITLE}", 16, "bold").pack(side="left")
        self.count_label = label(top, "", 12, muted=True)
        self.count_label.pack(side="left", padx=12)
        button(top, "Export CSV", self.export, "neutral", 110, 32).pack(side="right")
        button(top, "Refresh", self.on_show, "neutral", 90, 32).pack(side="right", padx=8)

        visible = [f for f in self.FIELDS if not f.get("hidden")]
        columns = [("ID", 60)] + [(f["label"], f.get("width", 130)) for f in visible] + self.EXTRA_COLUMNS
        self.table = DataTable(box, columns, on_select=self.on_select)
        self.table.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))

    # ========================================================= form helpers
    def read(self, f):
        w = self.widgets[f["key"]]
        return w.get("1.0", "end").strip() if f["kind"] == "textarea" else w.get().strip()

    def write(self, f, value):
        w, text = self.widgets[f["key"]], ("" if value is None else str(value))
        if f["kind"] == "textarea":
            w.delete("1.0", "end")
            w.insert("1.0", text)
        elif f["kind"] == "combo":
            w.set(text)
        elif f["kind"] == "image":
            w.delete(0, "end")
            w.insert(0, text)
            prev = self.image_previews.get(f["key"])
            if prev:
                pic = theme.load_image(text, 64, 64) if text else None
                theme.set_label_image(prev, pic, "" if pic else ("Image file not found" if text else "No image selected"))
        else:
            w.delete(0, "end")
            w.insert(0, text)

    def reset_form_widgets(self):
        for f in self.FIELDS:
            self.write(f, f.get("default", "Select") if f["kind"] == "combo" else "")

    def clear(self):
        self.selected_id = None
        self.reset_form_widgets()
        for prev in self.image_previews.values():
            theme.set_label_image(prev, None, "No image selected")
        self.table.clear_selection()

    def collect(self, adding):
        """Read + validate the whole form. Returns {column: value}. Raises ValueError with a friendly message."""
        data = {}
        for f in self.FIELDS:
            raw, kind, name = self.read(f), f["kind"], f["label"]
            col = f.get("col", f["key"])
            if kind == "password":
                if not raw:
                    if adding and f.get("required"):
                        raise ValueError(f"{name} is required")
                    continue                       # blank on update = keep the old password
                if len(raw) < 6:
                    raise ValueError("Password must be at least 6 characters")
                data[col] = utils.hash_password(raw)
            elif f.get("lookup"):
                if raw in ("", "Select"):
                    raise ValueError(f"Please select a {name.lower()}")
                data[col] = self.lookups[f["key"]][raw]
            elif kind == "combo":
                if raw in ("", "Select"):
                    raise ValueError(f"Please select {name.lower()}")
                data[col] = raw
            else:
                if f.get("required") and not raw:
                    raise ValueError(f"{name} is required")
                data[col] = utils.validate(kind, raw, name) if raw else None
        return data

    # =================================================================== CRUD
    def add(self):
        if self.selected_id is not None:
            return utils.info(self, "A record is selected.\nUse Update to change it, or press Clear to enter a new one.")
        try:
            data = self.collect(True)
            cols = ", ".join(data)
            db.execute(f"INSERT INTO {self.TABLE} ({cols}) VALUES ({', '.join(['%s'] * len(data))})", list(data.values()))
        except ValueError as e:
            return utils.error(self, str(e))
        except Error as e:
            return utils.error(self, utils.friendly_db_error(e))
        self.done("Added", f"{self.ITEM.title()} saved successfully")

    def update(self):
        if self.selected_id is None:
            return utils.error(self, f"Select a {self.ITEM} from the table first.")
        try:
            data = self.collect(False)
            sets = ", ".join(f"{c}=%s" for c in data)
            db.execute(f"UPDATE {self.TABLE} SET {sets} WHERE id=%s", list(data.values()) + [self.selected_id])
        except ValueError as e:
            return utils.error(self, str(e))
        except Error as e:
            return utils.error(self, utils.friendly_db_error(e))
        self.done("Updated", f"{self.ITEM.title()} updated successfully")

    def delete(self):
        row = self.table.selected_row()
        if self.selected_id is None or row is None:
            return utils.error(self, f"Select a {self.ITEM} from the table first.")
        problem = self.can_delete(row)
        if problem:
            return utils.error(self, problem)
        if not utils.confirm(self, f"Do you really want to delete this {self.ITEM}?"):
            return None
        try:
            db.execute(f"DELETE FROM {self.TABLE} WHERE id=%s", (self.selected_id,))
        except Error as e:
            return utils.error(self, utils.friendly_db_error(e))
        self.done("Deleted", f"{self.ITEM.title()} deleted")
        return None

    def can_delete(self, row):
        """Subclasses may return a message to block a delete."""
        return None

    def done(self, verb, message):
        name = next((self.read(f) for f in self.FIELDS if f["key"] == self.NAME_FIELD), "")
        utils.log_activity(f"{verb} {self.ITEM}: {name}")
        self.clear()
        self.on_show()
        theme.toast(self, message)

    # ========================================================== table / search
    def on_select(self, row):
        self.selected_id = row[0]
        visible = [f for f in self.FIELDS if not f.get("hidden")]
        for f, value in zip(visible, row[1:]):
            self.write(f, value)
        for f in self.FIELDS:
            if f.get("hidden"):
                self.write(f, "")

    def on_show(self):
        """Called every time the page is opened - keeps drop-downs and table fresh."""
        try:
            for f in self.FIELDS:
                if f.get("lookup"):
                    pairs = db.fetch_all(f["lookup"])
                    self.lookups[f["key"]] = {name: pk for pk, name in pairs}
                    w = self.widgets[f["key"]]
                    w.configure(values=["Select"] + list(self.lookups[f["key"]]))
                    if w.get() not in self.lookups[f["key"]]:
                        w.set("Select")
            self.refresh()
        except Error as e:
            utils.error(self, utils.friendly_db_error(e))

    def refresh(self):
        sql, params = self.LIST_SQL, []
        text = self.search_entry.get().strip()
        if text:
            by = self.search_by.get()
            columns = list(self.SEARCH.values()) if by == "All" else [self.SEARCH[by]]
            sql += " WHERE " + " OR ".join(f"{c} LIKE %s" for c in columns)
            params = [f"%{text}%"] * len(columns)
        rows = db.fetch_all(f"{sql} {self.ORDER_BY}", params)
        self.table.load(rows, self.row_tag)
        self.count_label.configure(text=f"{len(rows)} record(s)")

    def row_tag(self, row):
        return None

    def search_later(self, _event=None):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(250, self.safe_refresh)

    def safe_refresh(self):
        try:
            self.refresh()
        except Error as e:
            utils.error(self, utils.friendly_db_error(e))

    def clear_search(self):
        self.search_entry.delete(0, "end")
        self.search_by.set("All")
        self.safe_refresh()

    def export(self):
        headings = [h for h, _ in self.table.columns]
        utils.export_csv(self, headings, self.table.current_rows(), f"{self.TITLE.lower()}.csv")
