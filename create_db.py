"""
create_db.py  -  builds or upgrades the MySQL database in-place.
Upgrades v2 databases to v3 without losing any existing data.
Can be run standalone: python create_db.py

Tables:
    employees       - staff accounts (also used for login)
    categories      - product categories
    suppliers       - product suppliers
    customers       - customer contact details and order links
    products        - items sold (with cost_price, selling price, qty, sku, image)
    purchases       - stock-in purchases from suppliers
    purchase_items  - products and unit costs received in each purchase
    sales           - one row per bill (linked to customer & cashier)
    sale_items      - items inside each bill (with unit_cost snapshot)
    sale_returns    - refunded/returned items that restore product stock
    settings        - shop profile, theme, timeout and currency configuration
    activity_log    - audit trail (who did what, when)
"""
import random
from datetime import datetime, timedelta

import mysql.connector

import config
import utils
from db import db

# Base DDL schemas for all tables (using CREATE TABLE IF NOT EXISTS)
SCHEMA = [
    """CREATE TABLE IF NOT EXISTS employees (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(120) NOT NULL UNIQUE,
        gender VARCHAR(10) NOT NULL DEFAULT 'Male',
        phone VARCHAR(20) NOT NULL,
        dob DATE NULL,
        doj DATE NULL,
        role VARCHAR(20) NOT NULL DEFAULT 'Employee',
        password VARCHAR(200) NOT NULL,
        address VARCHAR(255) NULL,
        salary DECIMAL(10,2) NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB""",

    """CREATE TABLE IF NOT EXISTS categories (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(80) NOT NULL UNIQUE
    ) ENGINE=InnoDB""",

    """CREATE TABLE IF NOT EXISTS suppliers (
        id INT AUTO_INCREMENT PRIMARY KEY,
        invoice_no VARCHAR(30) NOT NULL UNIQUE,
        name VARCHAR(100) NOT NULL UNIQUE,
        contact VARCHAR(20) NOT NULL,
        description VARCHAR(255) NULL
    ) ENGINE=InnoDB""",

    """CREATE TABLE IF NOT EXISTS customers (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        phone VARCHAR(20) NOT NULL UNIQUE,
        address VARCHAR(255) NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB""",

    """CREATE TABLE IF NOT EXISTS products (
        id INT AUTO_INCREMENT PRIMARY KEY,
        category_id INT NOT NULL,
        supplier_id INT NOT NULL,
        name VARCHAR(120) NOT NULL UNIQUE,
        cost_price DECIMAL(10,2) NOT NULL DEFAULT 0,
        price DECIMAL(10,2) NOT NULL,
        qty INT NOT NULL DEFAULT 0,
        status VARCHAR(10) NOT NULL DEFAULT 'Active',
        sku VARCHAR(60) NULL UNIQUE,
        image_path VARCHAR(255) NULL,
        CONSTRAINT fk_prod_cat FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT,
        CONSTRAINT fk_prod_sup FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT
    ) ENGINE=InnoDB""",

    """CREATE TABLE IF NOT EXISTS purchases (
        id INT AUTO_INCREMENT PRIMARY KEY,
        ref_no VARCHAR(40) NOT NULL UNIQUE,
        supplier_id INT NOT NULL,
        total DECIMAL(12,2) NOT NULL,
        received_by INT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_purch_sup FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT,
        CONSTRAINT fk_purch_emp FOREIGN KEY (received_by) REFERENCES employees(id) ON DELETE SET NULL
    ) ENGINE=InnoDB""",

    """CREATE TABLE IF NOT EXISTS purchase_items (
        id INT AUTO_INCREMENT PRIMARY KEY,
        purchase_id INT NOT NULL,
        product_id INT NOT NULL,
        qty INT NOT NULL,
        unit_cost DECIMAL(10,2) NOT NULL,
        line_total DECIMAL(12,2) NOT NULL,
        CONSTRAINT fk_pitem_purch FOREIGN KEY (purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
        CONSTRAINT fk_pitem_prod FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
    ) ENGINE=InnoDB""",

    """CREATE TABLE IF NOT EXISTS sales (
        id INT AUTO_INCREMENT PRIMARY KEY,
        invoice_no VARCHAR(30) NOT NULL UNIQUE,
        customer_id INT NULL,
        customer_name VARCHAR(100) NOT NULL,
        customer_phone VARCHAR(20) NULL,
        subtotal DECIMAL(12,2) NOT NULL,
        discount_percent DECIMAL(5,2) NOT NULL DEFAULT 0,
        total DECIMAL(12,2) NOT NULL,
        sold_by INT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_sale_emp FOREIGN KEY (sold_by) REFERENCES employees(id) ON DELETE SET NULL,
        CONSTRAINT fk_sale_cust FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
    ) ENGINE=InnoDB""",

    """CREATE TABLE IF NOT EXISTS sale_items (
        id INT AUTO_INCREMENT PRIMARY KEY,
        sale_id INT NOT NULL,
        product_id INT NULL,
        product_name VARCHAR(120) NOT NULL,
        qty INT NOT NULL,
        unit_cost DECIMAL(10,2) NOT NULL DEFAULT 0,
        unit_price DECIMAL(10,2) NOT NULL,
        line_total DECIMAL(12,2) NOT NULL,
        CONSTRAINT fk_item_sale FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
        CONSTRAINT fk_item_prod FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
    ) ENGINE=InnoDB""",

    """CREATE TABLE IF NOT EXISTS sale_returns (
        id INT AUTO_INCREMENT PRIMARY KEY,
        sale_id INT NOT NULL,
        product_id INT NOT NULL,
        qty INT NOT NULL,
        refund_amount DECIMAL(10,2) NOT NULL,
        reason VARCHAR(255) NOT NULL,
        created_by INT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_ret_sale FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
        CONSTRAINT fk_ret_prod FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
        CONSTRAINT fk_ret_emp FOREIGN KEY (created_by) REFERENCES employees(id) ON DELETE SET NULL
    ) ENGINE=InnoDB""",

    """CREATE TABLE IF NOT EXISTS settings (
        key_name VARCHAR(60) PRIMARY KEY,
        value TEXT NOT NULL
    ) ENGINE=InnoDB""",

    """CREATE TABLE IF NOT EXISTS activity_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        employee_id INT NULL,
        action VARCHAR(250) NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_log_emp FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE SET NULL
    ) ENGINE=InnoDB""",
]

CATEGORIES = ["Electronics", "Groceries", "Clothing", "Stationery", "Home & Kitchen"]
SUPPLIERS = [
    ("SUP-1001", "Prime Traders", "01711000001", "Electronics wholesale"),
    ("SUP-1002", "Fresh Mart Supply", "01811000002", "Daily grocery items"),
    ("SUP-1003", "Urban Wear Ltd", "01911000003", "Clothing and fashion"),
    ("SUP-1004", "Paper Plus", "01611000004", "Office and school stationery"),
    ("SUP-1005", "HomeNest", "01511000005", "Kitchen and home items"),
]
# (category, supplier, name, cost_price, price, qty, sku)
PRODUCTS = [
    ("Electronics", "Prime Traders", "Wireless Mouse", 550, 850, 42, "SKU-MOU-01"),
    ("Electronics", "Prime Traders", "USB-C Charger 20W", 850, 1250, 6, "SKU-CHG-02"),
    ("Electronics", "Prime Traders", "Bluetooth Earbuds", 1600, 2400, 18, "SKU-EAR-03"),
    ("Electronics", "Prime Traders", "Power Bank 10000mAh", 1200, 1800, 4, "SKU-BNK-04"),
    ("Groceries", "Fresh Mart Supply", "Basmati Rice 5kg", 620, 780, 60, "SKU-RIC-05"),
    ("Groceries", "Fresh Mart Supply", "Soybean Oil 2L", 430, 520, 35, "SKU-OIL-06"),
    ("Groceries", "Fresh Mart Supply", "Green Tea Box", 240, 340, 9, "SKU-TEA-07"),
    ("Clothing", "Urban Wear Ltd", "Cotton T-Shirt", 420, 650, 28, "SKU-TSH-08"),
    ("Clothing", "Urban Wear Ltd", "Denim Jeans", 1350, 1950, 15, "SKU-JEA-09"),
    ("Clothing", "Urban Wear Ltd", "Hoodie", 1500, 2200, 8, "SKU-HOD-10"),
    ("Stationery", "Paper Plus", "A4 Paper Ream", 360, 480, 50, "SKU-PPR-11"),
    ("Stationery", "Paper Plus", "Gel Pen Pack (10)", 105, 160, 75, "SKU-PEN-12"),
    ("Stationery", "Paper Plus", "Notebook 200 pages", 80, 120, 3, "SKU-NBK-13"),
    ("Home & Kitchen", "HomeNest", "Non-stick Pan", 1000, 1450, 12, "SKU-PAN-14"),
    ("Home & Kitchen", "HomeNest", "Electric Kettle", 1450, 2100, 7, "SKU-KTL-15"),
    ("Home & Kitchen", "HomeNest", "Dinner Set (24 pcs)", 2700, 3900, 20, "SKU-SET-16"),
]


# ---------------------------------------------------- In-place schema helpers
def column_exists(table, column):
    """Check information_schema to see if a table already has a specific column."""
    cfg = config.load_db_config()
    db_name = cfg["database"]
    row = db.fetch_one(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        (db_name, table, column)
    )
    return bool(row and row[0] > 0)


def add_column_if_missing(table, column, col_def_sql):
    """Adds a new column to an existing table only if it does not exist yet."""
    if not column_exists(table, column):
        db.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {col_def_sql}")


def fk_exists(table, constraint_name):
    """Check if a foreign key constraint already exists."""
    cfg = config.load_db_config()
    db_name = cfg["database"]
    row = db.fetch_one(
        "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND CONSTRAINT_NAME = %s",
        (db_name, table, constraint_name)
    )
    return bool(row and row[0] > 0)


def setup_database():
    """Create the database, the tables, and apply in-place upgrades for v3."""
    cfg = config.load_db_config()
    name = cfg["database"]
    server = mysql.connector.connect(connection_timeout=5, host=cfg["host"], port=cfg["port"],
                                     user=cfg["user"], password=cfg["password"])
    cur = server.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cur.close()
    server.close()

    db.close()
    db.connect()

    # 1. Create any missing tables
    for statement in SCHEMA:
        db.execute(statement)

    # 2. In-place upgrade for existing v2 tables
    add_column_if_missing("products", "cost_price", "DECIMAL(10,2) NOT NULL DEFAULT 0")
    add_column_if_missing("products", "sku", "VARCHAR(60) NULL UNIQUE")
    add_column_if_missing("products", "image_path", "VARCHAR(255) NULL")
    add_column_if_missing("sale_items", "unit_cost", "DECIMAL(10,2) NOT NULL DEFAULT 0")
    add_column_if_missing("sales", "customer_id", "INT NULL")

    if not fk_exists("sales", "fk_sale_cust"):
        try:
            db.execute("ALTER TABLE sales ADD CONSTRAINT fk_sale_cust "
                       "FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL")
        except Exception:
            pass

    # 3. Seed demo data or backfill empty fields
    seed()


def seed():
    """Seeds starting accounts and sample products, or backfills v3 columns."""
    # Seed default employees if none exist
    if db.fetch_one("SELECT COUNT(*) FROM employees")[0] == 0:
        add = ("INSERT INTO employees (name,email,gender,phone,dob,doj,role,password,address,salary) "
               "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)")
        db.execute(add, (config.APP_AUTHOR, "admin@ims.com", "Male", "01866000000", "2002-01-15",
                         "2025-01-01", "Admin", utils.hash_password("admin123"), "Dhaka", 60000))
        if config.SEED_DEMO_DATA:
            db.execute(add, ("Demo Cashier", "cashier@ims.com", "Female", "01977000000", "2000-08-09",
                             "2025-06-01", "Employee", utils.hash_password("cashier123"), "Dhaka", 25000))

    # Seed default settings if missing
    default_settings = [
        ("shop_name", config.SHOP_NAME),
        ("shop_address", config.SHOP_ADDRESS),
        ("shop_phone", config.SHOP_PHONE),
        ("currency", config.CURRENCY),
        ("low_stock_limit", str(config.LOW_STOCK_LIMIT)),
        ("default_discount", str(config.DEFAULT_DISCOUNT)),
        ("theme", config.DEFAULT_THEME),
        ("idle_timeout", str(config.DEFAULT_IDLE_TIMEOUT)),
        ("language", config.DEFAULT_LANG),
    ]
    for key, val in default_settings:
        db.execute("INSERT IGNORE INTO settings (key_name, value) VALUES (%s, %s)", (key, val))

    # Seed products if empty
    if config.SEED_DEMO_DATA and db.fetch_one("SELECT COUNT(*) FROM products")[0] == 0:
        for c in CATEGORIES:
            db.execute("INSERT IGNORE INTO categories (name) VALUES (%s)", (c,))
        for s in SUPPLIERS:
            db.execute("INSERT IGNORE INTO suppliers (invoice_no,name,contact,description) VALUES (%s,%s,%s,%s)", s)
        cat = dict((n, i) for i, n in db.fetch_all("SELECT id, name FROM categories"))
        sup = dict((n, i) for i, n in db.fetch_all("SELECT id, name FROM suppliers"))
        for c, s, name, cost, price, qty, sku in PRODUCTS:
            db.execute(
                "INSERT IGNORE INTO products (category_id,supplier_id,name,cost_price,price,qty,status,sku) "
                "VALUES (%s,%s,%s,%s,%s,%s,'Active',%s)",
                (cat[c], sup[s], name, cost, price, qty, sku)
            )
        seed_sales()

    # ONE-TIME upgrade of old (v2) data. A flag in the settings table makes sure this runs only once,
    # otherwise a product the owner deliberately set to cost 0 would be rewritten on every launch.
    done = db.fetch_one("SELECT value FROM settings WHERE key_name = 'v3_backfill_done'")
    if done is None:
        db.execute("UPDATE products SET cost_price = ROUND(price * 0.70, 2) WHERE cost_price = 0")
        db.execute("UPDATE sale_items si JOIN products p ON p.id = si.product_id "
                   "SET si.unit_cost = p.cost_price WHERE si.unit_cost = 0")
        backfill_customers()
        db.execute("INSERT INTO settings (key_name, value) VALUES ('v3_backfill_done', '1')")


def backfill_customers():
    """Populates the customers table from past sales phone numbers."""
    try:
        rows = db.fetch_all(
            "SELECT DISTINCT customer_name, customer_phone FROM sales "
            "WHERE customer_phone IS NOT NULL AND customer_phone != ''"
        )
        for name, phone in rows:
            db.execute("INSERT IGNORE INTO customers (name, phone) VALUES (%s, %s)", (name, phone))
            cust = db.fetch_one("SELECT id FROM customers WHERE phone = %s", (phone,))
            if cust:
                db.execute("UPDATE sales SET customer_id = %s WHERE customer_phone = %s AND customer_id IS NULL",
                           (cust[0], phone))
    except Exception:
        pass


def seed_sales():
    """Generates demo sales with accurate unit costs for reporting."""
    rnd = random.Random(7)
    products = db.fetch_all("SELECT id, name, price, cost_price FROM products")
    admin_id = db.fetch_one("SELECT id FROM employees ORDER BY id LIMIT 1")[0]
    customers = [("Rahim Uddin", "01711111111"), ("Nusrat Jahan", "01822222222"),
                 ("Tanvir Ahmed", "01933333333"), ("Sadia Islam", "01644444444")]

    for cname, cphone in customers:
        db.execute("INSERT IGNORE INTO customers (name, phone) VALUES (%s, %s)", (cname, cphone))

    cust_map = dict(db.fetch_all("SELECT phone, id FROM customers"))
    count = 0
    for days_ago in range(6, -1, -1):
        for _ in range(rnd.randint(2, 4)):
            count += 1
            when = datetime.now() - timedelta(days=days_ago, hours=rnd.randint(0, 6), minutes=rnd.randint(0, 59))
            if days_ago == 0:
                when = datetime.now() - timedelta(minutes=rnd.randint(5, 90))
            picks = rnd.sample(products, rnd.randint(1, 3))
            items = [(p[0], p[1], rnd.randint(1, 3), float(p[2]), float(p[3])) for p in picks]
            subtotal = sum(q * price for _, _, q, price, _ in items)
            pct = rnd.choice([0, 5, 5, 10])
            total = round(subtotal * (1 - pct / 100), 2)
            invoice = f"INV-{when:%Y%m%d}-{count:03d}"
            cname, cphone = rnd.choice(customers)
            cid = cust_map.get(cphone)

            sale_id = db.execute(
                "INSERT INTO sales (invoice_no,customer_id,customer_name,customer_phone,subtotal,"
                "discount_percent,total,sold_by,created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (invoice, cid, cname, cphone, subtotal, pct, total, admin_id, when)
            )
            for pid, pname, q, price, cost in items:
                db.execute(
                    "INSERT INTO sale_items (sale_id,product_id,product_name,qty,unit_cost,unit_price,line_total) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (sale_id, pid, pname, q, cost, price, q * price)
                )
    db.execute("INSERT INTO activity_log (employee_id, action) VALUES (%s, %s)",
               (admin_id, "System initialized with v3 database schema"))


if __name__ == "__main__":
    setup_database()
    print("Database ready and upgraded to v3:", config.load_db_config()["database"])
