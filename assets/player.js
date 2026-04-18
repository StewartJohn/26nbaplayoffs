// Player detail page rendering

const ROUND_LABEL = { 1: "Round 1", 2: "Conference Semis", 3: "Conference Finals", 4: "Finals" };
const WINNER_PTS = { 1: 1, 2: 2, 3: 4, 4: 8 };

async function loadData() {
  const [bracket, picks, standings] = await Promise.all([
    fetch("data/bracket.json").then(r => r.json()),
    fetch("data/picks.json").then(r => r.json()),
    fetch("data/standings.json").then(r => r.json()),
  ]);
  return { bracket, picks, standings };
}

function getPlayerId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("id");
}

function formatDate(iso) {
  if (!iso) return "never";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit"
  });
}

function scorePick(pick, series, rules) {
  if (!series || series.status !== "complete" || !pick) {
    return { earned: 0, possible: null, status: "pending" };
  }
  const pts = rules.winner_points_by_round || WINNER_PTS;
  const winnerPts = pts[series.round] ?? 0;
  if (pick.winner !== series.winner) {
    return { earned: 0, possible: winnerPts + (rules.exact_games_bonus ?? 2), status: "lost" };
  }
  let earned = winnerPts;
  const gamesPlayed = series.games_played || (series.top_wins + series.bottom_wins);
  if (pick.games === gamesPlayed) earned += rules.exact_games_bonus ?? 2;
  else if (Math.abs(pick.games - gamesPlayed) === 1) earned += rules.within_one_bonus ?? 1;
  return { earned, possible: winnerPts + (rules.exact_games_bonus ?? 2), status: "earned" };
}

function renderPlayer(player, bracket, standings) {
  document.title = `${player.name} — 2026 NBA Playoffs Pool`;
  document.querySelector("#player-name").textContent = player.name;

  const row = (standings.standings || []).find(s => s.player_id === player.id);
  if (row) {
    document.querySelector("#player-summary").textContent =
      `Total: ${row.total} pts · Correct winners: ${row.correct_winners} · Exact games: ${row.exact_games} · Close: ${row.close_games}`;
  }

  const rules = standings.scoring_rules || {};
  const container = document.querySelector("#picks-by-round");
  container.innerHTML = "";

  for (const round of [1, 2, 3, 4]) {
    const seriesInRound = (bracket.series || []).filter(s => s.round === round);
    if (!seriesInRound.length) continue;
    const block = document.createElement("div");
    block.className = "round-block";
    const h = document.createElement("h3");
    h.textContent = ROUND_LABEL[round];
    block.appendChild(h);

    const grid = document.createElement("div");
    grid.className = "picks-grid";

    seriesInRound.forEach(series => {
      const pick = (player.picks || {})[series.id];
      grid.appendChild(renderPickCard(series, pick, rules));
    });

    block.appendChild(grid);
    container.appendChild(block);
  }
}

function renderPickCard(series, pick, rules) {
  const card = document.createElement("div");
  card.className = "pick-card";

  const matchupLabel = matchupString(series);
  const matchup = document.createElement("div");
  matchup.className = "pick-matchup";
  matchup.textContent = `${series.id} · ${matchupLabel}`;
  card.appendChild(matchup);

  const line = document.createElement("div");
  line.className = "pick-line";

  const pred = document.createElement("div");
  pred.className = "pick-prediction";
  if (pick) {
    pred.textContent = `${pick.winner} in ${pick.games}`;
  } else {
    pred.textContent = "— no pick —";
    pred.style.color = "var(--muted)";
  }
  line.appendChild(pred);

  const score = scorePick(pick, series, rules);
  const pts = document.createElement("div");
  pts.className = `pick-points ${score.status}`;
  if (score.status === "pending") {
    pts.textContent = series.status === "not_started" ? "—" : "pending";
  } else if (score.status === "lost") {
    pts.textContent = "0 pts";
  } else {
    pts.textContent = `+${score.earned} pts`;
  }
  line.appendChild(pts);

  card.appendChild(line);

  if (series.status === "complete") {
    const actual = document.createElement("div");
    actual.className = "pick-actual";
    const games = series.games_played || (series.top_wins + series.bottom_wins);
    actual.textContent = `Actual: ${series.winner} in ${games}`;
    card.appendChild(actual);
  } else if (series.status === "in_progress") {
    const actual = document.createElement("div");
    actual.className = "pick-actual";
    actual.textContent = `In progress: ${series.top_team?.abbr ?? "?"} ${series.top_wins}–${series.bottom_wins} ${series.bottom_team?.abbr ?? "?"}`;
    card.appendChild(actual);
  }

  return card;
}

function matchupString(series) {
  const t = series.top_team, b = series.bottom_team;
  if (!t && !b) return "TBD";
  const l = t ? `${t.seed ? `(${t.seed}) ` : ""}${t.abbr}` : "TBD";
  const r = b ? `${b.seed ? `(${b.seed}) ` : ""}${b.abbr}` : "TBD";
  return `${l} vs ${r}`;
}

(async function init() {
  const id = getPlayerId();
  if (!id) {
    document.querySelector("#player-name").textContent = "No player selected";
    return;
  }
  try {
    const { bracket, picks, standings } = await loadData();
    const player = (picks.players || []).find(p => p.id === id);
    if (!player) {
      document.querySelector("#player-name").textContent = `Unknown player: ${id}`;
      return;
    }
    renderPlayer(player, bracket, standings);
  } catch (err) {
    console.error(err);
    document.querySelector("#player-name").textContent = "Failed to load data.";
  }
})();
