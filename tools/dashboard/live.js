// Live layer for the weekly-matchup report, served by tools/dashboard_server.py.
// Polls /api/live, /api/rosters and /api/static on their own intervals and redraws the
// parts of the report that change during games; the preview analysis is left as written.
(() => {
  const S = { cfg: window.DASH_BOOT, live: null, rosters: null, static: null, paused: false, timers: {}, okAt: {}, err: {} };
  const GROUPS = ["live", "rosters", "static"];
  const FIX = { JAC: "JAX", WAS: "WSH" };
  const team = (t) => FIX[t] || t;
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const f1 = (n) => (+n).toFixed(1);
  const etTime = (d, opts) => new Date(d).toLocaleString("en-US", { timeZone: "America/New_York", ...opts });
  const kickoff = (iso) => etTime(iso, { weekday: "short", hour: "numeric", minute: "2-digit" }).replace(",", "") + " ET";
  const slotLabel = (s) => (s === "RB/WR/TE" ? "FLEX" : s);
  const isBench = (s) => s === "BE" || s === "IR";

  // restore scroll after an auto-reload triggered by a new report
  try {
    const y = sessionStorage.getItem("dash-scroll");
    if (y) { sessionStorage.removeItem("dash-scroll"); addEventListener("load", () => scrollTo(0, +y)); }
  } catch {}

  // ---------- polling
  async function tick(g, force = false) {
    clearTimeout(S.timers[g]);
    if (!S.paused || force) {
      try {
        const r = await fetch(`/api/${g}${force ? "?force=1" : ""}`, { cache: "no-store" });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const res = await r.json();
        S[g] = res;
        S.err[g] = res.error || null;
        if (res.data) S.okAt[g] = Date.now() - res.age_s * 1000;
        render(g);
      } catch (e) {
        S.err[g] = `${e.message} (server unreachable?)`;
      }
      pill();
    }
    S.timers[g] = setTimeout(() => tick(g), S.cfg.intervals[g] * 1000);
  }

  function render(g) {
    if (g === "static") return checkReport();
    if (!S.live?.data) return;
    const L = S.live.data;
    S.idx = new Map(L.players.map((p) => [`${p.name}|${p.pro_team}`, p]));
    S.game = new Map();
    L.games.forEach((x) => { S.game.set(team(x.away), x); S.game.set(team(x.home), x); });
    S.me = L.matchup?.my_team_id; S.opp = L.matchup?.opponent_id;
    // fantasy matchup by team id: { mine: {team_id, score, projected}, other: {...} }
    S.mu = new Map();
    (L.matchups || []).forEach((m) => { S.mu.set(m.home.team_id, { mine: m.home, other: m.away }); S.mu.set(m.away.team_id, { mine: m.away, other: m.home }); });
    renderScore(L.matchup);
    renderGames();
    renderLiveCards();
    loadGameDetails();
    renderSidebar();
    renderCards();
    renderLens();
    const eb = document.querySelector(".eyebrow b") || document.querySelector(".eyebrow")?.appendChild(document.createElement("b"));
    if (eb) eb.textContent = `live · updated ${etTime(Date.now(), { hour: "numeric", minute: "2-digit", second: "2-digit" })} ET`;
  }

  const teamName = (id) => S.rosters?.data?.teams.find((t) => t.team_id === id)?.name || (id === S.me ? "The Man Wolf" : "Opponent");
  const shortName = (id) => (id === S.me ? "Man Wolf" : teamName(id));
  const playerOf = (name, ...teams) => teams.map((t) => S.idx.get(`${name}|${team(t)}`)).find(Boolean);

  // ---------- actual-points chip
  function chip(p) {
    if (!p || p.game_state === "pre" || p.game_state === "bye") return null;
    if (p.slot === "IR" || (["OUT", "INJURY_RESERVE"].includes(p.injury_status) && !p.points))
      return '<span class="actp neu" tabindex="0" data-v="Did not play" data-l="OUT / IR">DNP</span>';
    const d = p.points - p.projected;
    if (p.game_state === "in") {
      const g = S.game.get(p.pro_team);
      return `<span class="actp live" tabindex="0" data-v="${f1(p.points)} pts" data-l="Live — ${esc(g?.detail)}">${f1(p.points)}<small>live</small></span>`;
    }
    return `<span class="actp ${d >= 0 ? "good" : "bad"}" tabindex="0" data-v="${f1(p.points)} pts" data-l="Final · ESPN projected ${f1(p.projected)}">${f1(p.points)}<small>${d >= 0 ? "+" : "−"}${f1(Math.abs(d))}</small></span>`;
  }
  function pending(p) {
    if (!p || p.game_state === "bye" || p.on_bye) return '<span class="muted small">bye</span>';
    const g = S.game.get(p.pro_team), k = kickoff(g.kickoff);
    const night = /^(Sun|Mon|Thu) [89]:/.test(k) ? { Sun: "SNF", Mon: "MNF", Thu: "TNF" }[k.slice(0, 3)] : k;
    return `<span class="muted small">${night}</span>`;
  }

  // ---------- 1. live score panel
  function renderScore(m) {
    const sec = document.getElementById("matchup");
    if (!sec || !m) return;
    let box = sec.querySelector(".livebox");
    if (!box) {
      sec.querySelector("h2").insertAdjacentHTML("afterend", '<div class="livebox"></div><h3 class="pregame">Pre-game projection <span class="muted small">(unchanged)</span></h3>');
      box = sec.querySelector(".livebox");
    }
    const me = m.me, op = m.opponent, mx = Math.max(me.projected_final, op.projected_final, 1) * 1.3;
    const seg = (v, cls, k, lab) => (v > 0 ? `<span class="sseg ${cls} ${k}" style="width:${(v / mx) * 100}%" tabindex="0" data-v="${f1(v)}" data-l="${esc(lab)}"></span>` : "");
    const lead = me.score - op.score;
    const row = (t, id, cls, sign) => `<div class="sbrow"><div class="sbname"><b>${esc(teamName(id))}</b><span>${sign * lead > 0 ? "leads" : sign * lead < 0 ? "trails" : "tied"}${lead ? " by " + f1(Math.abs(lead)) : ""}</span></div>
      <div class="sbtrack">${seg(t.banked, cls, "solid", "Banked (games final)")}${seg(t.live, cls, "live", "In live games: " + t.playing.map((p) => p.name).join(", "))}${seg(t.remaining_projection, cls, "soft", "ESPN projection still to play: " + (t.to_play.map((p) => p.name).join(", ") || "nobody"))}
      <span class="sbtot">${f1(t.score)}<small> → ${f1(t.projected_final)}</small></span></div></div>`;
    const left = (t) => (t.to_play.length ? "to play: " + t.to_play.map((p) => `${esc(p.name)} <span class="muted">(${kickoff(S.game.get(p.pro_team)?.kickoff).slice(0, 3)}, proj ${f1(p.projected)})</span>`).join(", ") : "all starters done or playing");
    const margin = me.projected_final - op.projected_final, band = 36;
    const done = (id) => S.live.data.players.filter((p) => p.fantasy_team_id === id && p.starter && p.game_state !== "pre").sort((a, b) => b.points - a.points).slice(0, 2);
    const np = (p) => `${esc(p.name)} ${f1(p.points)} <span class="muted">(proj ${f1(p.projected)})</span>`;
    const bench = S.live.data.players.filter((p) => p.fantasy_team_id === S.me && p.slot === "BE" && p.game_state === "post" && p.points > 0).sort((a, b) => b.points - a.points)[0];
    const notes = [
      done(S.opp).length && `<li><b>${esc(shortName(S.opp))}'s best:</b> ${done(S.opp).map(np).join("; ")}.</li>`,
      done(S.me).length && `<li><b>Our best:</b> ${done(S.me).map(np).join("; ")}.</li>`,
      bench && `<li><b>Best on our bench:</b> ${np(bench)}.</li>`,
    ].filter(Boolean).join("");
    box.innerHTML = `<h3>Live score <span class="muted small">· auto-updating</span></h3>
      <div class="sbars">${row(me, S.me, "s1", 1)}${row(op, S.opp, "s2", -1)}
      <div class="legend"><span><i class="key s1 solid"></i>Banked</span><span><i class="key s1 live"></i>Live game</span><span><i class="key s1 soft"></i>Still to play (ESPN proj)</span><span class="muted">score → projected finish</span></div></div>
      <p class="small"><b>${esc(shortName(S.me))}</b> ${left(me)}. <b>${esc(shortName(S.opp))}</b> ${left(op)}.</p>
      <p class="small"><b>Projected finish:</b> ${f1(me.projected_final)} – ${f1(op.projected_final)} (margin ${margin >= 0 ? "+" : ""}${f1(margin)}), ${Math.abs(margin) < band ? `inside the ±${band} toss-up band` : `outside the ±${band} band`}. ESPN misses individual players by ~6 pts: a lean, not a result.</p>
      ${notes ? `<ul class="small">${notes}</ul>` : ""}`;
  }

  // ---------- 2. game headers
  function gameResult(g) {
    if (g.state === "post") {
      const aw = g.away_score > g.home_score, hw = g.home_score > g.away_score;
      return `<span class="gst">${esc(g.detail)}</span>${aw ? "<b>" : ""}${g.away} ${g.away_score}${aw ? "</b>" : ""} – ${hw ? "<b>" : ""}${g.home_score} ${g.home}${hw ? "</b>" : ""}`;
    }
    if (g.state === "in") return `<span class="gst">Live · ${esc(g.detail)}</span>${g.away} ${g.away_score}–${g.home_score} ${g.home}`;
    return `<span class="gst">Upcoming</span>${kickoff(g.kickoff)}${g.line ? ` · line now ${esc(g.line)}, total ${g.over_under}` : ""}`;
  }
  const sectionTeams = (sec) => sec.id.replace(/^g-/, "").toUpperCase().split("-");
  function renderGames() {
    document.querySelectorAll("section.game[id^='g-']").forEach((sec) => {
      const g = S.game.get(sectionTeams(sec)[0]);
      if (!g) return;
      let el = sec.querySelector(".gres");
      if (!el) { sec.querySelector(".when")?.insertAdjacentHTML("afterend", '<div class="gres"></div>'); el = sec.querySelector(".gres"); }
      if (!el) return;
      el.className = `gres ${g.state}`;
      el.innerHTML = gameResult(g);
    });
  }

  // ---------- 2b. live game card (in-progress games only): score + clock, situation + field,
  // win probability ring + sparkline, fantasy stat lines, collapsible drive/scoring/team detail.
  // Field runs left = away end zone (0) to right = home end zone (100).
  function ballSpot(g, s) {
    const m = (s.possession_text || "").match(/^([A-Z]{2,3})?\s*(\d{1,2})$/);
    if (!m) return null;
    const yd = +m[2];
    const x = yd === 50 || !m[1] ? 50 : team(m[1]) === team(g.away) ? yd : 100 - yd;
    const dir = team(s.possession) === team(g.away) ? 1 : -1; // away drives toward the home end zone
    const goal = /goal/i.test(s.down_distance_text || s.short_text || "");
    const togo = goal ? (dir > 0 ? 100 : 0) : Math.min(100, Math.max(0, x + dir * (s.distance || 0)));
    return { x, togo, dir };
  }
  const QTR = 900;
  function clockRing(g) {
    const per = g.period || 1, left = g.clock_s ?? QTR;
    const frac = Math.min(1, ((Math.min(per, 4) - 1) * QTR + (QTR - left)) / (4 * QTR));
    const r = 15, c = 2 * Math.PI * r;
    const lab = per > 4 ? "OT" : `Q${per}`;
    return `<span class="lc-clock" tabindex="0" data-v="${lab} ${esc(g.display_clock || "")}" data-l="${Math.round(frac * 100)}% of regulation played">
      <svg viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="${r}" class="ring-track"/><circle cx="20" cy="20" r="${r}" class="ring-clock" stroke-dasharray="${(frac * c).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 20 20)"/></svg>
      <span><b>${lab}</b><small>${esc(g.display_clock || "")}</small></span></span>`;
  }
  function wpRing(wp, g) {
    const home = wp.home_pct, away = 100 - home, lead = home >= away ? [g.home, home, "s2"] : [g.away, away, "s1"];
    const r = 24, c = 2 * Math.PI * r, gap = 2;
    const arc = (pct, off, cls) => `<circle cx="30" cy="30" r="${r}" class="ring-${cls}" stroke-dasharray="${Math.max(0, (pct / 100) * c - gap).toFixed(1)} ${c.toFixed(1)}" stroke-dashoffset="${(-off / 100 * c).toFixed(1)}" transform="rotate(-90 30 30)"/>`;
    const d = wp.last_play_delta || 0, dTeam = d >= 0 ? g.home : g.away;
    return `<div class="lc-wp" tabindex="0" data-v="${esc(g.away)} ${f1(away)}% · ${esc(g.home)} ${f1(home)}%" data-l="ESPN win probability">
      <svg viewBox="0 0 60 60" role="img" aria-label="${esc(lead[0])} ${f1(lead[1])}% to win">${arc(away, 0, "s1")}${arc(home, away, "s2")}</svg>
      <span class="lc-wpc"><b>${Math.round(lead[1])}%</b><small>${esc(lead[0])}</small></span></div>
      ${Math.abs(d) >= 0.1 ? `<span class="lc-delta muted small">${d >= 0 ? "▲" : "▼"} ${esc(dTeam)} ${f1(Math.abs(d))} last play</span>` : ""}`;
  }
  function spark(wp, g) {
    const pts = wp.series, n = pts.length;
    if (n < 2) return "";
    const W = 150, H = 48, x = (i) => (i / (n - 1)) * W, y = (v) => H - (v / 100) * H;
    const hits = pts.map((v, i) => `<rect x="${(x(i) - W / n / 2).toFixed(1)}" y="0" width="${(W / n).toFixed(1)}" height="${H}" fill="transparent" data-v="${esc(g.home)} ${f1(v)}%" data-l="Home win probability through the game"></rect>`).join("");
    // y: top = home certain, middle = 50/50, bottom = away certain; x: kickoff -> now
    return `<div class="lc-spark"><div class="lc-sparkrow"><span class="lc-sparky muted"><span>${esc(g.home)}</span><span>${esc(g.away)}</span></span>
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(g.home)} win probability from kickoff to now">
      <line x1="0" x2="${W}" y1="${H / 2}" y2="${H / 2}" class="wpmid"/><polyline points="${pts.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ")}" class="wpline"/>${hits}</svg></div>
      <span class="lc-sparkax muted"><span>kickoff</span><span>50/50 line</span><span>now</span></span></div>`;
  }
  // "12 car 57 yds · 2-15 (3 tgt)", "14/22 187 yds 1 TD 1 INT"
  function statText(st) {
    const out = [], td = (n) => (n ? ` ${n} TD` : "");
    if (st.passingAttempts) out.push(`${st.passingCompletions || 0}/${st.passingAttempts} ${st.passingYards || 0} yds${td(st.passingTouchdowns)}${st.passingInterceptions ? ` ${st.passingInterceptions} INT` : ""}`);
    if (st.rushingAttempts) out.push(`${st.rushingAttempts} car ${st.rushingYards || 0} yds${td(st.rushingTouchdowns)}`);
    if (st.receivingTargets || st.receivingReceptions) out.push(`${st.receivingReceptions || 0}-${st.receivingYards || 0}${td(st.receivingTouchdowns)} (${st.receivingTargets || 0} tgt)`);
    if (st.lostFumbles) out.push(`${st.lostFumbles} fum lost`);
    return out.join(" · ") || "no stats yet";
  }
  // Field state from possession (ESPN has no per-player snap data): a player's unit is on the
  // field when his team has the ball (a D/ST when the opponent has it); red zone = that drive
  // is inside the 20. "Last play" = named in the last play's text ("D.Henry").
  const FSTATE = {
    rz: ["◎", "Red zone"], on: ["●", "On field"], off: ["○", "Sideline"],
    rzd: ["◎", "Defending red zone"], ond: ["●", "Defense on field"],
  };
  function fieldState(p, s) {
    if (!s?.possession) return "off";
    const hasBall = team(s.possession) === p.pro_team;
    if (p.position === "D/ST") return hasBall ? "off" : s.is_red_zone ? "rzd" : "ond";
    return !hasBall ? "off" : s.is_red_zone ? "rz" : "on";
  }
  function onLastPlay(p, text) {
    if (!text || p.position === "D/ST") return false;
    const parts = p.name.replace(/\s+(Jr\.?|Sr\.?|II|III|IV)$/, "").split(" ");
    const last = parts.slice(1).join(" ").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(`\\b${parts[0][0]}\\.\\s?${last}\\b`).test(text);
  }
  // the player's fantasy matchup this week: his team first, ESPN live score -> live projection
  function fantasyMatchup(id) {
    const m = S.mu?.get(id);
    if (!m) return "";
    const nm = (t) => (t.team_id === S.me ? "Man Wolf" : t.team_id === S.opp ? shortName(S.opp) : teamName(t.team_id));
    const diff = m.mine.score - m.other.score, lead = diff > 0 ? "mine" : diff < 0 ? "other" : null;
    const side = (t, k) => `<span class="mu-t${lead === k ? " lead" : ""}" title="${esc(teamName(t.team_id))}"><span class="mu-n">${esc(nm(t))}</span> <b>${f1(t.score)}</b> <small>→ ${f1(t.projected)}</small></span>`;
    const st = !lead ? '<span class="mu-st">tied</span>' : `<span class="mu-st ${lead === "mine" ? "up" : "down"}">${lead === "mine" ? "▲ leads" : "▼ trails"} by ${f1(Math.abs(diff))}</span>`;
    return `<span class="lc-mu small" aria-label="Fantasy matchup">${side(m.mine, "mine")}<span class="muted">vs</span>${side(m.other, "other")}${st}</span>`;
  }
  // last play seen per game (id, else text): a row flashes only when a NEW play names him,
  // never on a plain refresh and never on page load
  S.seenPlay = {};
  function newPlay(g) {
    const lp = g.situation?.last_play, key = lp ? lp.id || lp.text : null, prev = S.seenPlay[g.id];
    S.seenPlay[g.id] = key;
    return prev !== undefined && key != null && key !== prev;
  }
  // flash start time per player id, so a re-render mid-flash continues the animation instead of cutting it
  S.flashStart = {};
  const FLASH_MS = 1500;
  function flashAttr(p) {
    const age = Date.now() - (S.flashStart[p.player_id] || 0);
    return age < FLASH_MS ? { cls: " flash", style: ` style="animation-delay:-${age}ms"` } : { cls: "", style: "" };
  }
  function playerRows(ps, s) {
    const abbrev = (id) => S.rosters?.data?.teams.find((t) => t.team_id === id)?.abbrev || "";
    return ps.map((p) => {
      const cls = p.fantasy_team_id === S.me ? "mw" : p.fantasy_team_id === S.opp ? "op" : "";
      const fs = fieldState(p, s), [icon, lab] = FSTATE[fs], lp = onLastPlay(p, s?.last_play?.text);
      const fl = flashAttr(p);
      return `<li class="${cls}${fl.cls}"${fl.style} data-fs="${fs.replace(/d$/, "")}"><span class="lc-pn">${esc(p.name)} <span class="muted small">${esc(p.position)} · ${esc(p.pro_team)}</span></span>
        <span class="tag ${cls}">${cls === "mw" ? "Man Wolf" : cls === "op" ? esc(shortName(S.opp)) : esc(abbrev(p.fantasy_team_id))}</span>
        <span class="lc-st small"><span class="fstat ${fs.replace(/d$/, "")}"><i aria-hidden="true">${icon}</i>${lab}</span>${lp ? '<span class="lastp" title="Named in the last play">★ Last play</span>' : ""}
        <span>${p.position === "D/ST" ? "team defense" : esc(statText(p.stats || {}))}</span></span>
        <span class="lc-pts">${f1(p.points)}</span>${breakdown(p)}${fantasyMatchup(p.fantasy_team_id)}</li>`;
    }).join("");
  }
  function renderLiveCards() {
    document.querySelectorAll("section.game[id^='g-']").forEach((sec) => {
      const g = S.game.get(sectionTeams(sec)[0]);
      let el = sec.querySelector(".lcard");
      if (g?.state !== "in") { el?.remove(); sec.classList.remove("is-live"); return; }
      if (!el) {
        sec.querySelector(".ghead").insertAdjacentHTML("afterend", `<div class="lcard" data-id="${g.id}"></div>`);
        el = sec.querySelector(".lcard");
      }
      sec.classList.add("is-live");
      const open = new Set([...el.querySelectorAll("details[open]")].map((d) => d.dataset.k)); // keep expanded sections open across refreshes
      const s = g.situation || {}, d = S.detail[g.id] || {}, cd = d.current_drive;
      if (newPlay(g)) S.live.data.players.filter((p) => onLastPlay(p, s.last_play?.text) && [team(g.away), team(g.home)].includes(p.pro_team))
        .forEach((p) => { S.flashStart[p.player_id] = Date.now(); });
      const pcls = team(s.possession) === team(g.away) ? "s1" : "s2";
      const pips = (n) => `<span class="pips" aria-label="${n ?? 0} timeouts">${[0, 1, 2].map((i) => `<i class="${i < (n ?? 0) ? "on" : ""}"></i>`).join("")}</span>`;
      const teamRow = (ab, sc, q, to, cls) => `<div class="lc-team"><i class="key ${cls}"></i><b>${esc(ab)}</b>
        ${team(s.possession) === team(ab) ? '<span class="lc-ball" title="Has the ball">◀</span>' : '<span class="lc-ball"></span>'}
        <span class="lc-sc" tabindex="0" data-v="${sc}" data-l="By quarter: ${q.join(" · ") || "—"}">${sc}</span>${pips(to)}</div>`;
      const spot = ballSpot(g, s);
      const field = spot ? `<div class="field" role="img" aria-label="${esc(s.possession || "")} ball, ${esc(s.down_distance_text || "")}">
          <span class="fez l">${esc(g.away)}</span><span class="fez r">${esc(g.home)}</span>
          <span class="frz ${spot.dir > 0 ? "r" : "l"}${s.is_red_zone ? " on" : ""}"></span>
          ${[10, 20, 30, 40, 50, 60, 70, 80, 90].map((y) => `<i class="fyl" style="left:${y}%"><b>${y > 50 ? 100 - y : y}</b></i>`).join("")}
          <i class="flos" style="left:${spot.x}%" tabindex="0" data-v="Line of scrimmage" data-l="${esc(s.possession_text)}"></i>
          <i class="ftogo" style="left:${spot.togo}%" tabindex="0" data-v="Line to gain" data-l="${esc(s.short_text || "")}"></i>
          <i class="fball ${pcls}" style="left:${spot.x}%"></i></div>` : "";
      const finished = cd?.result && s.possession && team(cd.team) !== team(s.possession);
      const driveStats = cd ? `<div class="lc-drive small"><span class="muted">${finished ? `Last drive (${esc(cd.team)}): ${esc(cd.result)}` : `${esc(cd.team)} drive`}</span>
          <span title="Plays">⟳ ${cd.plays ?? 0} plays</span><span title="Yards">↗ ${cd.yards ?? 0} yds</span>${cd.time_elapsed ? `<span title="Time of possession">⏱ ${esc(cd.time_elapsed)}</span>` : ""}${cd.start ? `<span class="muted">from ${esc(cd.start)}</span>` : ""}</div>` : "";
      // fantasy starters in this game (bench ignored): Man Wolf + opponent first, then other teams'
      const inGame = S.live.data.players.filter((p) => [team(g.away), team(g.home)].includes(p.pro_team) && p.starter)
        .sort((a, b) => b.points - a.points);
      const ours = inGame.filter((p) => p.fantasy_team_id === S.me || p.fantasy_team_id === S.opp)
        .sort((a, b) => (a.fantasy_team_id !== S.me) - (b.fantasy_team_id !== S.me) || b.points - a.points);
      const others = inGame.filter((p) => p.fantasy_team_id !== S.me && p.fantasy_team_id !== S.opp);
      const ts = d.team_stats || {}, TS = [["totalYards", "Total yards"], ["yardsPerPlay", "Yards / play"], ["netPassingYards", "Pass yards"], ["rushingYards", "Rush yards"],
        ["thirdDownEff", "3rd down"], ["turnovers", "Turnovers"], ["possessionTime", "Possession"]].filter(([k]) => ts[g.away]?.[k] != null || ts[g.home]?.[k] != null);
      const det = (k, title, body) => (body ? `<details data-k="${k}"${open.has(k) ? " open" : ""}><summary>${title}</summary>${body}</details>` : "");
      el.innerHTML = `<div class="lc-top">
        <div class="lc-score">${teamRow(g.away, g.away_score, g.away_by_quarter || [], s.away_timeouts, "s1")}${teamRow(g.home, g.home_score, g.home_by_quarter || [], s.home_timeouts, "s2")}${clockRing(g)}</div>
        <div class="lc-sit">
          <div class="lc-chips">${s.possession ? `<span class="poss ${pcls}">${esc(s.possession)} ball</span>` : ""}${s.short_text ? `<span class="chip"><b>${esc(s.short_text)}</b></span>` : ""}${s.possession_text ? `<span class="chip">at ${esc(s.possession_text)}</span>` : ""}${s.is_red_zone ? '<span class="rz">Red zone</span>' : ""}</div>
          ${field}${driveStats}
          ${s.last_play?.text ? `<p class="lastplay small"><b>Last play:</b> ${esc(s.last_play.text)}</p>` : ""}
        </div>
        <div class="lc-prob">${d.win_probability ? `<div class="lc-wprow">${wpRing(d.win_probability, g)}</div>${spark(d.win_probability, g)}` : '<span class="muted small">Win probability loading…</span>'}</div>
      </div>
      <div class="lc-players">
        ${ours.length || others.length ? `<p class="fkey muted"><span class="fstat on"><i>●</i>On field</span><span class="fstat rz"><i>◎</i>Red zone</span><span class="fstat off"><i>○</i>Sideline</span><span>from possession, not individual snaps · ★ = named in the last play</span></p>${PBK_KEY}` : ""}
        ${ours.length ? `<h4>${esc(shortName(S.me))} vs ${esc(shortName(S.opp))}</h4><ul>${playerRows(ours, s)}</ul>` : ""}
        ${others.length ? `<h4>Other starters in this game</h4><ul class="others">${playerRows(others, s)}</ul>` : ""}
        ${!ours.length && !others.length ? '<p class="muted small">No league starters in this game.</p>' : ""}
      </div>
      <div class="lc-more">
        ${det("plays", `Plays this drive${cd?.recent_plays?.length ? ` (${cd.recent_plays.length})` : ""}`, cd?.recent_plays?.length ? `<ol class="plays">${cd.recent_plays.map((p) => `<li${p.scoring ? ' class="score"' : ""}><span class="pdd muted">${esc(p.down_distance_text || p.type || "")}</span>${esc(p.text || "")}</li>`).join("")}</ol>` : "")}
        ${det("drives", "Previous drives", (d.previous_drives || []).length ? `<ul class="plain">${d.previous_drives.map((x) => `<li><b>${esc(x.team || "")}</b> ${esc(x.result || "")} <span class="muted">${esc(x.description || "")}</span></li>`).join("")}</ul>` : "")}
        ${det("scoring", `Scoring plays (${(d.scoring_plays || []).length})`, (d.scoring_plays || []).length ? `<ul class="plain">${d.scoring_plays.map((x) => `<li><span class="muted">Q${x.period} ${esc(x.clock || "")}</span> <b>${esc(x.team || "")}</b> ${esc(x.text || "")} <span class="muted">(${x.away_score}–${x.home_score})</span></li>`).join("")}</ul>` : "")}
        ${det("teamstats", "Team stats", TS.length ? `<table class="lc-ts"><thead><tr><th></th><th>${esc(g.away)}</th><th>${esc(g.home)}</th></tr></thead><tbody>${TS.map(([k, lab]) => `<tr><td>${lab}</td><td>${esc(ts[g.away]?.[k] ?? "—")}</td><td>${esc(ts[g.home]?.[k] ?? "—")}</td></tr>`).join("")}</tbody></table>` : "")}
      </div>`;
    });
  }

  S.detail = {};
  async function loadGameDetails() {
    const live = S.live.data.games.filter((g) => g.state === "in");
    await Promise.all(live.map(async (g) => {
      try {
        const r = await fetch(`/api/game/${g.id}`, { cache: "no-store" });
        const res = await r.json();
        if (res.data) S.detail[g.id] = res.data;
      } catch {}
    }));
    if (live.length) renderLiveCards();
  }

  // ---------- 3. sidebar: scores + one dot per Man Wolf / opponent player
  function renderSidebar() {
    document.querySelectorAll(".gside a.sbg[href^='#g-']").forEach((a) => {
      const [aw, hm] = a.getAttribute("href").slice(3).toUpperCase().split("-");
      const g = S.game.get(aw);
      let gn = a.querySelector(".sbgn");
      if (!gn) { gn = document.createElement("span"); gn.className = "sbgn"; gn.append(...a.childNodes); a.append(gn); }
      const ps = S.live.data.players.filter((p) => [aw, hm].includes(p.pro_team) && [S.me, S.opp].includes(p.fantasy_team_id));
      gn.querySelectorAll(".sbds").forEach((x) => x.remove());
      for (const [id, cls] of [[S.me, "mw"], [S.opp, "op"]]) {
        const mine = ps.filter((p) => p.fantasy_team_id === id).sort((x, y) => isBench(x.slot) - isBench(y.slot));
        if (!mine.length) continue;
        gn.insertAdjacentHTML("beforeend", `<span class="sbds">${mine.map((p) => `<i class="sbd ${cls}${isBench(p.slot) ? " bench" : ""}" title="${esc(p.name)} · ${esc(shortName(id))} ${isBench(p.slot) ? "bench" : "starter"} (${slotLabel(p.slot)})"></i>`).join("")}</span>`);
      }
      a.querySelector(".sbsc")?.remove();
      if (g && g.state !== "pre") {
        a.classList.add("wsc");
        a.insertAdjacentHTML("beforeend", `<small class="sbsc${g.state === "in" ? " live" : ""}">${g.state === "in" ? "● " : ""}${g.away} ${g.away_score}–${g.home_score} ${g.home}${/OT/.test(g.detail) ? " OT" : ""}</small>`);
      }
      a.querySelector(".sbdd")?.remove();
      const s = g?.state === "in" ? g.situation : null;
      if (s?.short_text) a.insertAdjacentHTML("beforeend", `<small class="sbdd${s.is_red_zone ? " rz" : ""}">${esc(s.possession || "")} · ${esc(s.short_text)}${s.possession_text ? " · " + esc(s.possession_text) : ""}</small>`);
    });
  }

  // ---------- 4. player cards: points chip, slot changes, pre-game status
  function renderCards() {
    document.querySelectorAll("section.game[id^='g-']").forEach((sec) => {
      const [aw, hm] = sectionTeams(sec);
      let moved = false;
      sec.querySelectorAll("details.pcard").forEach((card) => {
        const sum = card.querySelector("summary");
        const p = playerOf(card.querySelector(".pn")?.textContent.trim(), aw, hm);
        if (!p) return;
        sum.querySelector(".actp")?.remove();
        const c = chip(p);
        if (c) sum.querySelector(".pj")?.insertAdjacentHTML("beforebegin", c);
        sum.querySelector(".pbk")?.remove();
        const bk = breakdown(p);
        if (bk) sum.insertAdjacentHTML("beforeend", bk);
        // slot label "POS · SLOT"
        const lab = sum.querySelector(".muted.small");
        const m = lab?.textContent.match(/^(.*) · (.+)$/);
        if (m && m[2] !== slotLabel(p.slot)) {
          const wasBench = isBench(m[2] === "FLEX" ? "RB/WR/TE" : m[2]);
          lab.textContent = `${m[1]} · ${slotLabel(p.slot)}`;
          if (wasBench !== isBench(p.slot)) { moveCard(sec, card, isBench(p.slot)); moved = true; }
        }
        if (p.game_state === "pre") statusBadge(sum, p);
      });
      if (moved) recount(sec);
      if (!sec.querySelector(".pbk-key") && sec.querySelector(".pbk")) sec.querySelector("h4.grp")?.insertAdjacentHTML("beforebegin", PBK_KEY);
    });
  }

  // ---------- 4b. points breakdown: how a player's points were earned (ESPN's per-category points)
  const PBK_ORDER = ["yards", "td", "rec", "dst", "other"];
  const PBK_MAX = 40; // shared scale across cards so bars are comparable
  const PBK_KEY = `<p class="pbk-key muted small">Points from: ${[["yards", "yards"], ["td", "TDs"], ["rec", "receptions"], ["dst", "D/ST"], ["other", "other"]]
    .map(([g, l]) => `<span><i class="pk g-${g}"></i>${l}</span>`).join("")}<span><i class="pk g-neg"></i>points lost</span></p>`;
  const num = (n) => (n < 0 ? "−" : "") + f1(Math.abs(n));
  function breakdown(p) {
    if (!p || p.game_state === "pre" || p.game_state === "bye" || p.slot === "IR") return "";
    const items = p.points_breakdown || [];
    if (!items.length) return '<span class="pbk"><span class="pbk-txt muted">No points yet</span></span>';
    const pos = items.filter((i) => i.points > 0).sort((a, b) => PBK_ORDER.indexOf(a.group) - PBK_ORDER.indexOf(b.group) || b.points - a.points);
    const lost = -items.filter((i) => i.points < 0).reduce((t, i) => t + i.points, 0);
    const gross = pos.reduce((t, i) => t + i.points, 0);
    const w = (v) => (Math.min(v, PBK_MAX) / PBK_MAX) * 100;
    const tip = (i) => `data-v="${esc(i.label)} · ${num(i.points)} pts" data-l="${i.stat != null ? esc(i.stat) + " → " : ""}${num(i.points)} fantasy points${i.provisional ? " (provisional: tier can change before the final whistle)" : ""}"`;
    const segs = pos.map((i) => `<span class="pseg pk g-${i.group}" style="width:${w(i.points)}%" tabindex="0" ${tip(i)}></span>`).join("");
    const negs = items.filter((i) => i.points < 0);
    const over = lost ? `<span class="pseg-neg" style="left:${w(Math.max(0, gross - lost))}%;width:${w(Math.min(lost, gross || lost))}%" tabindex="0" data-v="Points lost · −${f1(lost)}" data-l="${esc(negs.map((i) => `${i.stat ?? ""} ${i.short} ${num(i.points)}`.trim()).join(", "))}"></span>` : "";
    const txt = [...pos, ...items.filter((i) => i.points < 0)].map((i) => `<span class="${i.points < 0 ? "neg" : ""}">${i.stat != null ? esc(i.stat) + " " : ""}${esc(i.short)} <b>${num(i.points)}</b>${i.provisional ? ' <em class="prov">provisional</em>' : ""}</span>`).join(" · ");
    return `<span class="pbk"><span class="pbar-bk" role="img" aria-label="${esc(p.name)}: ${esc(items.map((i) => `${i.label} ${num(i.points)}`).join(", "))}">${segs}${over}</span><span class="pbk-txt">${txt}</span></span>`;
  }
  function moveCard(sec, card, toBench) {
    let grp = sec.querySelector("details.benchgrp");
    if (toBench) {
      if (!grp) {
        const last = [...sec.querySelectorAll("details.pcard")].filter((c) => !c.closest(".benchgrp")).pop();
        (last || sec.querySelector("h4.grp")).insertAdjacentHTML("afterend", '<details class="benchgrp"><summary>Bench &amp; IR</summary></details>');
        grp = sec.querySelector("details.benchgrp");
      }
      card.removeAttribute("open");
      grp.append(card);
    } else {
      (grp || sec.querySelector("h4.grp")).insertAdjacentElement(grp ? "beforebegin" : "afterend", card);
    }
  }
  function recount(sec) {
    const all = [...sec.querySelectorAll("details.pcard")];
    const bench = all.filter((c) => c.closest(".benchgrp"));
    const h = sec.querySelector("h4.grp");
    if (h) h.innerHTML = `Starters <span class="muted small">(${all.length - bench.length})</span>`;
    const grp = sec.querySelector("details.benchgrp");
    if (!grp) return;
    if (!bench.length) return grp.remove();
    const mine = bench.filter((c) => c.classList.contains("mw")).map((c) => esc(c.querySelector(".pn").textContent));
    grp.querySelector("summary").innerHTML = `Bench &amp; IR <span class="muted small">(${bench.length})</span>` +
      (mine.length ? ` <span class="tag mw">Man Wolf</span> <span class="small">${mine.join(", ")}</span>` : "");
  }
  function statusBadge(sum, p) {
    const nfl = (S.rosters?.data?.nfl_injuries?.[p.pro_team] || []).find((i) => i.name === p.name)?.status;
    const espn = p.injury_status;
    let kind = null, lab = null;
    if (/^(Out|Injured Reserve|Doubtful)/i.test(nfl || "") || ["OUT", "DOUBTFUL", "INJURY_RESERVE", "SUSPENSION"].includes(espn)) { kind = ["crit", "✕", "OUT"]; lab = nfl || espn; }
    else if (/^Questionable/i.test(nfl || "") || espn === "QUESTIONABLE") { kind = ["warn", "!", "Q"]; lab = nfl || espn; }
    if (!kind) return; // never downgrade a hand-written status to "Active"
    const b = sum.querySelector(".sbadge");
    if (!b) return;
    b.dataset.v = kind[2]; b.dataset.l = `Live injury report: ${lab}`;
    b.innerHTML = `<i class="sico ${kind[0]}">${kind[1]}</i>${kind[2]}`;
  }

  // ---------- 5. lens tables: Actual column + slot
  function renderLens() {
    for (const id of ["lens", "opp"]) {
      const sec = document.getElementById(id), table = sec?.querySelector("table");
      if (!table) continue;
      const ths = [...table.querySelectorAll("thead th")];
      let col = ths.findIndex((th) => th.textContent.trim() === "Actual");
      if (col < 0) {
        const pj = ths.findIndex((th) => th.textContent.trim() === "ESPN proj");
        if (pj < 0) continue;
        ths[pj].insertAdjacentHTML("afterend", "<th>Actual</th>");
        table.querySelectorAll("tbody tr").forEach((tr) => tr.children[pj]?.insertAdjacentHTML("afterend", '<td class="nowrap"></td>'));
        col = pj + 1;
      }
      table.querySelectorAll("tbody tr").forEach((tr) => {
        const name = tr.querySelector(".pname")?.textContent.trim();
        const tm = tr.querySelector(".pname + .muted")?.textContent.match(/· ([A-Z]{2,3}) (?:vs|@) /);
        const cell = tr.children[col];
        if (!name || !cell) return;
        const p = tm && playerOf(name, tm[1]);
        cell.innerHTML = !tm ? '<span class="muted small">bye</span>' : !p ? "—" : chip(p) || pending(p);
        const slot = tr.querySelector("td.slot");
        if (p && slot && slot.textContent !== slotLabel(p.slot)) slot.textContent = slotLabel(p.slot);
      });
    }
  }

  // ---------- static: reload when the report file changes
  function checkReport() {
    const m = S.static?.data?.mtime;
    if (m == null) return;
    if (S.reportMtime == null) S.reportMtime = m;
    else if (m !== S.reportMtime) {
      try { sessionStorage.setItem("dash-scroll", String(scrollY)); } catch {}
      location.reload();
    }
  }

  // ---------- status pill + settings
  const LABELS = { live: "Scores & points", rosters: "Rosters & injuries", static: "Report file check" };
  document.body.insertAdjacentHTML("beforeend", `
    <div class="dash" role="region" aria-label="Live dashboard">
      <button class="dash-pill" aria-expanded="false"><i class="dash-dot"></i><span class="dash-txt">Connecting…</span><span aria-hidden="true">⚙</span></button>
      <div class="dash-panel" hidden>
        ${GROUPS.map((g) => `<label><span>${LABELS[g]}</span><span class="dash-in"><input type="number" data-g="${g}" min="${S.cfg.limits[g][0]}" max="${S.cfg.limits[g][1]}" value="${S.cfg.intervals[g]}"> s</span><small data-age="${g}"></small></label>`).join("")}
        <div class="dash-btns"><button data-act="pause">Pause</button><button data-act="now">Refresh now</button></div>
        <p class="dash-err" hidden></p>
      </div>
    </div>`);
  const D = document.querySelector(".dash"), panel = D.querySelector(".dash-panel"), btn = D.querySelector(".dash-pill");
  btn.addEventListener("click", () => { panel.hidden = !panel.hidden; btn.setAttribute("aria-expanded", String(!panel.hidden)); });
  panel.addEventListener("change", async (e) => {
    const g = e.target.dataset.g;
    if (!g) return;
    try {
      const r = await fetch("/api/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ [g]: +e.target.value }) });
      S.cfg = { ...S.cfg, ...(await r.json()) };
    } catch {}
    e.target.value = S.cfg.intervals[g];
    tick(g);
  });
  panel.addEventListener("click", (e) => {
    const act = e.target.dataset.act;
    if (act === "pause") { S.paused = !S.paused; e.target.textContent = S.paused ? "Resume" : "Pause"; pill(); }
    if (act === "now") GROUPS.forEach((g) => tick(g, true));
  });
  const ago = (t) => (t ? `${Math.max(0, Math.round((Date.now() - t) / 1000))}s ago` : "—");
  function pill() {
    const errs = GROUPS.filter((g) => S.err[g]);
    D.dataset.state = S.paused ? "paused" : errs.length ? "stale" : S.okAt.live ? "ok" : "wait";
    D.querySelector(".dash-txt").textContent = S.paused ? "Paused" : `${errs.length ? "Stale" : "Live"} · ${ago(S.okAt.live)}`;
    GROUPS.forEach((g) => { D.querySelector(`[data-age="${g}"]`).textContent = `updated ${ago(S.okAt[g])}`; });
    const pe = D.querySelector(".dash-err");
    pe.hidden = !errs.length;
    pe.textContent = errs.map((g) => `${LABELS[g]}: ${S.err[g]}`).join(" · ");
  }
  setInterval(pill, 1000);
  GROUPS.forEach((g) => tick(g));
})();
