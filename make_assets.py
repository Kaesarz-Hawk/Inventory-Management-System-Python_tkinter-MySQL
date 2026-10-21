"""
make_assets.py  -  draws the login banner, app logo and window icon with Pillow.
Run once (python make_assets.py) if you ever want to regenerate them.
Prefer your own pictures? Just replace images/login_banner.png with any 460x570 image.
"""
import os

from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
FONT_DIR = os.environ.get("IMS_FONT_DIR", "/tmp")


def gradient(size, c1, c2, c3):
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = (x / w * 0.45 + y / h * 0.55)
            a, b, k = (c1, c2, t * 2) if t < 0.5 else (c2, c3, (t - 0.5) * 2)
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))
    return img


def iso(i, j, k, cx, cy, s, h):
    return cx + (i - j) * s, cy + (i + j) * s * 0.5 - k * h


def cube(d, apex, s, h, top, left, right):
    x, y = apex
    T, R, B, L = (x, y), (x + s, y + s * 0.5), (x, y + s), (x - s, y + s * 0.5)
    d.polygon([L, B, (B[0], B[1] + h), (L[0], L[1] + h)], fill=left)
    d.polygon([B, R, (R[0], R[1] + h), (B[0], B[1] + h)], fill=right)
    d.polygon([T, R, B, L], fill=top)
    d.line([B, (B[0], B[1] + h)], fill=(255, 255, 255, 90), width=2)       # carton edge


def boxes(d, cx, cy, s, h):
    top, left, right = (255, 255, 255, 245), (199, 210, 254, 255), (165, 180, 252, 255)
    for (i, j, k) in [(0, 0, 0), (0, 0, 1), (1, 0, 0), (0, 1, 0), (1, 1, 0)]:
        cube(d, iso(i, j, k, cx, cy, s, h), s, h, top, left, right)


def banner():
    w, h = 460, 570
    base = gradient((w, h), (79, 70, 229), (124, 58, 237), (14, 165, 233)).convert("RGBA")
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    for box, alpha in [((-80, -60, 260, 280), 40), ((250, 130, 560, 440), 34), ((40, 380, 330, 670), 30)]:
        g.ellipse(box, fill=(255, 255, 255, alpha))
    base = Image.alpha_composite(base, glow)
    art = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    boxes(ImageDraw.Draw(art), 230, 170, 62, 62)
    base = Image.alpha_composite(base, art)
    d = ImageDraw.Draw(base)
    def load(file, size):
        try:
            return ImageFont.truetype(f"{FONT_DIR}/{file}", size)
        except OSError:                       # font not installed -> fall back to Pillow's built-in font
            return ImageFont.load_default()
    title, sub, small = load("Poppins-Bold.ttf", 33), load("Poppins-Regular.ttf", 15), load("Poppins-Regular.ttf", 13)
    d.text((40, 372), "Inventory\nManagement System", font=title, fill="white", spacing=6)
    d.text((40, 466), "Track stock, sales and suppliers\nin one simple place.", font=sub, fill=(224, 231, 255), spacing=5)
    d.text((40, 526), "Developed by Kawsar Hoque", font=small, fill=(199, 210, 254))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=16, fill=255)
    base.putalpha(mask)
    base.save(os.path.join(OUT, "login_banner.png"))


def logo():
    n = 256
    img = gradient((n, n), (79, 70, 229), (124, 58, 237), (14, 165, 233)).convert("RGBA")
    art = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    cube(ImageDraw.Draw(art), (128, 52), 84, 84, (255, 255, 255, 255), (199, 210, 254, 255), (165, 180, 252, 255))
    img = Image.alpha_composite(img, art)
    mask = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, n - 1, n - 1), radius=56, fill=255)
    img.putalpha(mask)
    img.resize((128, 128), Image.LANCZOS).save(os.path.join(OUT, "app_logo.png"))
    img.save(os.path.join(OUT, "app_icon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    banner()
    logo()
    print("images created in", OUT)
