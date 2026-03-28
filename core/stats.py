"""
core/stats.py

Profile parsing and metric calculations.
All stat computation lives here — rendering and detection modules only consume
the structured dict produced by parse_profile().
"""

from datetime import datetime, timezone


# ── Metric helpers ────────────────────────────────────────────────────────────

def calculate_kd(kills: int, deaths: int) -> float:
    return round(kills / deaths, 2) if deaths > 0 else float(kills)


def calculate_winrate(wins: int, losses: int) -> float:
    total = wins + losses
    return round((wins / total) * 100, 2) if total > 0 else 0.0


# ── Profile parser ────────────────────────────────────────────────────────────

def parse_profile(profile: dict) -> dict:
    """
    Aggregate raw API profile data into a structured dict.

    Output shape:
        clan:               str
        current_season:     int | str  ("-" when no ranked data)
        current:            dict  — stats for the most recent ranked season
        ranked:             dict  — lifetime ranked totals
        non_ranked:         dict  — casual + custom combined
        most_played_season: dict | None
        creation_year:      int | None
    """
    stats = profile.get("stats", {})
    clan_name: str = profile.get("clan", {}).get("basicInfo", {}).get("name", "Unknown")
    creation_year = _parse_creation_year(profile)
    seasonal_stats: list = stats.get("seasonal_stats", [])

    ranked_kills = ranked_deaths = ranked_wins = ranked_losses = 0
    current_ranked: dict | None = None
    current_season_number: int = -1
    seasons_game_counts: list[tuple[int, int]] = []

    casual_kills = casual_deaths = 0
    custom_kills = custom_deaths = 0

    for season in seasonal_stats:
        ranked = season.get("ranked", {})
        wins = ranked.get("w", 0)
        losses = ranked.get("l", 0)
        season_number: int = season.get("season", 0)

        if wins + losses > 0:
            ranked_kills += ranked.get("k", 0)
            ranked_deaths += ranked.get("d", 0)
            ranked_wins += wins
            ranked_losses += losses
            seasons_game_counts.append((season_number, wins + losses))

            if season_number > current_season_number:
                current_season_number = season_number
                current_ranked = ranked

        casual = season.get("casual", {})
        custom = season.get("custom", {})
        custom_lobbies = season.get("custom_lobbies", {})

        casual_kills += casual.get("k", 0)
        casual_deaths += casual.get("d", 0)
        custom_kills += custom.get("k", 0) + custom_lobbies.get("k", 0)
        custom_deaths += custom.get("d", 0) + custom_lobbies.get("d", 0)

    current = current_ranked or {}
    current_kills: int = current.get("k", 0)
    current_deaths: int = current.get("d", 0)
    current_wins: int = current.get("w", 0)
    current_losses: int = current.get("l", 0)

    total_ranked_games = ranked_wins + ranked_losses
    non_ranked_kills = casual_kills + custom_kills
    non_ranked_deaths = casual_deaths + custom_deaths

    most_played_season = _find_most_played_season(seasons_game_counts, total_ranked_games)

    return {
        "clan": clan_name,
        "current_season": current_season_number if current_season_number >= 0 else "-",
        "current": {
            "kills": current_kills,
            "deaths": current_deaths,
            "wins": current_wins,
            "losses": current_losses,
            "kd": calculate_kd(current_kills, current_deaths),
            "winrate": calculate_winrate(current_wins, current_losses),
            "games": current_wins + current_losses,
        },
        "ranked": {
            "kills": ranked_kills,
            "deaths": ranked_deaths,
            "wins": ranked_wins,
            "losses": ranked_losses,
            "kd": calculate_kd(ranked_kills, ranked_deaths),
            "winrate": calculate_winrate(ranked_wins, ranked_losses),
            "total_games": total_ranked_games,
        },
        "non_ranked": {
            "kills": non_ranked_kills,
            "deaths": non_ranked_deaths,
            "kd": calculate_kd(non_ranked_kills, non_ranked_deaths),
        },
        "most_played_season": most_played_season,
        "creation_year": creation_year,
    }


def _parse_creation_year(profile: dict) -> int | None:
    """
    Extract account creation year from raw profile data.
    Handles ISO date strings ("2019-03-15T...") and Unix timestamps (seconds).
    Returns None if the field is absent or unparseable.
    """
    basic_info = profile.get("basicInfo", {})
    raw = (
        basic_info.get("created")
        or basic_info.get("created_at")
        or basic_info.get("createdAt")
        or profile.get("created")
        or profile.get("created_at")
        or profile.get("createdAt")
    )
    if not raw:
        return None
    try:
        s = str(raw).strip()
        if s.isdigit():
            # Unix timestamp in seconds — 10 digits covers up to year 2286
            return datetime.fromtimestamp(int(s), tz=timezone.utc).year
        # ISO 8601 or any YYYY-prefixed string
        return int(s[:4])
    except (ValueError, TypeError, OSError):
        return None


def _find_most_played_season(
    seasons_game_counts: list[tuple[int, int]],
    total_ranked_games: int,
) -> dict | None:
    if not seasons_game_counts or total_ranked_games == 0:
        return None

    best_season, best_games = max(seasons_game_counts, key=lambda x: x[1])
    percentage = round((best_games / total_ranked_games) * 100, 2)
    return {"season": best_season, "percentage": percentage}
