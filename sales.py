"""
Sales screen - every bill ever generated, searchable, with live bill preview,
item return/refund processing, Windows printing, and CSV export.
"""
import customtkinter as ctk
from mysql.connector import Error

import theme
import utils
from db import db
from theme import DataTable, button, card, combo, entry, label

SQL = ("SELECT s.id, s.invoice_no, s.created_at, s.customer_name, s.customer_phone, s.total, COALESCE(e.name, '-') "
       "FROM sales s LEFT JOIN employees e ON e.id = s.sold_by")


class SalesPage(ctk.CTkFrame):
    ADMIN_ONLY = False

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.bill_path = None
        self._job = None
        self.selected_sale_id = None
        self.selected_invoice = None

        self.grid_columnconfigure(0, weight=5, uniform="s")
        self.grid_columnconfigure(1, weight=3, uniform="s")
        self.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        head.grid_columnconfigure(0, weight=1)
        theme.page_header(head, "Sales", "Every customer bill, with search, live preview, and item refunds").grid(row=0, column=0, sticky="w")
        bar = ctk.CTkFrame(head, fg_color="transparent")
        bar.grid(row=0, column=1, sticky="e")
        self.search = entry(bar, "Search invoice no. or customer...", width=280)
        self.search.pack(side="left")
        self.search.bind("<KeyRelease>", self.search_later)
        button(bar, "Clear", self.clear_search, "neutral", 70).pack(side="left", padx=(8, 0))

        # Left: Bills Table
        left = card(self)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(left, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))
        label(top, "All Bills", 16, "bold").pack(side="left")
        self.summary = label(top, "", 12, muted=True)
        self.summary.pack(side="left", padx=12)
        button(top, "Export CSV", self.export, "neutral", 110, 32).pack(side="right")
        self.table = DataTable(left, [("ID", 50), ("Invoice No.", 160), ("Date", 160), ("Customer", 140),
                                      ("Phone", 110), ("Total", 100), ("Cashier", 120)], on_select=self.on_select)
        self.table.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))

        # Right: Bill Preview & Actions
        right = card(self)
        right.grid(row=1, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        top2 = ctk.CTkFrame(right, fg_color="transparent")
        top2.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))
        label(top2, "Bill Preview", 16, "bold").pack(side="left")
        button(top2, "Print", self.print_bill, "primary", 75, 32).pack(side="right")
        button(top2, "Return Item", self.open_return_dialog, "warning", 95, 32).pack(side="right", padx=6)

        self.box = ctk.CTkTextbox(right, font=ctk.CTkFont(family="Consolas", size=12), fg_color=theme.CARD_ALT, border_width=1,
                                  border_color=theme.BORDER, text_color=theme.TEXT, wrap="none")
        self.box.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        picture = theme.load_image("sales.jpg", 380, 260)
        self.placeholder = ctk.CTkLabel(right, text="Select a bill to preview it", image=picture, compound="top",
                                        font=theme.font(13), text_color=theme.MUTED)
        self.placeholder.grid(row=1, column=0)
        self.box.grid_remove()

    def on_show(self):
        self.refresh()

    def refresh(self):
        sql, params = SQL, []
        text = self.search.get().strip()
        if text:
            sql += " WHERE s.invoice_no LIKE %s OR s.customer_name LIKE %s"
            params = [f"%{text}%"] * 2
        try:
            rows = db.fetch_all(f"{sql} ORDER BY s.id DESC", params)
        except Error as e:
            return utils.error(self, utils.friendly_db_error(e))
        self.table.load(rows)
        revenue = sum(float(r[5]) for r in rows)
        self.summary.configure(text=f"{len(rows)} bill(s)   -   {utils.money(revenue)}")
        return None

    def search_later(self, _event=None):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(250, self.refresh)

    def clear_search(self):
        self.search.delete(0, "end")
        self.refresh()

    def on_select(self, row):
        sale_id, invoice, when, customer, phone, total, cashier = row
        self.selected_sale_id = sale_id
        self.selected_invoice = invoice
        try:
            sale = db.fetch_one("SELECT subtotal, discount_percent FROM sales WHERE id = %s", (sale_id,))
            items = db.fetch_all("SELECT product_name, qty, unit_price, line_total FROM sale_items WHERE sale_id = %s", (sale_id,))
            returns = db.fetch_all(
                "SELECT COALESCE(p.name, 'Product'), sr.qty, sr.refund_amount "
                "FROM sale_returns sr LEFT JOIN products p ON p.id = sr.product_id WHERE sr.sale_id = %s",
                (sale_id,)
            )
        except Error as e:
            return utils.error(self, utils.friendly_db_error(e))

        subtotal, pct = float(sale[0]), float(sale[1])
        text = utils.build_bill(invoice, when, customer, phone, items, subtotal, pct,
                                subtotal - float(total), total, cashier, returns=returns)
        self.bill_path = utils.save_bill_file(invoice, text)
        self.placeholder.grid_remove()
        self.box.grid()
        self.box.configure(state="normal")
        self.box.delete("1.0", "end")
        self.box.insert("1.0", text)
        self.box.configure(state="disabled")
        return None

    def open_return_dialog(self):
        if not self.selected_sale_id:
            return utils.error(self, "Please select a bill from the table first.")
        ReturnItemDialog(self, self.selected_sale_id, self.selected_invoice, self.on_return_success)

    def on_return_success(self):
        row = self.table.selected_row()
        if row:
            self.on_select(row)
        self.refresh()

    def print_bill(self):
        if not self.bill_path:
            return utils.error(self, "Select a bill first.")
        utils.print_file(self, self.bill_path)
        return None

    def export(self):
        utils.export_csv(self, [h for h, _ in self.table.columns], self.table.current_rows(), "sales.csv")


# ------------------------------------------------------------- Return Dialog
class ReturnItemDialog(ctk.CTkToplevel):
    """Dialog to return an item from a selected bill and restore stock."""
    def __init__(self, parent, sale_id, invoice_no, on_success):
        super().__init__(parent)
        self.sale_id = sale_id
        self.invoice_no = invoice_no
        self.on_success = on_success

        self.title(f"Return Item - {invoice_no}")
        self.geometry("450x480")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG)
        self.transient(parent.winfo_toplevel())
        self.after(150, self.lift)

        label(self, "Return Item from Bill", 18, "bold").pack(anchor="w", padx=24, pady=(20, 2))
        label(self, f"Invoice: {invoice_no}", 13, muted=True).pack(anchor="w", padx=24, pady=(0, 14))

        # Fetch sold items and calculate returnable balance.
        # The customer paid the DISCOUNTED price, so that is the most we can refund per unit.
        self.items_data = {}
        disc = db.fetch_one("SELECT discount_percent FROM sales WHERE id = %s", (sale_id,))
        disc_pct = float(disc[0]) if disc else 0.0
        rows = db.fetch_all(
            "SELECT si.product_id, si.product_name, si.qty, si.unit_price, "
            "COALESCE((SELECT SUM(sr.qty) FROM sale_returns sr WHERE sr.sale_id = si.sale_id AND sr.product_id = si.product_id), 0) "
            "FROM sale_items si WHERE si.sale_id = %s",
            (sale_id,)
        )
        for pid, name, sold_q, price, ret_q in rows:
            if pid is None:
                continue                       # product was deleted later - nothing to put back in stock
            net_avail = int(sold_q) - int(ret_q)
            paid_price = round(float(price) * (1 - disc_pct / 100), 2)
            self.items_data[name] = {"pid": pid, "price": paid_price, "max_qty": net_avail, "sold": sold_q, "ret": ret_q}

        label(self, "Select Product Line *", 12, "bold", muted=True).pack(anchor="w", padx=24)
        self.item_combo = combo(self, ["Select"] + list(self.items_data.keys()), command=self.on_item_select)
        self.item_combo.pack(fill="x", padx=24, pady=(2, 10))

        self.info_lbl = label(self, "Choose an item to see returnable quantity", 12, muted=True)
        self.info_lbl.pack(anchor="w", padx=24, pady=(0, 10))

        label(self, "Return Quantity *", 12, "bold", muted=True).pack(anchor="w", padx=24)
        self.qty_entry = entry(self, placeholder="Qty")
        self.qty_entry.pack(fill="x", padx=24, pady=(2, 10))
        self.qty_entry.bind("<KeyRelease>", self.on_qty_change)

        label(self, "Refund Amount *", 12, "bold", muted=True).pack(anchor="w", padx=24)
        self.amount_entry = entry(self, placeholder="0.00")
        self.amount_entry.pack(fill="x", padx=24, pady=(2, 10))

        label(self, "Reason for Return *", 12, "bold", muted=True).pack(anchor="w", padx=24)
        self.reason_entry = entry(self, placeholder="Defective, wrong item, customer request, etc.")
        self.reason_entry.pack(fill="x", padx=24, pady=(2, 16))

        row_b = ctk.CTkFrame(self, fg_color="transparent")
        row_b.pack(fill="x", padx=24, pady=8)
        button(row_b, "Confirm Return", self.process_return, "danger", width=140).pack(side="left")
        button(row_b, "Cancel", self.destroy, "neutral", width=90).pack(side="right")

    def on_item_select(self, item_name):
        info = self.items_data.get(item_name)
        if not info:
            return
        self.info_lbl.configure(
            text=f"Sold: {info['sold']} | Already Returned: {info['ret']} | Available to Return: {info['max_qty']}"
        )
        self.qty_entry.delete(0, "end")
        self.qty_entry.insert(0, str(min(1, info['max_qty'])))
        self.on_qty_change()

    def on_qty_change(self, _event=None):
        item_name = self.item_combo.get()
        info = self.items_data.get(item_name)
        if not info:
            return
        text = self.qty_entry.get().strip()
        if text.isdigit():
            q = int(text)
            self.amount_entry.delete(0, "end")
            self.amount_entry.insert(0, f"{round(q * info['price'], 2):.2f}")

    def process_return(self):
        item_name = self.item_combo.get()
        info = self.items_data.get(item_name)
        if not info:
            return utils.error(self, "Please select an item line.")
        if info['max_qty'] <= 0:
            return utils.error(self, "All units of this product have already been returned.")

        try:
            qty = utils.validate("int", self.qty_entry.get().strip(), "Return Quantity")
            refund = utils.validate("float", self.amount_entry.get().strip(), "Refund Amount")
            if qty <= 0:
                return utils.error(self, "Return quantity must be at least 1.")
            if qty > info['max_qty']:
                return utils.error(self, f"Cannot return {qty}. Maximum returnable is {info['max_qty']}.")
            if refund > round(qty * info['price'], 2) + 0.01:
                return utils.error(self, f"Refund cannot be more than what the customer paid ({utils.money(qty * info['price'])}).")
        except ValueError as e:
            return utils.error(self, str(e))

        reason = self.reason_entry.get().strip()
        if not reason:
            return utils.error(self, "Please provide a reason for the return.")

        # Atomic transaction: record return and restore stock
        try:
            with db.transaction() as cur:
                cur.execute(
                    "INSERT INTO sale_returns (sale_id, product_id, qty, refund_amount, reason, created_by) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (self.sale_id, info['pid'], qty, refund, reason, utils.session.get("id"))
                )
                if info['pid'] is not None:
                    # Restore product quantity and re-activate if inactive
                    cur.execute(
                        "UPDATE products SET qty = qty + %s, status = 'Active' WHERE id = %s",
                        (qty, info['pid'])
                    )
        except Error as e:
            return utils.error(self, utils.friendly_db_error(e))

        utils.log_activity(f"Refund for {self.invoice_no}: {qty}x {item_name} ({utils.money(refund)})")
        theme.toast(self.master, f"Processed refund for {qty}x {item_name}")
        self.destroy()
        self.on_success()
        return None
