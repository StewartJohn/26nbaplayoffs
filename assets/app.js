// Shared helpers + index page rendering

const BRACKET_COLUMNS = [
  { title: "East R1", filter: s => s.round === 1 && s.conference === "East" },
  { title: "East Semis", filter: s => s.round === 2 && s.conference === "East" },
  { title: "East Finals", filter: s => s.round === 3 && s.conference === "East" },
  { title: "Finals", filter: s => s.round === 4 },
  { title: "West Finals", filter: s => s.round === 3 && s.conference === "West" },
  { title: "West Semis", filter: s => s.round === 2 && s.conference === "West" },
  { title: "West R1", filter: s => s.round === 1 && s.conference === "West" },
];

const ROUND_LABEL = { 1: "Round 1", 2: "Conf. Semis", 3: "Conf. Finals", 4: "Finals" };

async function loadData() {
  const [bracket, picks, standings] = await Promise.all([
    fetch("data/bracket.json").then(r => r.json()),
    fetch("data/picks.json").then(r => r.json()),
    fetch("data/standings.json").then(r => r.json()),
  ]);
  return { bracket, picks, standings };
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

function renderStandings(standings, picksDoc) {
  const tbody = document.querySelector("#standings-table tbody");
  tbody.innerHTML = "";
  const nameById = Object.fromEntries((picksDoc.players || []).map(p => [p.id, p.name]));
  const rows = [...standings.standings].sort((a, b) => b.total - a.total);
  rows.forEach((row, i) => {
    const tr = document.createElement("tr");
    tr.onclick = () => { window.location.href = `player.html?id=${encodeURIComponent(row.player_id)}`; };
    tr.innerHTML = `
      <td class="rank">${i + 1}</td>
      <td><a href="player.html?id=${encodeURIComponent(row.player_id)}">${nameById[row.player_id] || row.name}</a></td>
      <td class="total">${row.total}</td>
      <td>${row.correct_winners}</td>
      <td>${row.exact_games}</td>
      <td>${row.close_games}</td>
      <td>${row.by_round?.[1] ?? 0}</td>
      <td>${row.by_round?.[2] ?? 0}</td>
      <td>${row.by_round?.[3] ?? 0}</td>
      <td>${row.by_round?.[4] ?? 0}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderBracket(bracket) {
  const container = document.querySelector("#bracket");
  container.innerHTML = "";
  BRACKET_COLUMNS.forEach(col => {
    const div = document.createElement("div");
    div.className = "bracket-column";
    const h = document.createElement("h3");
    h.textContent = col.title;
    div.appendChild(h);
    (bracket.series || []).filter(col.filter).forEach(s => div.appendChild(renderSeriesBox(s)));
    container.appendChild(div);
  });
}

function renderSeriesBox(s) {
  const box = document.createElement("div");
  box.className = "series-box";
  const top = teamRow(s.top_team, s.top_wins, s.winner, s);
  const bot = teamRow(s.bottom_team, s.bottom_wins, s.winner, s);
  box.appendChild(top);
  box.appendChild(bot);

  const status = document.createElement("div");
  status.className = `series-status ${s.status || "not_started"}`;
  if (s.status === "complete" && s.winner) {
    status.textContent = `${s.winner} wins ${Math.max(s.top_wins, s.bottom_wins)}-${Math.min(s.top_wins, s.bottom_wins)}`;
  } else if (s.status === "in_progress") {
    status.textContent = `${s.top_wins}-${s.bottom_wins}`;
  } else {
    status.textContent = "TBD";
  }
  box.appendChild(status);
  return box;
}

function teamRow(team, wins, winnerAbbr, series) {
  const row = document.createElement("div");
  row.className = "series-team";
  if (!team) {
    row.innerHTML = `<span class="seed"></span><span class="team-name" style="color:var(--muted)">—</span><span class="wins"></span>`;
    return row;
  }
  if (winnerAbbr && winnerAbbr === team.abbr) row.classList.add("winner");
  if (winnerAbbr && winnerAbbr !== team.abbr) row.classList.add("eliminated");
  row.innerHTML = `
    <span class="seed">${team.seed ?? ""}</span>
    <span class="team-name">${team.abbr}</span>
    <span class="wins">${wins ?? 0}</span>
  `;
  return row;
}

function renderRules(standings) {
  const ul = document.querySelector("#rules");
  if (!ul) return;
  const r = standings.scoring_rules || {};
  const pts = r.winner_points_by_round || {};
  ul.innerHTML = `
    <li>Round 1 correct winner: <strong>${pts[1] ?? 1}</strong> pt</li>
    <li>Round 2 correct winner: <strong>${pts[2] ?? 2}</strong> pts</li>
    <li>Conference Finals correct winner: <strong>${pts[3] ?? 4}</strong> pts</li>
    <li>Finals correct winner: <strong>${pts[4] ?? 8}</strong> pts</li>
    <li>Exact game count bonus: <strong>+${r.exact_games_bonus ?? 2}</strong></li>
    <li>Game count off by one: <strong>+${r.within_one_bonus ?? 1}</strong></li>
    <li>Points are awarded only once a series is complete.</li>
  `;
}

(async function init() {
  try {
    const { bracket, picks, standings } = await loadData();
    document.querySelector("#updated").textContent =
      `Last updated: ${formatDate(bracket.last_updated || standings.last_updated)}`;
    renderStandings(standings, picks);
    renderBracket(bracket);
    renderRules(standings);
  } catch (err) {
    console.error(err);
    document.querySelector("#updated").textContent = "Failed to load data.";
  }
})();
