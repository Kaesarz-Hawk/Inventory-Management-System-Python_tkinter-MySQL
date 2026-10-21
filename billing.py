"""
Billing screen - pick products, scan SKU/barcode, fill the cart, and print bills.
Saving a bill is ONE atomic database transaction:
  insert sale -> create customer if new -> snapshot unit_cost -> decrement stock -> insert items.
If anything fails, everything is rolled back (no partial bills or corrupted stock).
"""
import re
from datetime import datetime
import customtkinter as ctk
from mysql.connector import Error

import settings
import theme
import utils
from db import db
from theme import DataTable, button, card, entry, label


class BillingPage(ctk.CTkFrame):
    ADMIN_ONLY = False

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.cart = {}                 # product id -> {"name", "price", "qty", "stock"}
        self.last_bill_path = None
        self.grid_columnconfigure(0, weight=5, uniform="col")
        self.grid_columnconfigure(1, weight=4, uniform="col")
        self.grid_rowconfigure(1, weight=1)

        theme.page_header(self, "Billing / Point of Sale",
                          "Type or scan SKU + Enter to add item, or double-click product list").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))
        self.build_left()
        self.build_right()
        self.recalc()

    # ------------------------------------------------------------ Left Column
    def build_left(self):
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=3)
        left.grid_rowconfigure(1, weight=2)

        # Products list card
        prod = card(left)
        prod.grid(row=0, column=0, sticky="nsew", pady=(0, 14))
        prod.grid_columnconfigure(0, weight=1)
        prod.grid_rowconfigure(1, weight=1)

        bar = ctk.CTkFrame(prod, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        label(bar, "Available Products", 16, "bold").pack(side="left")
        button(bar, "Show All", self.clear_search, "neutral", 85, 32).pack(side="right")
        self.search = entry(bar, "Search product or scan SKU...", width=250)
        self.search.pack(side="right", padx=8)
        self.search.bind("<KeyRelease>", lambda e: self.load_products())
        self.search.bind("<Return>", self.on_search_enter)

        self.prod_table = DataTable(
            prod,
            [("ID", 50), ("Product", 190), ("Category", 110), ("Price", 85), ("Stock", 75), ("SKU", 85)],
            on_select=self.on_pick, on_double=self.add_to_cart
        )
        self.prod_table.grid(row=1, column=0, sticky="nsew", padx=12)

        # Product selection / thumbnail / quantity bar
        pick = ctk.CTkFrame(prod, fg_color="transparent")
        pick.grid(row=2, column=0, sticky="ew", padx=16, pady=10)
        self.pick_img_label = label(pick, "")
        self.pick_img_label.pack(side="left", padx=(0, 8))
        self.pick_label = label(pick, "Select a product from the list", 13, "bold")
        self.pick_label.pack(side="left")
        button(pick, "Add | Update", self.add_to_cart, "success", 110).pack(side="right")
        self.qty = entry(pick, "Qty", width=65, justify="center")
        self.qty.pack(side="right", padx=8)
        self.qty.insert(0, "1")
        self.qty.bind("<Return>", lambda e: self.add_to_cart())

        # Cart card
        cart = card(left)
        cart.grid(row=1, column=0, sticky="nsew")
        cart.grid_columnconfigure(0, weight=1)
        cart.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(cart, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        self.cart_title = label(top, "Cart", 16, "bold")
        self.cart_title.pack(side="left")
        button(top, "Remove Selected", self.remove_selected, "danger", 130, 32).pack(side="right")

        self.cart_table = DataTable(
            cart,
            [("ID", 50), ("Product", 210), ("Price", 90), ("Qty", 65), ("Total", 100)],
            on_select=self.on_cart_pick
        )
        self.cart_table.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

    # ----------------------------------------------------------- Right Column
    def build_right(self):
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=1, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        # Customer Details
        cust = card(right)
        cust.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        cust.grid_columnconfigure((0, 1), weight=1, uniform="c")
        label(cust, "Customer Details", 16, "bold").grid(row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(14, 4))
        label(cust, "Contact No.", 12, "bold", muted=True).grid(row=1, column=0, sticky="w", padx=18)
        label(cust, "Name *", 12, "bold", muted=True).grid(row=1, column=1, sticky="w", padx=8)

        self.cust_phone = entry(cust, "01XXXXXXXXX")
        self.cust_phone.grid(row=2, column=0, sticky="ew", padx=(18, 8), pady=(2, 16))
        self.cust_phone.bind("<KeyRelease>", self.on_phone_change)
        self.cust_name = entry(cust, "Customer name")
        self.cust_name.grid(row=2, column=1, sticky="ew", padx=(8, 18), pady=(2, 16))

        # Totals and Actions
        tot = card(right)
        tot.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        tot.grid_columnconfigure((0, 1, 2), weight=1, uniform="t")
        self.lbl_sub = self.stat(tot, 0, "Bill Amount", theme.ACCENT)
        self.lbl_disc = self.stat(tot, 1, "Discount", theme.SUCCESS)
        self.lbl_net = self.stat(tot, 2, "Net Pay", theme.INFO)

        row = ctk.CTkFrame(tot, fg_color="transparent")
        row.grid(row=1, column=0, columnspan=3, sticky="ew", padx=14, pady=(0, 6))
        label(row, "Discount %", 12, "bold", muted=True).pack(side="left", padx=(4, 8))
        self.discount = entry(row, "0", width=65, justify="center")
        self.discount.pack(side="left")
        self.discount.insert(0, str(settings.get_default_discount()))
        self.discount.bind("<KeyRelease>", lambda e: self.recalc())
        button(row, "Calculator", self.open_calculator, "warning", 100).pack(side="right")

        acts = ctk.CTkFrame(tot, fg_color="transparent")
        acts.grid(row=2, column=0, columnspan=3, sticky="ew", padx=14, pady=(0, 14))
        acts.grid_columnconfigure(0, weight=2)
        acts.grid_columnconfigure((1, 2), weight=1)
        button(acts, "Generate Bill", self.generate_bill, "success", 10, 40).grid(row=0, column=0, sticky="ew", padx=4)
        button(acts, "Print", self.print_bill, "primary", 10, 40).grid(row=0, column=1, sticky="ew", padx=4)
        button(acts, "Clear All", self.clear_all, "neutral", 10, 40).grid(row=0, column=2, sticky="ew", padx=4)

        # Receipt preview
        bill = card(right)
        bill.grid(row=2, column=0, sticky="nsew")
        bill.grid_columnconfigure(0, weight=1)
        bill.grid_rowconfigure(1, weight=1)
        label(bill, "Customer Bill Area", 16, "bold").grid(row=0, column=0, sticky="w", padx=18, pady=(14, 6))
        self.bill_box = ctk.CTkTextbox(bill, font=ctk.CTkFont(family="Consolas", size=12), fg_color=theme.CARD_ALT,
                                       border_width=1, border_color=theme.BORDER, text_color=theme.TEXT, wrap="none")
        self.bill_box.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self.show_bill("Your generated bill will appear here.")

    def stat(self, parent, col, title, color):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=0, column=col, sticky="ew", padx=14, pady=(14, 8))
        label(box, title, 12, muted=True).pack(anchor="w")
        val = label(box, "", 20, "bold", color=color)
        val.pack(anchor="w")
        return val

    # ------------------------------------------------------------- Products & SKU
    def on_show(self):
        self.load_products()

    def load_products(self):
        text = f"%{self.search.get().strip()}%"
        try:
            rows = db.fetch_all(
                "SELECT p.id, p.name, c.name, p.price, p.qty, COALESCE(p.sku, '-'), p.image_path "
                "FROM products p JOIN categories c ON c.id = p.category_id "
                "WHERE p.status = 'Active' AND (p.name LIKE %s OR p.sku LIKE %s) ORDER BY p.name",
                (text, text)
            )
        except Error as e:
            return utils.error(self, utils.friendly_db_error(e))
        
        # Display id, name, cat, price, qty, sku in table; image_path is at index 6
        table_rows = [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows]
        limit = settings.get_low_stock_limit()
        self.prod_table.load(table_rows, lambda r: "low" if int(r[4]) <= limit else None)
        self._raw_products = {r[0]: r for r in rows}
        return None

    def on_search_enter(self, _event=None):
        """SKU Barcode Scan: Pressing Enter on a SKU match instantly adds 1 unit to cart."""
        text = self.search.get().strip()
        if not text:
            return
        row = db.fetch_one(
            "SELECT id, name, price, qty, image_path FROM products WHERE sku = %s AND status = 'Active'",
            (text,)
        )
        if row:
            pid, name, price, stock, _img = row
            curr = self.cart.get(pid, {}).get("qty", 0)
            if curr + 1 > stock:
                utils.error(self, f"Only {stock} items in stock for '{name}'.")
                return
            self.cart[pid] = {"name": name, "price": float(price), "qty": curr + 1, "stock": stock}
            self.refresh_cart()
            self.search.delete(0, "end")
            self.load_products()
            theme.toast(self, f"Added 1x {name}")
        else:
            self.load_products()

    def clear_search(self):
        self.search.delete(0, "end")
        self.load_products()

    def on_pick(self, row):
        raw = getattr(self, "_raw_products", {}).get(row[0])
        img_path = raw[6] if raw else None
        if img_path:
            pic = theme.load_image(img_path, 40, 40)
            theme.set_label_image(self.pick_img_label, pic)
        else:
            theme.set_label_image(self.pick_img_label, None)

        self.pick_label.configure(text=f"{row[1]}   -   {utils.money(row[3])}   ({row[4]} in stock)")
        self.qty.delete(0, "end")
        self.qty.insert(0, str(self.cart[row[0]]["qty"]) if row[0] in self.cart else "1")

    def on_cart_pick(self, row):
        pass

    def on_phone_change(self, _event=None):
        """Auto-fill customer name if the phone number already exists."""
        phone = re.sub(r"[\s-]", "", self.cust_phone.get().strip())
        if len(phone) >= 7:
            row = db.fetch_one("SELECT name FROM customers WHERE phone = %s", (phone,))
            if row:
                self.cust_name.delete(0, "end")
                self.cust_name.insert(0, row[0])

    # ----------------------------------------------------------------- Cart
    def add_to_cart(self):
        row = self.prod_table.selected_row()
        if not row:
            return utils.error(self, "Select a product from the list first.")
        pid, name, _cat, price, stock, _sku = row
        text = self.qty.get().strip()
        if not text.isdigit():
            return utils.error(self, "Quantity must be a whole number (0 removes the product).")
        qty = int(text)
        if qty == 0:
            self.cart.pop(pid, None)
        elif qty > stock:
            return utils.error(self, f"Only {stock} of '{name}' are in stock.")
        else:
            self.cart[pid] = {"name": name, "price": float(price), "qty": qty, "stock": stock}
        self.refresh_cart()
        return None

    def remove_selected(self):
        row = self.cart_table.selected_row()
        if not row:
            return utils.error(self, "Select an item in the cart first.")
        self.cart.pop(row[0], None)
        self.refresh_cart()
        return None

    def refresh_cart(self):
        rows = [(pid, c["name"], c["price"], c["qty"], c["price"] * c["qty"]) for pid, c in self.cart.items()]
        self.cart_table.load(rows)
        self.cart_title.configure(text=f"Cart   -   {len(rows)} product(s)")
        self.recalc()

    # --------------------------------------------------------------- Totals
    def discount_value(self):
        text = self.discount.get().strip() or "0"
        try:
            pct = float(text)
        except ValueError:
            return None
        return pct if 0 <= pct <= 100 else None

    def totals(self):
        subtotal = sum(c["price"] * c["qty"] for c in self.cart.values())
        pct = self.discount_value() or 0
        disc = round(subtotal * pct / 100, 2)
        return subtotal, pct, disc, round(subtotal - disc, 2)

    def recalc(self):
        subtotal, pct, disc, net = self.totals()
        self.lbl_sub.configure(text=utils.money(subtotal))
        self.lbl_disc.configure(text=f"{utils.money(disc)}  ({pct:g}%)")
        self.lbl_net.configure(text=utils.money(net))

    # ------------------------------------------------------------- Generate Bill
    def generate_bill(self):
        name, phone = self.cust_name.get().strip(), self.cust_phone.get().strip()
        if not name:
            return utils.error(self, "Customer name is required.")
        if not self.cart:
            return utils.error(self, "The cart is empty. Add at least one product.")
        if self.discount_value() is None:
            return utils.error(self, "Discount must be a number between 0 and 100.")
        try:
            if phone:
                phone = utils.validate("phone", phone, "Contact No.")
        except ValueError as e:
            return utils.error(self, str(e))

        subtotal, pct, disc, net = self.totals()
        when = datetime.now()
        invoice = f"INV-{when:%Y%m%d-%H%M%S}"
        items = []

        try:
            with db.transaction() as cur:
                # 1. Customer linkage or auto-creation
                customer_id = None
                if phone:
                    cur.execute("SELECT id FROM customers WHERE phone = %s", (phone,))
                    crow = cur.fetchone()
                    if crow:
                        customer_id = crow[0]
                    else:
                        cur.execute("INSERT INTO customers (name, phone) VALUES (%s, %s)", (name, phone))
                        customer_id = cur.lastrowid

                # 2. Insert into sales
                cur.execute(
                    "INSERT INTO sales (invoice_no, customer_id, customer_name, customer_phone, subtotal, "
                    "discount_percent, total, sold_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (invoice, customer_id, name, phone or None, subtotal, pct, net, utils.session.get("id"))
                )
                sale_id = cur.lastrowid

                # 3. Insert sale items with cost price snapshot & update stock
                for pid, c in self.cart.items():
                    # Concurrency check: stock must be >= ordered qty
                    cur.execute("UPDATE products SET qty = qty - %s WHERE id = %s AND qty >= %s", (c["qty"], pid, c["qty"]))
                    if cur.rowcount == 0:
                        raise ValueError(f"Not enough stock left for '{c['name']}'. Refresh and try again.")

                    # Deactivate if stock depleted
                    cur.execute("UPDATE products SET status = 'Inactive' WHERE id = %s AND qty = 0", (pid,))

                    # Snapshot the product's cost_price at this moment
                    cur.execute("SELECT cost_price FROM products WHERE id = %s", (pid,))
                    cp_row = cur.fetchone()
                    unit_cost = float(cp_row[0]) if cp_row else 0.0

                    line = c["price"] * c["qty"]
                    cur.execute(
                        "INSERT INTO sale_items (sale_id, product_id, product_name, qty, unit_cost, unit_price, line_total) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (sale_id, pid, c["name"], c["qty"], unit_cost, c["price"], line)
                    )
                    items.append((c["name"], c["qty"], c["price"], line))
        except ValueError as e:
            self.load_products()
            return utils.error(self, str(e))
        except Error as e:
            return utils.error(self, utils.friendly_db_error(e))

        text = utils.build_bill(invoice, when, name, phone, items, subtotal, pct, disc, net, utils.session.get("name", ""))
        self.last_bill_path = utils.save_bill_file(invoice, text)
        self.show_bill(text)
        utils.log_activity(f"Generated bill {invoice} ({utils.money(net)})")
        self.cart.clear()
        self.refresh_cart()
        self.load_products()
        self.cust_name.delete(0, "end")
        self.cust_phone.delete(0, "end")
        theme.toast(self, f"Bill {invoice} saved")
        return None

    def show_bill(self, text):
        self.bill_box.configure(state="normal")
        self.bill_box.delete("1.0", "end")
        self.bill_box.insert("1.0", text)
        self.bill_box.configure(state="disabled")

    def print_bill(self):
        if not self.last_bill_path:
            return utils.error(self, "Generate a bill first, then print it.")
        utils.print_file(self, self.last_bill_path)
        return None

    def clear_all(self):
        self.cart.clear()
        self.refresh_cart()
        self.cust_name.delete(0, "end")
        self.cust_phone.delete(0, "end")
        self.discount.delete(0, "end")
        self.discount.insert(0, str(settings.get_default_discount()))
        self.recalc()
        self.show_bill("Your generated bill will appear here.")
        self.load_products()

    # ----------------------------------------------------------- Calculator
    def open_calculator(self):
        Calculator(self)


class Calculator(ctk.CTkToplevel):
    """Small pop-up calculator with buttons."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Calculator")
        self.geometry("300x400")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG)
        self.after(150, self.lift)
        self.expr = ""
        self.screen = ctk.CTkEntry(self, height=56, font=theme.font(24, "bold"), justify="right", state="readonly",
                                   fg_color=theme.CARD, border_color=theme.BORDER, text_color=theme.TEXT)
        self.screen.pack(fill="x", padx=14, pady=14)
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        keys = ["7", "8", "9", "/", "4", "5", "6", "*", "1", "2", "3", "-", "0", ".", "C", "+"]
        for i, key in enumerate(keys):
            kind = "danger" if key == "C" else "primary" if key in "/*-+" else "neutral"
            button(grid, key, lambda k=key: self.press(k), kind, 60, 52).grid(row=i // 4, column=i % 4, padx=4, pady=4, sticky="nsew")
        button(grid, "=", lambda: self.press("="), "success", 60, 52).grid(row=4, column=0, columnspan=4, padx=4, pady=4, sticky="nsew")
        for c in range(4):
            grid.grid_columnconfigure(c, weight=1)

    def press(self, key):
        if key == "C":
            self.expr = ""
        elif key == "=":
            try:
                self.expr = f"{eval(self.expr, {'__builtins__': {}}):g}"
            except Exception:
                self.expr = "Error"
        else:
            self.expr = "" if self.expr == "Error" else self.expr
            self.expr += key
        self.screen.configure(state="normal")
        self.screen.delete(0, "end")
        self.screen.insert(0, self.expr)
        self.screen.configure(state="readonly")
