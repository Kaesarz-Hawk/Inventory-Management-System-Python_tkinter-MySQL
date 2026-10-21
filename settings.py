"""
settings.py  -  loads and saves application settings from the database.
If the database table is not ready yet, it safely falls back to config.py defaults.
This allows the Admin to change the shop name, address, currency, discount %, etc.
from the UI without modifying any code.
"""
import config
from db import db

# In-memory cache so we do not query the database repeatedly for settings
_SETTINGS_CACHE = {}


def get_setting(key, default=None):
    """
    Get a single setting by key.
    Checks memory cache first, then the database, then fallback default.
    """
    if key in _SETTINGS_CACHE:
        return _SETTINGS_CACHE[key]

    try:
        row = db.fetch_one("SELECT value FROM settings WHERE key_name = %s", (key,))
        if row is not None:
            _SETTINGS_CACHE[key] = row[0]
            return row[0]
    except Exception:
        # If DB is not yet initialized or unreachable, use default (and do NOT cache it)
        return default if default is not None else _fallbacks().get(key, "")

    # Row not in the table: use the default (cached, so we do not query again and again)
    value = default if default is not None else _fallbacks().get(key, "")
    _SETTINGS_CACHE[key] = str(value)
    return value


def _fallbacks():
    """Default values from config.py"""
    return {
        "shop_name": config.SHOP_NAME,
        "shop_address": config.SHOP_ADDRESS,
        "shop_phone": config.SHOP_PHONE,
        "currency": config.CURRENCY,
        "low_stock_limit": str(config.LOW_STOCK_LIMIT),
        "default_discount": str(config.DEFAULT_DISCOUNT),
        "theme": config.DEFAULT_THEME,
        "idle_timeout": str(config.DEFAULT_IDLE_TIMEOUT),
        "language": config.DEFAULT_LANG,
    }


def set_setting(key, value):
    """Save or update a setting in the database. Returns True if it was really saved."""
    val_str = str(value)
    try:
        db.execute(
            "INSERT INTO settings (key_name, value) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE value = %s",
            (key, val_str, val_str)
        )
    except Exception:
        return False                       # nothing was saved - the caller shows an error
    _SETTINGS_CACHE[key] = val_str         # only remember it after the database accepted it
    return True


def reload_settings():
    """Reload all settings from the database into the memory cache."""
    _SETTINGS_CACHE.clear()
    try:
        rows = db.fetch_all("SELECT key_name, value FROM settings")
        for k, v in rows:
            _SETTINGS_CACHE[k] = v
    except Exception:
        pass


# ------------------------------------------------ Typed convenience helpers
def get_shop_name():
    return get_setting("shop_name", config.SHOP_NAME)


def get_shop_address():
    return get_setting("shop_address", config.SHOP_ADDRESS)


def get_shop_phone():
    return get_setting("shop_phone", config.SHOP_PHONE)


def get_currency():
    return get_setting("currency", config.CURRENCY)


def get_low_stock_limit():
    try:
        return int(get_setting("low_stock_limit", config.LOW_STOCK_LIMIT))
    except (TypeError, ValueError):
        return config.LOW_STOCK_LIMIT


def get_default_discount():
    try:
        return float(get_setting("default_discount", config.DEFAULT_DISCOUNT))
    except (TypeError, ValueError):
        return config.DEFAULT_DISCOUNT


def get_idle_timeout():
    try:
        return int(get_setting("idle_timeout", config.DEFAULT_IDLE_TIMEOUT))
    except (TypeError, ValueError):
        return config.DEFAULT_IDLE_TIMEOUT


def get_theme():
    return get_setting("theme", config.DEFAULT_THEME)


def get_language():
    return get_setting("language", config.DEFAULT_LANG)

