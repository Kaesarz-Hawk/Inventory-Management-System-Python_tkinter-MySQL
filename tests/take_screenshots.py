"""
Takes a screenshot of every page at 1920x1080 and 1280x720 -> screenshots/<size>/
Run:   python tests/take_screenshots.py        (uses the test database, never your real one)
"""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ.setdefault("IMS_DB_DATABASE", "ims_test_db")
if "test" not in os.environ["IMS_DB_DATABASE"].lower():
    sys.exit("Refusing to run: database name must contain 'test'.")

import tkinter                      # noqa: E402
from PIL import ImageGrab           # noqa: E402
import utils                        # noqa: E402

tkinter.Tk.report_callback_exception = lambda self, *a: traceback.print_exception(*a)
utils.messagebox.showerror = lambda t, m, **k: print("ERROR BOX:", m)
utils.messagebox.showinfo = lambda t, m, **k: None
from dashboard import App           # noqa: E402

SIZES = ("1920x1080", "1280x720")
if len(sys.argv) == 1:                       # no size given: run each size in its OWN process (clean fonts/images)
    import subprocess
    for one in SIZES:
        subprocess.run([sys.executable, os.path.abspath(__file__), one], check=False)
    print("Screenshots saved in", os.path.join(ROOT, "screenshots"))
    sys.exit(0)

for size in (sys.argv[1],):
    out = os.path.join(ROOT, "screenshots", size)
    os.makedirs(out, exist_ok=True)
    app = App()
    app.geometry(f"{size}+0+0")
    steps = []

    def grab(name, app=app, out=out):
        app.update_idletasks(); app.update()
        x, y, w, h = app.winfo_rootx(), app.winfo_rooty(), app.winfo_width(), app.winfo_height()
        kw = {"xdisplay": os.environ["DISPLAY"]} if sys.platform.startswith("linux") and os.environ.get("DISPLAY") else {}
        ImageGrab.grab(bbox=(x, y, x + w, y + h), **kw).save(os.path.join(out, f"{name}.png"))
        print("saved", name)

    def go(delay, fn, steps=steps):
        steps.append((delay, fn))

    def run(app=app, steps=steps):
        if not steps:
            app.destroy(); return
        d, fn = steps.pop(0); app.after(d, lambda: (fn(), run(app, steps)))

    go(2500, lambda: grab("00_login"))
    go(200, lambda a=app: (a.login.email.insert(0, "admin@ims.com"), a.login.password.insert(0, "admin123"), a.login.attempt()))
    for i, (page, _icon, _cls) in enumerate(App.NAV, start=1):
        go(800, lambda p=page, a=app: a.show_page(p))
        go(900, lambda p=page, i=i: grab(f"{i:02d}_{p}"))
    run()
    app.mainloop()
