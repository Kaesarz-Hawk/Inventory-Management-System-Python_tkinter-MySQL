"""
config.py  -  every setting lives here, so you never hunt through the screens.
Change the shop name, colours of the currency, low-stock limit, etc. in this one file.
"""
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_path(rel_path="", writable=False):
    """
    ONE unified path helper for both source code and PyInstaller frozen executable:
    - Read-only assets (images, icons) come from sys._MEIPASS when frozen.
    - Writable files (db_config.json, bills, backups, product photos) go in %LOCALAPPDATA%/InventoryManager
      when frozen, or in the project directory when running from source.
    """
    if writable:
        if getattr(sys, "frozen", False):
            base = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "InventoryManager")
        else:
            base = BASE_DIR
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, rel_path) if rel_path else base
    else:
        base = getattr(sys, "_MEIPASS", BASE_DIR)
        return os.path.join(base, rel_path) if rel_path else base


IMAGE_DIR = get_path("images", writable=False)
BILL_DIR = get_path("bill", writable=True)
BACKUP_DIR = get_path("backups", writable=True)
PRODUCT_IMG_DIR = get_path(os.path.join("images", "products"), writable=True)
DB_CONFIG_FILE = get_path("db_config.json", writable=True)

# ---------- application identity ----------
APP_NAME = "Inventory Management System"
APP_AUTHOR = "Kawsar Hoque"
APP_VERSION = "3.0"

# ---------- shop details printed on every bill ----------
SHOP_NAME = "Smart Inventory Store"
SHOP_ADDRESS = "Dhaka, Bangladesh"
SHOP_PHONE = "01XXXXXXXXX"

# ---------- behaviour ----------
CURRENCY = "৳"
LOW_STOCK_LIMIT = 10        # products with this many items (or fewer) are flagged red
DEFAULT_DISCOUNT = 5        # % discount pre-filled on the billing screen
DEFAULT_THEME = "Dark"      # "Dark" or "Light"
DEFAULT_IDLE_TIMEOUT = 15   # minutes of inactivity before auto-logout
DEFAULT_LANG = "en"         # "en" for English, "bn" for Bangla
SEED_DEMO_DATA = True       # fill an empty database with sample data (set False for real use)
SHOW_LOGIN_HINT = True      # show the demo login on the login screen

# ---------- MySQL connection ----------
# Defaults match a fresh XAMPP / WAMP install (user root, empty password).
# The app also lets you change these from a pop-up and saves them to db_config.json.
DEFAULT_DB = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "ims_db",
}


def load_db_config():
    cfg = dict(DEFAULT_DB)
    source = DB_CONFIG_FILE
    if not os.path.exists(source) and getattr(sys, "frozen", False):
        bundled = get_path("db_config.json", writable=False)
        if os.path.exists(bundled):
            source = bundled
    if os.path.exists(source):
        try:
            with open(source, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (OSError, ValueError):
            pass
    # environment variables win (handy for testing)
    for key in cfg:
        env = os.environ.get("IMS_DB_" + key.upper())
        if env is not None:
            cfg[key] = int(env) if key == "port" else env
    return cfg


def save_db_config(cfg):
    with open(DB_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

