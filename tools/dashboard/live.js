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
    renderScore(L.matchup);
    renderGames();
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
    });
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
