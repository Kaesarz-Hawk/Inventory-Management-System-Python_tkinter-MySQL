"""
Unit tests - no window and no database needed.
Run:   python tests/test_utils.py        (or:  pytest tests)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import settings                      # noqa: E402
import utils                         # noqa: E402
from datetime import datetime        # noqa: E402

# give the settings cache fixed values so the tests never need MySQL
settings._SETTINGS_CACHE.update({"currency": "৳", "shop_name": "Test Shop", "shop_address": "Dhaka", "shop_phone": "0100"})


def raises(kind, raw):
    try:
        utils.validate(kind, raw, "Field")
    except ValueError:
        return True
    return False


def test_validation():
    assert utils.validate("email", "A@B.com", "x") == "a@b.com"
    assert raises("email", "not-an-email")
    assert utils.validate("phone", "0171-122 3344", "x") == "01711223344"
    assert raises("phone", "12")
    assert utils.validate("date", "2001-05-24", "x") == "2001-05-24"
    assert raises("date", "2001-13-45")
    assert utils.validate("int", "12", "x") == 12 and raises("int", "-3") and raises("int", "1.5")
    assert utils.validate("float", "12.345", "x") == 12.35 and raises("float", "-1") and raises("float", "abc")


def test_password_hash():
    stored = utils.hash_password("secret1")
    assert "$" in stored and "secret1" not in stored
    assert utils.verify_password("secret1", stored)
    assert not utils.verify_password("wrong", stored)
    assert utils.hash_password("secret1") != stored          # random salt -> different every time
    assert not utils.verify_password("x", "garbage-without-dollar")


def test_text_helpers():
    assert utils.short_number(950) == "950" and utils.short_number(12500) == "12.5K" and utils.short_number(2_000_000) == "2M"
    assert utils.ellipsize("short", 10) == "short"
    assert utils.ellipsize("Electric Kettle Deluxe", 10).endswith("…") and len(utils.ellipsize("Electric Kettle Deluxe", 10)) <= 10
    assert utils.money(1234.5) == "৳ 1,234.50"


def test_bill_text():
    when = datetime(2026, 10, 18, 14, 30)
    text = utils.build_bill("INV-1", when, "Rahim", "01711223344", [("Mouse", 2, 850, 1700)], 1700, 5, 85, 1615, "Kawsar")
    assert "Test Shop" in text and "NET PAY" in text and "1,615.00" in text and "Rahim" in text
    refunded = utils.build_bill("INV-1", when, "Rahim", "", [("Mouse", 2, 850, 1700)], 1700, 5, 85, 1615, "Kawsar",
                                returns=[("Mouse", 1, 807.5)])
    assert "Total Refunded" in refunded and "ADJUSTED NET PAY" in refunded and "807.50" in refunded


def test_profit_maths():
    """profit = revenue - refunds - (cost of goods sold - cost of returned goods)"""
    revenue, cost, refunds, returned_cost = 1615.0, 1000.0, 807.5, 500.0
    assert revenue - refunds - (cost - returned_cost) == 307.5


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"\nAll {len(tests)} unit tests passed.")
