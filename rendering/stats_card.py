"""
rendering/stats_card.py

Generates a 1024×1024 player stats card image using Pillow.
Accepts only pre-parsed data — all calculations live in core/.

Performance:
- _STATIC_TEMPLATE is built ONCE at import time and contains:
    background, grid, accent gradient, all panel shapes/borders,
    static labels, win-rate ring glow + track, watermark.
- render_stats_card() copies the template and draws ONLY dynamic
    elements: text, numbers, progress bars, arcs.
- Glow compositing (the most expensive step) never runs per-render.
"""

from __future__ import annotations

import logging
import os
import numpy as np
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter

_log = logging.getLogger(__name__)

_FONT_BOLD  = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
_FONT_MED   = "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf"
_FONT_LIGHT = "/usr/share/fonts/truetype/google-fonts/Poppins-Light.ttf"

BG_DARK    = (10, 10, 18)
PANEL_BG   = (18, 20, 32)
PANEL_EDGE = (35, 38, 60)
ACCENT     = (255, 140, 0)
TEXT_HI    = (240, 240, 255)
TEXT_MID   = (160, 165, 200)
TEXT_LOW   = (90, 95, 130)
GREEN      = (80, 220, 120)
RED_C      = (220, 80, 80)
BLUE       = (80, 160, 255)

SIZE = 1024

# Stat-panel geometry — fixed for 5 rows, used by both template builder and renderer
_PANEL_W = 476
_PANEL_H = 320
_ROW_H   = (_PANEL_H - 56) // 5   # 52 px per row
_ROW_KEYS = ("K / D", "K/D Ratio", "W / L", "Win Rate", "Games")

# Win-rate ring geometry
_RING_CX, _RING_CY, _RING_R = 180, 730, 108


# ── Proportional font scale system ───────────────────────────────────────────
#
# SCALE is derived from the 512px design base. Each tier uses a different
# power exponent so that large display text scales linearly while small UI
# labels scale sub-linearly, preserving visual hierarchy without over-scaling.
#
#   exp ≈ 1.00 → display text  (title, big footer numbers)  — full linear
#   exp ≈ 0.90 → mid values    (casual display, badges)
#   exp ≈ 0.85 → stat values   (row numbers, clan text)
#   exp ≈ 0.75 → UI labels     (row keys, section headers)
#   exp ≈ 0.65 → micro text    (watermark)

SCALE      = SIZE / 512  # 2.0 at 1024px
FONT_SCALE = 1.0         # global font size multiplier — increase to enlarge all text


def _fs(base: int, exp: float = 1.0) -> int:
    """Scale a 512-base font size using a power curve, then apply FONT_SCALE."""
    return round(base * FONT_SCALE * (SCALE ** exp))


# Named font size constants (computed once; values shown for SCALE=2, FONT_SCALE=2):
_F_TITLE   = _fs(26)         # 104  — username headline          (linear)
_F_DISPLAY = _fs(28)         # 112  — footer large numbers       (linear)
_F_VAL_LG  = _fs(18, 0.95)  #  70  — casual display values
_F_BADGE   = _fs(14, 0.95)  #  54  — season badge / WR ring text
_F_VAL_SM  = _fs(12, 0.95)  #  46  — stat row values
_F_CLAN    = _fs(11, 0.90)  #  41  — clan text
_F_BAR_PCT = _fs(10, 0.90)  #  37  — smurf bar percentage
_F_KEY     = _fs(10, 0.90)  #  37  — stat row key labels
_F_HDR     = _fs( 9, 0.90)  #  34  — section headers
_F_WR_LBL  = _fs( 9, 0.80)  #  31  — "WR" ring label  (decorative)
_F_WATER   = _fs( 8, 0.75)  #  27  — watermark         (decorative)


@lru_cache(maxsize=None)
def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        if not os.path.exists(path):
            _log.warning(
                "Font file not found: %s — falling back to default (font sizes will NOT scale)", path
            )
        return ImageFont.load_default(size=size)


_FONTS = {
    (p, s): _load_font(p, s)
    for p, s in [
        (_FONT_BOLD,  _F_TITLE),    # computed from _fs(26)        → 104
        (_FONT_BOLD,  _F_DISPLAY),  # computed from _fs(28)        → 112
        (_FONT_BOLD,  _F_VAL_LG),  # computed from _fs(18, 0.95)  →  70
        (_FONT_BOLD,  _F_BADGE),   # computed from _fs(14, 0.95)  →  54
        (_FONT_BOLD,  _F_VAL_SM),  # computed from _fs(12, 0.95)  →  46
        (_FONT_BOLD,  _F_BAR_PCT), # computed from _fs(10, 0.90)  →  37
        (_FONT_MED,   _F_CLAN),    # computed from _fs(11, 0.90)  →  41
        (_FONT_MED,   _F_HDR),     # computed from _fs( 9, 0.90)  →  34
        (_FONT_LIGHT, _F_KEY),     # computed from _fs(10, 0.90)  →  37
        (_FONT_LIGHT, _F_WR_LBL), # computed from _fs( 9, 0.80)  →  31
        (_FONT_LIGHT, _F_WATER),   # computed from _fs( 8, 0.75)  →  27
    ]
}


def FB(size: int) -> ImageFont.FreeTypeFont: return _FONTS[(_FONT_BOLD,  size)]
def FM(size: int) -> ImageFont.FreeTypeFont: return _FONTS[(_FONT_MED,   size)]
def FL(size: int) -> ImageFont.FreeTypeFont: return _FONTS[(_FONT_LIGHT, size)]


# ── Drawing primitives ────────────────────────────────────────────────────────

def _tw(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> int:
    b = draw.textbbox((0, 0), text, font=fnt)
    return b[2] - b[0]


def _rr(
    draw: ImageDraw.ImageDraw,
    xy: tuple,
    radius: int,
    fill: tuple | None = None,
    outline: tuple | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _progress_bar(
    draw: ImageDraw.ImageDraw,
    x: int, y: int, w: int, h: int,
    pct: float,
    color_fill: tuple,
    color_bg: tuple = (30, 33, 52),
    radius: int = 8,
) -> None:
    _rr(draw, (x, y, x + w, y + h), radius, fill=color_bg)
    fill_w = max(int(w * min(pct, 1.0)), radius * 2 if pct > 0 else 0)
    if fill_w > 0:
        _rr(draw, (x, y, x + fill_w, y + h), radius, fill=color_fill)


def _glow_circle(img: Image.Image, cx: int, cy: int, r: int, color: tuple) -> None:
    margin = r + 60
    x0, y0 = max(cx - margin, 0), max(cy - margin, 0)
    x1, y1 = min(cx + margin, SIZE), min(cy + margin, SIZE)
    crop_w, crop_h = x1 - x0, y1 - y0

    glow = Image.new("RGBA", (crop_w, crop_h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    lcx, lcy = cx - x0, cy - y0
    for step in range(6, 0, -1):
        alpha = int(40 * (step / 6))
        rr = r + step * 8
        gd.ellipse((lcx - rr, lcy - rr, lcx + rr, lcy + rr), fill=(*color, alpha))

    glow = glow.filter(ImageFilter.GaussianBlur(radius=16))
    base_crop = img.crop((x0, y0, x1, y1)).convert("RGBA")
    img.paste(Image.alpha_composite(base_crop, glow).convert("RGB"), (x0, y0))


def _accent_gradient(img: Image.Image) -> None:
    """
    Smooth ACCENT-color top gradient composited over the background.

    Structure: an 8px fully-opaque cap at the very top (the solid bar edge),
    followed by a power-curve decay to fully transparent over 48px.
    Using alpha_composite ensures correct blending over the dark background
    with no visible banding.
    """
    height = 56   # total gradient band height in px
    cap    = 8    # fully-opaque top cap

    alpha = np.empty(height, dtype=np.float32)
    alpha[:cap] = 255.0
    t = np.linspace(0.0, 1.0, height - cap, endpoint=True)
    alpha[cap:] = 255.0 * (1.0 - t) ** 1.5
    alpha = np.clip(alpha, 0, 255).astype(np.uint8)

    r, g, b = ACCENT
    layer = np.empty((height, SIZE, 4), dtype=np.uint8)
    layer[:, :, 0] = r
    layer[:, :, 1] = g
    layer[:, :, 2] = b
    layer[:, :, 3] = alpha[:, np.newaxis]   # broadcast across full width

    grad_img  = Image.fromarray(layer, "RGBA")
    base_crop = img.crop((0, 0, SIZE, height)).convert("RGBA")
    img.paste(Image.alpha_composite(base_crop, grad_img).convert("RGB"), (0, 0))


# ── Static template builder ───────────────────────────────────────────────────

def _build_static_template() -> Image.Image:
    # Background + grid
    arr = np.full((SIZE, SIZE, 3), BG_DARK, dtype=np.uint8)
    grid_color = np.array([12, 12, 20], dtype=np.uint8)
    for i in range(0, SIZE, 64):
        arr[i, :] = grid_color
        arr[:, i] = grid_color
    img = Image.fromarray(arr, "RGB")

    # Smooth top accent gradient (replaces blocky rectangles)
    _accent_gradient(img)
    draw = ImageDraw.Draw(img, "RGBA")  # bind draw after gradient paste

    # Header panel — username/clan/season badge drawn dynamically
    _rr(draw, (24, 32, SIZE - 24, 176), 20, fill=PANEL_BG, outline=PANEL_EDGE, width=2)

    # Smurf detection panel + static label
    _rr(draw, (24, 192, SIZE - 24, 264), 16, fill=PANEL_BG, outline=PANEL_EDGE, width=2)
    draw.text((48, 204), "SMURF DETECTION", font=FM(_F_HDR), fill=TEXT_LOW)

    # Current-season stat panel + static row key labels
    cx, cy = 24, 280
    _rr(draw, (cx, cy, cx + _PANEL_W, cy + _PANEL_H), 16, fill=PANEL_BG, outline=PANEL_EDGE, width=2)
    for i, key in enumerate(_ROW_KEYS):
        draw.text((cx + 20, cy + 48 + i * _ROW_H), key, font=FL(_F_KEY), fill=TEXT_MID)

    # Overall ranked stat panel + header label + static row key labels
    ox, oy = 524, 280
    _rr(draw, (ox, oy, ox + _PANEL_W, oy + _PANEL_H), 16, fill=PANEL_BG, outline=PANEL_EDGE, width=2)
    draw.text((ox + 20, oy + 16), "OVERALL RANKED", font=FM(_F_HDR), fill=TEXT_LOW)
    for i, key in enumerate(_ROW_KEYS):
        draw.text((ox + 20, oy + 48 + i * _ROW_H), key, font=FL(_F_KEY), fill=TEXT_MID)

    # Win-rate ring: expensive glow compositing done once here
    _glow_circle(img, _RING_CX, _RING_CY, _RING_R, ACCENT)
    draw = ImageDraw.Draw(img, "RGBA")  # rebind after paste
    draw.ellipse(
        (_RING_CX - _RING_R, _RING_CY - _RING_R, _RING_CX + _RING_R, _RING_CY + _RING_R),
        outline=(35, 38, 60), width=20,
    )

    # Casual + custom panel + static labels
    _rr(draw, (320, 624, SIZE - 24, 840), 16, fill=PANEL_BG, outline=PANEL_EDGE, width=2)
    draw.text((348, 640), "CASUAL + CUSTOM", font=FM(_F_HDR), fill=TEXT_LOW)
    draw.text((348, 680), "Total Kills",     font=FL(_F_KEY), fill=TEXT_MID)
    draw.text((348, 752), "K/D Ratio",       font=FL(_F_KEY), fill=TEXT_MID)

    # Footer panel + divider + static labels
    _rr(draw, (24, 860, SIZE - 24, 1000), 16, fill=PANEL_BG, outline=PANEL_EDGE, width=2)
    draw.line([(SIZE // 2, 880), (SIZE // 2, 984)], fill=PANEL_EDGE, width=2)
    draw.text((56,               880), "OVERALL K/D",  font=FM(_F_HDR), fill=TEXT_LOW)
    draw.text((SIZE // 2 + 32,   880), "RANKED GAMES", font=FM(_F_HDR), fill=TEXT_LOW)

    # Watermark
    wm = "cwazy stats bot"
    draw.text((SIZE - _tw(draw, wm, FL(_F_WATER)) - 28, SIZE - 28), wm, font=FL(_F_WATER), fill=TEXT_LOW)

    return img.copy()


_STATIC_TEMPLATE: Image.Image = _build_static_template()


# ── Public render function ────────────────────────────────────────────────────

def render_stats_card(data: dict) -> Image.Image:
    """
    Render a 1024×1024 stats card from pre-parsed profile data.

    Expected keys in `data`:
        username        str
        clan            str
        current_season  int | str
        current         dict  (kills, deaths, wins, losses, kd, winrate, games)
        ranked          dict  (kills, deaths, wins, losses, kd, winrate, total_games)
        non_ranked      dict  (kills, deaths, kd)
        smurf_score     float
    """
    username: str       = data["username"]
    current_season      = data["current_season"]
    current: dict       = data["current"]
    ranked: dict        = data["ranked"]
    non_ranked: dict    = data["non_ranked"]
    smurf_score: float  = data["smurf_score"]

    img = _STATIC_TEMPLATE.copy()
    draw = ImageDraw.Draw(img, "RGBA")

    # ── Header ───────────────────────────────────────────────────
    draw.text((56, 48),  username,                font=FB(_F_TITLE), fill=TEXT_HI)
    draw.text((56, 112), f"Clan: {data['clan']}", font=FM(_F_CLAN),  fill=TEXT_MID)
    season_txt = f"S{current_season}"
    sw = _tw(draw, season_txt, FB(_F_BADGE))
    _rr(draw, (SIZE - 56 - sw - 24, 56, SIZE - 48, 112), 12, fill=ACCENT)
    draw.text((SIZE - 56 - sw - 8, 64), season_txt, font=FB(_F_BADGE), fill=(20, 10, 0))

    # ── Smurf detection bar ──────────────────────────────────────
    smurf_color = GREEN if smurf_score < 35 else ACCENT if smurf_score < 65 else RED_C
    _progress_bar(draw, 48, 236, SIZE - 96, 12, smurf_score / 100, smurf_color)
    pct_txt = f"{smurf_score}%"
    draw.text((SIZE - 48 - _tw(draw, pct_txt, FB(_F_BAR_PCT)), 200), pct_txt, font=FB(_F_BAR_PCT), fill=smurf_color)

    # ── Current-season stat values ───────────────────────────────
    cx, cy = 24, 280
    draw.text((cx + 20, cy + 16), f"CURRENT SEASON (S{current_season})", font=FM(_F_HDR), fill=TEXT_LOW)
    current_vals = [
        (f"{current['kills']} / {current['deaths']}",              TEXT_HI),
        (str(current["kd"]),   BLUE if current["kd"] >= 1 else RED_C),
        (f"{current['wins']} / {current['losses']}",               TEXT_HI),
        (f"{current['winrate']}%", GREEN if current["winrate"] >= 50 else RED_C),
        (str(current["games"]),                                     TEXT_MID),
    ]
    for i, (val, col) in enumerate(current_vals):
        ry = cy + 48 + i * _ROW_H
        draw.text((cx + _PANEL_W - 20 - _tw(draw, val, FB(_F_VAL_SM)), ry - 2), val, font=FB(_F_VAL_SM), fill=col)

    # ── Overall ranked stat values ───────────────────────────────
    ox, oy = 524, 280
    ranked_vals = [
        (f"{ranked['kills']} / {ranked['deaths']}",                TEXT_HI),
        (str(ranked["kd"]),    BLUE if ranked["kd"] >= 1 else RED_C),
        (f"{ranked['wins']} / {ranked['losses']}",                 TEXT_HI),
        (f"{ranked['winrate']}%", GREEN if ranked["winrate"] >= 50 else RED_C),
        (str(ranked["total_games"]),                                TEXT_MID),
    ]
    for i, (val, col) in enumerate(ranked_vals):
        ry = oy + 48 + i * _ROW_H
        draw.text((ox + _PANEL_W - 20 - _tw(draw, val, FB(_F_VAL_SM)), ry - 2), val, font=FB(_F_VAL_SM), fill=col)

    # ── Win-rate arc + center text ───────────────────────────────
    wr_angle = 360 * (ranked["winrate"] / 100)
    if wr_angle > 0:
        bbox = (_RING_CX - _RING_R, _RING_CY - _RING_R, _RING_CX + _RING_R, _RING_CY + _RING_R)
        draw.arc(bbox, start=-90, end=-90 + wr_angle, fill=ACCENT, width=20)
    wr_str = f"{ranked['winrate']}%"
    draw.text((_RING_CX - _tw(draw, wr_str,  FB(_F_BADGE))  // 2, _RING_CY - 24), wr_str, font=FB(_F_BADGE),  fill=TEXT_HI)
    draw.text((_RING_CX - _tw(draw, "WR",    FL(_F_WR_LBL)) // 2, _RING_CY + 8),  "WR",   font=FL(_F_WR_LBL), fill=TEXT_LOW)

    # ── Casual + custom values ───────────────────────────────────
    draw.text((348, 708), f"{non_ranked['kills']:,}", font=FB(_F_VAL_LG), fill=TEXT_HI)
    draw.text((348, 780), str(non_ranked["kd"]),      font=FB(_F_VAL_LG), fill=BLUE)

    # ── Footer values ────────────────────────────────────────────
    kd_col = BLUE if ranked["kd"] >= 1.0 else RED_C
    draw.text((56,               910), str(ranked["kd"]),          font=FB(_F_DISPLAY), fill=kd_col)
    draw.text((SIZE // 2 + 32,   910), str(ranked["total_games"]), font=FB(_F_DISPLAY), fill=TEXT_HI)

    return img
