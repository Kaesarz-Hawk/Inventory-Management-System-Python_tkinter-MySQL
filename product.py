"""Products screen - prices, cost price, stock levels, SKU and product images."""
import settings
from base_page import CrudPage


class ProductPage(CrudPage):
    TITLE, SUBTITLE = "Products", "Prices, cost, stock levels and availability (low stock shows in red)"
    TABLE, ITEM = "products", "product"
    ADMIN_ONLY = False
    FIELDS = [
        {"key": "category", "label": "Category", "kind": "combo", "col": "category_id", "width": 130,
         "lookup": "SELECT id, name FROM categories ORDER BY name"},
        {"key": "supplier", "label": "Supplier", "kind": "combo", "col": "supplier_id", "width": 140,
         "lookup": "SELECT id, name FROM suppliers ORDER BY name"},
        {"key": "name", "label": "Product Name", "kind": "text", "required": True, "width": 200},
        {"key": "sku", "label": "SKU / Barcode", "kind": "text", "width": 120, "placeholder": "SKU-1001"},
        {"key": "cost_price", "label": "Cost Price", "kind": "float", "required": True, "width": 95, "placeholder": "0.00"},
        {"key": "price", "label": "Selling Price", "kind": "float", "required": True, "width": 95, "placeholder": "0.00"},
        {"key": "qty", "label": "Quantity", "kind": "int", "required": True, "width": 80},
        {"key": "status", "label": "Status", "kind": "combo", "values": ["Active", "Inactive"], "default": "Active", "width": 85},
        {"key": "image_path", "label": "Image File", "kind": "image", "width": 100, "placeholder": "Optional picture"},
    ]
    LIST_SQL = ("SELECT p.id, c.name, s.name, p.name, p.sku, p.cost_price, p.price, p.qty, p.status, p.image_path "
                "FROM products p JOIN categories c ON c.id = p.category_id JOIN suppliers s ON s.id = p.supplier_id")
    SEARCH = {"Name": "p.name", "SKU": "p.sku", "Category": "c.name", "Supplier": "s.name"}

    def row_tag(self, row):
        try:
            return "low" if int(row[7]) <= settings.get_low_stock_limit() else None
        except (ValueError, TypeError, IndexError):
            return None
