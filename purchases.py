"""
purchases.py  -  stock-in management (Admin only).
Allows receiving new inventory from suppliers. In ONE atomic transaction:
1. Inserts the purchase record and line items.
2. Increases products.qty.
3. Automatically sets products.status = 'Active'.
4. Updates products.cost_price to the latest received unit cost.
"""
from datetime import datetime
import customtkinter as ctk
from mysql.connector import Error

import settings
import theme
import utils
from db import db
from theme import DataTable, button, card, combo, entry, label


class PurchasesPage(ctk.CTkFrame):
    ADMIN_ONLY = True

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.items = []              # list of tuples: (product_id, product_name, qty, unit_cost, line_total)
        self.suppliers_map = {}      # supplier_name -> supplier_id
        self.products_map = {}       # product_name -> (product_id, current_cost)
        self.last_purchase_text = ""

        self.grid_columnconfigure(0, weight=5, uniform="p")
        self.grid_columnconfigure(1, weight=4, uniform="p")
        self.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        theme.page_header(head, "Purchases / Stock-In",
                          "Receive stock from suppliers, update cost prices, and increase inventory").pack(side="left")

        self.build_left()
        self.build_right()

    # ------------------------------------------------------------- Left Form
    def build_left(self):
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        # Header fields: Supplier & Reference Number
        top_box = card(left)
        top_box.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        top_box.grid_columnconfigure((0, 1), weight=1, uniform="hdr")

        label(top_box, "Supplier *", 12, "bold", muted=True).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 2))
        label(top_box, "Purchase Ref No. *", 12, "bold", muted=True).grid(row=0, column=1, sticky="w", padx=16, pady=(12, 2))

        self.sup_combo = combo(top_box, ["Select"])
        self.sup_combo.set("Select")
        self.sup_combo.grid(row=1, column=0, sticky="ew", padx=(16, 8), pady=(0, 10))
        self.ref_entry = entry(top_box, placeholder="PO-XXXX")
        self.ref_entry.grid(row=1, column=1, sticky="ew", padx=(8, 16), pady=(0, 10))

        # Item Picker: Product, Qty, Unit Cost
        label(top_box, "Add Product to Purchase", 13, "bold").grid(row=2, column=0, columnspan=2, sticky="w", padx=16, pady=(4, 2))
        
        pick_row = ctk.CTkFrame(top_box, fg_color="transparent")
        pick_row.grid(row=3, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 14))
        pick_row.grid_columnconfigure((0, 1), weight=1)

        # product name gets its OWN full-width row (long names were being cut off)
        self.prod_combo = combo(pick_row, ["Select"], command=self.on_product_pick)
        self.prod_combo.set("Select")
        self.prod_combo.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        self.qty_entry = entry(pick_row, placeholder="Qty", justify="center")
        self.qty_entry.insert(0, "1")
        self.qty_entry.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        self.cost_entry = entry(pick_row, placeholder="Unit Cost", justify="center")
        self.cost_entry.grid(row=1, column=1, sticky="ew", padx=6)
        button(pick_row, "Add Item", self.add_item, "primary", width=90).grid(row=1, column=2, padx=(6, 0))

        # Staging Cart Table
        cart_box = card(left)
        cart_box.grid(row=1, column=0, sticky="nsew")
        cart_box.grid_columnconfigure(0, weight=1)
        cart_box.grid_rowconfigure(1, weight=1)

        cbar = ctk.CTkFrame(cart_box, fg_color="transparent")
        cbar.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        label(cbar, "Purchase Items Staging", 15, "bold").pack(side="left")
        button(cbar, "Remove Item", self.remove_item, "danger", width=100, height=30).pack(side="right")

        self.items_table = DataTable(cart_box, [("ID", 50), ("Product", 180), ("Qty", 60), ("Unit Cost", 95), ("Total", 100)])
        self.items_table.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))

        # Bottom Action Bar
        act_box = ctk.CTkFrame(cart_box, fg_color="transparent")
        act_box.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))
        self.total_label = label(act_box, "Total: ৳ 0.00", 17, "bold", color=theme.SUCCESS)
        self.total_label.pack(side="left")
        button(act_box, "Clear Form", self.clear_form, "neutral", width=95).pack(side="right", padx=(8, 0))
        button(act_box, "Save Purchase", self.save_purchase, "success", width=130).pack(side="right")

    # ------------------------------------------------------------ Right Side
    def build_right(self):
        right = card(self)
        right.grid(row=1, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        right.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(right, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        label(top, "Purchase History", 15, "bold").pack(side="left")
        button(top, "Export CSV", self.export_csv, "neutral", width=100, height=32).pack(side="right")
        button(top, "Refresh", self.load_history, "neutral", width=80, height=32).pack(side="right", padx=6)

        self.history_table = DataTable(right, [("ID", 45), ("Ref No.", 130), ("Supplier", 120),
                                              ("Total", 95), ("Date", 130)], on_select=self.on_select_history)
        self.history_table.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

        # Monospace purchase invoice preview
        prev_box = ctk.CTkFrame(right, fg_color="transparent")
        prev_box.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        prev_box.grid_columnconfigure(0, weight=1)
        prev_box.grid_rowconfigure(1, weight=1)
        
        pbar = ctk.CTkFrame(prev_box, fg_color="transparent")
        pbar.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        label(pbar, "Purchase Order Preview", 13, "bold").pack(side="left")
        button(pbar, "Print PO", self.print_po, "primary", width=80, height=28).pack(side="right")

        self.preview_box = ctk.CTkTextbox(prev_box, font=ctk.CTkFont(family="Consolas", size=11),
                                          fg_color=theme.CARD_ALT, border_width=1, border_color=theme.BORDER)
        self.preview_box.grid(row=1, column=0, sticky="nsew")
        self.preview_box.insert("1.0", "Select a purchase from the history list to view details.")
        self.preview_box.configure(state="disabled")

    # ------------------------------------------------------------- Lifecycle
    def on_show(self):
        self.refresh_lookups()
        self.load_history()
        if not self.ref_entry.get().strip():
            self.generate_ref()

    def generate_ref(self):
        self.ref_entry.delete(0, "end")
        self.ref_entry.insert(0, f"PO-{datetime.now():%Y%m%d-%H%M%S}")

    def refresh_lookups(self):
        try:
            sups = db.fetch_all("SELECT id, name FROM suppliers ORDER BY name")
            self.suppliers_map = {name: sid for sid, name in sups}
            self.sup_combo.configure(values=["Select"] + list(self.suppliers_map))

            prods = db.fetch_all("SELECT id, name, cost_price FROM products ORDER BY name")
            self.products_map = {name: (pid, float(cost)) for pid, name, cost in prods}
            self.prod_combo.configure(values=["Select"] + list(self.products_map))
        except Error as e:
            utils.error(self, utils.friendly_db_error(e))

    def on_product_pick(self, chosen):
        if chosen in self.products_map:
            _pid, cost = self.products_map[chosen]
            self.cost_entry.delete(0, "end")
            self.cost_entry.insert(0, f"{cost:.2f}")

    def add_item(self):
        chosen = self.prod_combo.get()
        if chosen not in self.products_map:
            return utils.error(self, "Please select a product.")
        pid, _ = self.products_map[chosen]
        qty_str = self.qty_entry.get().strip()
        cost_str = self.cost_entry.get().strip()
        try:
            qty = utils.validate("int", qty_str, "Quantity")
            cost = utils.validate("float", cost_str, "Unit Cost")
            if qty <= 0:
                return utils.error(self, "Quantity must be at least 1.")
        except ValueError as e:
            return utils.error(self, str(e))

        line_total = round(qty * cost, 2)
        # Update if already in list
        for i, item in enumerate(self.items):
            if item[0] == pid:
                self.items[i] = (pid, chosen, qty, cost, line_total)
                self.refresh_items()
                return None
        self.items.append((pid, chosen, qty, cost, line_total))
        self.refresh_items()
        return None

    def remove_item(self):
        row = self.items_table.selected_row()
        if not row:
            return utils.error(self, "Select an item to remove.")
        self.items = [it for it in self.items if it[0] != row[0]]
        self.refresh_items()
        return None

    def refresh_items(self):
        self.items_table.load(self.items)
        sub = sum(it[4] for it in self.items)
        self.total_label.configure(text=f"Total: {utils.money(sub)}")

    def clear_form(self):
        self.items.clear()
        self.refresh_items()
        self.sup_combo.set("Select")
        self.prod_combo.set("Select")
        self.qty_entry.delete(0, "end")
        self.qty_entry.insert(0, "1")
        self.cost_entry.delete(0, "end")
        self.generate_ref()

    # ------------------------------------------------------------- Save Action
    def save_purchase(self):
        sup_name = self.sup_combo.get()
        if sup_name not in self.suppliers_map:
            return utils.error(self, "Please select a valid supplier.")
        ref_no = self.ref_entry.get().strip()
        if not ref_no:
            return utils.error(self, "Purchase Reference Number is required.")
        if not self.items:
            return utils.error(self, "Please add at least one product to the purchase order.")

        sup_id = self.suppliers_map[sup_name]
        total = sum(it[4] for it in self.items)

        try:
            with db.transaction() as cur:
                # 1. Insert purchase header
                cur.execute(
                    "INSERT INTO purchases (ref_no, supplier_id, total, received_by) VALUES (%s, %s, %s, %s)",
                    (ref_no, sup_id, total, utils.session.get("id"))
                )
                purchase_id = cur.lastrowid
                # 2. Insert line items & update stock + latest cost price
                for pid, _pname, qty, cost, line in self.items:
                    cur.execute(
                        "INSERT INTO purchase_items (purchase_id, product_id, qty, unit_cost, line_total) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (purchase_id, pid, qty, cost, line)
                    )
                    cur.execute(
                        "UPDATE products SET qty = qty + %s, cost_price = %s, status = 'Active' WHERE id = %s",
                        (qty, cost, pid)
                    )
        except Error as e:
            return utils.error(self, utils.friendly_db_error(e))

        utils.log_activity(f"Recorded purchase {ref_no} ({utils.money(total)})")
        theme.toast(self, f"Purchase {ref_no} saved successfully")
        self.clear_form()
        self.load_history()
        self.refresh_lookups()
        return None

    # ---------------------------------------------------------- History & PO
    def load_history(self):
        try:
            rows = db.fetch_all(
                "SELECT p.id, p.ref_no, s.name, p.total, p.created_at "
                "FROM purchases p JOIN suppliers s ON s.id = p.supplier_id ORDER BY p.id DESC"
            )
            self.history_table.load(rows)
        except Error as e:
            utils.error(self, utils.friendly_db_error(e))

    def on_select_history(self, row):
        pid, ref, sname, total, when = row
        try:
            items = db.fetch_all(
                "SELECT pr.name, pi.qty, pi.unit_cost, pi.line_total "
                "FROM purchase_items pi JOIN products pr ON pr.id = pi.product_id WHERE pi.purchase_id = %s",
                (pid,)
            )
        except Error as e:
            return utils.error(self, utils.friendly_db_error(e))

        w = 44
        cur = settings.get_currency()
        out = [settings.get_shop_name().center(w), "STOCK PURCHASE RECEIPT".center(w), "=" * w,
               f"Ref No   : {ref}", f"Supplier : {sname}", f"Date     : {str(when)[:19]}",
               "-" * w, f"{'Product':<20}{'Qty':>6}{'Cost':>8}{'Total':>10}", "-" * w]
        for name, q, c, lt in items:
            out.append(f"{str(name)[:19]:<20}{q:>6}{float(c):>8.2f}{float(lt):>10.2f}")
        out += ["=" * w, f"{'TOTAL PURCHASE':<28}{cur} {float(total):>13,.2f}", "=" * w]
        
        self.last_purchase_text = "\n".join(out)
        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", "end")
        self.preview_box.insert("1.0", self.last_purchase_text)
        self.preview_box.configure(state="disabled")
        return None

    def print_po(self):
        if not self.last_purchase_text:
            return utils.error(self, "Select a purchase record first.")
        path = utils.save_bill_file("PURCHASE_PO", self.last_purchase_text)
        utils.print_file(self, path)
        return None

    def export_csv(self):
        headings = [h for h, _ in self.history_table.columns]
        utils.export_csv(self, headings, self.history_table.current_rows(), "purchases_history.csv")

