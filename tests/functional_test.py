"""
End-to-end test: drives the real screens against a REAL but SEPARATE MySQL database (ims_test_db).
Run:   python tests/functional_test.py
It refuses to run on any database whose name does not contain "test", so your real data is safe.
"""
import os
import sys
import time
import traceback
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ.setdefault("IMS_DB_DATABASE", "ims_test_db")
if "test" not in os.environ["IMS_DB_DATABASE"].lower():
    sys.exit("Refusing to run: database name must contain 'test'.")

import mysql.connector                       # noqa: E402
import tkinter                               # noqa: E402
import config                                # noqa: E402
import utils                                 # noqa: E402

FAILS, PASSES, errors = [], [], []
tkinter.Tk.report_callback_exception = lambda self, *a: (traceback.print_exception(*a), FAILS.append("exception inside a Tk callback"))
utils.messagebox.showerror = lambda t, m, **k: errors.append(m)
utils.messagebox.showinfo = lambda t, m, **k: None
utils.messagebox.askyesno = lambda *a, **k: True
utils.filedialog.asksaveasfilename = lambda **k: ""


def check(name, cond, detail=""):
    (PASSES if cond else FAILS).append(name)
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else f"   -> {detail}"))


def server_connection(database=None):
    cfg = config.load_db_config()
    return mysql.connector.connect(host=cfg["host"], port=cfg["port"], user=cfg["user"], password=cfg["password"],
                                   **({"database": database} if database else {}))


def reset_database(name):
    conn = server_connection()
    conn.cursor().execute(f"DROP DATABASE IF EXISTS `{name}`")
    conn.close()


# ======================================================================================
# PART 1 - upgrade a v2 database to v3 (must keep every row)
# ======================================================================================
def test_migration():
    print("\n--- v2 -> v3 database upgrade ---")
    from db import db
    from create_db import setup_database
    name = os.environ["IMS_DB_DATABASE"]
    mig = name.replace("test", "migtest") if "test" in name else name + "_migtest"
    reset_database(mig)
    os.environ["IMS_DB_DATABASE"] = mig
    conn = server_connection(); conn.cursor().execute(f"CREATE DATABASE `{mig}`"); conn.close()
    conn = server_connection(mig); cur = conn.cursor()
    for sql in [
        "CREATE TABLE employees (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(100) NOT NULL, email VARCHAR(120) NOT NULL UNIQUE, gender VARCHAR(10) NOT NULL DEFAULT 'Male', phone VARCHAR(20) NOT NULL, dob DATE NULL, doj DATE NULL, role VARCHAR(20) NOT NULL DEFAULT 'Employee', password VARCHAR(200) NOT NULL, address VARCHAR(255) NULL, salary DECIMAL(10,2) NOT NULL DEFAULT 0, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB",
        "CREATE TABLE categories (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(80) NOT NULL UNIQUE) ENGINE=InnoDB",
        "CREATE TABLE suppliers (id INT AUTO_INCREMENT PRIMARY KEY, invoice_no VARCHAR(30) NOT NULL UNIQUE, name VARCHAR(100) NOT NULL UNIQUE, contact VARCHAR(20) NOT NULL, description VARCHAR(255) NULL) ENGINE=InnoDB",
        "CREATE TABLE products (id INT AUTO_INCREMENT PRIMARY KEY, category_id INT NOT NULL, supplier_id INT NOT NULL, name VARCHAR(120) NOT NULL UNIQUE, price DECIMAL(10,2) NOT NULL, qty INT NOT NULL DEFAULT 0, status VARCHAR(10) NOT NULL DEFAULT 'Active', FOREIGN KEY (category_id) REFERENCES categories(id), FOREIGN KEY (supplier_id) REFERENCES suppliers(id)) ENGINE=InnoDB",
        "CREATE TABLE sales (id INT AUTO_INCREMENT PRIMARY KEY, invoice_no VARCHAR(30) NOT NULL UNIQUE, customer_name VARCHAR(100) NOT NULL, customer_phone VARCHAR(20) NULL, subtotal DECIMAL(12,2) NOT NULL, discount_percent DECIMAL(5,2) NOT NULL DEFAULT 0, total DECIMAL(12,2) NOT NULL, sold_by INT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB",
        "CREATE TABLE sale_items (id INT AUTO_INCREMENT PRIMARY KEY, sale_id INT NOT NULL, product_id INT NULL, product_name VARCHAR(120) NOT NULL, qty INT NOT NULL, unit_price DECIMAL(10,2) NOT NULL, line_total DECIMAL(12,2) NOT NULL, FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE) ENGINE=InnoDB",
        "CREATE TABLE activity_log (id INT AUTO_INCREMENT PRIMARY KEY, employee_id INT NULL, action VARCHAR(250) NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB",
        "INSERT INTO categories (name) VALUES ('Old Cat')",
        "INSERT INTO suppliers (invoice_no,name,contact) VALUES ('S-1','Old Supplier','01700000000')",
        "INSERT INTO products (category_id,supplier_id,name,price,qty) VALUES (1,1,'Old Product',1000,7)",
        "INSERT INTO sales (invoice_no,customer_name,customer_phone,subtotal,discount_percent,total) VALUES ('OLD-1','Old Customer','01711111111',2000,0,2000)",
        "INSERT INTO sale_items (sale_id,product_id,product_name,qty,unit_price,line_total) VALUES (1,1,'Old Product',2,1000,2000)",
    ]:
        cur.execute(sql)
    conn.commit(); conn.close()

    db.close()
    setup_database()
    q = lambda sql: db.fetch_one(sql)
    check("upgrade: old product kept", q("SELECT qty FROM products WHERE name='Old Product'") == (7,))
    check("upgrade: old sale kept", q("SELECT total FROM sales WHERE invoice_no='OLD-1'")[0] == 2000)
    check("upgrade: all new tables exist", q("SELECT COUNT(*) FROM information_schema.TABLES WHERE table_schema=DATABASE() AND table_name IN "
                                           "('customers','purchases','purchase_items','sale_returns','settings')")[0] == 5)
    check("upgrade: old product got a cost (70% of price)", q("SELECT cost_price FROM products WHERE name='Old Product'")[0] == 700)
    check("upgrade: old bill items got the cost snapshot", q("SELECT unit_cost FROM sale_items WHERE sale_id=1")[0] == 700)
    check("upgrade: old customer registered from old sale", q("SELECT COUNT(*) FROM customers WHERE phone='01711111111'")[0] == 1)
    db.execute("UPDATE products SET cost_price = 0 WHERE name='Old Product'")
    db.execute("UPDATE sale_items SET unit_cost = 0 WHERE sale_id = 1")
    setup_database()                                            # a second launch
    check("upgrade: second launch does NOT rewrite cost 0", q("SELECT cost_price FROM products WHERE name='Old Product'")[0] == 0)
    check("upgrade: second launch does NOT rewrite old snapshot", q("SELECT unit_cost FROM sale_items WHERE sale_id=1")[0] == 0)
    db.close()
    reset_database(mig)
    os.environ["IMS_DB_DATABASE"] = name


# ======================================================================================
# PART 2 - the application
# ======================================================================================
def main():
    from db import db
    import settings
    import lang
    name = os.environ["IMS_DB_DATABASE"]
    test_migration()
    reset_database(name)

    bills_before = set(os.listdir(config.BILL_DIR)) if os.path.isdir(config.BILL_DIR) else set()
    backups_before = set(os.listdir(config.BACKUP_DIR)) if os.path.isdir(config.BACKUP_DIR) else set()

    from dashboard import App
    app = App()
    app.geometry("1600x900+0+0")

    def pump(ms=300):
        end = time.time() + ms / 1000
        while time.time() < end:
            app.update()
            time.sleep(0.01)

    def login(email, pw):
        app.login.email.delete(0, "end"); app.login.password.delete(0, "end")
        app.login.email.insert(0, email); app.login.password.insert(0, pw)
        app.login.attempt(); pump(600)

    def last_error():
        return errors[-1] if errors else ""

    def q(sql, params=()):
        return db.fetch_one(sql, params)

    def pick(page_table, value, col):
        for iid, row in page_table.rows.items():
            if row[col] == value:
                page_table.tree.selection_set(iid); pump(100)
                return True
        return False

    print("\n--- login & roles ---")
    pump(1800)
    login("admin@ims.com", "wrong")
    check("wrong password rejected", app.login is not None and "Incorrect" in app.login.message.cget("text"))
    login("admin@ims.com", "admin123")
    check("admin can log in", utils.session.get("role") == "Admin")
    check("admin sees all 11 pages", len(app.nav_buttons) == 11, str(list(app.nav_buttons)))

    # a product we fully control
    cat, sup = q("SELECT MIN(id) FROM categories")[0], q("SELECT MIN(id) FROM suppliers")[0]
    db.execute("INSERT INTO products (category_id,supplier_id,name,sku,cost_price,price,qty,status) VALUES (%s,%s,'Test Widget','TW-1',100,200,5,'Active')", (cat, sup))
    pid = q("SELECT id FROM products WHERE name='Test Widget'")[0]

    print("\n--- billing ---")
    app.show_page("Billing"); pump(300); B = app.pages["Billing"]
    B.search.delete(0, "end"); B.search.insert(0, "TW-1"); B.on_search_enter(); pump(200)
    check("SKU + Enter adds 1 unit to the cart", pid in B.cart and B.cart[pid]["qty"] == 1, str(B.cart))
    B.search.delete(0, "end"); B.load_products(); pump(100)
    pick(B.prod_table, "Test Widget", 1)
    B.qty.delete(0, "end"); B.qty.insert(0, "3"); B.add_to_cart()
    check("cart total = 3 x 200 = 600, 5% discount -> 570", "570.00" in B.lbl_net.cget("text"), B.lbl_net.cget("text"))
    n = len(errors); B.generate_bill()
    check("bill needs a customer name", len(errors) > n)
    B.cust_name.insert(0, "Test Customer"); B.cust_phone.insert(0, "01711223344")
    before_customers = q("SELECT COUNT(*) FROM customers")[0]
    B.generate_bill(); pump(300)
    sale = q("SELECT id, total, customer_id, invoice_no FROM sales WHERE customer_name='Test Customer'")
    check("sale saved with 5% discount", sale and float(sale[1]) == 570.0, str(sale))
    sale_id, invoice = sale[0], sale[3]
    check("new customer created and linked to the bill", q("SELECT COUNT(*) FROM customers")[0] == before_customers + 1 and sale[2] is not None)
    check("stock reduced 5 -> 2", q("SELECT qty FROM products WHERE id=%s", (pid,))[0] == 2)
    check("cost price snapshot stored on the sale item", q("SELECT unit_cost FROM sale_items WHERE sale_id=%s", (sale_id,))[0] == 100)
    check("bill .txt file written", B.last_bill_path and os.path.exists(B.last_bill_path))
    B.clear_all(); pump(100)
    B.cust_phone.insert(0, "01711223344"); B.on_phone_change(); pump(100)
    check("typing a known phone number auto-fills the customer name", B.cust_name.get() == "Test Customer", B.cust_name.get())
    B.clear_all()

    print("\n--- purchases (stock-in) ---")
    app.show_page("Purchases"); pump(300); P = app.pages["Purchases"]
    check("purchase combos start on 'Select' (not blank)", P.sup_combo.get() == "Select" and P.prod_combo.get() == "Select")
    sup_name = q("SELECT name FROM suppliers WHERE id=%s", (sup,))[0]
    P.sup_combo.set(sup_name); P.prod_combo.set("Test Widget"); P.on_product_pick("Test Widget")
    check("picking a product pre-fills its cost", P.cost_entry.get() == "100.00", P.cost_entry.get())
    P.qty_entry.delete(0, "end"); P.qty_entry.insert(0, "10"); P.cost_entry.delete(0, "end"); P.cost_entry.insert(0, "120")
    P.add_item(); ref = P.ref_entry.get(); P.save_purchase(); pump(300)
    check("purchase INCREASES stock 2 -> 12", q("SELECT qty FROM products WHERE id=%s", (pid,))[0] == 12)
    check("purchase updates cost price to 120", float(q("SELECT cost_price FROM products WHERE id=%s", (pid,))[0]) == 120)
    check("purchase is in the history", q("SELECT COUNT(*) FROM purchases WHERE ref_no=%s", (ref,))[0] == 1)
    check("OLD sale snapshot is NOT changed by the new cost", q("SELECT unit_cost FROM sale_items WHERE sale_id=%s", (sale_id,))[0] == 100)
    P.sup_combo.set(sup_name); P.prod_combo.set("Test Widget"); P.qty_entry.delete(0, "end"); P.qty_entry.insert(0, "1")
    P.cost_entry.delete(0, "end"); P.cost_entry.insert(0, "120"); P.add_item()
    P.ref_entry.delete(0, "end"); P.ref_entry.insert(0, ref); n = len(errors); P.save_purchase()
    check("duplicate purchase reference -> friendly error", len(errors) > n and "already exists" in last_error(), last_error())
    P.clear_form()

    print("\n--- stock safety ---")
    app.show_page("Billing"); pump(300)
    B.search.delete(0, "end"); B.search.insert(0, "Test Widget"); B.load_products(); pump(100); pick(B.prod_table, "Test Widget", 1)
    B.qty.delete(0, "end"); B.qty.insert(0, "12"); B.add_to_cart()
    db.execute("UPDATE products SET qty = 1 WHERE id=%s", (pid,))              # somebody else sold it meanwhile
    B.cust_name.insert(0, "Rollback Test"); sales_before = q("SELECT COUNT(*) FROM sales")[0]; n = len(errors); B.generate_bill(); pump(200)
    check("stale stock -> error and NOTHING half-saved (rollback)", len(errors) > n and q("SELECT COUNT(*) FROM sales")[0] == sales_before and q("SELECT qty FROM products WHERE id=%s", (pid,))[0] == 1)
    B.clear_all(); db.execute("UPDATE products SET qty = 12 WHERE id=%s", (pid,))
    B.search.delete(0, "end"); B.search.insert(0, "Test Widget"); B.load_products(); pump(100); pick(B.prod_table, "Test Widget", 1)
    B.qty.delete(0, "end"); B.qty.insert(0, "12"); B.add_to_cart(); B.cust_name.insert(0, "Sold Out Customer"); B.generate_bill(); pump(300)
    check("selling the last units sets the product Inactive", q("SELECT qty, status FROM products WHERE id=%s", (pid,)) == (0, "Inactive"))
    B.clear_all()

    print("\n--- returns / refunds ---")
    app.show_page("Sales"); pump(400); S = app.pages["Sales"]
    pick(S.table, invoice, 1)
    from sales import ReturnItemDialog
    d = ReturnItemDialog(S, sale_id, invoice, lambda: None); pump(200)
    d.item_combo.set("Test Widget"); d.on_item_select("Test Widget"); pump(100)
    check("refund default respects the 5% bill discount (200 x 0.95 = 190)", d.amount_entry.get() == "190.00", d.amount_entry.get())
    d.amount_entry.delete(0, "end"); d.amount_entry.insert(0, "500"); d.reason_entry.insert(0, "test"); n = len(errors); d.process_return()
    check("refund above what the customer paid is blocked", len(errors) > n and "paid" in last_error(), last_error())
    d.qty_entry.delete(0, "end"); d.qty_entry.insert(0, "9"); n = len(errors); d.process_return()
    check("returning more than was sold is blocked", len(errors) > n and "Maximum" in last_error(), last_error())
    d.qty_entry.delete(0, "end"); d.qty_entry.insert(0, "1"); d.on_qty_change(); d.process_return(); pump(300)
    check("return restores stock 0 -> 1 and re-activates the product", q("SELECT qty, status FROM products WHERE id=%s", (pid,)) == (1, "Active"))
    check("return is recorded", float(q("SELECT refund_amount FROM sale_returns WHERE sale_id=%s", (sale_id,))[0]) == 190.0)
    S.on_select(S.table.selected_row()); pump(100)
    check("bill preview shows the refund", "Total Refunded" in S.box.get("1.0", "end"))

    print("\n--- reports reconcile with the database ---")
    app.show_page("Reports"); pump(300); R = app.pages["Reports"]
    R.from_entry.delete(0, "end"); R.from_entry.insert(0, "2020-01-01"); R.apply_filter(); pump(400)
    revenue = float(q("SELECT SUM(total) FROM sales")[0]); cost = float(q("SELECT SUM(qty*unit_cost) FROM sale_items")[0])
    refunds = float(q("SELECT COALESCE(SUM(refund_amount),0) FROM sale_returns")[0])
    ret_cost = float(q("SELECT COALESCE(SUM(sr.qty*si.unit_cost),0) FROM sale_returns sr JOIN sale_items si ON si.sale_id=sr.sale_id AND si.product_id=sr.product_id")[0])
    expected_profit = revenue - refunds - (cost - ret_cost)
    check("trend chart revenue adds up to the real revenue", abs(sum(r for _, r, _ in R.daily_data) - revenue) < 0.01, f"{sum(r for _, r, _ in R.daily_data)} vs {revenue}")
    check("trend chart profit adds up to the net profit", abs(sum(p for _, _, p in R.daily_data) - expected_profit) < 0.01, f"{sum(p for _, _, p in R.daily_data)} vs {expected_profit}")
    check("itemized revenue adds up to the real revenue", abs(sum(float(r[4]) for r in R.table.current_rows()) - revenue) < 1.0)
    check("itemized profit = revenue - cost (before refunds)", abs(sum(float(r[6]) for r in R.table.current_rows()) - (revenue - cost)) < 1.0)
    check("'Sold' column shows whole numbers", all(isinstance(r[3], int) for r in R.table.current_rows()))
    sold = int(q("SELECT SUM(qty) FROM sale_items")[0]) - int(q("SELECT COALESCE(SUM(qty),0) FROM sale_returns")[0])
    check("items-sold card = sold minus returned", R.cards["items"].value.cget("text") == str(sold), R.cards["items"].value.cget("text"))
    R.from_entry.delete(0, "end"); R.from_entry.insert(0, "2030-01-01"); n = len(errors); R.apply_filter()
    check("From date after To date is rejected", len(errors) > n)
    R.set_30d(); pump(300); R.draw_trend(); R.draw_top_products()
    check("charts draw without errors", True)

    print("\n--- settings, language, theme, backup ---")
    app.show_page("Settings"); pump(300); ST = app.pages["Settings"]
    ST.currency_sym.delete(0, "end"); n = len(errors); ST.save_store_settings()
    check("empty currency rejected", len(errors) > n)
    ST.currency_sym.insert(0, "$"); ST.def_disc.delete(0, "end"); ST.def_disc.insert(0, "150"); n = len(errors); ST.save_store_settings()
    check("discount over 100% rejected", len(errors) > n)
    ST.def_disc.delete(0, "end"); ST.def_disc.insert(0, "7"); ST.shop_name.delete(0, "end"); ST.shop_name.insert(0, "Kawsar Test Shop"); ST.save_store_settings()
    check("settings saved to MySQL", q("SELECT value FROM settings WHERE key_name='shop_name'")[0] == "Kawsar Test Shop" and q("SELECT value FROM settings WHERE key_name='currency'")[0] == "$")
    check("new currency used everywhere", utils.money(10) == "$ 10.00")
    ST.currency_sym.delete(0, "end"); ST.currency_sym.insert(0, "৳"); ST.shop_name.delete(0, "end"); ST.shop_name.insert(0, "Smart Inventory Store"); ST.def_disc.delete(0, "end"); ST.def_disc.insert(0, "5"); ST.save_store_settings()
    ST.on_lang_select("Bangla (বাংলা)"); pump(600)
    check("Bangla: text is translated", lang.t("Save") == "সংরক্ষণ" and lang.t("Products") == "পণ্য")
    check("Bangla: whole window rebuilt (sidebar + page title)", "ড্যাশবোর্ড" in app.nav_buttons["Dashboard"].cget("text") and app.page_title.cget("text") == "সেটিংস")
    for page in ("Employees", "Products", "Billing", "Reports", "Purchases", "Dashboard"):
        app.show_page(page); pump(250)
    check("Bangla: every page opens without errors", True)
    app.pages["Settings"].on_lang_select("English"); pump(600)
    check("English restored", lang.t("Save") == "Save" and app.page_title.cget("text") == "Settings")
    app.pages["Settings"].on_theme_select("Light"); pump(300)
    check("theme choice is saved", q("SELECT value FROM settings WHERE key_name='theme'")[0] == "Light")
    app.pages["Settings"].on_theme_select("Dark"); pump(200)
    ST = app.pages["Settings"]; ST.backup_database(); pump(300)
    new_zips = set(os.listdir(config.BACKUP_DIR)) - backups_before
    check("backup creates a zip", len(new_zips) == 1, str(new_zips))
    if new_zips:
        zf = zipfile.ZipFile(os.path.join(config.BACKUP_DIR, next(iter(new_zips))))
        check("backup contains all 12 tables as CSV", len(zf.namelist()) == 12, str(zf.namelist()))
        zf.close()

    print("\n--- product form + dashboard ---")
    app.show_page("Products"); pump(300); PR = app.pages["Products"]
    logo = os.path.join(config.IMAGE_DIR, "app_logo.png")
    try:
        PR.write({"key": "image_path", "kind": "image"}, logo); pump(150); PR.clear(); pump(150); PR.clear(); pump(100)
        check("clearing the form after choosing a picture does not crash", True)
    except Exception as e:                                                       # noqa: BLE001
        check("clearing the form after choosing a picture does not crash", False, repr(e))
    app.show_page("Dashboard"); pump(300)
    t0 = len(app.tk.call("after", "info"))
    for _ in range(8):
        app.show_page("Employees"); app.show_page("Dashboard")
    check("dashboard refresh timers do not pile up", len(app.tk.call("after", "info")) - t0 <= 2, f"{t0} -> {len(app.tk.call('after', 'info'))}")

    print("\n--- idle auto-logout ---")
    from datetime import datetime, timedelta
    settings.set_setting("idle_timeout", 0); app.last_activity = datetime.now() - timedelta(hours=3); app.check_idle_timeout(); pump(200)
    check("idle timeout 0 means NEVER log out", app.shell is not None)
    settings.set_setting("idle_timeout", 1); app.last_activity = datetime.now() - timedelta(hours=3); app.check_idle_timeout(); pump(500)
    check("idle timeout 1 minute logs out and shows the login screen", app.shell is None and app.login is not None and app.login.winfo_exists())
    settings.set_setting("idle_timeout", 15)

    print("\n--- cashier (non-admin) ---")
    login("cashier@ims.com", "cashier123")
    check("cashier logs in", utils.session.get("role") == "Employee")
    check("cashier cannot see admin pages", set(app.nav_buttons) == {"Dashboard", "Products", "Customers", "Billing", "Sales", "Settings"}, str(set(app.nav_buttons)))
    app.show_page("Settings"); pump(400); ST = app.pages["Settings"]
    ST.shop_name.configure(state="normal"); shown = ST.shop_name.get(); ST.shop_name.configure(state="disabled")
    check("disabled store settings still SHOW the current shop name", shown == "Smart Inventory Store", repr(shown))
    n = len(errors); ST.save_store_settings()
    check("cashier cannot save store settings", len(errors) > n)
    ST.old_pw.insert(0, "badold"); ST.new_pw.insert(0, "newpass1"); ST.confirm_pw.insert(0, "newpass1"); n = len(errors); ST.change_password()
    check("password change needs the correct old password", len(errors) > n and "incorrect" in last_error().lower())
    ST.old_pw.delete(0, "end"); ST.old_pw.insert(0, "cashier123"); ST.change_password(); pump(200)
    check("password change works and is hashed", utils.verify_password("newpass1", q("SELECT password FROM employees WHERE email='cashier@ims.com'")[0]))
    db.execute("UPDATE employees SET password=%s WHERE email='cashier@ims.com'", (utils.hash_password("cashier123"),))

    # ---- cleanup of files created by the test ----
    for f in set(os.listdir(config.BILL_DIR)) - bills_before:
        os.remove(os.path.join(config.BILL_DIR, f))
    for f in new_zips:
        os.remove(os.path.join(config.BACKUP_DIR, f))
    db.close(); app.destroy(); reset_database(name)
    print(f"\nRESULT: {len(PASSES)} passed, {len(FAILS)} failed")
    if FAILS:
        print("FAILED:", FAILS)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
