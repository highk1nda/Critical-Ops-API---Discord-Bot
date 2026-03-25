from config.constants import (
    SMURF_KILLS_LOW,
    SMURF_KILLS_HIGH,
    SMURF_GAMES_LOW,
    SMURF_GAMES_HIGH,
    SMURF_KD_THRESHOLD,
    SMURF_WINRATE_THRESHOLD,
    SMURF_WEIGHT_KILLS,
    SMURF_WEIGHT_GAMES,
    SMURF_WEIGHT_KD,
    SMURF_WEIGHT_WINRATE,
)


def calculate_smurf_score(parsed_profile: dict) -> float:
    """
    Returns a 0–100 score estimating smurf likelihood.
    Reads from the output of core.stats.parse_profile().
    """
    kd: float = parsed_profile["ranked"]["kd"]
    non_ranked_kills: int = parsed_profile["non_ranked"]["kills"]
    ranked_games: int = parsed_profile["ranked"]["total_games"]
    ranked_winrate: float = parsed_profile["ranked"]["winrate"]

    if non_ranked_kills < SMURF_KILLS_LOW:
        f1 = 1.0
    elif non_ranked_kills <= SMURF_KILLS_HIGH:
        f1 = max(0.0, 1 - (non_ranked_kills - SMURF_KILLS_LOW) / (SMURF_KILLS_HIGH - SMURF_KILLS_LOW))
    else:
        f1 = 0.0

    if ranked_games < SMURF_GAMES_LOW:
        f2 = 1.0
    elif ranked_games <= SMURF_GAMES_HIGH:
        f2 = max(0.0, 1 - ranked_games / SMURF_GAMES_HIGH)
    else:
        f2 = 0.0

    f3 = 1.0 if kd >= SMURF_KD_THRESHOLD else (kd / SMURF_KD_THRESHOLD if kd > 0 else 0.0)
    f4 = (
        1.0
        if ranked_winrate >= SMURF_WINRATE_THRESHOLD
        else (ranked_winrate / SMURF_WINRATE_THRESHOLD if ranked_winrate > 0 else 0.0)
    )

    if (
        non_ranked_kills < SMURF_KILLS_LOW
        and ranked_games < SMURF_GAMES_LOW
        and kd >= SMURF_KD_THRESHOLD
        and ranked_winrate >= SMURF_WINRATE_THRESHOLD
    ):
        return 100.0

    score = (
        SMURF_WEIGHT_KILLS * f1
        + SMURF_WEIGHT_GAMES * f2
        + SMURF_WEIGHT_KD * f3
        + SMURF_WEIGHT_WINRATE * f4
    )
    return round(min(score, 100), 2)
