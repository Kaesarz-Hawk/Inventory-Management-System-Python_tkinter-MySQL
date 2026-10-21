"""Customers screen - manage customer contact details and view purchase history."""
from base_page import CrudPage


class CustomerPage(CrudPage):
    TITLE, SUBTITLE = "Customers", "Keep track of customer contacts, orders, and total spending"
    TABLE, ITEM = "customers", "customer"
    ADMIN_ONLY = False
    FIELDS = [
        {"key": "name", "label": "Full Name", "kind": "text", "required": True, "width": 180},
        {"key": "phone", "label": "Phone Number", "kind": "phone", "required": True, "width": 140, "placeholder": "01XXXXXXXXX"},
        {"key": "address", "label": "Address", "kind": "textarea", "width": 240},
    ]
    # Subqueries compute total orders and total money spent per customer without breaking WHERE clauses
    LIST_SQL = (
        "SELECT c.id, c.name, c.phone, c.address, "
        "(SELECT COUNT(*) FROM sales s WHERE s.customer_id = c.id), "
        "(SELECT COALESCE(SUM(s.total), 0) FROM sales s WHERE s.customer_id = c.id) "
        "FROM customers c"
    )
    EXTRA_COLUMNS = [("Orders", 85), ("Total Spent", 115)]
    SEARCH = {"Name": "c.name", "Phone": "c.phone"}
    NAME_FIELD = "name"

    def can_delete(self, row):
        try:
            if int(row[4]) > 0:
                return "This customer has previous orders on record and cannot be deleted."
        except (ValueError, TypeError, IndexError):
            pass
        return None

