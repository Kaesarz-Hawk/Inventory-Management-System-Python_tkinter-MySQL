"""Suppliers screen - who supplies our stock."""
from base_page import CrudPage


class SupplierPage(CrudPage):
    TITLE, SUBTITLE = "Suppliers", "Keep supplier contacts and invoice numbers in one place"
    TABLE, ITEM = "suppliers", "supplier"
    ADMIN_ONLY = True
    FIELDS = [
        {"key": "invoice_no", "label": "Invoice No.", "kind": "text", "required": True, "width": 110, "placeholder": "SUP-1006"},
        {"key": "name", "label": "Supplier Name", "kind": "text", "required": True, "width": 170},
        {"key": "contact", "label": "Contact", "kind": "phone", "required": True, "width": 120, "placeholder": "01XXXXXXXXX"},
        {"key": "description", "label": "Description", "kind": "textarea", "width": 220},
    ]
    LIST_SQL = ("SELECT s.id, s.invoice_no, s.name, s.contact, s.description, "
                "(SELECT COUNT(*) FROM products p WHERE p.supplier_id = s.id) FROM suppliers s")
    EXTRA_COLUMNS = [("Products", 90)]
    SEARCH = {"Invoice No.": "s.invoice_no", "Name": "s.name", "Contact": "s.contact"}
    NAME_FIELD = "name"
