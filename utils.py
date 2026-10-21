"""
utils.py  -  small helpers used everywhere: password hashing, validation,
message boxes, CSV export, bill text and the activity log.
"""
import csv
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime
from tkinter import filedialog, messagebox

import config
import settings
from db import db

session = {}          # who is logged in: {"id":..., "name":..., "role":...}


# ---------------------------------------------------------------- security
def hash_password(password):
    """PBKDF2-SHA256 with a random salt. Stored as  salt$hash  (never the real password)."""
    salt = secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${digest}"


def verify_password(password, stored):
    try:
        salt, digest = stored.split("$")
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return hmac.compare_digest(check, digest)


def is_admin():
    return session.get("role") == "Admin"


# -------------------------------------------------------------- validation
EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def validate(kind, raw, label):
    """Check one input. Returns the cleaned value or raises ValueError with a friendly message."""
    if kind == "email":
        if not EMAIL_RE.match(raw):
            raise ValueError(f"{label}: enter a valid email address (name@example.com)")
        return raw.lower()
    if kind == "phone":
        cleaned = re.sub(r"[\s-]", "", raw)
        if not re.fullmatch(r"\+?\d{7,15}", cleaned):
            raise ValueError(f"{label}: enter a valid phone number (digits only, 7-15 long)")
        return cleaned
    if kind == "date":
        try:
            return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError(f"{label}: use the format YYYY-MM-DD (example 2001-05-24)")
    if kind == "int":
        if not raw.isdigit():
            raise ValueError(f"{label}: enter a whole number (0 or more)")
        return int(raw)
    if kind == "float":
        try:
            value = float(raw)
        except ValueError:
            raise ValueError(f"{label}: enter a number")
        if value < 0:
            raise ValueError(f"{label}: cannot be negative")
        return round(value, 2)
    return raw


def friendly_db_error(e):
    code = getattr(e, "errno", None)
    if code == 1062:
        return "This record already exists (a name, email or invoice number must be unique)."
    if code == 1451:
        return "This record is still used by other records (for example products linked to it), so it cannot be deleted."
    if code == 1452:
        return "The selected related record does not exist any more. Refresh and try again."
    if code in (1045, 1044):
        return "MySQL rejected the username or password."
    if code in (2003, 2002, 2005, 2013):
        return "Cannot reach the MySQL server. Make sure MySQL (XAMPP/WAMP) is running."
    return f"Database error: {getattr(e, 'msg', None) or e}"


# ------------------------------------------------------------ message boxes
def error(parent, text):
    messagebox.showerror("Error", text, parent=parent.winfo_toplevel())


def info(parent, text):
    messagebox.showinfo("Information", text, parent=parent.winfo_toplevel())


def confirm(parent, text):
    return messagebox.askyesno("Please confirm", text, parent=parent.winfo_toplevel())


# ----------------------------------------------------------------- numbers
def money(value):
    cur = settings.get_currency() if "settings" in globals() else config.CURRENCY
    return f"{cur} {float(value):,.2f}"


def ellipsize(text, limit):
    """Shorten long text with an ellipsis instead of cutting a word in half."""
    text = str(text)
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def short_number(value):
    value = float(value)
    for limit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if value >= limit:
            return f"{value / limit:.1f}".rstrip("0").rstrip(".") + suffix
    return f"{value:.0f}"


# --------------------------------------------------------------------- CSV
def export_csv(parent, headings, rows, default_name):
    if not rows:
        return info(parent, "There is nothing to export yet.")
    path = filedialog.asksaveasfilename(
        parent=parent.winfo_toplevel(), defaultextension=".csv", initialfile=default_name,
        filetypes=[("CSV file (opens in Excel)", "*.csv")])
    if not path:
        return None
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headings)
        writer.writerows(rows)
    info(parent, f"Exported {len(rows)} rows to:\n{path}")
    return path


# -------------------------------------------------------------------- bill
def build_bill(invoice, when, customer, phone, items, subtotal, disc_pct, disc_amt, total, cashier, returns=None):
    """Plain-text bill. items = [(name, qty, unit_price, line_total), ...].
    returns = [(name, qty, refund_amount), ...] (optional)."""
    w = 48
    cur = settings.get_currency()
    shop_name = settings.get_shop_name()
    shop_addr = settings.get_shop_address()
    shop_phone = settings.get_shop_phone()
    line, thin = "=" * w, "-" * w
    out = [shop_name.center(w), shop_addr.center(w),
           f"Phone: {shop_phone}".center(w), line,
           f"Customer : {customer}", f"Phone    : {phone or '-'}",
           f"Bill No  : {invoice}", f"Date     : {when:%d/%m/%Y  %I:%M %p}",
           f"Cashier  : {cashier}", line,
           f"{'Product':<22}{'Qty':>5}{'Price':>10}{'Total':>11}", thin]
    for name, qty, price, line_total in items:
        out.append(f"{str(name)[:21]:<22}{qty:>5}{float(price):>10.2f}{float(line_total):>11.2f}")
    out += [line,
            f"{'Bill Amount':<30}{cur} {float(subtotal):>14,.2f}",
            f"{f'Discount ({float(disc_pct):g}%)':<30}{cur} {float(disc_amt):>14,.2f}",
            f"{'NET PAY':<30}{cur} {float(total):>14,.2f}"]

    if returns:
        out += [line, "RETURNED / REFUNDED ITEMS".center(w), thin,
                f"{'Product':<24}{'Qty':>6}{'Refund':>18}", thin]
        total_refunded = 0
        for r_name, r_qty, r_amount in returns:
            total_refunded += float(r_amount)
            out.append(f"{str(r_name)[:23]:<24}{r_qty:>6}{float(r_amount):>18.2f}")
        out += [thin,
                f"{'Total Refunded':<30}{cur} {total_refunded:>14,.2f}",
                f"{'ADJUSTED NET PAY':<30}{cur} {float(total) - total_refunded:>14,.2f}"]

    out += [line,
            "Thank you for shopping with us!".center(w),
            f"Developed by {config.APP_AUTHOR}".center(w)]
    return "\n".join(out)


def save_bill_file(invoice, text):
    os.makedirs(config.BILL_DIR, exist_ok=True)
    path = os.path.join(config.BILL_DIR, f"{invoice}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def print_file(parent, path):
    try:
        os.startfile(path, "print")            # Windows
    except AttributeError:
        info(parent, f"Printing works on Windows.\nThe bill was saved here:\n{path}")
    except OSError as e:
        error(parent, f"Could not print: {e}")


# ------------------------------------------------------------ activity log
def log_activity(text):
    """Audit trail: who did what. Never allowed to crash the app."""
    try:
        db.execute("INSERT INTO activity_log (employee_id, action) VALUES (%s, %s)",
                   (session.get("id"), text[:250]))
    except Exception:
        pass
