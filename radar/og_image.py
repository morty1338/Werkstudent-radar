"""Social preview image (1200×630) with today's headline numbers.

Messengers and LinkedIn show it when someone shares the site's link, so it is
redrawn with every build. It uses a system font (DejaVu Sans on the GitHub
runner, Arial on macOS/Windows), so the repo doesn't ship font files. Without
one it falls back to Pillow's bundled font, which lacks "€" and umlauts, and
spells those out instead.
"""

import os
from datetime import date
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 630
BG = "#121211"
INK = "#ffffff"
INK_2 = "#c3c2b7"
INK_3 = "#94938a"
LINE = "#2f2f2c"
ACCENT = "#3987e5"
SITE = "morty1338.github.io/werkstudent-radar"


FONTS = {
    False: [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ],
    True: [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ],
}


@lru_cache(maxsize=None)
def font_path(bold):
    return next((p for p in FONTS[bold] if os.path.exists(p)), None)


def font(size, bold=False):
    path = font_path(bold)
    return ImageFont.truetype(path, size) if path else ImageFont.load_default(size=size)


def text(draw, xy, value, size, fill, bold=False, anchor="la", max_width=None):
    if not font_path(bold):
        value = value.replace("€", "EUR ").replace("ü", "ue").replace("ä", "ae").replace("ö", "oe")
    f = font(size, bold)
    # Shrink rather than run into the next column; font metrics differ between systems.
    while max_width and size > 12 and draw.textlength(value, font=f) > max_width:
        size -= 2
        f = font(size, bold)
    # Pillow's bundled font has a single weight: fake bold with a thin stroke.
    stroke = max(1, size // 28) if bold and not font_path(bold) else 0
    draw.text(xy, value, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=fill)


def logo(draw, cx, cy, r):
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ACCENT)
    for rr in (r * 0.64, r * 0.29):
        draw.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline="#9cc3f2", width=2)
    draw.line((cx, cy, cx + r * 0.78, cy - r * 0.5), fill=INK, width=4)
    draw.ellipse((cx + r * 0.35, cy + r * 0.2, cx + r * 0.5, cy + r * 0.35), fill=INK)


def render(summary, path):
    t = summary["totals"]
    day = date.fromisoformat(summary["as_of"])
    as_of = f"{day.day} {day:%b %Y}"

    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(img)
    pad = 72

    logo(d, pad + 22, pad + 22, 22)
    text(d, (pad + 60, pad + 22), "Werkstudent Radar", 30, INK, bold=True, anchor="lm")
    text(d, (WIDTH - pad, pad + 22), "updated daily", 24, INK_3, anchor="rm")

    text(d, (pad, 170), "The German working-student", 58, INK, bold=True, max_width=WIDTH - 2 * pad)
    text(d, (pad, 238), "job market in numbers", 58, INK, bold=True, max_width=WIDTH - 2 * pad)

    stats = [
        (f"{t['jobs']:,}", "Werkstudent postings online"),
        (f"€{t['median_pay']:.2f}", "median pay per hour"),
        (f"{t['no_german_share'] * 100:.1f}%", "open without German"),
    ]
    col = (WIDTH - 2 * pad) / 3
    top = 360
    for i, (value, label) in enumerate(stats):
        x = pad + i * col
        width = col - 28 - 24  # inner padding plus a gap before the next column
        d.rectangle((x, top, x + 6, top + 120), fill=ACCENT)
        text(d, (x + 28, top + 4), value, 68, INK, bold=True, max_width=width)
        text(d, (x + 28, top + 92), label, 24, INK_2, max_width=width)

    d.line((pad, HEIGHT - 92, WIDTH - pad, HEIGHT - 92), fill=LINE, width=2)
    text(d, (pad, HEIGHT - 52), f"Data as of {as_of} · Bundesagentur für Arbeit", 24, INK_3, anchor="lm")
    text(d, (WIDTH - pad, HEIGHT - 52), SITE, 24, INK_2, anchor="rm")

    img.save(path, "PNG", optimize=True)
    return path
