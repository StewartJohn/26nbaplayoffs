"""Scrape NBA playoff bracket + series state from ESPN's public JSON APIs.

Strategy:
 1. Hit the postseason scoreboard for every day from the playoffs' start until today.
 2. Each game block has `competitions[0].competitors` with team + winner.
 3. Aggregate wins per unordered team-pair into a series record.
 4. Pull playoff seeds from the standings API so we can key series by seed matchup
    (1v8, 4v5, 3v6, 2v7 within each conference).
 5. Merge into the canonical series structure below and return a bracket doc
    ready to write to data/bracket.json.

Round 2+ series are filled in once first-round winners are known, using the
`feeds_into` graph from the canonical structure.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Any

import requests

log = logging.getLogger(__name__)

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
ESPN_STANDINGS = "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"

# ESPN uses a few short forms; we surface the more common 3-letter abbr so picks can
# be written with the familiar spelling (NYK, SAS, GSW, NOP, UTA, WAS).
ABBR_NORMALIZE = {
    "NY": "NYK",
    "SA": "SAS",
    "GS": "GSW",
    "NO": "NOP",
    "UTAH": "UTA",
    "WSH": "WAS",
}


def _norm_abbr(abbr: str | None) -> str | None:
    if not abbr:
        return abbr
    return ABBR_NORMALIZE.get(abbr, abbr)

# Canonical 2026 bracket structure. Round 1 is keyed by (conference, seed_pair).
# Round 2+ is derived from `feeds_into` edges once R1 winners land.
CANONICAL_SERIES = [
    {"id": "E1", "round": 1, "conference": "East", "seeds": (1, 8), "feeds_into": "ES1"},
    {"id": "E2", "round": 1, "conference": "East", "seeds": (4, 5), "feeds_into": "ES1"},
    {"id": "E3", "round": 1, "conference": "East", "seeds": (3, 6), "feeds_into": "ES2"},
    {"id": "E4", "round": 1, "conference": "East", "seeds": (2, 7), "feeds_into": "ES2"},
    {"id": "W1", "round": 1, "conference": "West", "seeds": (1, 8), "feeds_into": "WS1"},
    {"id": "W2", "round": 1, "conference": "West", "seeds": (4, 5), "feeds_into": "WS1"},
    {"id": "W3", "round": 1, "conference": "West", "seeds": (3, 6), "feeds_into": "WS2"},
    {"id": "W4", "round": 1, "conference": "West", "seeds": (2, 7), "feeds_into": "WS2"},
    {"id": "ES1", "round": 2, "conference": "East", "feeds_into": "EF"},
    {"id": "ES2", "round": 2, "conference": "East", "feeds_into": "EF"},
    {"id": "WS1", "round": 2, "conference": "West", "feeds_into": "WF"},
    {"id": "WS2", "round": 2, "conference": "West", "feeds_into": "WF"},
    {"id": "EF", "round": 3, "conference": "East", "feeds_into": "F"},
    {"id": "WF", "round": 3, "conference": "West", "feeds_into": "F"},
    {"id": "F", "round": 4, "conference": "Finals", "feeds_into": None},
]

# Playoffs reliably begin the Saturday after the play-in tournament in mid-April.
# Scanning from April 1 is safe and cheap (one GET per day).
PLAYOFFS_START = datetime(2026, 4, 12, tzinfo=timezone.utc)


def _http_get(url: str, **params) -> dict[str, Any]:
    r = requests.get(url, params=params, timeout=20, headers={"User-Agent": "nba-playoffs-pool/1.0"})
    r.raise_for_status()
    return r.json()


def fetch_playoff_seeds() -> dict[str, dict[str, Any]]:
    """Return {team_abbr: {'seed': int, 'conference': 'East'|'West', 'name': str}}.

    Seeds are found in the standings payload's `playoffSeed` stat.
    """
    out: dict[str, dict[str, Any]] = {}
    try:
        data = _http_get(ESPN_STANDINGS, seasontype=2)
    except Exception as e:
        log.warning("Could not fetch standings: %s", e)
        return out

    for child in data.get("children", []):
        conf_raw = (child.get("name") or "").lower()
        if "eastern" in conf_raw:
            conf = "East"
        elif "western" in conf_raw:
            conf = "West"
        else:
            continue
        entries = (child.get("standings") or {}).get("entries") or child.get("entries") or []
        for entry in entries:
            team = entry.get("team") or {}
            abbr = _norm_abbr(team.get("abbreviation"))
            if not abbr:
                continue
            seed = None
            for stat in entry.get("stats", []):
                if stat.get("type") == "playoffseed" or stat.get("name") == "playoffSeed":
                    try:
                        seed = int(stat.get("value") or stat.get("displayValue"))
                    except (TypeError, ValueError):
                        pass
                    break
            if seed and 1 <= seed <= 8:
                out[abbr] = {"seed": seed, "conference": conf, "name": team.get("displayName") or team.get("name") or abbr}
    return out


def fetch_playoff_games(start: datetime, end: datetime) -> list[dict[str, Any]]:
    """Scan postseason scoreboard day-by-day between `start` and `end` (inclusive)."""
    games: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    day = start
    while day.date() <= end.date():
        ymd = day.strftime("%Y%m%d")
        try:
            data = _http_get(ESPN_SCOREBOARD, dates=ymd, seasontype=3, limit=50)
        except Exception as e:
            log.warning("Scoreboard fetch failed for %s: %s", ymd, e)
            day += timedelta(days=1)
            continue
        for event in data.get("events", []):
            if event.get("id") in seen_ids:
                continue
            seen_ids.add(event.get("id"))
            games.append(event)
        day += timedelta(days=1)
    return games


def _team_from_competitor(comp: dict[str, Any]) -> dict[str, Any]:
    t = comp.get("team") or {}
    return {
        "abbr": _norm_abbr(t.get("abbreviation")),
        "name": t.get("displayName") or t.get("name"),
    }


def aggregate_series(games: list[dict[str, Any]]) -> dict[frozenset, dict[str, Any]]:
    """Aggregate completed postseason games into series records keyed by unordered team pair."""
    series: dict[frozenset, dict[str, Any]] = defaultdict(lambda: {
        "wins": defaultdict(int),
        "games_played": 0,
        "teams": {},
    })
    for event in games:
        # ESPN's scoreboard ignores ?seasontype=3 and returns regular-season + play-in games too.
        # Keep only true postseason games (season.type == 3).
        if (event.get("season") or {}).get("type") != 3:
            continue
        comp = (event.get("competitions") or [{}])[0]
        competitors = comp.get("competitors") or []
        if len(competitors) != 2:
            continue
        status = (event.get("status") or {}).get("type", {})
        if not status.get("completed"):
            continue
        a = _team_from_competitor(competitors[0])
        b = _team_from_competitor(competitors[1])
        if not a["abbr"] or not b["abbr"]:
            continue
        key = frozenset([a["abbr"], b["abbr"]])
        rec = series[key]
        rec["teams"][a["abbr"]] = a
        rec["teams"][b["abbr"]] = b
        rec["games_played"] += 1
        for c in competitors:
            if c.get("winner"):
                rec["wins"][_norm_abbr((c.get("team") or {}).get("abbreviation"))] += 1
    return series


def _empty_series(tmpl: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": tmpl["id"],
        "round": tmpl["round"],
        "conference": tmpl["conference"],
        "feeds_into": tmpl.get("feeds_into"),
        "top_team": None,
        "bottom_team": None,
        "top_wins": 0,
        "bottom_wins": 0,
        "winner": None,
        "games_played": 0,
        "status": "not_started",
    }


def _fill_series(out: dict[str, Any], top: dict[str, Any], bottom: dict[str, Any], agg: dict[frozenset, dict[str, Any]]):
    out["top_team"] = top
    out["bottom_team"] = bottom
    key = frozenset([top["abbr"], bottom["abbr"]])
    rec = agg.get(key)
    if not rec:
        out["status"] = "not_started"
        return
    out["top_wins"] = rec["wins"].get(top["abbr"], 0)
    out["bottom_wins"] = rec["wins"].get(bottom["abbr"], 0)
    out["games_played"] = rec["games_played"]
    if out["top_wins"] >= 4:
        out["winner"] = top["abbr"]
        out["status"] = "complete"
    elif out["bottom_wins"] >= 4:
        out["winner"] = bottom["abbr"]
        out["status"] = "complete"
    else:
        out["status"] = "in_progress" if rec["games_played"] > 0 else "not_started"


def build_bracket(seeds: dict[str, dict[str, Any]], agg: dict[frozenset, dict[str, Any]]) -> list[dict[str, Any]]:
    series_out: dict[str, dict[str, Any]] = {t["id"]: _empty_series(t) for t in CANONICAL_SERIES}

    # By conference + seed, resolve team info.
    by_conf_seed: dict[tuple[str, int], dict[str, Any]] = {}
    for abbr, info in seeds.items():
        by_conf_seed[(info["conference"], info["seed"])] = {
            "abbr": abbr, "seed": info["seed"], "name": info["name"]
        }

    # Round 1 — direct seed matchups.
    for tmpl in CANONICAL_SERIES:
        if tmpl["round"] != 1:
            continue
        top_seed, bottom_seed = tmpl["seeds"]
        top = by_conf_seed.get((tmpl["conference"], top_seed))
        bottom = by_conf_seed.get((tmpl["conference"], bottom_seed))
        if not top or not bottom:
            continue
        _fill_series(series_out[tmpl["id"]], top, bottom, agg)

    # Round 2+ — inherit winners along `feeds_into` edges, then attach matchup data.
    # `feeds_into` alone doesn't tell us which side of the next series a winner goes to;
    # we preserve seeding order so the higher seed becomes `top_team`.
    children_of: dict[str, list[str]] = defaultdict(list)
    for tmpl in CANONICAL_SERIES:
        parent = tmpl.get("feeds_into")
        if parent:
            children_of[parent].append(tmpl["id"])

    def resolve(series_id: str):
        s = series_out[series_id]
        if s["round"] == 1:
            return
        kids = children_of.get(series_id, [])
        winners = []
        for kid_id in kids:
            kid = series_out[kid_id]
            resolve(kid_id)
            if kid["winner"]:
                team = kid["top_team"] if kid["winner"] == kid["top_team"]["abbr"] else kid["bottom_team"]
                winners.append(team)
        if len(winners) < 2:
            return
        # Top team = lower seed number (better seed). Fall back to alpha if seeds tie/missing.
        winners.sort(key=lambda t: (t.get("seed") or 99, t.get("abbr") or ""))
        top, bottom = winners[0], winners[1]
        _fill_series(s, top, bottom, agg)

    for tmpl in CANONICAL_SERIES:
        resolve(tmpl["id"])

    return [series_out[t["id"]] for t in CANONICAL_SERIES]


def fetch_bracket() -> dict[str, Any]:
    seeds = fetch_playoff_seeds()
    games = fetch_playoff_games(PLAYOFFS_START, datetime.now(timezone.utc))
    agg = aggregate_series(games)
    series = build_bracket(seeds, agg)
    return {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": "2025-26",
        "series": series,
    }
