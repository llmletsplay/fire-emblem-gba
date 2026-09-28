const $ = (id) => document.getElementById(id);
const channelPattern = /^[a-z0-9_]{1,25}$/;
const params = new URLSearchParams(window.location.search);
const configuredChannel = (params.get("channel") || "").trim().toLowerCase();
const channel = channelPattern.test(configuredChannel) ? configuredChannel : "";
const obsCapture = params.get("capture") === "obs";
document.querySelector(".overlay").classList.toggle("obs-capture", obsCapture);
const lastFrames = { "1P": "", "2P": "" };
let lastDecisionSignature = "";

const text = (id, value) => {
  const node = $(id);
  if (node) node.textContent = value == null || value === "" ? "—" : String(value);
};

const count = (value) => Number.isInteger(value) && value >= 0 ? value : null;

function formatTime(seconds) {
  if (!Number.isInteger(seconds) || seconds < 0) return "00:00";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  return hours > 0
    ? `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`
    : `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function formatUnit(id) {
  if (!Number.isInteger(id)) return "Unit ?";
  return `Unit ${id.toString(16).toUpperCase().padStart(2, "0")}`;
}

function setChat() {
  const instructions = $("chat-instructions");
  const popout = $("chat-popout");
  const iframe = $("chat-embed");
  if (!channel) {
    text("chat-channel-label", "TWITCH · NOT SET");
    instructions.textContent = "Add your Twitch handle when launching the runner: -TwitchChannel yourhandle. Then add Twitch chat as an OBS Browser Source.";
    return;
  }
  text("chat-channel-label", `@${channel}`);
  const popoutUrl = `https://www.twitch.tv/popout/${encodeURIComponent(channel)}/chat?popout=`;
  popout.href = popoutUrl;
  popout.hidden = false;
  if (window.location.protocol === "https:") {
    iframe.src = `https://www.twitch.tv/embed/${encodeURIComponent(channel)}/chat?parent=${encodeURIComponent(window.location.hostname)}`;
    iframe.hidden = false;
    $("chat-setup").hidden = true;
  } else {
    instructions.textContent = "Twitch requires a secure parent for chat embeds. Add the Twitch chat popout as an OBS Browser Source and place it over this panel.";
    text("chat-channel-label", `@${channel} · READY`);
  }
}

function setTeam(side, team) {
  const prefix = side === "1P" ? "onep" : "twop";
  const alive = count(team?.alive);
  const total = count(team?.total);
  const hp = count(team?.hp_current);
  const maxHp = count(team?.hp_max);
  text(`${prefix}-alive`, alive === null ? "—" : alive);
  const aliveNode = $(`${prefix}-alive`);
  if (aliveNode) {
    const small = document.createElement("small");
    small.textContent = ` / ${total === null ? "5" : total}`;
    aliveNode.replaceChildren(document.createTextNode(alive === null ? "—" : String(alive)), small);
  }
  text(`${prefix}-record`, `${count(team?.kos) ?? 0} KO`);
  text(`${prefix}-hp-label`, `HP ${hp === null ? "—" : hp} / ${maxHp === null ? "—" : maxHp}`);
  const bar = $(`${prefix}-hp`);
  if (bar) bar.style.width = maxHp > 0 && hp !== null ? `${Math.max(0, Math.min(100, hp / maxHp * 100))}%` : "0%";
}

function renderRecent(items) {
  const list = $("exchange-list");
  if (!Array.isArray(items) || items.length === 0) {
    list.innerHTML = '<div class="empty-exchange">Waiting for the first agent decision…</div>';
    text("footer-decision", "Awaiting the opening map…");
    return;
  }
  const recent = items.slice(0, 4);
  list.replaceChildren();
  for (const event of recent) {
    const card = document.createElement("article");
    card.className = `exchange-item side-${event.side === "B" ? "B" : "A"}`;
    const heading = document.createElement("b");
    heading.textContent = `${event.side === "A" ? "1P" : "2P"} · ${event.agent || "AGENT"}`;
    heading.title = heading.textContent;
    const matchup = document.createElement("p");
    matchup.textContent = `${formatUnit(event.attacker_id)} → ${formatUnit(event.defender_id)}`;
    matchup.title = matchup.textContent;
    const weapon = document.createElement("small");
    weapon.textContent = `${event.weapon || "Unknown weapon"}${Number.isFinite(event.evaluation) ? ` · EV ${event.evaluation.toFixed(1)}` : ""}`;
    weapon.title = weapon.textContent;
    const rationale = document.createElement("small");
    rationale.className = "exchange-rationale";
    rationale.textContent = event.rationale || "";
    rationale.title = event.rationale || "";
    card.append(heading, matchup, weapon, rationale);
    list.append(card);
  }
  const latest = recent[0];
  const signature = `${latest.side}|${latest.attacker_id}|${latest.defender_id}|${latest.weapon}|${latest.timestamp}`;
  const action = `${latest.side === "A" ? "1P" : "2P"}: ${formatUnit(latest.attacker_id)} attacks ${formatUnit(latest.defender_id)} with ${latest.weapon || "unknown weapon"}`;
  text("footer-decision", action);
  if (signature !== lastDecisionSignature) {
    lastDecisionSignature = signature;
    list.classList.remove("new-decision");
    requestAnimationFrame(() => list.classList.add("new-decision"));
  }
}

function renderSeries(series) {
  const games = count(series?.games_played) ?? 0;
  const wins = series?.wins || {};
  const onep = count(wins["1P"]) ?? 0;
  const twop = count(wins["2P"]) ?? 0;
  const draws = count(series?.draws) ?? 0;
  text("series-score", `SERIES · 1P ${onep}–${twop} 2P · ${games}G`);
  const recent = Array.isArray(series?.recent_games) ? series.recent_games : [];
  const history = recent.length
    ? recent.map((game) => {
        const score = game.official_score?.points_by_seat;
        const result = score && Number.isInteger(score["1P"]) && Number.isInteger(score["2P"])
          ? ` ${score["1P"]}–${score["2P"]}` : "";
        return `${game.winner || "?"}${Number.isInteger(game.game_number) ? ` G${game.game_number}` : ""}${result}`;
      }).join(" · ")
    : "NO COMPLETED GAMES";
  text("series-history", `${history}${draws ? ` · ${draws} DRAW${draws === 1 ? "" : "S"}` : ""}`);
  const historyNode = $("series-history");
  if (historyNode) historyNode.title = `1P wins: ${onep}; 2P wins: ${twop}; draws: ${draws}; games: ${games}`;

  const points = series?.official_points;
  const scored = count(points?.games_scored) ?? 0;
  const totals = points?.totals || {};
  const onepPoints = count(totals["1P"]);
  const twopPoints = count(totals["2P"]);
  const official = onepPoints !== null && twopPoints !== null && scored > 0
    ? `1P ${onepPoints}–${twopPoints} 2P · ${scored} SCORED G`
    : `NO VERIFIED SCORES · ${scored}/${games} G`;
  text("official-score", official);
  const officialNode = $("official-score");
  if (officialNode) {
    const latest = points?.most_recent?.points_by_seat;
    officialNode.title = latest && Number.isInteger(latest["1P"]) && Number.isInteger(latest["2P"])
      ? `Most recent verified FE7 result: 1P ${latest["1P"]} – ${latest["2P"]} 2P`
      : "Only synchronized, recognized FE7 final result screens are included.";
  }
}

function runnerLabel(match) {
  const state = match?.runner_state || "starting";
  if (state === "complete") return match.winner ? `${match.winner} VICTORY` : "MATCH COMPLETE";
  if (state === "playing") return `LIVE · ${match.mode === "llm_duel" ? "LLM DUEL" : match.mode === "mixed_agents" ? "MODEL MATCH" : "MINIMAX"}`;
  if (state === "ready") return "READY · SUPERVISED";
  if (state === "stopped_for_supervision") return "SUPERVISOR NEEDED";
  if (state === "stopped") return "RUNNER STOPPED";
  if (state === "setting_up") return `SETUP · ${(match.runner_stage || "LINKING").replaceAll("_", " ").toUpperCase()}`;
  return state.replaceAll("_", " ").toUpperCase();
}

function render(data) {
  const match = data.match || {};
  const game = data.game || {};
  const teams = data.teams || {};
  const metrics = data.metrics || {};
  const agents = match.agents || {};
  renderSeries(data.series);
  text("agent-labels", `${agents["1P"] || "1P"} VS ${agents["2P"] || "2P"}`);
  const agentLabels = $("agent-labels");
  if (agentLabels) agentLabels.title = `${agents["1P"] || "1P"} vs ${agents["2P"] || "2P"}`;
  const turn = Number.isInteger(game.turn) && game.turn > 0 ? game.turn : null;
  const isOnline = game.coherent;
  const dot = document.querySelector(".live-dot");
  if (dot) dot.className = `live-dot${isOnline ? " connected" : " warning"}`;
  text("runner-state", runnerLabel(match));
  text("match-id", `MATCH ${match.id || "—"}`);
  text("elapsed", formatTime(match.elapsed_seconds));
  text("screen-status", isOnline ? "LINKED · FRAME SYNCED" : "WAITING FOR STABLE LINK");
  text("data-health", isOnline ? "BRIDGES SYNCED" : "SYNCING CORES");
  const modeLabel = match.mode === "llm_duel" ? "LLM DUEL"
    : match.mode === "mixed_agents" ? "MODEL VS POLICY"
      : match.mode === "minimax" ? "MINIMAX DUEL" : "SUPERVISED MATCH";
  text("footer-mode", modeLabel);
  text("footer-turn", turn);
  text("footer-phase", game.phase_label || "LINK SETUP");
  text("turn-label", turn !== null
    ? `TURN ${turn} · ${game.phase_label || "LINK ARENA"}`
    : "AWAITING LINK ARENA MAP");
  text("phase-value", game.phase_label || "SETUP");
  text("onep-alive", "—");
  setTeam("1P", teams["1P"]);
  setTeam("2P", teams["2P"]);

  const active = document.querySelector(".duel-center");
  if (active) active.className = `duel-center${game.active_side === "1P" ? " active-1p" : game.active_side === "2P" ? " active-2p" : ""}`;
  const exchanges = metrics.exchanges || {};
  const inputs = metrics.inputs || {};
  text("exchange-count", `${exchanges["1P"] ?? 0} · ${exchanges["2P"] ?? 0}`);
  text("input-count", `${inputs["1P"] ?? 0} · ${inputs["2P"] ?? 0}`);
  const last = Array.isArray(metrics.recent_exchanges) ? metrics.recent_exchanges[0] : null;
  text("eval-value", Number.isFinite(last?.evaluation) ? `${last.side === "A" ? "1P" : "2P"} ${last.evaluation.toFixed(1)}` : "—");
  renderRecent(metrics.recent_exchanges);

  const placeholder = $("screen-placeholder");
  if (obsCapture) {
    $("game-image-1p").hidden = true;
    $("game-image-2p").hidden = true;
    placeholder.hidden = true;
  }
  const warning = $("setup-warning");
  const error = match.runner_error;
  warning.hidden = !error;
  if (error) warning.textContent = `RUNNER PAUSED · ${error}`;
}

let polling = false;
async function refresh() {
  if (polling) return;
  polling = true;
  try {
    const response = await fetch("/v1/stream?frame=0", { cache: "no-store" });
    if (!response.ok) throw new Error(`stream feed returned ${response.status}`);
    render(await response.json());
  } catch (error) {
    const dot = document.querySelector(".live-dot");
    if (dot) dot.className = "live-dot warning";
    text("runner-state", "FEED DISCONNECTED");
    text("screen-status", "RECONNECTING TO RUNNER");
    text("data-health", error instanceof Error ? error.message : "FEED UNAVAILABLE");
  } finally {
    polling = false;
  }
}

let framePolling = false;
async function refreshFrames() {
  if (obsCapture || framePolling) return;
  framePolling = true;
  try {
    const response = await fetch("/v1/stream/frames", { cache: "no-store" });
    if (!response.ok) throw new Error(`capture feed returned ${response.status}`);
    const { frames } = await response.json();
    for (const [side, id] of [["1P", "game-image-1p"], ["2P", "game-image-2p"]]) {
      const image = $(id);
      if (frames?.[side]) {
        image.hidden = false;
        if (frames[side] !== lastFrames[side]) {
          lastFrames[side] = frames[side];
          image.src = frames[side];
        }
      }
    }
    $("screen-placeholder").hidden = Boolean(frames?.["1P"] && frames?.["2P"]);
  } catch {
    // Keep the last complete pair of screenshots visible while the next frame
    // arrives. Match status still reports bridge health through /v1/stream.
  } finally {
    framePolling = false;
  }
}

setChat();
refresh();
window.setInterval(refresh, 1000);
if (!obsCapture) {
  refreshFrames();
  window.setInterval(refreshFrames, 250);
}
