import io
import aiohttp
import discord
from generate_stats_card import render_stats_card

API_URL = "https://1-60-0.prod.copsapi.criticalforce.fi/api/public/profile"

# ============================================================
# GLOBAL SESSION (REUSED)
# ============================================================

SESSION: aiohttp.ClientSession | None = None


async def get_session() -> aiohttp.ClientSession:
    global SESSION

    if SESSION is None or SESSION.closed:
        SESSION = aiohttp.ClientSession()

    return SESSION


async def close_session():
    global SESSION
    if SESSION and not SESSION.closed:
        await SESSION.close()


# ============================================================
# Math Helpers
# ============================================================

def calculate_kd(k: int, d: int) -> float:
    return round(k / d, 2) if d > 0 else float(k)


def calculate_winrate(w: int, l: int) -> float:
    total = w + l
    return round((w / total) * 100, 2) if total > 0 else 0.0


def calculate_smurf_percentage(
    kd: float,
    total_kills_non_ranked: int,
    ranked_games: int,
    ranked_winrate: float
) -> float:

    if total_kills_non_ranked < 1000:
        f1 = 1.0
    elif total_kills_non_ranked <= 3000:
        f1 = max(0, 1 - (total_kills_non_ranked - 1000) / 2000)
    else:
        f1 = 0.0

    if ranked_games < 300:
        f2 = 1.0
    elif ranked_games <= 600:
        f2 = max(0, 1 - ranked_games / 600)
    else:
        f2 = 0.0

    f3 = 1.0 if kd >= 1.3 else (kd / 1.3 if kd > 0 else 0)
    f4 = 1.0 if ranked_winrate >= 65 else (ranked_winrate / 65 if ranked_winrate > 0 else 0)

    score = 40 * f1 + 30 * f2 + 20 * f3 + 10 * f4

    if (
        total_kills_non_ranked < 1000 and
        ranked_games < 300 and
        kd >= 1.3 and
        ranked_winrate >= 65
    ):
        return 100.0

    return round(min(score, 100), 2)


# ============================================================
# API FETCH
# ============================================================

async def get_profile_info(username: str):
    try:
        session = await get_session()
        url = f"{API_URL}?usernames={username}"

        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:

            if response.status != 200:
                return None

            data = await response.json()

            if not isinstance(data, list) or not data:
                return None

            return data[0]

    except Exception:
        return None


# ============================================================
# STATS CARD IMAGE
# ============================================================

def build_stats_image(username: str, profile: dict) -> discord.File:
    """Render a 512×512 stats card and return it as a discord.File."""
    img = render_stats_card(username, profile)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return discord.File(buf, filename="stats.png")


# ============================================================
# EMBED BUILDERS
# ============================================================

def build_main_embed(username, profile):
    stats = profile.get("stats", {})
    clan_name = profile.get("clan", {}).get("basicInfo", {}).get("name", "Unknown")

    ranked_totals = {"k": 0, "d": 0, "w": 0, "l": 0}
    current_ranked = None
    current_season_number = -1
    seasons_data = []

    seasonal_stats = stats.get("seasonal_stats", [])

    for season in seasonal_stats:
        ranked = season.get("ranked", {})
        games = ranked.get("w", 0) + ranked.get("l", 0)

        if games > 0:
            season_number = season.get("season", 0)

            ranked_totals["k"] += ranked.get("k", 0)
            ranked_totals["d"] += ranked.get("d", 0)
            ranked_totals["w"] += ranked.get("w", 0)
            ranked_totals["l"] += ranked.get("l", 0)

            seasons_data.append((season_number, games))

            if season_number > current_season_number:
                current_season_number = season_number
                current_ranked = ranked

    k = ranked_totals["k"]
    d = ranked_totals["d"]
    w = ranked_totals["w"]
    l = ranked_totals["l"]

    kd = calculate_kd(k, d)
    winrate = calculate_winrate(w, l)
    total_ranked_games = w + l

    if current_ranked:
        c_k = current_ranked.get("k", 0)
        c_d = current_ranked.get("d", 0)
        c_w = current_ranked.get("w", 0)
        c_l = current_ranked.get("l", 0)
        c_kd = calculate_kd(c_k, c_d)
        c_winrate = calculate_winrate(c_w, c_l)
    else:
        c_k = c_d = c_w = c_l = c_kd = c_winrate = 0

    most_played = ("", 0)

    for season_number, games in seasons_data:
        pct = round((games / total_ranked_games) * 100, 2) if total_ranked_games else 0
        if pct > most_played[1]:
            most_played = (season_number, pct)

    casual_k = casual_d = custom_k = custom_d = 0

    for season in seasonal_stats:
        casual = season.get("casual", {})
        custom = season.get("custom", {})
        custom_lobbies = season.get("custom_lobbies", {})

        casual_k += casual.get("k", 0)
        casual_d += casual.get("d", 0)

        custom_k += custom.get("k", 0)
        custom_d += custom.get("d", 0)

        custom_k += custom_lobbies.get("k", 0)
        custom_d += custom_lobbies.get("d", 0)

    total_k = casual_k + custom_k
    total_d = casual_d + custom_d
    total_kd = calculate_kd(total_k, total_d)

    smurf_pct = calculate_smurf_percentage(
        kd=kd,
        total_kills_non_ranked=total_k,
        ranked_games=total_ranked_games,
        ranked_winrate=winrate
    )

    embed = discord.Embed(
        title=f"📊 Profile Stats — {username}",
        color=discord.Color.orange()
    )

    embed.add_field(name="Clan", value=clan_name, inline=False)
    embed.add_field(name="Smurf Detection %", value=f"{smurf_pct}%", inline=False)

    embed.add_field(
        name="Current Ranked Stats",
        value=(
            f"K: {c_k} | W: {c_w}\n"
            f"D: {c_d} | L: {c_l}\n"
            f"KD: {c_kd} | WinRate: {c_winrate}%\n"
            f"Played Games: {c_w + c_l}"
        ),
        inline=False
    )

    embed.add_field(
        name="Overall Ranked",
        value=(
            f"K: {k} | W: {w}\n"
            f"D: {d} | L: {l}\n"
            f"KD: {kd} | WinRate: {winrate}%\n"
            f"Played Games: {total_ranked_games}"
        ),
        inline=False
    )

    if most_played[0] != "":
        embed.add_field(
            name="Most Played Season",
            value=f"Season {most_played[0]}, {most_played[1]}%",
            inline=False
        )

    embed.add_field(
        name="Casual + Custom Combined",
        value=f"Total Kills: {total_k} | K/D: {total_kd}",
        inline=False
    )

    embed.set_footer(text="cwazy stats bot")

    # Attach the stats card image to the embed so it shows inline
    embed.set_image(url="attachment://stats.png")

    return embed


# ============================================================
# VIEW CONTROLLER
# ============================================================

class ProfileStatsView(discord.ui.View):

    def __init__(self, username, profile):
        super().__init__(timeout=120)
        self.username = username
        self.profile = profile

    async def on_timeout(self):
        self.stop()

    @discord.ui.button(label="Summary", style=discord.ButtonStyle.secondary)
    async def summary(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = build_main_embed(self.username, self.profile)
        file = build_stats_image(self.username, self.profile)
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)