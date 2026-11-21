#!/usr/bin/env python3
"""Draw one 1024x1024 front-page summary of 21 November 2026 world news.

Everything on the page is typeset by this program with PIL and the Noto
fonts bundled in fonts/. No network, no randomness, no clock: two runs
write byte-identical PNG files.

Run:  mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "out"))

CANVAS_W = 1024
CANVAS_H = 1024
MARGIN = 46

# ---- palette: ink, paper and three restrained accents -----------------------
PAPER = (250, 247, 238)      # warm off-white page
INK = (24, 28, 32)           # near-black text
BODY_INK = (52, 58, 64)      # body copy
TEAL = (13, 58, 69)          # masthead band
TEAL_DARK = (9, 42, 50)      # bottom strip band
GOLD = (198, 155, 58)        # rules and small caps
RUST = (178, 58, 32)         # kicker red
SLATE = (88, 96, 104)        # secondary text
HAIRLINE = (196, 188, 172)   # thin dividers
CARD = (255, 253, 247)       # story card fill
CHIP = (13, 58, 69)          # number badge fill
WHITE = (255, 255, 255)
PALE = (235, 238, 240)       # light text on dark bands


def load_font(name, size):
    """Load a bundled Noto font; fall back to PIL's bitmap font if absent."""
    path = HERE / "fonts" / name
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


FONTS = {
    "masthead": load_font("NotoSerifDisplay-Black.ttf", 56),
    "dateline": load_font("NotoSans-Bold.ttf", 19),
    "kicker": load_font("NotoSans-Bold.ttf", 19),
    "lead_head": load_font("NotoSerif-Bold.ttf", 41),
    "lead_deck": load_font("NotoSans-Regular.ttf", 22),
    "story_head": load_font("NotoSans-Bold.ttf", 25),
    "story_body": load_font("NotoSans-Regular.ttf", 20),
    "wide_head": load_font("NotoSans-Bold.ttf", 25),
    "wide_body": load_font("NotoSans-Regular.ttf", 20),
    "also_head": load_font("NotoSans-Bold.ttf", 19),
    "also_body": load_font("NotoSans-Regular.ttf", 19),
    "source": load_font("NotoSans-Regular.ttf", 16),
    "footer": load_font("NotoSans-Regular.ttf", 15),
    "badge": load_font("NotoSans-Bold.ttf", 22),
}


def wrap_text(draw, text, font, max_width):
    """Greedy word wrap; returns a list of lines that fit max_width."""
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            trial = current + " " + word
            if draw.textlength(trial, font=font) <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def draw_lines(draw, x, y, lines, font, fill, leading):
    """Draw lines top-down; return the y just below the last line."""
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += leading
    return y


def fit_block(draw, x, y, width, text, font, leading, max_lines, fill=INK):
    """Wrap text into at most max_lines; raise if it will not fit."""
    lines = wrap_text(draw, text, font, width)
    if len(lines) > max_lines:
        raise ValueError(f"text needs {len(lines)} lines, only {max_lines} fit: {text!r}")
    return draw_lines(draw, x, y, lines, font, fill, leading)


def draw_badge(draw, cx, cy, number):
    """Numbered circle badge used to anchor each story."""
    r = 17
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=CHIP)
    label = str(number)
    w = draw.textlength(label, font=FONTS["badge"])
    draw.text((cx - w / 2, cy - 14), label, font=FONTS["badge"], fill=WHITE)


def draw_masthead(draw):
    """Teal band with the paper name, the date and a gold rule."""
    draw.rectangle([0, 0, CANVAS_W, 116], fill=TEAL)
    title = "THE WORLD TODAY"
    tw = draw.textlength(title, font=FONTS["masthead"])
    draw.text(((CANVAS_W - tw) / 2, 14), title, font=FONTS["masthead"], fill=WHITE)
    date = "SATURDAY, 21 NOVEMBER 2026"
    dw = draw.textlength(date, font=FONTS["dateline"])
    draw.text(((CANVAS_W - dw) / 2, 82), date, font=FONTS["dateline"], fill=GOLD)
    draw.rectangle([0, 116, CANVAS_W, 120], fill=GOLD)


def draw_lead(draw):
    """Full-width lead story: COP31 overtime in Antalya. Returns bottom y."""
    x = MARGIN
    y = 128
    draw.text((x, y), "CLIMATE  ·  ANTALYA, TÜRKIYE", font=FONTS["kicker"], fill=RUST)
    y += 28
    y = fit_block(
        draw, x, y, CANVAS_W - 2 * MARGIN,
        "COP31 runs into overtime as fossil fuels vanish from the draft deal",
        FONTS["lead_head"], leading=48, max_lines=2,
    )
    y += 4
    y = fit_block(
        draw, x, y, CANVAS_W - 2 * MARGIN,
        "Negotiators from nearly 200 countries fail to agree a final text in "
        "Antalya; the slimmed-down draft drops every mention of fossil fuels.",
        FONTS["lead_deck"], leading=29, max_lines=2, fill=BODY_INK,
    )
    y += 4
    draw.text((x, y), "Sources: Reuters · UN News · AP", font=FONTS["source"], fill=SLATE)
    return y + 20


def draw_story_card(draw, x, y, w, h, number, kicker, headline, body, source):
    """One grid card: badge + kicker row, headline, short body, source line."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=CARD,
                           outline=HAIRLINE, width=1)
    pad = 18
    ix = x + pad
    draw_badge(draw, ix + 17, y + 29, number)
    draw.text((ix + 44, y + 18), kicker, font=FONTS["kicker"], fill=RUST)
    iy = y + 52
    iy = fit_block(draw, ix, iy, w - 2 * pad, headline,
                   FONTS["story_head"], leading=28, max_lines=2)
    iy += 3
    fit_block(draw, ix, iy, w - 2 * pad, body,
              FONTS["story_body"], leading=24, max_lines=3, fill=BODY_INK)
    draw.text((ix, y + h - 22), source, font=FONTS["source"], fill=SLATE)
    return y + h


def draw_wide_story(draw, x, y, w, h, number, kicker, headline, body, source):
    """Full-width strip story: badge left, headline + two-line body right."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=CARD,
                           outline=HAIRLINE, width=1)
    pad = 18
    draw_badge(draw, x + pad + 17, y + h // 2, number)
    tx = x + pad + 52
    tw = w - pad - 52 - pad
    draw.text((tx, y + 10), kicker, font=FONTS["kicker"], fill=RUST)
    sw = draw.textlength(source, font=FONTS["source"])
    draw.text((x + w - pad - sw, y + 10), source, font=FONTS["source"], fill=SLATE)
    if draw.textlength(headline, font=FONTS["wide_head"]) > tw:
        raise ValueError(f"wide headline too long: {headline!r}")
    draw.text((tx, y + 34), headline, font=FONTS["wide_head"], fill=INK)
    fit_block(draw, tx, y + 61, tw, body,
              FONTS["wide_body"], leading=24, max_lines=2, fill=BODY_INK)
    return y + h


def draw_also_today(draw, y, h):
    """Dark band with two short items that did not make the main grid."""
    draw.rectangle([0, y, CANVAS_W, y + h], fill=TEAL_DARK)
    draw.text((MARGIN, y + 8), "ALSO TODAY", font=FONTS["also_head"], fill=GOLD)
    col_w = (CANVAS_W - 2 * MARGIN - 30) // 2
    items = [
        "Trump: Iran wants a deal, but terms are unacceptable; US "
        "sanctions four trustees.  (AP)",
        "India\u2019s NSE passes Nasdaq as the world\u2019s fifth-largest listed "
        "exchange.  (Reuters)",
    ]
    iy = y + 32
    for i, item in enumerate(items):
        x = MARGIN + i * (col_w + 30)
        fit_block(draw, x, iy, col_w, item, FONTS["also_body"],
                  leading=23, max_lines=2, fill=PALE)
    return y + h


def build_image():
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), PAPER)
    draw = ImageDraw.Draw(img)

    draw_masthead(draw)
    y = draw_lead(draw)
    draw.line([(MARGIN, y), (CANVAS_W - MARGIN, y)], fill=HAIRLINE, width=2)

    grid_y = y + 12
    card_w = (CANVAS_W - 2 * MARGIN - 20) // 2
    card_h = 210
    gap = 20
    stories = [
        (1, "DENMARK  ·  ESPIONAGE",
         "Denmark foils \u201cRussian plot to kill rapper\u201d and expels envoy",
         "PET says Russia plotted to kill rapper Kyivstoner in Copenhagen; "
         "two men charged.",
         "Sources: PET · Reuters · Al Jazeera"),
        (2, "STRAIT OF HORMUZ",
         "Tanker hit by projectile catches fire off Oman",
         "Hit 8 nautical miles north of Oman\u2019s Khasab; fire reported "
         "on board, no casualties.",
         "Sources: UKMTO · Reuters"),
        (3, "UKRAINE  ·  KYIV",
         "Russian strikes kill eight in Kyiv as France seeks UN meeting",
         "Missiles and drones hit Kyiv and energy sites; Estonia to shut "
         "its Russia crossings.",
         "Sources: AP · Reuters"),
        (4, "INDIA  ·  WEATHER",
         "Cyclone Akvan weakens after landfall on India\u2019s east coast",
         "The storm crosses the Odisha coast near Gopalpur, bringing "
         "heavy rain and disruption.",
         "Sources: Jagran Josh · The Hindu"),
    ]
    for i, story in enumerate(stories):
        cx = MARGIN + (i % 2) * (card_w + gap)
        cy = grid_y + (i // 2) * (card_h + 10)
        draw_story_card(draw, cx, cy, card_w, card_h, *story)

    wide_y = grid_y + 2 * card_h + 10 + 12
    draw_wide_story(
        draw, MARGIN, wide_y, CANVAS_W - 2 * MARGIN, 116,
        5, "MARKETS  ·  TECH",
        "Anthropic shares slide after record $81.3bn IPO debut",
        "Shares pull back after the biggest IPO ever opened 34% higher; "
        "US stocks fall for a fifth straight session.",
        "Source: Reuters",
    )

    also_y = wide_y + 116 + 10
    also_h = 80
    bottom = draw_also_today(draw, also_y, also_h)

    footer = ("All stories from reporting first published on 21 November 2026  ·  "
              "Drawn entirely by code — no photography, no AI imagery")
    fw = draw.textlength(footer, font=FONTS["footer"])
    draw.text(((CANVAS_W - fw) / 2, CANVAS_H - 21), footer,
              font=FONTS["footer"], fill=SLATE)
    if bottom > CANVAS_H - 26:
        raise ValueError(f"layout overflow: bottom band ends at {bottom}")
    return img


def main():
    img = build_image()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / "entry.png"
    img.save(target, format="PNG")
    print(f"wrote {target} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
