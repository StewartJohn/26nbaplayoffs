# NBA Playoffs Pool

A static website for running a bracket pick-em pool with friends. Scores update automatically by pulling live data from ESPN.

No backend, no database, no paid hosting required. Works great on GitHub Pages.

---

## How it works

The site is three HTML pages that read from three JSON files in `data/`. A Python script (`updater/update.py`) scrapes ESPN for current playoff results, recomputes everyone's scores, and commits the updated JSON back to the repo. GitHub Actions runs that script on a schedule so the site stays current without any manual intervention.

```
data/bracket.json   ← live series state, scraped from ESPN
data/picks.json     ← everyone's bracket picks, hand-edited
data/standings.json ← computed leaderboard, generated automatically
```

---

## Scoring

| Event | Points |
|---|---|
| Correct series winner — Round 1 | 1 |
| Correct series winner — Round 2 | 2 |
| Correct series winner — Conf. Finals | 4 |
| Correct series winner — Finals | 8 |
| Exact series length (e.g. picked 6, went 6) | +2 bonus |
| Series length off by one game | +1 bonus |

Points are only awarded once a series is complete.

---

## Setup

### 1. Fork and clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

### 2. Install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r updater/requirements.txt
```

### 3. Add your players' picks

Edit `data/picks.json`. Each player needs a unique `id`, a display `name`, and a `picks` object keyed by series ID.

Series IDs follow this structure:

| ID | Round | Matchup |
|---|---|---|
| E1–E4 | Round 1 East | 1v8, 4v5, 3v6, 2v7 |
| W1–W4 | Round 1 West | 1v8, 4v5, 3v6, 2v7 |
| ES1, ES2 | Conf. Semis East | winners of E1/E2 and E3/E4 |
| WS1, WS2 | Conf. Semis West | winners of W1/W2 and W3/W4 |
| EF | East Finals | winners of ES1/ES2 |
| WF | West Finals | winners of WS1/WS2 |
| F | NBA Finals | EF winner vs WF winner |

Each pick specifies the winning team's abbreviation and predicted series length:

```json
{
  "players": [
    {
      "id": "alice",
      "name": "Alice",
      "picks": {
        "E1": { "winner": "BOS", "games": 5 },
        "E2": { "winner": "NYK", "games": 6 },
        "F":  { "winner": "OKC", "games": 7 }
      }
    }
  ]
}
```

Players can have partial picks — unselected series simply score zero.

### 4. Run the updater

```bash
python updater/update.py --no-push    # scrape + score, write files locally
python updater/update.py              # scrape + score + commit + push to GitHub
```

On first run this populates `data/bracket.json` with live matchups and `data/standings.json` with current scores.

### 5. Enable GitHub Pages

In your repo: **Settings → Pages → Source: Deploy from branch → main / (root)**.

Your site will be at `https://YOUR_USERNAME.github.io/YOUR_REPO/`.

### 6. Enable automated updates

The included GitHub Actions workflow (`.github/workflows/update.yml`) runs the updater on a schedule. It commits updated JSON back to the repo, which triggers a Pages redeploy automatically.

In your repo: **Settings → Actions → General → Workflow permissions → Read and write permissions**.

You can also trigger a manual run any time from the **Actions** tab.

---

## Viewing the site locally

Browsers block `fetch()` on `file://` URLs, so open via a local server:

```bash
python3 -m http.server 8000
# then open http://localhost:8000
```

---

## Updater reference

```bash
python updater/update.py                 # full run: scrape, score, commit, push
python updater/update.py --no-push       # scrape and score, skip git
python updater/update.py --no-scrape     # recompute standings only (no ESPN fetch)
python updater/update.py --dry-run       # preview without writing anything
```

`--no-scrape` is useful after editing `picks.json` — it regenerates `standings.json` without hitting ESPN.

---

## Adding or removing players

Edit `data/picks.json` directly — add or remove entries from the `players` array. Then run the updater with `--no-scrape` to regenerate standings, and push.

---

## Team abbreviations

The scraper normalises a few ESPN short forms to the more common spellings:

| ESPN | Used here |
|---|---|
| NY | NYK |
| SA | SAS |
| GS | GSW |
| NO | NOP |

Use the "Used here" column in `picks.json`.
