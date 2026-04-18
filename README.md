# 2026 NBA Playoffs Pool

Static site for tracking bracket picks and accuracy across a group of friends. The site reads three JSON files under `data/`; a local Python script refreshes them from ESPN and pushes to GitHub.

## Layout

```
.
├── index.html            # Leaderboard + bracket
├── player.html           # Per-player picks detail (?id=john)
├── assets/
│   ├── style.css
│   ├── app.js            # Index page
│   └── player.js         # Detail page
├── data/
│   ├── bracket.json      # Live series state (scraped)
│   ├── picks.json        # Everyone's bracket picks (hand-edited)
│   └── standings.json    # Computed leaderboard (generated)
└── updater/
    ├── update.py         # Daily runner
    ├── scraper.py        # ESPN scoreboard + standings → bracket
    ├── scoring.py        # Points calculation
    └── requirements.txt
```

## Running locally

Any static server works for browsing (the JS uses `fetch`, which needs HTTP, not `file://`):

```bash
python -m http.server 8000
# open http://localhost:8000
```

## Daily update

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r updater/requirements.txt

python updater/update.py                 # scrape, score, commit, push
python updater/update.py --no-push       # write files, skip git
python updater/update.py --no-scrape     # recompute standings only
python updater/update.py --dry-run       # preview without writing
```

The script is safe to run multiple times a day — it no-ops if nothing changed.

### One-time git setup

The script pushes to whatever `origin` is configured in the working tree. To hook this up to the repo at https://github.com/StewartJohn/26nbaplayoffs :

```bash
cd /Users/johnstewart/Documents/Claude/NBA
git init
git remote add origin git@github.com:StewartJohn/26nbaplayoffs.git
git add .
git commit -m "Initial commit"
git branch -M main
git push -u origin main
```

After that, daily runs only need `python updater/update.py`.

### GitHub Pages

In the repo settings → **Pages**, set source to `main` / root. The site will live at `https://stewartjohn.github.io/26nbaplayoffs/`.

## Scoring

| Event | Points |
| --- | --- |
| Correct R1 winner | 1 |
| Correct R2 winner | 2 |
| Correct Conf. Finals winner | 4 |
| Correct Finals winner | 8 |
| Exact series length | +2 |
| Off by one game | +1 |

Points are only awarded once a series ends.

## Adding players

Edit `data/picks.json`. Append a new entry to the `players` array with a unique `id`, a `name`, and a `picks` object keyed by series id (`E1`, `W1`, `ES1`, `F`, etc. — see `data/bracket.json`). All players appear automatically in the leaderboard and the detail page.

```json
{
  "id": "sam",
  "name": "Sam",
  "picks": {
    "E1": { "winner": "CLE", "games": 6 },
    ...
  }
}
```

A player can skip series they haven't picked — unknown series simply count as zero for that player.

## Editing picks

Give me the picks verbatim in chat (e.g. "John picks Cavs in 6, Knicks in 7, …") and I'll paste them into `data/picks.json`. Re-run the updater to refresh standings.
