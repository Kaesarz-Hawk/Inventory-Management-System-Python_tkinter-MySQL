"""Categories screen - groups for products (Phone, Grocery, ...)."""
from base_page import CrudPage


class CategoryPage(CrudPage):
    TITLE, SUBTITLE = "Categories", "Organise products into groups"
    TABLE, ITEM = "categories", "category"
    ADMIN_ONLY = True
    FIELDS = [
        {"key": "name", "label": "Category Name", "kind": "text", "required": True, "width": 220},
    ]
    LIST_SQL = ("SELECT c.id, c.name, (SELECT COUNT(*) FROM products p WHERE p.category_id = c.id) "
                "FROM categories c")
    EXTRA_COLUMNS = [("Products", 100)]
    SEARCH = {"Name": "c.name"}
    FORM_IMAGE = "cat.jpg"
