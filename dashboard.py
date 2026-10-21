"""
dashboard.py  -  the main window (App) and the Dashboard page.

App manages:
  - Security session, login, role restrictions
  - Responsive collapsible sidebar with English/Bangla language support
  - Dark/Light theme switching with database persistence
  - Idle auto-logout after N minutes of inactivity
  - Global keyboard shortcuts: F11 (fullscreen), Ctrl+F (search), Ctrl+N (clear), F5 (refresh)
  - Navigation between Dashboard, Employees, Suppliers, Categories, Products,
    Customers, Purchases, Billing, Sales, Reports, and Settings.
"""
from datetime import date, datetime, timedelta
import math
import os
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from mysql.connector import Error

import config
import lang
import settings
import theme
import utils
from billing import BillingPage
from category import CategoryPage
from create_db import setup_database
from customer import CustomerPage
from db import db
from employee import EmployeePage
from login import DBSettingsDialog, LoginFrame
from product import ProductPage
from purchases import PurchasesPage
from reports import ReportsPage
from sales import SalesPage
from settings_page import SettingsPage
from supplier import SupplierPage
from theme import StatCard, button, card, label


# =================================================================== DASHBOARD
class DashboardPage(ctk.CTkFrame):
    ADMIN_ONLY = False

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.week = []
        for c in range(6):
            self.grid_columnconfigure(c, weight=1, uniform="d")
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)

        greeting = ctk.CTkFrame(self, fg_color="transparent")
        greeting.grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 14))
        self.hello = label(greeting, "", 26, "bold")
        self.hello.pack(anchor="w")
        self.subtitle = label(greeting, "", 13, muted=True)
        self.subtitle.pack(anchor="w")

        self.cards = {}
        specs = [("employees", "Employees", "👤", "#6366F1"), ("suppliers", "Suppliers", "🚚", "#F97316"),
                 ("categories", "Categories", "🗂", "#14B8A6"), ("products", "Products", "📦", "#0EA5E9"),
                 ("sales", "Total Sales", "🧾", "#EAB308"), ("revenue", "Revenue", "💰", "#10B981")]
        for i, (key, title, icon, color) in enumerate(specs):
            c = StatCard(self, title, icon, color)
            c.grid(row=1, column=i, sticky="ew", padx=(0 if i == 0 else 5, 0 if i == 5 else 5), pady=(0, 14))
            self.cards[key] = c

        # ---- chart ----
        chart_card = card(self)
        chart_card.grid(row=2, column=0, columnspan=4, sticky="nsew", padx=(0, 5), pady=(0, 14))
        chart_card.grid_columnconfigure(0, weight=1)
        chart_card.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(chart_card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 0))
        label(top, "Sales - last 7 days", 16, "bold").pack(side="left")
        self.today_label = label(top, "", 12, "bold", color=theme.SUCCESS)
        self.today_label.pack(side="right")
        self.canvas = tk.Canvas(chart_card, highlightthickness=0, bd=0, height=120)
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=10, pady=(4, 10))
        self.canvas.bind("<Configure>", lambda e: self.draw_chart())

        # ---- low stock ----
        self.low_card = card(self)
        self.low_card.grid(row=2, column=4, columnspan=2, sticky="nsew", padx=(5, 0), pady=(0, 14))

        # ---- bottom 3 cards: recent sales + activity + reorder suggestions ----
        self.recent_card = card(self)
        self.recent_card.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=(0, 5))
        self.activity_card = card(self)
        self.activity_card.grid(row=3, column=2, columnspan=2, sticky="nsew", padx=5)
        self.reorder_card = card(self)
        self.reorder_card.grid(row=3, column=4, columnspan=2, sticky="nsew", padx=(5, 0))

    # ------------------------------------------------------------------ data
    def on_show(self):
        try:
            counts = {t: db.fetch_one(f"SELECT COUNT(*) FROM {t}")[0] for t in ("employees", "suppliers", "categories", "products")}
            n_sales, revenue = db.fetch_one("SELECT COUNT(*), COALESCE(SUM(total), 0) FROM sales")
            today = db.fetch_one("SELECT COALESCE(SUM(total), 0) FROM sales WHERE DATE(created_at) = CURDATE()")[0]
            by_day = dict(db.fetch_all("SELECT DATE(created_at), SUM(total) FROM sales "
                                       "WHERE created_at >= CURDATE() - INTERVAL 6 DAY GROUP BY DATE(created_at)"))
            limit = settings.get_low_stock_limit()
            low = db.fetch_all("SELECT name, qty FROM products WHERE qty <= %s AND status = 'Active' ORDER BY qty, name LIMIT 4",
                               (limit,))
            recent = db.fetch_all("SELECT invoice_no, customer_name, total FROM sales ORDER BY id DESC LIMIT 4")
            activity = db.fetch_all("SELECT a.action, a.created_at, COALESCE(e.name, 'System') FROM activity_log a "
                                    "LEFT JOIN employees e ON e.id = a.employee_id ORDER BY a.id DESC LIMIT 4")

            # Reorder suggestions formula:
            # 1. Safety stock target: 2 * low_stock_limit - current_qty (guarantees safe buffer).
            # 2. Demand during replenishment lead time (assuming 14 days lead time):
            #    (total units sold over last 30 days / 30.0) * 14 days.
            # 3. Suggestion: max(safety_stock_target, lead_time_demand), rounded up with math.ceil.
            low_prods = db.fetch_all(
                "SELECT p.id, p.name, p.qty, "
                "COALESCE((SELECT SUM(si.qty) FROM sale_items si JOIN sales s ON s.id = si.sale_id "
                "WHERE si.product_id = p.id AND s.created_at >= CURDATE() - INTERVAL 30 DAY), 0) "
                "FROM products p WHERE p.qty <= %s AND p.status = 'Active' ORDER BY p.qty ASC LIMIT 4",
                (limit,)
            )
            reorder_rows = []
            for pid, pname, pqty, sold_30d in low_prods:
                avg_daily = float(sold_30d) / 30.0
                lead_time_demand = math.ceil(avg_daily * 14)
                safety_target = limit * 2 - int(pqty)
                suggested = max(safety_target, lead_time_demand, 1)
                reorder_rows.append((pid, pname, pqty, suggested))

        except Error as e:
            return utils.error(self, utils.friendly_db_error(e))

        hour = datetime.now().hour
        part = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"
        self.hello.configure(text=f"Good {part}, {utils.session.get('name', '').split(' ')[0]} 👋")
        self.subtitle.configure(text=f"{datetime.now():%A, %d %B %Y}  -  here is how your store is doing")
        for key in ("employees", "suppliers", "categories", "products"):
            self.cards[key].set(counts[key])
        self.cards["sales"].set(n_sales)
        self.cards["revenue"].set(f"{settings.get_currency()}{utils.short_number(revenue)}")
        self.today_label.configure(text=f"Today: {utils.money(today)}")

        days = [date.today() - timedelta(days=i) for i in range(6, -1, -1)]
        self.week = [(d.strftime("%a"), float(by_day.get(d, 0))) for d in days]
        self.draw_chart()

        self.fill(self.low_card, "⚠  Low stock alerts", low, self.low_row, "All products are well stocked 🎉")
        self.fill(self.recent_card, "Recent sales", recent, self.recent_row, "No sales yet")
        self.fill(self.activity_card, "Recent activity", activity, self.activity_row, "No activity yet")
        self.fill(self.reorder_card, "⚡ Reorder suggestions", reorder_rows, self.reorder_row, "Stock levels optimal")
        if self._refresh_job:                       # never keep more than ONE pending refresh timer
            self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(30000, self.auto_refresh)
        return None

    _refresh_job = None

    def auto_refresh(self):
        self._refresh_job = None
        if self.winfo_ismapped():
            self.on_show()

    # ----------------------------------------------------------------- lists
    def fill(self, frame, title, rows, row_builder, empty_text):
        for child in frame.winfo_children():
            child.destroy()
        frame.grid_columnconfigure(0, weight=1)
        label(frame, title, 15, "bold").grid(row=0, column=0, sticky="w", padx=16, pady=(12, 6))
        if not rows:
            label(frame, empty_text, 12, muted=True).grid(row=1, column=0, pady=16)
            return
        for i, row in enumerate(rows, start=1):
            line = ctk.CTkFrame(frame, fg_color="transparent")
            line.grid(row=i, column=0, sticky="ew", padx=16, pady=2)
            row_builder(line, row)

    def low_row(self, line, row):
        name, qty = row
        label(line, name, 12).pack(side="left")
        ctk.CTkLabel(line, text=f" {qty} left " if qty else " Out of stock ", fg_color=theme.DANGER if qty <= 5 else theme.WARNING,
                     text_color="white", corner_radius=8, font=theme.font(10, "bold")).pack(side="right")

    def recent_row(self, line, row):
        invoice, customer, total = row
        label(line, invoice, 12, "bold").pack(side="left")
        label(line, f"  {utils.ellipsize(customer, 14)}", 11, muted=True).pack(side="left")
        label(line, utils.money(total), 12, "bold", color=theme.SUCCESS).pack(side="right")

    def activity_row(self, line, row):
        action, when, who = row
        label(line, utils.ellipsize(action, 26), 12).pack(side="left")
        label(line, utils.ellipsize(str(who).split(" ")[0], 10), 11, muted=True).pack(side="right")

    def reorder_row(self, line, row):
        _pid, name, qty, suggested = row
        label(line, f"{utils.ellipsize(name, 17)} ({qty} left)", 12).pack(side="left")
        button(line, f"+ {suggested} units", lambda: self.app.open_purchases_for(name, suggested),
               "warning", width=80, height=24).pack(side="right")

    # ----------------------------------------------------------------- chart
    def on_theme_change(self):
        self.draw_chart()

    def draw_chart(self):
        c = self.canvas
        c.delete("all")
        c.configure(bg=theme.resolve(theme.CARD))
        w, h = c.winfo_width(), c.winfo_height()
        if w < 120 or h < 100 or not self.week:
            return
        grid, muted, text = theme.resolve(theme.BORDER), theme.resolve(theme.MUTED), theme.resolve(theme.TEXT)
        values = [v for _, v in self.week]
        if max(values) == 0:
            c.create_text(w / 2, h / 2, text="No sales in the last 7 days", fill=muted, font=(theme.FONT_FAMILY, 13))
            return
        magnitude = 10 ** int(math.log10(max(values)))
        top_value = math.ceil(max(values) / magnitude) * magnitude
        left, right, top, bottom = 58, 18, 26, 32
        plot_h = h - top - bottom
        for i in range(5):
            y = top + plot_h * (1 - i / 4)
            c.create_line(left, y, w - right, y, fill=grid)
            c.create_text(left - 8, y, text=utils.short_number(top_value * i / 4), anchor="e", fill=muted, font=(theme.FONT_FAMILY, 9))
        slot = (w - left - right) / len(values)
        bar_w = min(slot * 0.5, 70)
        for i, (day, value) in enumerate(self.week):
            x0 = left + slot * i + (slot - bar_w) / 2
            y1 = top + plot_h * (1 - value / top_value)
            c.create_rectangle(x0, y1, x0 + bar_w, top + plot_h, fill=theme.ACCENT if i < 6 else theme.SUCCESS, outline="")
            if value:
                c.create_text(x0 + bar_w / 2, y1 - 10, text=utils.short_number(value), fill=text, font=(theme.FONT_FAMILY, 9, "bold"))
            c.create_text(x0 + bar_w / 2, h - bottom + 16, text=day, fill=muted, font=(theme.FONT_FAMILY, 10))


# ======================================================================== APP
class App(ctk.CTk):
    # Full navigation list for v3
    NAV = [
        ("Dashboard", "🏠", DashboardPage),
        ("Employees", "👤", EmployeePage),
        ("Suppliers", "🚚", SupplierPage),
        ("Categories", "🗂", CategoryPage),
        ("Products", "📦", ProductPage),
        ("Customers", "👥", CustomerPage),
        ("Purchases", "📥", PurchasesPage),
        ("Billing", "🧾", BillingPage),
        ("Sales", "📊", SalesPage),
        ("Reports", "📈", ReportsPage),
        ("Settings", "⚙", SettingsPage),
    ]

    def __init__(self):
        super().__init__()
        # Load persisted appearance mode from settings
        saved_theme = settings.get_theme()
        ctk.set_appearance_mode(saved_theme)
        self.title(f"{config.APP_NAME}  |  {config.APP_AUTHOR}")
        self.minsize(1100, 720)
        w, h = 1366, 768
        self.geometry(f"{w}x{h}+{max((self.winfo_screenwidth() - w) // 2, 0)}+{max((self.winfo_screenheight() - h) // 2 - 20, 0)}")
        self.configure(fg_color=theme.BG)
        theme.style_tables()

        self.pages, self.nav_buttons, self.current = {}, {}, None
        self.shell = self.login = None
        self.fullscreen = False
        self.clock_job = None
        self.idle_job = None
        self.last_activity = datetime.now()

        # Keyboard shortcuts (Tier 3)
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.exit_fullscreen)
        self.bind("<Control-f>", self.shortcut_search)
        self.bind("<Control-F>", self.shortcut_search)
        self.bind("<Control-n>", self.shortcut_new)
        self.bind("<Control-N>", self.shortcut_new)
        self.bind("<F5>", self.shortcut_refresh)

        # Activity monitors for idle auto-logout
        self.bind_all("<Key>", self._record_activity)
        self.bind_all("<Button>", self._record_activity)
        self.bind_all("<Motion>", self._record_activity)

        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        icon = os.path.join(config.IMAGE_DIR, "app_icon.ico")
        self.after(250, lambda: self.safe(lambda: self.iconbitmap(icon)))
        self.after(0, self.maximize)
        self.after(150, self.start)

    @staticmethod
    def safe(fn):
        try:
            fn()
        except Exception:
            pass

    def maximize(self):
        try:
            self.state("zoomed")
        except tk.TclError:
            self.safe(lambda: self.attributes("-zoomed", True))

    def toggle_fullscreen(self, _event=None):
        self.fullscreen = not self.fullscreen
        self.attributes("-fullscreen", self.fullscreen)

    def exit_fullscreen(self, _event=None):
        if self.fullscreen:
            self.fullscreen = False
            self.attributes("-fullscreen", False)

    def _record_activity(self, _event=None):
        self.last_activity = datetime.now()

    def check_idle_timeout(self):
        if self.shell is not None:
            timeout_min = settings.get_idle_timeout()
            idle_seconds = (datetime.now() - self.last_activity).total_seconds()
            if timeout_min > 0 and idle_seconds >= timeout_min * 60:      # 0 = never log out
                utils.log_activity("Logged out due to idle timeout")
                self.logout(prompt=False)
                messagebox.showinfo("Session Expired", "You have been logged out due to inactivity.", parent=self)
                return
        self.idle_job = self.after(10000, self.check_idle_timeout)

    # --------------------------------------------------------------- shortcuts
    def shortcut_search(self, _event=None):
        page = self.pages.get(self.current)
        if page:
            for attr in ("search", "search_entry"):
                w = getattr(page, attr, None)
                if w:
                    w.focus_set()
                    return "break"
        return None

    def shortcut_new(self, _event=None):
        page = self.pages.get(self.current)
        if page:
            for method in ("clear", "clear_all", "clear_form"):
                fn = getattr(page, method, None)
                if fn:
                    fn()
                    return "break"
        return None

    def shortcut_refresh(self, _event=None):
        page = self.pages.get(self.current)
        if page:
            if hasattr(page, "on_show"):
                page.on_show()
                return "break"
            elif hasattr(page, "refresh"):
                page.refresh()
                return "break"
        return None

    # --------------------------------------------------------------- start up
    def start(self):
        problem = None
        while True:
            try:
                setup_database()
                break
            except Exception as e:
                problem = utils.friendly_db_error(e)
            dialog = DBSettingsDialog(self, problem)
            self.wait_window(dialog)
            if not dialog.saved:
                self.destroy()
                return
        self.show_login()

    def show_login(self):
        self.login = LoginFrame(self, self.start_session)
        self.login.pack(fill="both", expand=True)

    def start_session(self, user):
        utils.session.clear()
        utils.session.update(user)
        utils.log_activity("Logged in")
        self.last_activity = datetime.now()
        self.login.destroy()
        self.build_shell()
        self.show_page("Dashboard")
        self.tick()
        self.check_idle_timeout()

    # ----------------------------------------------------------------- layout
    def allowed(self):
        return [item for item in self.NAV if utils.is_admin() or not item[2].ADMIN_ONLY]

    def build_shell(self):
        self.shell = ctk.CTkFrame(self, fg_color="transparent")
        self.shell.pack(fill="both", expand=True)
        self.shell.grid_columnconfigure(1, weight=1)
        self.shell.grid_rowconfigure(0, weight=1)

        side = ctk.CTkFrame(self.shell, width=240, corner_radius=0, fg_color=theme.SIDEBAR)
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)
        logo = theme.load_image("app_logo.png", 40, 40)
        ctk.CTkLabel(side, text="  Inventory\n  Manager", image=logo, compound="left", font=theme.font(17, "bold"),
                     text_color="white", justify="left").pack(anchor="w", padx=18, pady=(20, 16))
        label(side, lang.t("MENU"), 11, "bold", color="#64748B").pack(anchor="w", padx=22, pady=(0, 6))

        for name, icon, _cls in self.allowed():
            b = ctk.CTkButton(side, text=f"   {icon}    {lang.t(name)}", anchor="w", height=40, corner_radius=10, fg_color="transparent",
                              hover_color=theme.SIDEBAR_HOVER, text_color="#CBD5E1", font=theme.font(13, "bold"),
                              command=lambda n=name: self.show_page(n))
            b.pack(fill="x", padx=12, pady=1)
            self.nav_buttons[name] = b

        ctk.CTkButton(side, text=f"   ⏻    {lang.t('Exit')}", anchor="w", height=40, corner_radius=10, fg_color="transparent",
                      hover_color="#7F1D1D", text_color="#FCA5A5", font=theme.font(13, "bold"),
                      command=self.quit_app).pack(side="bottom", fill="x", padx=12, pady=14)

        main = ctk.CTkFrame(self.shell, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        bar = ctk.CTkFrame(main, height=64, corner_radius=0, fg_color=theme.CARD, border_width=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)
        self.page_title = label(bar, "", 18, "bold")
        self.page_title.grid(row=0, column=0, padx=24, pady=16, sticky="w")
        self.clock = label(bar, "", 12, muted=True)
        self.clock.grid(row=0, column=1, sticky="e", padx=14)
        self.mode = ctk.CTkSwitch(bar, text="Dark", font=theme.font(12), text_color=theme.MUTED, progress_color=theme.ACCENT,
                                  command=self.toggle_theme, width=65)
        if settings.get_theme() == "Dark":
            self.mode.select()
        else:
            self.mode.deselect()
        self.mode.grid(row=0, column=2, padx=6)
        button(bar, "⛶", self.toggle_fullscreen, "neutral", 36, 32).grid(row=0, column=3, padx=4)

        chip = ctk.CTkFrame(bar, fg_color=theme.CARD_ALT, corner_radius=18)
        chip.grid(row=0, column=4, padx=(8, 6))
        initial = utils.session["name"][:1].upper()
        ctk.CTkLabel(chip, text=initial, width=30, height=30, corner_radius=15, fg_color=theme.ACCENT, text_color="white",
                     font=theme.font(13, "bold")).pack(side="left", padx=(4, 6), pady=4)
        who = ctk.CTkFrame(chip, fg_color="transparent")
        who.pack(side="left", padx=(0, 10))
        label(who, utils.session["name"], 11, "bold").pack(anchor="w")
        label(who, utils.session["role"], 10, muted=True).pack(anchor="w")
        button(bar, lang.t("Logout"), self.logout, "danger", 75, 32).grid(row=0, column=5, padx=(4, 20))

        self.content = ctk.CTkFrame(main, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=22, pady=18)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        foot = ctk.CTkFrame(main, height=30, corner_radius=0, fg_color=theme.CARD)
        foot.grid(row=2, column=0, sticky="ew")
        label(foot, f"{config.APP_NAME}  v{config.APP_VERSION}   |   Developed by {config.APP_AUTHOR}   |   "
                    "F11 = Full Screen | Ctrl+F = Search | Ctrl+N = New | F5 = Refresh", 11, muted=True).pack(pady=4)

    # ------------------------------------------------------------ navigation
    def show_page(self, name):
        cls = next(c for n, _i, c in self.NAV if n == name)
        if name not in self.pages:
            try:
                self.pages[name] = cls(self.content, self)
            except Error as e:
                return utils.error(self, utils.friendly_db_error(e))
            self.pages[name].grid(row=0, column=0, sticky="nsew")
        if self.current and self.current != name:
            self.pages[self.current].grid_remove()
        self.current = name
        self.pages[name].grid()
        self.pages[name].on_show()
        for n, b in self.nav_buttons.items():
            b.configure(fg_color=theme.ACCENT if n == name else "transparent",
                        text_color="white" if n == name else "#CBD5E1")
        self.page_title.configure(text=lang.t(name))
        return None

    def reload_ui(self, go_to="Settings"):
        """Rebuild the whole window so every label appears in the newly chosen language."""
        for job in (self.clock_job, self.idle_job):
            if job:
                self.after_cancel(job)
        self.clock_job = self.idle_job = None
        if self.shell:
            self.shell.destroy()
        self.pages, self.nav_buttons, self.current = {}, {}, None
        self.build_shell()
        self.show_page(go_to)
        self.tick()
        self.check_idle_timeout()

    def open_purchases_for(self, product_name, suggested_qty):
        """Cross-page navigation: Opens Purchases with product and quantity pre-filled."""
        if not utils.is_admin():
            return utils.error(self, "Purchases page is restricted to Admin accounts.")
        self.show_page("Purchases")
        page = self.pages.get("Purchases")
        if page and hasattr(page, "prod_combo"):
            page.prod_combo.set(product_name)
            page.on_product_pick(product_name)
            page.qty_entry.delete(0, "end")
            page.qty_entry.insert(0, str(suggested_qty))
        return None

    def toggle_theme(self):
        mode = "Dark" if self.mode.get() else "Light"
        settings.set_setting("theme", mode)
        ctk.set_appearance_mode(mode)
        theme.style_tables()
        theme.refresh_tables()
        for page in self.pages.values():
            if hasattr(page, "on_theme_change"):
                page.on_theme_change()

    def tick(self):
        self.clock.configure(text=f"{datetime.now():%a, %d %b %Y    %I:%M:%S %p}")
        self.clock_job = self.after(1000, self.tick)

    # ------------------------------------------------------- logout / quit
    def logout(self, prompt=True):
        if prompt and not utils.confirm(self, "Log out of the system?"):
            return
        utils.log_activity("Logged out")
        if self.clock_job:
            self.after_cancel(self.clock_job)
        if self.idle_job:
            self.after_cancel(self.idle_job)
        if self.shell:
            self.shell.destroy()
            self.shell = None
        self.pages, self.nav_buttons, self.current = {}, {}, None
        utils.session.clear()
        self.show_login()

    def quit_app(self):
        if self.shell is not None and not utils.confirm(self, "Close the application?"):
            return
        db.close()
        self.destroy()
