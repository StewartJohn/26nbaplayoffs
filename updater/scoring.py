"""Compute standings from picks.json + bracket.json."""

from datetime import datetime, timezone

DEFAULT_RULES = {
    "winner_points_by_round": {"1": 1, "2": 2, "3": 4, "4": 8},
    "exact_games_bonus": 2,
    "within_one_bonus": 1,
    "note": (
        "Points are awarded only after a series completes. "
        "Winner points by round (R1/R2/CF/F) = 1/2/4/8. "
        "If the series length prediction matches exactly, +2; if off by one game, +1."
    ),
}


def _winner_points(rules, round_num):
    pts = rules.get("winner_points_by_round", {})
    return pts.get(str(round_num), pts.get(round_num, 0))


def score_player(player, series_by_id, rules):
    total = 0
    correct_winners = 0
    exact_games = 0
    close_games = 0
    by_round = {1: 0, 2: 0, 3: 0, 4: 0}

    picks = player.get("picks", {}) or {}
    for series_id, pick in picks.items():
        series = series_by_id.get(series_id)
        if not series or series.get("status") != "complete":
            continue
        round_num = series.get("round")
        if pick.get("winner") != series.get("winner"):
            continue
        correct_winners += 1
        pts = _winner_points(rules, round_num)
        games_played = series.get("games_played") or (
            (series.get("top_wins") or 0) + (series.get("bottom_wins") or 0)
        )
        if pick.get("games") == games_played:
            pts += rules.get("exact_games_bonus", 2)
            exact_games += 1
        elif abs((pick.get("games") or 0) - games_played) == 1:
            pts += rules.get("within_one_bonus", 1)
            close_games += 1
        total += pts
        by_round[round_num] = by_round.get(round_num, 0) + pts

    return {
        "player_id": player["id"],
        "name": player["name"],
        "total": total,
        "correct_winners": correct_winners,
        "exact_games": exact_games,
        "close_games": close_games,
        "by_round": {str(k): v for k, v in by_round.items()},
    }


def compute_standings(picks_doc, bracket_doc, rules=None):
    rules = rules or DEFAULT_RULES
    series_by_id = {s["id"]: s for s in bracket_doc.get("series", [])}
    rows = [score_player(p, series_by_id, rules) for p in picks_doc.get("players", [])]
    rows.sort(key=lambda r: (-r["total"], -r["correct_winners"], r["name"]))
    return {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scoring_rules": rules,
        "standings": rows,
    }
