"""
login.py  -  the login screen and the "Database connection" pop-up.
Passwords are checked against the salted PBKDF2 hash stored in MySQL (never plain text).
"""
import customtkinter as ctk
import mysql.connector

import config
import theme
import utils
from db import db
from theme import button, card, entry, label


class LoginFrame(ctk.CTkFrame):
    def __init__(self, parent, on_success):
        super().__init__(parent, fg_color=theme.BG)
        self.on_success = on_success
        self.attempts = 0

        panel = card(self, width=960, height=590)
        panel.place(relx=0.5, rely=0.5, anchor="center")
        panel.grid_propagate(False)
        panel.grid_columnconfigure(0, weight=0)
        panel.grid_columnconfigure(1, weight=1)
        panel.grid_rowconfigure(0, weight=1)

        banner = theme.load_image("login_banner.png", 460, 570)
        side = ctk.CTkLabel(panel, text="", image=banner, fg_color="transparent")
        side.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        form = ctk.CTkFrame(panel, fg_color="transparent")
        form.grid(row=0, column=1, sticky="nsew", padx=44, pady=34)
        form.grid_columnconfigure(0, weight=1)
        label(form, "Welcome back 👋", 30, "bold").grid(row=0, column=0, sticky="w")
        label(form, "Sign in to manage your inventory", 14, muted=True).grid(row=1, column=0, sticky="w", pady=(2, 26))

        label(form, "Email", 12, "bold", muted=True).grid(row=2, column=0, sticky="w")
        self.email = entry(form, "name@example.com", height=44)
        self.email.grid(row=3, column=0, sticky="ew", pady=(2, 14))
        label(form, "Password", 12, "bold", muted=True).grid(row=4, column=0, sticky="w")
        self.password = entry(form, "Your password", height=44, show="•")
        self.password.grid(row=5, column=0, sticky="ew", pady=(2, 8))
        self.show_pw = ctk.CTkCheckBox(form, text="Show password", font=theme.font(12), text_color=theme.MUTED,
                                       fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self.toggle_password)
        self.show_pw.grid(row=6, column=0, sticky="w", pady=(0, 10))

        self.message = label(form, "", 12, "bold", color=theme.DANGER)
        self.message.grid(row=7, column=0, sticky="w")
        self.login_btn = button(form, "Sign In", self.attempt, "primary", height=46)
        self.login_btn.grid(row=8, column=0, sticky="ew", pady=(6, 14))

        if config.SHOW_LOGIN_HINT:
            hint = ctk.CTkFrame(form, fg_color=theme.CARD_ALT, corner_radius=10, border_width=1, border_color=theme.BORDER)
            hint.grid(row=9, column=0, sticky="ew")
            label(hint, "Demo accounts", 12, "bold").pack(anchor="w", padx=14, pady=(10, 0))
            label(hint, "Admin:  admin@ims.com  /  admin123", 12, muted=True).pack(anchor="w", padx=14)
            label(hint, "Cashier:  cashier@ims.com  /  cashier123", 12, muted=True).pack(anchor="w", padx=14, pady=(0, 10))

        for w in (self.email, self.password):
            w.bind("<Return>", self.attempt)
        self.after(200, self.email.focus_set)

    def toggle_password(self):
        self.password.configure(show="" if self.show_pw.get() else "•")

    def fail(self, text):
        self.message.configure(text=text)

    def attempt(self, _event=None):
        email, pw = self.email.get().strip().lower(), self.password.get()
        if not email or not pw:
            return self.fail("Please enter your email and password.")
        try:
            row = db.fetch_one("SELECT id, name, role, password FROM employees WHERE email = %s", (email,))
        except mysql.connector.Error as e:
            return self.fail(utils.friendly_db_error(e))
        if row is None or not utils.verify_password(pw, row[3]):
            self.attempts += 1
            if self.attempts >= 5:
                self.lock(15)
                return self.fail("Too many wrong attempts. Please wait 15 seconds.")
            return self.fail(f"Incorrect email or password. ({5 - self.attempts} tries left)")
        self.on_success({"id": row[0], "name": row[1], "role": row[2], "email": email})
        return None

    def lock(self, seconds):
        self.login_btn.configure(state="disabled")
        self.after(seconds * 1000, self.unlock)

    def unlock(self):
        self.attempts = 0
        self.login_btn.configure(state="normal")
        self.fail("")


class DBSettingsDialog(ctk.CTkToplevel):
    """Shown when MySQL cannot be reached - lets the user fix host/user/password without editing code."""

    def __init__(self, parent, problem):
        super().__init__(parent)
        self.saved = False
        self.title("MySQL connection")
        self.geometry("460x540")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        cfg = config.load_db_config()

        label(self, "Connect to MySQL", 22, "bold").pack(anchor="w", padx=28, pady=(24, 2))
        label(self, problem, 12, color=theme.DANGER, wraplength=400, justify="left").pack(anchor="w", padx=28, pady=(0, 10))
        self.fields = {}
        for key, title in (("host", "Host"), ("port", "Port"), ("user", "Username"), ("password", "Password"), ("database", "Database name")):
            label(self, title, 12, "bold", muted=True).pack(anchor="w", padx=28)
            e = entry(self, **({"show": "•"} if key == "password" else {}))
            e.insert(0, str(cfg[key]))
            e.pack(fill="x", padx=28, pady=(2, 8))
            self.fields[key] = e
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=28, pady=10)
        button(row, "Test & Save", self.save, "success", 140).pack(side="left")
        button(row, "Quit", self.destroy, "neutral", 90).pack(side="right")
        self.status = label(self, "", 12, color=theme.DANGER, wraplength=400, justify="left")
        self.status.pack(anchor="w", padx=28)
        self.after(200, self.focus_dialog)

    def focus_dialog(self):
        self.lift()
        self.focus_force()
        self.grab_set()

    def save(self):
        cfg = {k: w.get().strip() for k, w in self.fields.items()}
        cfg["password"] = self.fields["password"].get()
        try:
            cfg["port"] = int(cfg["port"])
            test = mysql.connector.connect(connection_timeout=5, host=cfg["host"], port=cfg["port"],
                                           user=cfg["user"], password=cfg["password"])
            test.close()
        except ValueError:
            return self.status.configure(text="Port must be a number (usually 3306).")
        except mysql.connector.Error as e:
            return self.status.configure(text=utils.friendly_db_error(e))
        config.save_db_config(cfg)
        self.saved = True
        self.destroy()
        return None
