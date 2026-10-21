"""
settings_page.py  -  system preferences, user profile, password change, and backups.
Admin can edit shop details, currency, low-stock threshold, default discount, and backup data.
Any user can change their own password and choose their preferred theme and language.
"""
import csv
import io
import os
import zipfile
from datetime import datetime
import customtkinter as ctk
from mysql.connector import Error

import config
import settings
import theme
import utils
from db import db
from theme import button, card, combo, entry, label


class SettingsPage(ctk.CTkFrame):
    ADMIN_ONLY = False

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        self.grid_columnconfigure((0, 1), weight=1, uniform="sp")
        self.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        theme.page_header(head, "Settings & Preferences", "Configure store profile, personal password, theme, and data backups").pack(side="left")

        self.build_left()
        self.build_right()

    # ------------------------------------------------------------- Left Column
    def build_left(self):
        left = card(self)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        left.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # Store Details (Admin only)
        label(scroll, "Store Identity & Defaults", 16, "bold").pack(anchor="w", padx=10, pady=(6, 2))
        label(scroll, "Printed on all receipts and customer bills (Admin only)", 12, muted=True).pack(anchor="w", padx=10, pady=(0, 12))

        label(scroll, "Shop Name", 12, "bold", muted=True).pack(anchor="w", padx=10)
        self.shop_name = entry(scroll, placeholder="Store name")
        self.shop_name.pack(fill="x", padx=10, pady=(2, 8))

        label(scroll, "Shop Address", 12, "bold", muted=True).pack(anchor="w", padx=10)
        self.shop_address = entry(scroll, placeholder="City, Country")
        self.shop_address.pack(fill="x", padx=10, pady=(2, 8))

        label(scroll, "Shop Phone", 12, "bold", muted=True).pack(anchor="w", padx=10)
        self.shop_phone = entry(scroll, placeholder="Phone number")
        self.shop_phone.pack(fill="x", padx=10, pady=(2, 8))

        row2 = ctk.CTkFrame(scroll, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=4)
        row2.grid_columnconfigure((0, 1), weight=1, uniform="r2")

        label(row2, "Currency Symbol", 12, "bold", muted=True).grid(row=0, column=0, sticky="w", padx=(0, 6))
        label(row2, "Low Stock Limit", 12, "bold", muted=True).grid(row=0, column=1, sticky="w", padx=(6, 0))
        self.currency_sym = entry(row2, placeholder="৳ or $")
        self.currency_sym.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(2, 8))
        self.low_limit = entry(row2, placeholder="10", justify="center")
        self.low_limit.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(2, 8))

        row3 = ctk.CTkFrame(scroll, fg_color="transparent")
        row3.pack(fill="x", padx=10, pady=4)
        row3.grid_columnconfigure((0, 1), weight=1, uniform="r3")

        label(row3, "Default Discount %", 12, "bold", muted=True).grid(row=0, column=0, sticky="w", padx=(0, 6))
        label(row3, "Idle Auto-Logout (Mins, 0 = never)", 12, "bold", muted=True).grid(row=0, column=1, sticky="w", padx=(6, 0))
        self.def_disc = entry(row3, placeholder="5", justify="center")
        self.def_disc.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(2, 8))
        self.idle_to = entry(row3, placeholder="15", justify="center")
        self.idle_to.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(2, 8))

        self.btn_save_store = button(scroll, "Save System Settings", self.save_store_settings, "primary", height=38)
        self.btn_save_store.pack(fill="x", padx=10, pady=(12, 14))

        if not utils.is_admin():
            for w in (self.shop_name, self.shop_address, self.shop_phone, self.currency_sym,
                      self.low_limit, self.def_disc, self.idle_to, self.btn_save_store):
                w.configure(state="disabled")

    # ------------------------------------------------------------ Right Column
    def build_right(self):
        right = card(self)
        right.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        right.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(right, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # User Profile & Password Change
        label(scroll, "Security & Password", 16, "bold").pack(anchor="w", padx=10, pady=(6, 2))
        label(scroll, "Change your personal account login password", 12, muted=True).pack(anchor="w", padx=10, pady=(0, 12))

        label(scroll, "Current Password *", 12, "bold", muted=True).pack(anchor="w", padx=10)
        self.old_pw = entry(scroll, placeholder="Enter current password", show="•")
        self.old_pw.pack(fill="x", padx=10, pady=(2, 8))

        label(scroll, "New Password *", 12, "bold", muted=True).pack(anchor="w", padx=10)
        self.new_pw = entry(scroll, placeholder="Minimum 6 characters", show="•")
        self.new_pw.pack(fill="x", padx=10, pady=(2, 8))

        label(scroll, "Confirm New Password *", 12, "bold", muted=True).pack(anchor="w", padx=10)
        self.confirm_pw = entry(scroll, placeholder="Retype new password", show="•")
        self.confirm_pw.pack(fill="x", padx=10, pady=(2, 8))

        button(scroll, "Update Password", self.change_password, "success", height=38).pack(fill="x", padx=10, pady=(8, 18))

        # Appearance & Language Preferences
        label(scroll, "Personal Preferences", 16, "bold").pack(anchor="w", padx=10, pady=(6, 2))
        label(scroll, "Theme and language are remembered between sessions", 12, muted=True).pack(anchor="w", padx=10, pady=(0, 12))

        row_pref = ctk.CTkFrame(scroll, fg_color="transparent")
        row_pref.pack(fill="x", padx=10, pady=4)
        row_pref.grid_columnconfigure((0, 1), weight=1, uniform="prf")

        label(row_pref, "Appearance Mode", 12, "bold", muted=True).grid(row=0, column=0, sticky="w", padx=(0, 6))
        label(row_pref, "Language", 12, "bold", muted=True).grid(row=0, column=1, sticky="w", padx=(6, 0))

        self.theme_combo = combo(row_pref, ["Dark", "Light"], command=self.on_theme_select)
        self.theme_combo.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(2, 8))

        self.lang_combo = combo(row_pref, ["English", "Bangla (বাংলা)"], command=self.on_lang_select)
        self.lang_combo.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(2, 8))

        # Database Backup (Admin only)
        if utils.is_admin():
            label(scroll, "Database Backup & Safety", 16, "bold").pack(anchor="w", padx=10, pady=(14, 2))
            label(scroll, "Export every table to CSV files bundled into a timestamped ZIP", 12, muted=True).pack(anchor="w", padx=10, pady=(0, 8))
            self.backup_btn = button(scroll, "Backup Database Now", self.backup_database, "warning", height=40)
            self.backup_btn.pack(fill="x", padx=10, pady=(4, 14))

    # ------------------------------------------------------------- Lifecycle
    def on_show(self):
        settings.reload_settings()
        self._fill(self.shop_name, settings.get_shop_name())
        self._fill(self.shop_address, settings.get_shop_address())
        self._fill(self.shop_phone, settings.get_shop_phone())
        self._fill(self.currency_sym, settings.get_currency())
        self._fill(self.low_limit, settings.get_low_stock_limit())
        self._fill(self.def_disc, f"{settings.get_default_discount():g}")
        self._fill(self.idle_to, settings.get_idle_timeout())
        self.theme_combo.set(settings.get_theme())
        self.lang_combo.set("Bangla (বাংলা)" if settings.get_language() == "bn" else "English")

    @staticmethod
    def _fill(box, value):
        """Put text in an entry even when it is disabled (a disabled box ignores insert())."""
        was = box.cget("state")
        box.configure(state="normal")
        box.delete(0, "end")
        box.insert(0, str(value))
        box.configure(state=was)

    def save_store_settings(self):
        if not utils.is_admin():
            return utils.error(self, "Only an Admin can modify system settings.")
        name = self.shop_name.get().strip()
        addr = self.shop_address.get().strip()
        phone = self.shop_phone.get().strip()
        cur = self.currency_sym.get().strip()
        try:
            limit = utils.validate("int", self.low_limit.get().strip(), "Low Stock Limit")
            disc = utils.validate("float", self.def_disc.get().strip(), "Default Discount")
            timeout = utils.validate("int", self.idle_to.get().strip(), "Idle Auto-Logout")
        except ValueError as e:
            return utils.error(self, str(e))
        if not name:
            return utils.error(self, "Shop name is required.")
        if not cur:
            return utils.error(self, "Currency symbol is required.")
        if disc > 100:
            return utils.error(self, "Default discount cannot be more than 100%.")
        if timeout > 1440:
            return utils.error(self, "Idle auto-logout cannot be more than 1440 minutes (24 hours).")

        results = [settings.set_setting(k, v) for k, v in (
            ("shop_name", name), ("shop_address", addr), ("shop_phone", phone), ("currency", cur),
            ("low_stock_limit", limit), ("default_discount", disc), ("idle_timeout", timeout))]
        if not all(results):
            return utils.error(self, "Settings could not be saved. Check that MySQL is running and try again.")

        utils.log_activity("Updated system settings")
        theme.toast(self, "Settings saved successfully")
        return None

    def change_password(self):
        old = self.old_pw.get()
        new = self.new_pw.get()
        confirm = self.confirm_pw.get()
        if not old or not new:
            return utils.error(self, "Please enter your current and new password.")
        if len(new) < 6:
            return utils.error(self, "New password must be at least 6 characters.")
        if new != confirm:
            return utils.error(self, "New passwords do not match.")

        emp_id = utils.session.get("id")
        row = db.fetch_one("SELECT password FROM employees WHERE id = %s", (emp_id,))
        if not row or not utils.verify_password(old, row[0]):
            return utils.error(self, "Current password is incorrect.")

        try:
            hashed = utils.hash_password(new)
            db.execute("UPDATE employees SET password = %s WHERE id = %s", (hashed, emp_id))
        except Error as e:
            return utils.error(self, utils.friendly_db_error(e))

        self.old_pw.delete(0, "end")
        self.new_pw.delete(0, "end")
        self.confirm_pw.delete(0, "end")
        utils.log_activity("Changed own password")
        theme.toast(self, "Password updated successfully")
        return None

    def on_theme_select(self, choice):
        if not settings.set_setting("theme", choice):
            return utils.error(self, "Could not save the theme. Check that MySQL is running.")
        ctk.set_appearance_mode(choice)
        theme.style_tables()
        theme.refresh_tables()
        if hasattr(self.app, "mode"):
            if choice == "Dark":
                self.app.mode.select()
            else:
                self.app.mode.deselect()
        for p in self.app.pages.values():
            if hasattr(p, "on_theme_change"):
                p.on_theme_change()

    def on_lang_select(self, choice):
        code = "bn" if "Bangla" in choice else "en"
        if not settings.set_setting("language", code):
            return utils.error(self, "Could not save the language. Check that MySQL is running.")
        self.app.reload_ui("Settings")          # rebuild the window in the new language

    # ------------------------------------------------------------- Backup
    def backup_database(self):
        """Export every table to a CSV file inside a timestamped ZIP in backups/"""
        tables = ["employees", "categories", "suppliers", "customers", "products",
                  "purchases", "purchase_items", "sales", "sale_items", "sale_returns",
                  "settings", "activity_log"]
        os.makedirs(config.BACKUP_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name = f"backup_ims_{ts}.zip"
        zip_path = os.path.join(config.BACKUP_DIR, zip_name)

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for t in tables:
                    columns = [c[0] for c in db.fetch_all(f"DESCRIBE `{t}`")]
                    rows = db.fetch_all(f"SELECT * FROM `{t}`")
                    out = io.StringIO()
                    writer = csv.writer(out)
                    writer.writerow(columns)
                    writer.writerows(rows)
                    zf.writestr(f"{t}.csv", out.getvalue().encode("utf-8-sig"))
        except Exception as e:
            return utils.error(self, f"Backup failed: {e}")

        utils.log_activity(f"Created database backup: {zip_name}")
        theme.toast(self, f"Backup created: {zip_name}")
        utils.info(self, f"Database backup was successfully saved to:\n\n{zip_path}")
        return None

