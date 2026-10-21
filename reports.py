"""
reports.py  -  executive business intelligence and reporting (Admin only).
Calculates true profit (Revenue - Cost of Goods Sold - Returns) across custom date ranges.
Features interactive Tkinter Canvas charts (daily trend, top 5 products, category distribution)
and an itemized sales performance table with CSV export.
"""
from datetime import date, timedelta
import math
import tkinter as tk
import tkinter.font as tkfont
import customtkinter as ctk
from mysql.connector import Error

import theme
import utils
from db import db
from theme import DataTable, StatCard, button, card, entry, label


class ReportsPage(ctk.CTkFrame):
    ADMIN_ONLY = True

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.daily_data = []      # [(date_str, revenue, profit)]
        self.top_products = []    # [(name, revenue)]
        self.category_sales = []  # [(cat_name, revenue)]

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Header and Date Filter
        self.build_filter_bar()
        self.build_kpi_cards()
        self.build_charts_section()
        self.build_table_section()

    # ------------------------------------------------------------- Filter Bar
    def build_filter_bar(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        head.grid_columnconfigure(0, weight=1)
        theme.page_header(head, "Analytics & Reports", "Financial KPIs, true profit margins, and sales trends").grid(row=0, column=0, sticky="w")

        bar = ctk.CTkFrame(head, fg_color="transparent")
        bar.grid(row=0, column=1, sticky="e")

        today_str = date.today().strftime("%Y-%m-%d")
        month_start = date.today().replace(day=1).strftime("%Y-%m-%d")

        label(bar, "From:", 12, "bold", muted=True).pack(side="left", padx=(0, 4))
        self.from_entry = entry(bar, "YYYY-MM-DD", width=105)
        self.from_entry.pack(side="left")
        self.from_entry.insert(0, month_start)

        label(bar, "To:", 12, "bold", muted=True).pack(side="left", padx=(8, 4))
        self.to_entry = entry(bar, "YYYY-MM-DD", width=105)
        self.to_entry.pack(side="left")
        self.to_entry.insert(0, today_str)

        button(bar, "Filter", self.apply_filter, "primary", width=70, height=32).pack(side="left", padx=8)

        # Quick preset buttons
        presets = [("Today", self.set_today), ("7 Days", self.set_7d),
                   ("30 Days", self.set_30d), ("This Month", self.set_month)]
        for name, cmd in presets:
            button(bar, name, cmd, "neutral", width=75, height=32).pack(side="left", padx=2)

    # ------------------------------------------------------------- KPI Cards
    def build_kpi_cards(self):
        kpi_row = ctk.CTkFrame(self, fg_color="transparent")
        kpi_row.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        for i in range(6):
            kpi_row.grid_columnconfigure(i, weight=1, uniform="k")

        self.cards = {}
        specs = [("revenue", "Revenue", "💰", "#10B981"),
                 ("cost", "Cost of Goods", "🏷", "#F59E0B"),
                 ("profit", "Net Profit", "📈", "#6366F1"),
                 ("bills", "Bills Count", "🧾", "#0EA5E9"),
                 ("items", "Items Sold", "📦", "#8B5CF6"),
                 ("refunds", "Refunds", "↩", "#EF4444")]
        for i, (key, title, icon, color) in enumerate(specs):
            c = StatCard(kpi_row, title, icon, color)
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 4, 0 if i == 5 else 4))
            self.cards[key] = c

    # ----------------------------------------------------------- Charts Section
    def build_charts_section(self):
        sec = ctk.CTkFrame(self, fg_color="transparent")
        sec.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        sec.grid_columnconfigure((0, 1), weight=1, uniform="ch")
        sec.grid_rowconfigure(0, weight=1)

        # Left Chart: Daily Sales & Profit
        trend_card = card(sec)
        trend_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        trend_card.grid_columnconfigure(0, weight=1)
        trend_card.grid_rowconfigure(1, weight=1)
        top1 = ctk.CTkFrame(trend_card, fg_color="transparent")
        top1.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 2))
        label(top1, "Sales & Profit Trend", 14, "bold").pack(side="left")
        self.canvas_trend = tk.Canvas(trend_card, highlightthickness=0, bd=0, height=130)
        self.canvas_trend.grid(row=1, column=0, sticky="nsew", padx=10, pady=(2, 8))
        self.canvas_trend.bind("<Configure>", lambda e: self.draw_trend())

        # Right Chart: Top 5 Best Sellers
        top_card = card(sec)
        top_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        top_card.grid_columnconfigure(0, weight=1)
        top_card.grid_rowconfigure(1, weight=1)
        top2 = ctk.CTkFrame(top_card, fg_color="transparent")
        top2.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 2))
        label(top2, "Top 5 Products by Revenue", 14, "bold").pack(side="left")
        self.canvas_top = tk.Canvas(top_card, highlightthickness=0, bd=0, height=130)
        self.canvas_top.grid(row=1, column=0, sticky="nsew", padx=10, pady=(2, 8))
        self.canvas_top.bind("<Configure>", lambda e: self.draw_top_products())

    # ------------------------------------------------------------ Table Section
    def build_table_section(self):
        sec = card(self)
        sec.grid(row=3, column=0, sticky="nsew")
        sec.grid_columnconfigure(0, weight=1)
        sec.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(sec, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(10, 6))
        label(top, "Itemized Sales & Margin Breakdown", 15, "bold").pack(side="left")
        button(top, "Export Report CSV", self.export_csv, "neutral", width=140, height=30).pack(side="right")

        self.table = DataTable(sec, [
            ("ID", 45), ("Product", 200), ("Category", 120), ("Sold", 65),
            ("Revenue", 100), ("Cost", 95), ("Profit", 100), ("Margin %", 80)
        ])
        self.table.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))

    # -------------------------------------------------------- Presets & Refresh
    def set_today(self):
        d = date.today().strftime("%Y-%m-%d")
        self.from_entry.delete(0, "end"); self.from_entry.insert(0, d)
        self.to_entry.delete(0, "end"); self.to_entry.insert(0, d)
        self.apply_filter()

    def set_7d(self):
        start = (date.today() - timedelta(days=6)).strftime("%Y-%m-%d")
        end = date.today().strftime("%Y-%m-%d")
        self.from_entry.delete(0, "end"); self.from_entry.insert(0, start)
        self.to_entry.delete(0, "end"); self.to_entry.insert(0, end)
        self.apply_filter()

    def set_30d(self):
        start = (date.today() - timedelta(days=29)).strftime("%Y-%m-%d")
        end = date.today().strftime("%Y-%m-%d")
        self.from_entry.delete(0, "end"); self.from_entry.insert(0, start)
        self.to_entry.delete(0, "end"); self.to_entry.insert(0, end)
        self.apply_filter()

    def set_month(self):
        start = date.today().replace(day=1).strftime("%Y-%m-%d")
        end = date.today().strftime("%Y-%m-%d")
        self.from_entry.delete(0, "end"); self.from_entry.insert(0, start)
        self.to_entry.delete(0, "end"); self.to_entry.insert(0, end)
        self.apply_filter()

    def on_show(self):
        self.apply_filter()

    def on_theme_change(self):
        self.draw_trend()
        self.draw_top_products()

    # ------------------------------------------------------------- Query Data
    def apply_filter(self):
        f_str, t_str = self.from_entry.get().strip(), self.to_entry.get().strip()
        try:
            d_from = utils.validate("date", f_str, "From Date")
            d_to = utils.validate("date", t_str, "To Date")
        except ValueError as e:
            return utils.error(self, str(e))
        if d_from > d_to:
            return utils.error(self, "From Date must be earlier than (or the same as) To Date.")

        rng = (d_from, f"{d_to} 23:59:59")
        try:
            # ---- headline numbers -------------------------------------------------------
            n_bills, revenue = db.fetch_one(
                "SELECT COUNT(*), COALESCE(SUM(total), 0) FROM sales WHERE created_at BETWEEN %s AND %s", rng)
            n_items, cost = db.fetch_one(
                "SELECT COALESCE(SUM(si.qty), 0), COALESCE(SUM(si.qty * si.unit_cost), 0) "
                "FROM sale_items si JOIN sales s ON s.id = si.sale_id WHERE s.created_at BETWEEN %s AND %s", rng)
            # Returns inside the range: money handed back, units returned, and what those units cost us
            # (returned goods go back on the shelf, so their cost is NOT a loss).
            refunds, ret_units, ret_cost = db.fetch_one(
                "SELECT COALESCE(SUM(sr.refund_amount), 0), COALESCE(SUM(sr.qty), 0), "
                "COALESCE(SUM(sr.qty * COALESCE(si.unit_cost, 0)), 0) FROM sale_returns sr "
                "LEFT JOIN sale_items si ON si.sale_id = sr.sale_id AND si.product_id = sr.product_id "
                "WHERE sr.created_at BETWEEN %s AND %s", rng)
            revenue, cost, refunds, ret_cost = float(revenue), float(cost), float(refunds), float(ret_cost)

            # Net profit = money in - money refunded - cost of the goods that really left the shop
            profit = revenue - refunds - (cost - ret_cost)

            self.cards["revenue"].set(utils.short_number(revenue))
            self.cards["cost"].set(utils.short_number(cost - ret_cost))
            self.cards["profit"].set(utils.short_number(profit))
            self.cards["bills"].set(n_bills)
            self.cards["items"].set(int(n_items) - int(ret_units))
            self.cards["refunds"].set(utils.short_number(refunds))

            # ---- daily trend: three SEPARATE queries, merged in Python ------------------
            # (joining sales to sale_items in one query repeats each bill's total once per item
            #  and inflates the revenue - that was a bug in the first version)
            day_rev = {str(d): float(v) for d, v in db.fetch_all(
                "SELECT DATE(created_at), SUM(total) FROM sales WHERE created_at BETWEEN %s AND %s "
                "GROUP BY DATE(created_at)", rng)}
            day_cost = {str(d): float(v) for d, v in db.fetch_all(
                "SELECT DATE(s.created_at), SUM(si.qty * si.unit_cost) FROM sale_items si JOIN sales s ON s.id = si.sale_id "
                "WHERE s.created_at BETWEEN %s AND %s GROUP BY DATE(s.created_at)", rng)}
            day_ret = {str(d): float(v) for d, v in db.fetch_all(
                "SELECT DATE(sr.created_at), SUM(sr.refund_amount - sr.qty * COALESCE(si.unit_cost, 0)) FROM sale_returns sr "
                "LEFT JOIN sale_items si ON si.sale_id = sr.sale_id AND si.product_id = sr.product_id "
                "WHERE sr.created_at BETWEEN %s AND %s GROUP BY DATE(sr.created_at)", rng)}
            first, last = date.fromisoformat(d_from), date.fromisoformat(d_to)
            if (last - first).days <= 31:                      # short range: show every day, even empty ones
                days = [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]
            else:                                              # long range: only days that had activity
                days = sorted(set(day_rev) | set(day_ret))
            self.daily_data = [(d[5:], day_rev.get(d, 0.0),
                                day_rev.get(d, 0.0) - day_cost.get(d, 0.0) - day_ret.get(d, 0.0)) for d in days]

            # ---- products: revenue is AFTER the bill discount so it adds up to the headline revenue
            item_rows = db.fetch_all(
                "SELECT p.id, si.product_name, c.name, SUM(si.qty), "
                "SUM(si.line_total * (1 - s.discount_percent / 100)), SUM(si.qty * si.unit_cost) "
                "FROM sale_items si JOIN sales s ON s.id = si.sale_id "
                "LEFT JOIN products p ON p.id = si.product_id LEFT JOIN categories c ON c.id = p.category_id "
                "WHERE s.created_at BETWEEN %s AND %s GROUP BY p.id, si.product_name, c.name ORDER BY 5 DESC", rng)
            formatted = []
            for pid, name, cat, qty, rev, cst in item_rows:
                rev, cst = round(float(rev), 2), round(float(cst), 2)
                pft = round(rev - cst, 2)
                margin = f"{pft / rev * 100:.1f}%" if rev > 0 else "0.0%"
                formatted.append((pid or "-", name, cat or "General", int(qty), rev, cst, pft, margin))
            self.table.load(formatted)
            self.top_products = [(r[1], r[4]) for r in formatted[:5]]
        except Error as e:
            return utils.error(self, utils.friendly_db_error(e))

        self.draw_trend()
        self.draw_top_products()
        return None

    # ------------------------------------------------------------- Pure Canvas Charts
    @staticmethod
    def _nice_top(peak):
        """Round the highest value UP to a tidy number (e.g. 23,400 -> 30,000) for the axis."""
        peak = max(peak, 1)
        magnitude = 10 ** int(math.log10(peak))
        return math.ceil(peak / magnitude) * magnitude

    @staticmethod
    def _fit_text(font, text, max_px):
        """Cut text with an ellipsis so it never runs past max_px."""
        if font.measure(text) <= max_px:
            return text
        while text and font.measure(text + "…") > max_px:
            text = text[:-1]
        return text.rstrip() + "…"

    def draw_trend(self):
        c = self.canvas_trend
        c.delete("all")
        c.configure(bg=theme.resolve(theme.CARD))
        w, h = c.winfo_width(), c.winfo_height()
        muted, grid = theme.resolve(theme.MUTED), theme.resolve(theme.BORDER)
        if w < 150 or h < 90:
            return
        if not any(r or p for _, r, p in self.daily_data):
            c.create_text(w / 2, h / 2, text="No sales data for this date range", fill=muted, font=(theme.FONT_FAMILY, 11))
            return

        top_value = self._nice_top(max(r for _, r, _ in self.daily_data))
        left, right, top, bottom = 50, 14, 24, 26
        plot_w, plot_h = w - left - right, h - top - bottom
        for i in range(5):                                       # grid lines + scale on the left
            y = top + plot_h * (1 - i / 4)
            c.create_line(left, y, w - right, y, fill=grid)
            c.create_text(left - 6, y, text=utils.short_number(top_value * i / 4), anchor="e", fill=muted, font=(theme.FONT_FAMILY, 8))

        n = len(self.daily_data)
        slot = plot_w / n
        bar_w = max(min(slot * 0.34, 24), 2)
        every = max(1, math.ceil(n / max(plot_w // 48, 1)))      # thin out the date labels when crowded
        for i, (day, rev, pft) in enumerate(self.daily_data):
            mid = left + slot * (i + 0.5)
            y_rev = top + plot_h * (1 - rev / top_value)
            y_pft = top + plot_h * (1 - max(pft, 0) / top_value)
            c.create_rectangle(mid - bar_w - 1, y_rev, mid - 1, top + plot_h, fill=theme.ACCENT, outline="")
            c.create_rectangle(mid + 1, y_pft, mid + bar_w + 1, top + plot_h, fill=theme.SUCCESS, outline="")
            if i % every == 0:
                c.create_text(mid, h - bottom + 12, text=day, fill=muted, font=(theme.FONT_FAMILY, 8))
        # legend
        lx = w - right - 150
        for text, color in (("Revenue", theme.ACCENT), ("Profit", theme.SUCCESS)):
            c.create_rectangle(lx, 8, lx + 9, 17, fill=color, outline="")
            c.create_text(lx + 14, 12, text=text, anchor="w", fill=muted, font=(theme.FONT_FAMILY, 8))
            lx += 72

    def draw_top_products(self):
        c = self.canvas_top
        c.delete("all")
        c.configure(bg=theme.resolve(theme.CARD))
        w, h = c.winfo_width(), c.winfo_height()
        muted, text_color = theme.resolve(theme.MUTED), theme.resolve(theme.TEXT)
        if w < 150 or h < 60:
            return
        if not self.top_products:
            c.create_text(w / 2, h / 2, text="No product sales in this period", fill=muted, font=(theme.FONT_FAMILY, 11))
            return

        fnt = tkfont.Font(family=theme.FONT_FAMILY, size=9)
        label_w = min(max(fnt.measure(name) for name, _ in self.top_products) + 14, w * 0.42)
        peak = max(v for _, v in self.top_products) or 1
        row_h = (h - 8) / len(self.top_products)                 # rows share the REAL height, so none is cut off
        bar_h = max(min(row_h * 0.62, 20), 6)
        max_len = max(w - label_w - 64, 20)
        for i, (name, rev) in enumerate(self.top_products):
            y = 4 + row_h * i + (row_h - bar_h) / 2
            c.create_text(label_w - 8, y + bar_h / 2, text=self._fit_text(fnt, name, label_w - 12), anchor="e",
                          fill=text_color, font=(theme.FONT_FAMILY, 9))
            length = max(max_len * (rev / peak), 2)
            c.create_rectangle(label_w, y, label_w + length, y + bar_h, fill=theme.SUCCESS, outline="")
            c.create_text(label_w + length + 6, y + bar_h / 2, text=utils.short_number(rev), anchor="w",
                          fill=muted, font=(theme.FONT_FAMILY, 9))

    def export_csv(self):
        headings = [h for h, _ in self.table.columns]
        utils.export_csv(self, headings, self.table.current_rows(), "reports_sales_margin.csv")

