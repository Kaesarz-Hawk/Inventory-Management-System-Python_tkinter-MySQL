"""Employees screen - staff accounts. Employees also use this table to log in."""
import utils
from base_page import CrudPage
from db import db


class EmployeePage(CrudPage):
    TITLE, SUBTITLE = "Employees", "Manage staff accounts, roles and salaries"
    TABLE, ITEM = "employees", "employee"
    ADMIN_ONLY = True
    FIELDS = [
        {"key": "name", "label": "Full Name", "kind": "text", "required": True, "width": 150},
        {"key": "email", "label": "Email", "kind": "email", "required": True, "width": 190, "placeholder": "name@example.com"},
        {"key": "gender", "label": "Gender", "kind": "combo", "values": ["Select", "Male", "Female", "Other"], "width": 90},
        {"key": "phone", "label": "Phone", "kind": "phone", "required": True, "width": 120, "placeholder": "01XXXXXXXXX"},
        {"key": "dob", "label": "Date of Birth", "kind": "date", "width": 110, "placeholder": "YYYY-MM-DD"},
        {"key": "doj", "label": "Date of Joining", "kind": "date", "width": 120, "placeholder": "YYYY-MM-DD"},
        {"key": "role", "label": "User Type", "kind": "combo", "values": ["Select", "Admin", "Employee"], "default": "Employee", "width": 100},
        {"key": "password", "label": "Password", "kind": "password", "required": True, "hidden": True,
         "placeholder": "min 6 characters (blank = keep current)"},
        {"key": "address", "label": "Address", "kind": "textarea", "width": 200},
        {"key": "salary", "label": "Salary", "kind": "float", "required": True, "width": 100},
    ]
    LIST_SQL = "SELECT id, name, email, gender, phone, dob, doj, role, address, salary FROM employees"
    SEARCH = {"Name": "name", "Email": "email", "Contact": "phone", "Role": "role"}

    def can_delete(self, row):
        if row[0] == utils.session.get("id"):
            return "You cannot delete the account you are logged in with."
        admins = db.fetch_one("SELECT COUNT(*) FROM employees WHERE role='Admin'")[0]
        if row[7] == "Admin" and admins <= 1:
            return "This is the last Admin account - the system needs at least one Admin."
        return None
