"""
generate_stats_card.py
Generates a 512x512 player stats card image using Pillow.

Performance notes:
- Fonts are loaded once at import time and cached
- The static background (grid + accent bar) is built once per process
- Glow effects operate on a small cropped region, not the full canvas
Usage: python generate_stats_card.py [username]
Main usage is by calling generate_stats_card.py and executing by discord command: /search [username]
"""

from __future__ import annotations
import sys
import numpy as np
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter

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

SIZE = 512


# Load a font once and cache by (path, size).
@lru_cache(maxsize=None)
def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

# Pre-load every font variant used in rendering.
_FONTS = {
    (p, s): _load_font(p, s)
    for p, s in [
        (_FONT_BOLD,  28), (_FONT_BOLD,  26), (_FONT_BOLD,  18),
        (_FONT_BOLD,  14), (_FONT_BOLD,  12), (_FONT_BOLD,  10),
        (_FONT_MED,   11), (_FONT_MED,    9),
        (_FONT_LIGHT, 10), (_FONT_LIGHT,  9), (_FONT_LIGHT,  8),
    ]
}

def FB(size: int) -> ImageFont.FreeTypeFont: return _FONTS[(_FONT_BOLD,  size)]
def FM(size: int) -> ImageFont.FreeTypeFont: return _FONTS[(_FONT_MED,   size)]
def FL(size: int) -> ImageFont.FreeTypeFont: return _FONTS[(_FONT_LIGHT, size)]


# Build the shared background once: dark fill, grid lines, and top accent bar.
def _build_static_bg() -> Image.Image:
    arr = np.full((SIZE, SIZE, 3), BG_DARK, dtype=np.uint8)
    grid_color = np.array([12, 12, 20], dtype=np.uint8)
    for i in range(0, SIZE, 32):
        arr[i, :] = grid_color
        arr[:, i] = grid_color
    bg = Image.fromarray(arr, "RGB")
    draw = ImageDraw.Draw(bg, "RGBA")
    for thickness, alpha in [(4, 255), (12, 60), (28, 20)]:
        draw.rectangle([(0, 0), (SIZE, thickness)], fill=(*ACCENT, alpha))
    return bg.copy()

_STATIC_BG: Image.Image = _build_static_bg()


# Draw a soft glow behind a circle by blurring on a small cropped area.
def _glow_circle(img: Image.Image, cx: int, cy: int, r: int, color: tuple) -> None:
    margin = r + 30
    x0, y0 = max(cx - margin, 0), max(cy - margin, 0)
    x1, y1 = min(cx + margin, SIZE), min(cy + margin, SIZE)
    crop_w, crop_h = x1 - x0, y1 - y0

    glow = Image.new("RGBA", (crop_w, crop_h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    lcx, lcy = cx - x0, cy - y0
    for step in range(6, 0, -1):
        alpha = int(40 * (step / 6))
        rr = r + step * 4
        gd.ellipse((lcx - rr, lcy - rr, lcx + rr, lcy + rr), fill=(*color, alpha))

    glow = glow.filter(ImageFilter.GaussianBlur(radius=8))
    base_crop = img.crop((x0, y0, x1, y1)).convert("RGBA")
    img.paste(Image.alpha_composite(base_crop, glow).convert("RGB"), (x0, y0))


# Return the rendered pixel width of a text string.
def _tw(draw, text, fnt) -> int:
    b = draw.textbbox((0, 0), text, font=fnt)
    return b[2] - b[0]

def _rr(draw, xy, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)

def _progress_bar(draw, x, y, w, h, pct, color_fill, color_bg=(30, 33, 52), radius=4):
    _rr(draw, (x, y, x + w, y + h), radius, fill=color_bg)
    fill_w = max(int(w * min(pct, 1.0)), radius * 2 if pct > 0 else 0)
    if fill_w > 0:
        _rr(draw, (x, y, x + fill_w, y + h), radius, fill=color_fill)


def _kd(k, d) -> float:
    return round(k / d, 2) if d > 0 else float(k)

def _wr(w, l) -> float:
    t = w + l
    return round((w / t) * 100, 2) if t > 0 else 0.0

# Score from 0–100 estimating smurf likelihood based on rank, games played, K/D, and win rate.
def _smurf(kd, nrk, ranked_games, ranked_wr) -> float:
    f1 = 1.0 if nrk < 1000 else (max(0.0, 1 - (nrk - 1000) / 2000) if nrk <= 3000 else 0.0)
    f2 = 1.0 if ranked_games < 300 else (max(0.0, 1 - ranked_games / 600) if ranked_games <= 600 else 0.0)
    f3 = 1.0 if kd >= 1.3 else (kd / 1.3 if kd > 0 else 0.0)
    f4 = 1.0 if ranked_wr >= 65 else (ranked_wr / 65 if ranked_wr > 0 else 0.0)
    if nrk < 1000 and ranked_games < 300 and kd >= 1.3 and ranked_wr >= 65:
        return 100.0
    return round(min(40 * f1 + 30 * f2 + 20 * f3 + 10 * f4, 100), 2)


def parse_profile(profile: dict) -> dict:
    stats = profile.get("stats", {})
    clan_name = profile.get("clan", {}).get("basicInfo", {}).get("name", "-")
    seasonal_stats = stats.get("seasonal_stats", [])

    rk = {"k": 0, "d": 0, "w": 0, "l": 0}
    cur_ranked, cur_snum = None, -1
    ck = cd = xk = xd = 0

    for s in seasonal_stats:
        ranked = s.get("ranked", {})
        games  = ranked.get("w", 0) + ranked.get("l", 0)
        snum   = s.get("season", 0)
        if games > 0:
            for key in ("k", "d", "w", "l"):
                rk[key] += ranked.get(key, 0)
            if snum > cur_snum:
                cur_snum, cur_ranked = snum, ranked

        casual  = s.get("casual", {})
        custom  = s.get("custom", {})
        lobbies = s.get("custom_lobbies", {})
        ck += casual.get("k", 0);  cd += casual.get("d", 0)
        xk += custom.get("k", 0) + lobbies.get("k", 0)
        xd += custom.get("d", 0) + lobbies.get("d", 0)

    k, d, w, l = rk["k"], rk["d"], rk["w"], rk["l"]
    kd = _kd(k, d)
    winrate = _wr(w, l)
    total_r = w + l
    nrk, nrd = ck + xk, cd + xd
    cur = cur_ranked or {}

    c_k, c_d, c_w, c_l = cur.get("k", 0), cur.get("d", 0), cur.get("w", 0), cur.get("l", 0)

    return dict(
        clan=clan_name,
        season=cur_snum if cur_snum >= 0 else "-",
        c_k=c_k, c_d=c_d, c_w=c_w, c_l=c_l,
        c_kd=_kd(c_k, c_d), c_wr=_wr(c_w, c_l), c_games=c_w + c_l,
        k=k, d=d, w=w, l=l,
        kd=kd, winrate=winrate, total_ranked=total_r,
        nonranked_k=nrk, nonranked_kd=_kd(nrk, nrd),
        smurf=_smurf(kd, nrk, total_r, winrate),
    )


def render_stats_card(username: str, profile: dict) -> Image.Image:
    data = parse_profile(profile)

    # Copy the pre-built background so we never modify the shared original.
    img  = _STATIC_BG.copy()
    draw = ImageDraw.Draw(img, "RGBA")

    # Header: username, clan, current season badge.
    _rr(draw, (12, 16, SIZE - 12, 88), 10, fill=PANEL_BG, outline=PANEL_EDGE, width=1)
    draw.text((28, 24), username,                font=FB(26), fill=TEXT_HI)
    draw.text((28, 56), f"Clan: {data['clan']}", font=FM(11), fill=TEXT_MID)
    season_txt = f"S{data['season']}"
    sw = _tw(draw, season_txt, FB(14))
    _rr(draw, (SIZE - 28 - sw - 12, 28, SIZE - 24, 56), 6, fill=ACCENT)
    draw.text((SIZE - 28 - sw - 4, 32), season_txt, font=FB(14), fill=(20, 10, 0))

    # Smurf detection bar: green = clean, orange = suspicious, red = likely smurf.
    smurf_color = GREEN if data["smurf"] < 35 else ACCENT if data["smurf"] < 65 else RED_C
    _rr(draw, (12, 96, SIZE - 12, 132), 8, fill=PANEL_BG, outline=PANEL_EDGE, width=1)
    draw.text((24, 102), "SMURF DETECTION", font=FM(9), fill=TEXT_LOW)
    _progress_bar(draw, 24, 118, SIZE - 48, 6, data["smurf"] / 100, smurf_color)
    pct_txt = f"{data['smurf']}%"
    draw.text((SIZE - 24 - _tw(draw, pct_txt, FB(10)), 100), pct_txt, font=FB(10), fill=smurf_color)

    # Resolve shared panel fonts once to avoid repeated dict lookups.
    f_label = FL(10); f_val = FB(12); f_hdr = FM(9)

    def stat_panel(label, items, x, y, w, h):
        _rr(draw, (x, y, x + w, y + h), 8, fill=PANEL_BG, outline=PANEL_EDGE, width=1)
        draw.text((x + 10, y + 8), label, font=f_hdr, fill=TEXT_LOW)
        row_h = (h - 28) // max(len(items), 1)
        for i, (key, val, col) in enumerate(items):
            ry = y + 24 + i * row_h
            draw.text((x + 10, ry), key, font=f_label, fill=TEXT_MID)
            draw.text((x + w - 10 - _tw(draw, val, f_val), ry - 1), val, font=f_val, fill=col)

    stat_panel(
        f"CURRENT SEASON (S{data['season']})",
        [
            ("K / D",     f"{data['c_k']} / {data['c_d']}",  TEXT_HI),
            ("K/D Ratio", str(data["c_kd"]),  BLUE if data["c_kd"] >= 1 else RED_C),
            ("W / L",     f"{data['c_w']} / {data['c_l']}",  TEXT_HI),
            ("Win Rate",  f"{data['c_wr']}%", GREEN if data["c_wr"] >= 50 else RED_C),
            ("Games",     str(data["c_games"]),               TEXT_MID),
        ],
        12, 140, 238, 160,
    )
    stat_panel(
        "OVERALL RANKED",
        [
            ("K / D",     f"{data['k']} / {data['d']}",       TEXT_HI),
            ("K/D Ratio", str(data["kd"]),    BLUE if data["kd"] >= 1 else RED_C),
            ("W / L",     f"{data['w']} / {data['l']}",       TEXT_HI),
            ("Win Rate",  f"{data['winrate']}%", GREEN if data["winrate"] >= 50 else RED_C),
            ("Games",     str(data["total_ranked"]),           TEXT_MID),
        ],
        262, 140, 238, 160,
    )

    # Win rate ring with a glow effect underneath.
    ring_cx, ring_cy, ring_r = 90, 388, 54
    _glow_circle(img, ring_cx, ring_cy, ring_r, ACCENT)
    draw = ImageDraw.Draw(img, "RGBA")  # rebind draw after paste modifies the image

    draw.ellipse(
        (ring_cx - ring_r, ring_cy - ring_r, ring_cx + ring_r, ring_cy + ring_r),
        outline=(35, 38, 60), width=10,
    )
    wr_angle = 360 * (data["winrate"] / 100)
    if wr_angle > 0:
        bbox = (ring_cx - ring_r, ring_cy - ring_r, ring_cx + ring_r, ring_cy + ring_r)
        draw.arc(bbox, start=-90, end=-90 + wr_angle, fill=ACCENT, width=10)
    wr_str = f"{data['winrate']}%"
    draw.text((ring_cx - _tw(draw, wr_str, FB(14)) // 2, ring_cy - 12), wr_str, font=FB(14), fill=TEXT_HI)
    draw.text((ring_cx - _tw(draw, "WR",   FL(9))  // 2, ring_cy + 4),  "WR",   font=FL(9),  fill=TEXT_LOW)

    # Casual + custom stats panel.
    _rr(draw, (160, 312, SIZE - 12, 420), 8, fill=PANEL_BG, outline=PANEL_EDGE, width=1)
    draw.text((174, 320), "CASUAL + CUSTOM", font=FM(9), fill=TEXT_LOW)
    f_big = FB(18)
    for i, (lbl, val, col) in enumerate([
        ("Total Kills", f"{data['nonranked_k']:,}", TEXT_HI),
        ("K/D Ratio",   str(data["nonranked_kd"]),  BLUE),
    ]):
        ry = 340 + i * 36
        draw.text((174, ry),      lbl, font=FL(10), fill=TEXT_MID)
        draw.text((174, ry + 14), val, font=f_big,  fill=col)

    # Footer: overall K/D and total ranked games side by side.
    _rr(draw, (12, 430, SIZE - 12, 500), 8, fill=PANEL_BG, outline=PANEL_EDGE, width=1)
    kd_str = str(data["kd"])
    kd_col = BLUE if data["kd"] >= 1.0 else RED_C
    f_big2 = FB(28)
    draw.text((28, 440), "OVERALL K/D",                       font=FM(9),  fill=TEXT_LOW)
    draw.text((28, 455), kd_str,                              font=f_big2, fill=kd_col)
    draw.line([(SIZE // 2, 440), (SIZE // 2, 492)],           fill=PANEL_EDGE, width=1)
    draw.text((SIZE // 2 + 16, 440), "RANKED GAMES",         font=FM(9),  fill=TEXT_LOW)
    draw.text((SIZE // 2 + 16, 455), str(data["total_ranked"]), font=f_big2, fill=TEXT_HI)

    # Subtle watermark in the bottom-right corner.
    wm = "cwazy stats bot"
    f_wm = FL(8)
    draw.text((SIZE - _tw(draw, wm, f_wm) - 14, SIZE - 14), wm, font=f_wm, fill=TEXT_LOW)

    return img


def demo_profile(username: str = "ProPlayer") -> dict:
    import random
    rng = random.Random(hash(username) & 0xFFFFFF)

    def make_season(n, k_base, wr):
        k     = rng.randint(k_base, k_base + 300)
        games = rng.randint(80, 400)
        w     = int(games * wr)
        l     = games - w
        d     = max(1, int(k / rng.uniform(0.8, 2.2)))
        return {
            "season": n,
            "ranked":         {"k": k, "d": d, "w": w, "l": l},
            "casual":         {"k": rng.randint(200, 800), "d": rng.randint(200, 600)},
            "custom":         {"k": rng.randint(50, 200),  "d": rng.randint(50, 200)},
            "custom_lobbies": {"k": rng.randint(10, 80),   "d": rng.randint(10, 80)},
        }

    return {
        "clan":  {"basicInfo": {"name": "CWAZY"}},
        "stats": {"seasonal_stats": [
            make_season(s, 400 + s * 50, rng.uniform(0.48, 0.72)) for s in range(1, 6)
        ]},
    }


if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "xSyrnyk"
    profile  = demo_profile(username)
    img = render_stats_card(username, profile)
    out = "/mnt/user-data/outputs/stats_card.png"
    img.save(out, "PNG", optimize=True)
    print(f"Saved -> {out}  ({img.size[0]}x{img.size[1]}px)")