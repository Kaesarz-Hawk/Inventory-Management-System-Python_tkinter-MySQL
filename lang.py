"""
lang.py  -  English / Bangla text dictionary.

How it works (easy to explain):
  * Every label, button and page title in the app is created through theme.label / theme.button /
    theme.page_header. Those call t(text), so ANY text that exists in TRANSLATIONS is shown in Bangla
    when the language setting is "bn". Text that is not in the dictionary simply stays English.
  * Changing the language in Settings rebuilds the window, so every screen shows the new language.
"""
import settings

# "English text": "Bangla text"
TRANSLATIONS = {
    # ---- menu / page titles
    "Dashboard": "ড্যাশবোর্ড", "Employees": "কর্মচারী", "Suppliers": "সরবরাহকারী", "Categories": "ক্যাটাগরি",
    "Products": "পণ্য", "Customers": "গ্রাহক", "Purchases": "ক্রয় / স্টক-ইন", "Billing": "বিলিং",
    "Sales": "বিক্রয়", "Reports": "রিপোর্ট", "Settings": "সেটিংস", "Exit": "প্রস্থান", "MENU": "মেনু",
    "Purchases / Stock-In": "ক্রয় / স্টক-ইন", "Billing / Point of Sale": "বিলিং / বিক্রয় কেন্দ্র",
    "Analytics & Reports": "বিশ্লেষণ ও রিপোর্ট", "Settings & Preferences": "সেটিংস ও পছন্দ",

    # ---- page sub-titles
    "Manage staff accounts, roles and salaries": "কর্মচারীর অ্যাকাউন্ট, ভূমিকা ও বেতন পরিচালনা করুন",
    "Keep supplier contacts and invoice numbers in one place": "সরবরাহকারীর যোগাযোগ ও ইনভয়েস নম্বর এক জায়গায় রাখুন",
    "Organise products into groups": "পণ্যগুলোকে গ্রুপে সাজান",
    "Keep track of customer contacts, orders, and total spending": "গ্রাহকের যোগাযোগ, অর্ডার ও মোট খরচের হিসাব রাখুন",
    "Prices, cost, stock levels and availability (low stock shows in red)": "দাম, ক্রয়মূল্য, স্টক ও প্রাপ্যতা (কম স্টক লাল রঙে)",
    "Type or scan SKU + Enter to add item, or double-click product list": "SKU লিখুন বা স্ক্যান করে Enter চাপুন, অথবা তালিকায় ডাবল-ক্লিক করুন",
    "Receive stock from suppliers, update cost prices, and increase inventory": "সরবরাহকারীর কাছ থেকে পণ্য গ্রহণ করুন, ক্রয়মূল্য হালনাগাদ করুন ও স্টক বাড়ান",
    "Financial KPIs, true profit margins, and sales trends": "আর্থিক সূচক, প্রকৃত লাভের হার ও বিক্রয়ের ধারা",
    "Every customer bill, with search, live preview, and item refunds": "প্রতিটি বিল, অনুসন্ধান, প্রিভিউ ও পণ্য ফেরতসহ",
    "Configure store profile, personal password, theme, and data backups": "দোকানের তথ্য, পাসওয়ার্ড, থিম ও ডেটা ব্যাকআপ ঠিক করুন",

    # ---- buttons
    "Save": "সংরক্ষণ", "Update": "হালনাগাদ", "Delete": "মুছুন", "Clear": "পরিষ্কার", "Export CSV": "সিএসভি এক্সপোর্ট",
    "Refresh": "রিফ্রেশ", "Print": "প্রিন্ট", "Search": "অনুসন্ধান", "Generate Bill": "বিল তৈরি করুন",
    "Calculator": "ক্যালকুলেটর", "Clear All": "সব মুছুন", "Add | Update": "যোগ / পরিবর্তন",
    "Remove Selected": "নির্বাচিত সরান", "Show All": "সব দেখুন", "Return Item": "পণ্য ফেরত", "Logout": "লগআউট",
    "Sign In": "লগইন করুন", "Test & Save": "যাচাই ও সংরক্ষণ", "Add Item": "আইটেম যোগ করুন",
    "Remove Item": "আইটেম সরান", "Save Purchase": "ক্রয় সংরক্ষণ", "Clear Form": "ফর্ম পরিষ্কার", "Filter": "ফিল্টার",
    "Today": "আজ", "7 Days": "৭ দিন", "30 Days": "৩০ দিন", "This Month": "এই মাস", "Print PO": "পিও প্রিন্ট",
    "Export Report CSV": "রিপোর্ট এক্সপোর্ট", "Update Password": "পাসওয়ার্ড পরিবর্তন",
    "Save System Settings": "সেটিংস সংরক্ষণ", "Backup Database Now": "এখনই ব্যাকআপ নিন",
    "Confirm Return": "ফেরত নিশ্চিত করুন", "Cancel": "বাতিল", "Quit": "বন্ধ করুন", "Browse": "বাছাই",

    # ---- form field labels
    "Full Name": "পুরো নাম", "Email": "ইমেইল", "Gender": "লিঙ্গ", "Phone": "ফোন", "Date of Birth": "জন্ম তারিখ",
    "Date of Joining": "যোগদানের তারিখ", "User Type": "ব্যবহারকারীর ধরন", "Address": "ঠিকানা", "Salary": "বেতন",
    "Password": "পাসওয়ার্ড", "Invoice No.": "ইনভয়েস নং", "Supplier Name": "সরবরাহকারীর নাম", "Contact": "যোগাযোগ",
    "Description": "বিবরণ", "Category Name": "ক্যাটাগরির নাম", "Category": "ক্যাটাগরি", "Supplier": "সরবরাহকারী",
    "Product Name": "পণ্যের নাম", "SKU / Barcode": "SKU / বারকোড", "Cost Price": "ক্রয়মূল্য",
    "Selling Price": "বিক্রয়মূল্য", "Quantity": "পরিমাণ", "Status": "অবস্থা", "Image File": "ছবি",
    "Phone Number": "ফোন নম্বর", "Name *": "নাম *", "Contact No.": "যোগাযোগ নম্বর", "Show password": "পাসওয়ার্ড দেখুন",
    "From:": "শুরু:", "To:": "শেষ:",

    # ---- card / section titles
    "Employee Details": "কর্মচারীর তথ্য", "Supplier Details": "সরবরাহকারীর তথ্য", "Category Details": "ক্যাটাগরির তথ্য",
    "Product Details": "পণ্যের তথ্য", "Customer Details": "গ্রাহকের তথ্য",
    "All Employees": "সব কর্মচারী", "All Suppliers": "সব সরবরাহকারী", "All Categories": "সব ক্যাটাগরি",
    "All Products": "সব পণ্য", "All Customers": "সব গ্রাহক", "All Bills": "সব বিল",
    "Available Products": "বিক্রয়যোগ্য পণ্য", "Cart": "কার্ট", "Customer Bill Area": "গ্রাহক বিল রসিদ",
    "Bill Preview": "বিল প্রিভিউ", "Purchase History": "ক্রয়ের ইতিহাস", "Purchase Order Preview": "ক্রয় রসিদ প্রিভিউ",
    "Purchase Items Staging": "ক্রয়ের তালিকা", "Add Product to Purchase": "ক্রয়ে পণ্য যোগ করুন",
    "Store Identity & Defaults": "দোকানের তথ্য ও ডিফল্ট", "Security & Password": "নিরাপত্তা ও পাসওয়ার্ড",
    "Personal Preferences": "ব্যক্তিগত পছন্দ", "Database Backup & Safety": "ডেটাবেজ ব্যাকআপ ও নিরাপত্তা",
    "Itemized Sales & Margin Breakdown": "পণ্যভিত্তিক বিক্রয় ও লাভের হিসাব",
    "Sales & Profit Trend": "বিক্রয় ও লাভের ধারা", "Top 5 Products by Revenue": "আয়ে সেরা ৫ পণ্য",
    "Sales - last 7 days": "বিক্রয় - গত ৭ দিন", "Low stock alerts": "কম স্টক সতর্কতা",
    "⚠  Low stock alerts": "⚠  কম স্টক সতর্কতা", "Recent sales": "সাম্প্রতিক বিক্রয়",
    "Recent activity": "সাম্প্রতিক কার্যক্রম", "⚡ Reorder suggestions": "⚡ পুনরায় ক্রয়ের পরামর্শ",

    # ---- statistics
    "Total Sales": "মোট বিক্রয়", "Revenue": "আয়", "Cost of Goods": "পণ্যের খরচ", "Net Profit": "নীট লাভ",
    "Bills Count": "বিলের সংখ্যা", "Items Sold": "বিক্রীত পণ্য", "Refunds": "ফেরত", "Bill Amount": "মোট মূল্য",
    "Discount": "ছাড়", "Discount %": "ছাড় %", "Net Pay": "পরিশোধযোগ্য",

    # ---- login
    "Welcome back 👋": "স্বাগতম 👋", "Sign in to manage your inventory": "আপনার ইনভেন্টরি পরিচালনায় প্রবেশ করুন",
    "Demo accounts": "ডেমো অ্যাকাউন্ট",
}


def t(key):
    """Return the Bangla text if the language is Bangla and a translation exists, else the original text."""
    if not isinstance(key, str) or not key:
        return key
    if settings.get_language() == "bn":
        return TRANSLATIONS.get(key, key)
    return key
