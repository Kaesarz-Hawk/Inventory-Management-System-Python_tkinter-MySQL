"""
Run this file to start the application:    python main.py
(MySQL must be running. The database and tables are created automatically.)
"""
import sys
import tkinter as tk
from tkinter import messagebox

try:
    import customtkinter
    import mysql.connector
    import PIL
except ImportError as missing:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Missing package", f"{missing}\n\nInstall everything with:\n    pip install -r requirements.txt")
    sys.exit(1)

from dashboard import App

if __name__ == "__main__":
    App().mainloop()
