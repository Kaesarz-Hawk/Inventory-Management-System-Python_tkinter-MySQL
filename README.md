# Inventory Management System v3.0
**Developed by Kawsar Hoque** — Python + CustomTkinter (Tkinter) + MySQL (`mysql-connector-python`) + Pillow

---

## How to Run (3 Steps)
1. **Start MySQL** (via XAMPP, WAMP, or MySQL service).
2. **Install requirements**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Start the app**:
   ```bash
   python main.py
   ```

*The database `ims_db`, all 12 normalized tables, in-place column upgrades, and initial demo data are created **automatically** on first run.*  
If MySQL requires a custom password or port, the app displays a **"Connect to MySQL"** dialog to test and save your credentials.

**Demo Logins**:
- **Admin**: `admin@ims.com` / `admin123` (all 11 pages)
- **Cashier**: `cashier@ims.com` / `cashier123` (Access restricted to Billing, Sales, Products, Customers, Dashboard)

---

## What We Upgraded in v3.0

| # | Feature / Upgrade | Tier | Description & Implementation | Location |
|---|-------------------|------|-----------------------------|----------|
| 1 | **Purchases / Stock-In** | Tier 1 | Admin records supplier restocks with unit cost in one transaction; increments stock, reactivates product, updates `cost_price`, generates PO receipt. | `purchases.py` |
| 2 | **Cost Price & Profit** | Tier 1 | Added `products.cost_price`; snapshots `sale_items.unit_cost` at moment of sale so historical profit never alters when prices change. | `product.py`, `billing.py` |
| 3 | **Customer CRM** | Tier 1 | Customers table tracking order count and total spend; auto-fills name in Billing on typing phone number; auto-creates new customers on sale. | `customer.py`, `billing.py` |
| 4 | **Returns & Refunds** | Tier 1 | Return item dialog on Sales page validating return quantity; atomic transaction records refund, restores stock, and reactivates product. | `sales.py` |
| 5 | **Analytics & Reports** | Tier 1 | Date range filtering (Presets: Today, 7D, 30D, Month); 6 KPI cards; Canvas trend & top-seller charts; itemized sales breakdown with CSV export. | `reports.py` |
| 6 | **Settings & Preferences** | Tier 1 | Database-backed settings (shop name, address, phone, currency, discount, low stock limit); user password change; theme & language persistence. | `settings.py`, `settings_page.py` |
| 7 | **Database Backup** | Tier 1 | One-click backup exporting all 12 tables into CSV files inside a timestamped ZIP in `backups/`. | `settings_page.py` |
| 8 | **SKU / Barcode Scan** | Tier 2 | Enter or scan product barcode in Billing search box and press `<Return>` to instantly add 1 unit to cart. | `billing.py`, `product.py` |
| 9 | **Product Images** | Tier 2 | Upload product pictures via file picker; stored safely in `images/products/`; rendered in form and Billing selection bar with safe fallbacks. | `base_page.py`, `billing.py` |
| 10 | **Reorder Suggestions** | Tier 2 | Intelligent inventory card recommending replenishment quantity using lead-time demand formula; one-click pre-fills Purchases order. | `dashboard.py` |
| 11 | **Idle Auto-Logout** | Tier 2 | Monitors keyboard/mouse activity; automatically logs out user and returns to login screen after N minutes of inactivity (default 15m). | `dashboard.py` |
| 12 | **Bilingual UI (Bangla/English)** | Tier 3 | Toggle UI language between English and Bangla (বাংলা); persists choice in settings; supports Bengali typography. | `lang.py`, `dashboard.py` |
| 13 | **Keyboard Shortcuts** | Tier 3 | Global shortcuts: `F11` (Full Screen), `Ctrl+F` (Focus Search), `Ctrl+N` (New / Clear), `F5` (Refresh Active Page). | `dashboard.py` |

---

## File Map (What Each File Does)

| File | Purpose & Role in viva |
|------|------------------------|
| `main.py` | Application entry point; verifies dependencies and launches `App`. |
| `config.py` | Application identity, default constants, and unified `get_path()` helper for PyInstaller compatibility. |
| `settings.py` | Database settings helper caching store profile, theme, and timeout configurations with fallback to `config.py`. |
| `lang.py` | Localization dictionary providing English and Bangla translations for menus, buttons, and notifications. |
| `db.py` | Singleton database layer; the ONLY file that talks to MySQL (`fetch_all`, `execute`, `transaction`). |
| `create_db.py` | In-place database migration script; adds new tables and columns without dropping or losing existing v2 data. |
| `utils.py` | PBKDF2 password hashing, validation helpers, formatted bill generator, CSV exporter, and activity log. |
| `theme.py` | Modern design system; adaptive dark/light tokens, font factories, toast popups, and `DataTable` treeview styling. |
| `base_page.py` | Abstract parent class `CrudPage` encapsulating Create, Read, Update, Delete workflows and image picking. |
| `employee.py` | Subclass of `CrudPage` managing employee staff accounts, salaries, and credentials. |
| `supplier.py` | Subclass of `CrudPage` managing suppliers, contact info, and product associations. |
| `category.py` | Subclass of `CrudPage` organizing products into departments/categories. |
| `customer.py` | Subclass of `CrudPage` tracking customer profiles, order frequencies, and total lifetime spend. |
| `product.py` | Subclass of `CrudPage` managing inventory items, cost prices, selling prices, quantities, SKUs, and images. |
| `purchases.py` | Admin stock-in interface; records purchase orders, updates cost prices, and increases warehouse stock atomically. |
| `billing.py` | Two-column responsive Point of Sale; SKU barcode entry, customer auto-fill, cart staging, and bill printing. |
| `sales.py` | Sales history archive, monospace receipt viewer, Windows printing, and itemized refund/return dialog. |
| `reports.py` | Executive analytics dashboard; date-range KPI metrics, canvas trend graphs, and profit margin analysis. |
| `settings_page.py`| Store identity editor, password updater, dark/light theme switch, and full ZIP database backup generator. |
| `dashboard.py` | Main window shell (`App`), responsive sidebar, header bar, clock, idle monitor, and dashboard page. |
| `make_assets.py` | Script to generate login banners, application logos, and window icons using Pillow. |

---

## Database Architecture (12 Tables)

All tables use **InnoDB** for ACID transactional reliability and strict foreign key integrity:
1. `employees` — Staff accounts, hashed passwords, roles (`Admin` vs `Employee`).
2. `categories` — Product groupings (`Electronics`, `Groceries`, etc.).
3. `suppliers` — Wholesalers and vendor contacts.
4. `customers` — Customer CRM records (`name`, `phone`, `address`).
5. `products` — Items with `cost_price`, selling `price`, `qty`, `status`, `sku`, and `image_path` (FK -> categories, suppliers).
6. `purchases` — Supplier stock-in orders (FK -> suppliers, employees).
7. `purchase_items` — Itemized lines received in each purchase with `unit_cost` (FK -> purchases, products).
8. `sales` — Generated customer bills (FK -> employees, customers).
9. `sale_items` — Sold lines with `unit_cost` snapshot and selling `unit_price` (FK -> sales, products).
10. `sale_returns` — Refunded/returned items restoring inventory stock (FK -> sales, products, employees).
11. `settings` — Key-value system configuration (`shop_name`, `theme`, `currency`, `low_stock_limit`, etc.).
12. `activity_log` — Security audit trail tracking employee operations.

---

## How to Explain It in a Viva (Short Answers)

### 1. Why use a database transaction (`with db.transaction() as cur:`)?
> **Answer**: Saving a bill or purchase updates multiple tables at once (e.g. inserting the sale, decrementing product stock, inserting item lines). A database transaction ensures **atomicity** (all-or-nothing). If one step fails (like insufficient stock or a network glitch), MySQL automatically rolls back all changes, preventing corrupted or half-saved records.

### 2. Why snapshot `cost_price` into `sale_items.unit_cost` at the moment of sale?
> **Answer**: Wholesale purchase costs fluctuate over time. If we computed historical profit by joining the *current* product cost, past financial reports would retroactively change whenever a new shipment arrives. Storing `unit_cost` inside `sale_items` preserves an exact historical snapshot of true margin.

### 3. Why store settings in a database table rather than hard-coding in `config.py`?
> **Answer**: Hard-coded values in code require a developer to modify files and recompile the application. Storing configuration in a MySQL `settings` table allows store administrators to change the store name, contact number, currency symbol, and theme directly from the GUI, while `config.py` serves as a safe default fallback.

### 4. How does the customer auto-fill and auto-creation workflow work?
> **Answer**: In `billing.py`, typing 7+ digits into the contact field triggers a debounced `<KeyRelease>` query that fetches the existing customer's name. When the bill is saved, the transaction verifies if the customer exists; if new, it automatically registers them in the `customers` table and links their `customer_id` on the invoice.

### 5. Why restore stock and reactivate products upon a return?
> **Answer**: When a customer returns an item, the physical inventory re-enters the warehouse. The return transaction records the refund in `sale_returns` for accounting and runs `UPDATE products SET qty = qty + %s, status = 'Active'` so the restored stock is immediately available for sale again.

### 6. Why use parameterized queries (`%s`) instead of string formatting?
> **Answer**: String concatenation (`f"SELECT ... '{user_input}'"`) leaves the application vulnerable to SQL Injection attacks. Parameterized queries send SQL commands and user values through separate channels in MySQL protocol, ensuring typed text is strictly treated as literal data, never executable SQL commands.

### 7. Why hash passwords with PBKDF2-SHA256 and unique salts?
> **Answer**: Plaintext passwords in a database are catastrophic if leaked. PBKDF2 with 100,000 hashing rounds is computationally expensive, defeating brute-force attacks. Unique salts prevent rainbow-table precomputation, ensuring identical passwords generate completely different hashes.

### 8. How does OOP inheritance in `CrudPage` benefit the codebase?
> **Answer**: Instead of rewriting Create, Read, Update, Delete forms, search debouncing, and CSV exports across Employee, Supplier, Category, Product, and Customer pages, the base logic is implemented once in `CrudPage`. Child classes are declarative, defining only table bindings, form fields, and queries in ~30 lines.

### 9. What is the formula behind the Reorder Suggestions card?
> **Answer**: It calculates:
> Suggested reorder = the LARGER of  (Low-stock limit x 2 - current stock)  and  (average daily sales of the last 30 days x 14 days, rounded up).
> This balances immediate safety-stock replenishment with demand velocity during a 2-week supplier delivery lead time.

### 10. How do file paths work when packaged into a PyInstaller `.exe`?
> **Answer**: When frozen, read-only assets (logos, icons) are unpacked into a temporary runtime folder (`sys._MEIPASS`). Writable files (`db_config.json`, customer bills, backups, and product images) are directed to `%LOCALAPPDATA%\InventoryManager\`. The unified `get_path()` helper in `config.py` routes paths dynamically based on `sys.frozen`.

---

## Testing & Verification
Tests use a SEPARATE database called `ims_test_db` (they refuse to run on any database whose name has no "test" in it).
```bash
python tests/test_utils.py          # 5 unit tests  (no window, no MySQL needed)
python tests/functional_test.py     # 64 end-to-end checks on every v3 feature + the v2 -> v3 upgrade
python tests/take_screenshots.py    # screenshots of every page at 1920x1080 and 1280x720 -> screenshots/
```
Your MySQL login is read from `db_config.json` (the same file the app uses).

## Before you submit or upload
Delete `build/`, `dist/`, `*.spec`, `__pycache__/`, `screenshots/`, `backups/`, `bill/` and **`db_config.json`** (it contains your MySQL password). The included `.gitignore` already skips them.
