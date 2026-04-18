"""Daily updater: fetches latest playoff data from ESPN, recomputes standings,
writes data/*.json, and (by default) commits + pushes to origin.

Usage:
    python updater/update.py                 # scrape + score + commit + push
    python updater/update.py --no-push       # write files only, skip git
    python updater/update.py --no-scrape     # recompute standings from existing bracket.json
    python updater/update.py --dry-run       # print what would happen, write nothing
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scraper import fetch_bracket  # noqa: E402
from scoring import compute_standings  # noqa: E402


def _write_json(path: Path, obj, dry_run: bool):
    rendered = json.dumps(obj, indent=2) + "\n"
    if dry_run:
        print(f"[dry-run] would write {path} ({len(rendered)} bytes)")
        return
    path.write_text(rendered)
    print(f"wrote {path.relative_to(ROOT)}")


def git_commit_and_push(dry_run: bool):
    if dry_run:
        print("[dry-run] would git add data/, commit, push")
        return
    try:
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("Skipping push: not inside a git work tree. Run `git init` and configure `origin` first.")
        return

    subprocess.run(["git", "add", "data/"], cwd=ROOT, check=True)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if diff.returncode == 0:
        print("No data changes to commit.")
        return

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    subprocess.run(["git", "commit", "-m", f"Update playoff data {stamp}"], cwd=ROOT, check=True)
    try:
        subprocess.run(["git", "push"], cwd=ROOT, check=True)
    except subprocess.CalledProcessError as e:
        print(f"git push failed: {e}. You can push manually from {ROOT}.")


def main():
    parser = argparse.ArgumentParser(description="Update NBA playoff data.")
    parser.add_argument("--no-scrape", action="store_true", help="Skip ESPN scrape; just recompute standings.")
    parser.add_argument("--no-push", action="store_true", help="Write files but don't commit or push.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned actions without writing anything.")
    args = parser.parse_args()

    if not args.no_scrape:
        print("Fetching latest bracket from ESPN…")
        bracket = fetch_bracket()
        _write_json(DATA_DIR / "bracket.json", bracket, args.dry_run)
    else:
        print("Skipping scrape; reading existing bracket.json")
        bracket = json.loads((DATA_DIR / "bracket.json").read_text())

    picks = json.loads((DATA_DIR / "picks.json").read_text())
    print(f"Scoring {len(picks.get('players', []))} players across {len(bracket.get('series', []))} series…")
    standings = compute_standings(picks, bracket)
    _write_json(DATA_DIR / "standings.json", standings, args.dry_run)

    if not args.no_push:
        git_commit_and_push(args.dry_run)
    else:
        print("Skipping git push (--no-push).")


if __name__ == "__main__":
    main()
