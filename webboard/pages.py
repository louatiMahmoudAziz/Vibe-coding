"""HTML pages for the leaderboard server (no template engine, no deps).

All dynamic data reaches the browser through the JSON API and is rendered
client-side with DOM `textContent`, so participant-controlled strings are
never interpolated into HTML.
"""

BASE_CSS = """
  :root {
    --bg: #0b1020; --panel: #131a30; --panel-2: #182142; --text: #e8ecf8;
    --muted: #8b93b0; --accent: #ffd166; --green: #2ee6a8; --amber: #ffb84d;
    --red: #ff6b81; --line: #232c4e;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;
    background:
      radial-gradient(1100px 500px at 85% -10%, #1b2a5e 0%, transparent 60%),
      radial-gradient(900px 500px at -10% 110%, #10305e33 0%, transparent 60%),
      var(--bg);
    color: var(--text); min-height: 100vh; padding: 40px 20px 64px;
  }
  .wrap { max-width: 1100px; margin: 0 auto; }
  header { display: flex; align-items: center; gap: 18px; margin-bottom: 8px; }
  .signal { display: flex; flex-direction: column; gap: 6px; background: #0a0e1c;
            border: 1px solid var(--line); border-radius: 12px; padding: 10px 8px; }
  .lamp { width: 16px; height: 16px; border-radius: 50%; opacity: 0.25; }
  .lamp.red { background: var(--red); }
  .lamp.amber { background: var(--amber); }
  .lamp.green { background: var(--green); opacity: 1; box-shadow: 0 0 14px 2px #2ee6a877; }
  h1 { font-size: 28px; margin: 0; letter-spacing: 0.3px; }
  h1 small { display: block; font-size: 14px; font-weight: 500; color: var(--muted); margin-top: 4px; }
  a { color: var(--accent); }
  .meta { color: var(--muted); font-size: 13px; margin: 14px 2px 24px; }
  .meta code { color: var(--accent); background: #ffffff10; padding: 1px 7px; border-radius: 6px; }
  .btn { display: inline-block; background: linear-gradient(160deg, #ffd166, #ff9a3d);
         color: #201200; font-weight: 700; padding: 10px 22px; border-radius: 10px;
         text-decoration: none; border: 0; font-size: 15px; cursor: pointer; }
  .btn.secondary { background: #ffffff14; color: var(--text); }
  table { width: 100%; border-collapse: separate; border-spacing: 0; background: var(--panel);
          border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }
  thead th { background: var(--panel-2); color: var(--muted); font-size: 12px;
             text-transform: uppercase; letter-spacing: 0.8px; padding: 13px 12px;
             text-align: right; border-bottom: 1px solid var(--line); }
  thead th.left { text-align: left; }
  tbody td { padding: 12px; text-align: right; border-bottom: 1px solid var(--line);
             font-variant-numeric: tabular-nums; }
  tbody tr:last-child td { border-bottom: 0; }
  tbody tr:hover { background: #ffffff08; }
  td.left { text-align: left; }
  td.name { text-align: left; font-weight: 600; }
  .badge { display: inline-flex; align-items: center; justify-content: center;
           min-width: 32px; height: 32px; border-radius: 10px; font-weight: 800;
           background: #ffffff12; color: var(--muted); }
  tr.p1 .badge { background: linear-gradient(160deg, #ffd166, #ff9a3d); color: #201200; }
  tr.p2 .badge { background: linear-gradient(160deg, #cfd8ea, #93a3c0); color: #101828; }
  tr.p3 .badge { background: linear-gradient(160deg, #e6a171, #b3663a); color: #21100a; }
  .total { font-size: 16px; font-weight: 800; color: var(--accent); }
  .cell { display: inline-flex; flex-direction: column; align-items: flex-end; gap: 4px; min-width: 64px; }
  .bar { width: 64px; height: 5px; border-radius: 3px; background: #ffffff14; overflow: hidden; }
  .bar i { display: block; height: 100%; border-radius: 3px; }
  .bar .ok { background: linear-gradient(90deg, #2ee6a8, #7bffcf); }
  .bar .warn { background: linear-gradient(90deg, #ffb84d, #ffd166); }
  .bar .bad { background: linear-gradient(90deg, #ff6b81, #ff9a8b); }
  .status-scored { color: var(--green); font-weight: 600; }
  .status-error { color: var(--red); font-weight: 600; }
  .status-busy { color: var(--amber); font-weight: 600; animation: pulse 1.2s infinite; }
  @keyframes pulse { 50% { opacity: 0.45; } }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
          padding: 24px 28px; margin-top: 18px; }
  .card h2 { margin: 0 0 14px; font-size: 17px; }
  label { display: block; color: var(--muted); font-size: 13px; margin: 14px 0 6px; }
  input[type=text] { width: 100%; max-width: 420px; background: #0a0e1c; color: var(--text);
          border: 1px solid var(--line); border-radius: 10px; padding: 11px 14px; font-size: 15px; }
  input[type=file] { color: var(--muted); }
  textarea { width: 100%; min-height: 180px; background: #0a0e1c; color: #cfe3ff;
             border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px;
             font-family: ui-monospace, "Cascadia Code", Consolas, monospace; font-size: 13px; }
  .msg { border-radius: 10px; padding: 12px 16px; margin: 14px 0; font-size: 14px; }
  .msg.ok { background: #123528; color: #9ff3d3; border: 1px solid #1d5c44; }
  .msg.err { background: #3a1622; color: #ffc4cd; border: 1px solid #6b2438; }
  .hint { color: var(--muted); font-size: 13px; line-height: 1.6; }
  .hint code { color: var(--accent); }
  footer { margin-top: 24px; color: var(--muted); font-size: 12.5px; line-height: 1.6; }
  footer code { color: var(--accent); }
  .empty { color: var(--muted); text-align: center; padding: 36px 0; }
  .usermenu { position: fixed; top: 18px; right: 22px; z-index: 50; }
  .usermenu .trigger { background: var(--panel); border: 1px solid var(--line);
      color: var(--text); padding: 9px 16px; border-radius: 10px; font-weight: 600;
      cursor: pointer; font-size: 14px; }
  .usermenu .trigger:hover { background: var(--panel-2); }
  .usermenu .chev { color: var(--muted); margin-left: 7px; font-size: 11px; }
  .usermenu .dropdown { display: none; position: absolute; right: 0; margin-top: 8px;
      background: var(--panel-2); border: 1px solid var(--line); border-radius: 12px;
      min-width: 190px; overflow: hidden; box-shadow: 0 12px 30px #000a; }
  .usermenu.open .dropdown { display: block; }
  .usermenu .dropdown a { display: block; padding: 11px 16px; color: var(--text);
      text-decoration: none; font-size: 14px; }
  .usermenu .dropdown a:hover { background: #ffffff10; }
  .usermenu .dropdown a.logout { color: var(--red); border-top: 1px solid var(--line); }

  /* --- AI engineer panel ------------------------------------------- */
  .ai-head { display: flex; align-items: baseline; justify-content: space-between;
             flex-wrap: wrap; gap: 12px; }
  .budget { display: flex; flex-direction: column; align-items: flex-end; gap: 6px;
            font-variant-numeric: tabular-nums; }
  .budget .figure { font-size: 13px; color: var(--muted); }
  .budget .figure b { color: var(--text); font-size: 15px; }
  .budget-bar { width: 190px; height: 7px; border-radius: 4px;
                background: #ffffff14; overflow: hidden; }
  .budget-fill { height: 100%; width: 100%; border-radius: 4px;
                 background: linear-gradient(90deg, #2ee6a8, #ffd166);
                 transition: width .45s ease; }
  .budget-fill.low  { background: linear-gradient(90deg, #ffb84d, #ff9a3d); }
  .budget-fill.gone { background: var(--red); }
  .ai-actions { display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
                margin-top: 14px; }
  .ai-note { font-size: 13px; color: var(--muted); }
  .ai-note.err { color: var(--red); }
  .ai-note.ok  { color: var(--green); }
  .btn[disabled] { opacity: .45; cursor: not-allowed; }
  .spinner { width: 15px; height: 15px; border-radius: 50%; display: inline-block;
             border: 2px solid #ffffff2e; border-top-color: var(--accent);
             animation: spin .7s linear infinite; vertical-align: -2px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) {
    .spinner { animation: none; } .budget-fill { transition: none; }
  }

  .btn .cost { display: block; font-size: 10px; font-weight: 500; opacity: .7;
               letter-spacing: .04em; margin-top: 2px; }
  .ai-answer { background: var(--panel-2); border: 1px solid var(--line);
               border-left: 3px solid var(--green); border-radius: 0 8px 8px 0;
               padding: 14px 16px; margin-top: 14px; font-size: 14.5px;
               line-height: 1.6; white-space: pre-wrap; color: var(--text); }
  .ai-answer .who { display: block; font-size: 10.5px; letter-spacing: .12em;
                    text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }

  /* --- intersection replay ----------------------------------------- */
  .replay-head { display: flex; justify-content: space-between; align-items: center;
                 gap: 14px; flex-wrap: wrap; }
  .replay-pick { display: flex; gap: 6px; flex-wrap: wrap; }
  .pick { font: 500 12px/1 "Segoe UI", system-ui, sans-serif; background: #ffffff14;
          color: var(--muted); border: 1px solid var(--line); padding: 7px 11px;
          border-radius: 8px; cursor: pointer; }
  .pick[aria-pressed="true"] { background: var(--accent); color: #201200;
                               border-color: var(--accent); font-weight: 700; }
  .pick:focus-visible { outline: 2px solid var(--green); outline-offset: 2px; }
  #replay-canvas { width: 100%; height: auto; display: block; border-radius: 12px;
                   background: #070b16; border: 1px solid var(--line); }
  .replay-foot { display: flex; justify-content: space-between; align-items: center;
                 gap: 14px; flex-wrap: wrap; font-family: ui-monospace, monospace;
                 font-size: 12px; color: var(--muted); }
  .replay-key { display: flex; gap: 14px; flex-wrap: wrap; }
  .replay-key span { display: inline-flex; align-items: center; gap: 6px; }
  .replay-key i { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
  .verdict-row { display: flex; flex-direction: column; gap: 1px; background: var(--line);
                 border: 1px solid var(--line); border-radius: 10px; overflow: hidden;
                 margin-top: 12px; }
  .vr { display: flex; justify-content: space-between; align-items: center; gap: 10px;
        background: var(--panel-2); padding: 11px 14px; font-family: ui-monospace, monospace;
        font-size: 12.5px; }
  .vr .lbl { color: var(--muted); }
  .vr .out { font-weight: 700; display: flex; align-items: center; gap: 8px; }
  .vr.pass .out { color: var(--green); }
  .vr.fail .out { color: var(--red); }
  .vr .dot { width: 8px; height: 8px; border-radius: 2px; background: currentColor; }

  /* --- act board ---------------------------------------------------- */
  .acts { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 10px; }
  @media (max-width: 700px) { .acts { grid-template-columns: minmax(0,1fr); } }
  .act { background: var(--panel-2); border: 1px solid var(--line); border-radius: 12px;
         padding: 15px 16px; display: flex; flex-direction: column; gap: 7px;
         transition: border-color .3s ease, opacity .3s ease; }
  .act.locked { opacity: .42; }
  .act.live { border-color: var(--accent); background: #ffd1660f; }
  .act.done { border-color: var(--green); }
  .act .tag { font-family: ui-monospace, monospace; font-size: 10px; letter-spacing: .14em;
              text-transform: uppercase; color: var(--muted); }
  .act.live .tag { color: var(--accent); }
  .act.done .tag { color: var(--green); }
  .act h3 { margin: 0; font-size: 15.5px; }
  .act p { margin: 0; font-size: 13.5px; color: var(--muted); line-height: 1.5; }
  .act .client { border-left: 2px solid var(--line); padding-left: 11px;
                 font-style: italic; color: var(--text); }
  .act.locked .client { display: none; }
  @media (prefers-reduced-motion: reduce) { .act { transition: none; } }
"""

# Renders the top-right user menu on any page when a session cookie is
# present. Plain string (not an f-string) so the JS braces stay literal.
USERMENU_SNIPPET = """
<script>
(async function () {
  let session;
  try {
    session = await (await fetch("/api/session", {cache: "no-store"})).json();
  } catch (err) { return; }
  if (!session.authenticated) return;
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const root = el("div", "usermenu");
  const trigger = el("button", "trigger", session.name);
  trigger.appendChild(el("span", "chev", "\\u25be"));
  const dropdown = el("div", "dropdown");
  const mine = el("a", "", "My submissions");   mine.href = "/me";
  const board = el("a", "", "Leaderboard");     board.href = "/";
  const logout = el("a", "logout", "Log out");  logout.href = "/logout";
  dropdown.append(mine, board, logout);
  root.append(trigger, dropdown);
  trigger.addEventListener("click", (event) => {
    event.stopPropagation();
    root.classList.toggle("open");
  });
  document.addEventListener("click", () => root.classList.remove("open"));
  document.body.appendChild(root);
})();
</script>
"""

_HEADER = """
  <header>
    <div class="signal" aria-hidden="true">
      <div class="lamp red"></div><div class="lamp amber"></div><div class="lamp green"></div>
    </div>
    <h1>Traffic Flow Challenge
      <small>Optimize latency vs. throughput &mdash; adaptive signal control for a four-way intersection</small>
    </h1>
  </header>
"""


INDEX_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Traffic Flow Challenge - Live Leaderboard</title>
<style>{BASE_CSS}</style>
</head>
<body>
<div class="wrap">
{_HEADER}
  <p class="meta" id="meta">Loading&hellip;</p>
  <p style="margin: 0 0 18px"><a class="btn" id="cta-btn" href="/signup">Join the challenge</a>
     <a class="btn secondary" id="login-btn" href="/login" style="margin-left:8px">Log in</a>
     <span class="hint" id="cta-hint" style="margin-left:12px">Create an account, then submit as often as you like &mdash; your best run counts, and requirements come before averages.</span></p>
  <table>
    <thead><tr id="head-row"></tr></thead>
    <tbody id="rows"><tr><td class="empty" id="empty-cell">Waiting for the first participant&hellip;</td></tr></tbody>
  </table>
  <footer>
    Three requirements have to hold on every scenario: <code>traffic keeps moving</code>,
    <code>the typical trip is reasonable</code>, and <code>nobody is stranded</code>.
    Miss one and you rank below everyone who missed none, whatever your averages say.
    Clear an act to unlock the next one. Furthest act wins first, then requirements,
    then lowest waiting time. Updates automatically.
  </footer>
</div>
<script>
const fmtAgo = (ts) => {{
  if (!ts) return "-";
  const s = Math.max(0, (Date.now() / 1000) - ts);
  if (s < 60) return Math.floor(s) + "s ago";
  if (s < 3600) return Math.floor(s / 60) + "m ago";
  return Math.floor(s / 3600) + "h " + Math.floor((s % 3600) / 60) + "m ago";
}};
const el = (tag, cls, text) => {{
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}};
const scoreCell = (value) => {{
  const td = el("td");
  if (value === null || value === undefined) {{ td.textContent = "-"; return td; }}
  const cell = el("span", "cell");
  cell.appendChild(el("b", "", value.toFixed(1)));
  const bar = el("span", "bar");
  const fill = el("i", value >= 70 ? "ok" : value >= 40 ? "warn" : "bad");
  fill.style.width = Math.max(2, Math.min(100, value)) + "%";
  bar.appendChild(fill);
  cell.appendChild(bar);
  td.appendChild(cell);
  return td;
}};

async function refresh() {{
  let payload;
  try {{
    payload = await (await fetch("/api/leaderboard", {{cache: "no-store"}})).json();
  }} catch (err) {{ return; }}

  document.getElementById("meta").textContent =
    "Seeds " + payload.seeds.join(", ") + " \\u00b7 " + payload.scenarios.length +
    (payload.scenarios.length === 1 ? " scenario" : " scenarios") +
    " scored this act \\u00b7 requirements before averages \\u00b7 " +
    payload.standings.length + " participant(s)" +
    (payload.backlog > 0 ? " \\u00b7 " + payload.backlog + " evaluation(s) queued" : "");

  const head = document.getElementById("head-row");
  head.replaceChildren(el("th", "left", "#"), el("th", "left", "Participant"),
                       el("th", "", "Act"), el("th", "left", "Requirements"),
                       el("th", "", "Wait"));
  for (const s of payload.scenarios) head.appendChild(el("th", "", s.title));
  head.appendChild(el("th", "", "Tries"));
  head.appendChild(el("th", "", "Last upload"));
  head.appendChild(el("th", "", "Status"));

  const body = document.getElementById("rows");
  body.replaceChildren();
  if (!payload.standings.length) {{
    const tr = el("tr");
    const td = el("td", "empty", "Waiting for the first participant\\u2026");
    td.colSpan = 8 + payload.scenarios.length;
    tr.appendChild(td);
    body.appendChild(tr);
    return;
  }}
  payload.standings.forEach((entry, index) => {{
    const rank = index + 1;
    // Only a passing run earns a podium colour. Ranking first while missing a
    // requirement should never look like winning.
    const tr = el("tr", rank <= 3 && entry.best_passed ? "p" + rank : "");
    const rankTd = el("td", "left");
    rankTd.appendChild(el("span", "badge", String(rank)));
    tr.appendChild(rankTd);
    tr.appendChild(el("td", "name", entry.name));

    const ACT_LABEL = {{act1: "1", act2: "2", deployment: "3"}};
    const actTd = el("td");
    const pill = el("span", "badge", ACT_LABEL[entry.act] || "1");
    if (entry.act === "deployment") pill.style.color = "var(--green)";
    actTd.appendChild(pill);
    tr.appendChild(actTd);

    const gateTd = el("td", "left");
    if (entry.best_passed === null || entry.best_score === null) {{
      gateTd.textContent = "\\u2014";
    }} else if (entry.best_passed) {{
      gateTd.appendChild(el("span", "status-scored", "all met"));
    }} else {{
      const miss = el("span", "status-error",
        "missed: " + (entry.failed_gates.length ? entry.failed_gates.join(", ") : "a requirement"));
      if (entry.best_worst_wait) miss.title = "worst wait " + entry.best_worst_wait + "s";
      gateTd.appendChild(miss);
    }}
    tr.appendChild(gateTd);
    tr.appendChild(el("td", "total", entry.best_wait === null || entry.best_wait === undefined
      ? "-" : entry.best_wait.toFixed(1) + "s"));
    for (const s of payload.scenarios) tr.appendChild(scoreCell(entry.scenario_scores[s.name]));
    tr.appendChild(el("td", "", String(entry.attempts)));
    tr.appendChild(el("td", "", fmtAgo(entry.last_activity)));
    const statusTd = el("td");
    const status = entry.latest_status;
    if (status === "pending" || status === "evaluating")
      statusTd.appendChild(el("span", "status-busy", "evaluating\\u2026"));
    else if (status === "error") {{
      const span = el("span", "status-error", "error");
      if (entry.latest_error) span.title = entry.latest_error;
      statusTd.appendChild(span);
    }} else if (status === "scored")
      statusTd.appendChild(el("span", "status-scored", "ok"));
    else statusTd.textContent = "-";
    tr.appendChild(statusTd);
    body.appendChild(tr);
  }});
}}
refresh();
setInterval(refresh, 4000);

// Signed-in visitors get a "New submission" button instead of signup/login.
(async function () {{
  let session;
  try {{
    session = await (await fetch("/api/session", {{cache: "no-store"}})).json();
  }} catch (err) {{ return; }}
  if (!session.authenticated) return;
  const cta = document.getElementById("cta-btn");
  cta.textContent = "New submission";
  cta.href = "/me";
  document.getElementById("login-btn").remove();
  document.getElementById("cta-hint").textContent =
    "Submit a new version whenever you like \\u2014 your best run is the one that counts.";
}})();
</script>
{USERMENU_SNIPPET}
</body>
</html>
"""


SIGNUP_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Join - Traffic Flow Challenge</title>
<style>{BASE_CSS}</style>
</head>
<body>
<div class="wrap" style="max-width: 640px">
{_HEADER}
  <div class="card">
    <h2>Create your account</h2>
    __ERROR__
    <form method="post" action="/signup">
      <label for="name">Your name (or team name) &mdash; shown on the leaderboard</label>
      <input type="text" id="name" name="name" maxlength="40" required autofocus
             placeholder="e.g. Ada's Autobahn">
      <label for="password">Password &mdash; so you can log back in from any device</label>
      <input type="password" id="password" name="password" maxlength="64" required
             placeholder="at least 4 characters">
      <p style="margin-top:18px"><button class="btn" type="submit">Create account</button>
         <a class="btn secondary" href="/login" style="margin-left:8px">I already have an account</a></p>
    </form>
    <p class="hint">You'll land on your personal upload page. Upload new versions of your
       policy as often as you like. Every run is checked against the
       <b>requirements</b> first &mdash; miss one and you rank below everyone who
       missed none, whatever your averages say &mdash; and your best run is what
       shows on the <a href="/">leaderboard</a>. Lost the tab? Just <a href="/login">log in</a> again.</p>
  </div>
</div>
</body>
</html>
"""


PRIMER_CSS = """
  .primer h3 { margin: 0 0 6px; font-size: 15px; letter-spacing: .2px; }
  .primer p { margin: 0; color: var(--muted); font-size: 13.5px; line-height: 1.55; }
  .primer b { color: var(--text); font-weight: 650; }
  .primer code { color: var(--accent); background: #ffffff10;
                 padding: 1px 6px; border-radius: 5px; font-size: 12.5px; }
  .phase-pair { display: flex; gap: 26px; flex-wrap: wrap; align-items: flex-start;
                margin: 4px 0 20px; }
  .phase-fig { text-align: center; }
  .phase-fig figcaption { color: var(--muted); font-size: 12.5px; margin-top: 6px; }
  .phase-fig figcaption b { color: var(--green); }
  .primer-grid { display: grid; gap: 18px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
  .gate-list { list-style: none; padding: 0; margin: 6px 0 0; }
  .gate-list li { display: flex; gap: 9px; align-items: baseline; padding: 5px 0;
                  color: var(--muted); font-size: 13.5px; border-bottom: 1px solid var(--line); }
  .gate-list li:last-child { border-bottom: 0; }
  .gate-list .num { color: var(--accent); font-weight: 700; font-variant-numeric: tabular-nums; }

  .unlock-veil { position: fixed; inset: 0; z-index: 90; display: flex;
                 align-items: center; justify-content: center; padding: 24px;
                 background: #04070fdd; animation: veil-in .25s ease-out; }
  .unlock-card { background: #16224a; border: 1px solid #2ee6a8;
                 border-radius: 18px; padding: 34px 38px; max-width: 460px;
                 text-align: center; box-shadow: 0 0 60px #2ee6a855;
                 animation: pop-in .35s cubic-bezier(.2,1.4,.4,1); }
  .unlock-title { font-size: 13px; font-weight: 800; letter-spacing: 3px;
                  color: #2ee6a8; margin-bottom: 12px; }
  .unlock-card p { color: var(--text); font-size: 17px; line-height: 1.5;
                   margin: 0 0 22px; }
  @keyframes veil-in { from { opacity: 0 } to { opacity: 1 } }
  @keyframes pop-in { from { transform: scale(.86); opacity: 0 }
                      to { transform: scale(1); opacity: 1 } }
  body.flash-pass::after { content: ""; position: fixed; inset: 0; z-index: 80;
                           pointer-events: none; background: #2ee6a8;
                           animation: flash .9s ease-out forwards; }
  @keyframes flash { from { opacity: .35 } to { opacity: 0 } }
"""

def _phase_svg(green_ns: bool) -> str:
    """One little intersection, one phase lit."""
    on, off = "#2ee6a8", "#ff6b81"
    ns, ew = (on, off) if green_ns else (off, on)
    return f'''<svg width="150" height="150" viewBox="0 0 150 150" role="img">
  <rect width="150" height="150" rx="10" fill="#0a0e1c"/>
  <rect x="0" y="57" width="150" height="36" fill="#161d33"/>
  <rect x="57" y="0" width="36" height="150" fill="#161d33"/>
  <rect x="57" y="57" width="36" height="36" fill="#1d2643"/>
  <circle cx="75" cy="46"  r="6" fill="{ns}"/>
  <circle cx="75" cy="104" r="6" fill="{ns}"/>
  <circle cx="46"  cy="75" r="6" fill="{ew}"/>
  <circle cx="104" cy="75" r="6" fill="{ew}"/>
  <text x="75" y="14" fill="#8b93b0" font-size="10" text-anchor="middle"
        font-family="monospace">north</text>
  <text x="75" y="144" fill="#8b93b0" font-size="10" text-anchor="middle"
        font-family="monospace">south</text>
  <text x="16" y="79" fill="#8b93b0" font-size="10" text-anchor="middle"
        font-family="monospace">west</text>
  <text x="134" y="79" fill="#8b93b0" font-size="10" text-anchor="middle"
        font-family="monospace">east</text>
</svg>'''


PRIMER_CARD = f"""
  <div class="card primer">
    <h2 style="margin:0 0 4px">How the intersection works</h2>
    <p style="margin-bottom:14px">Read this once. It is the whole problem.</p>

    <div class="phase-pair">
      <figure class="phase-fig" style="margin:0">
        {_phase_svg(True)}
        <figcaption><b>NS_GREEN</b><br>north and south move</figcaption>
      </figure>
      <figure class="phase-fig" style="margin:0">
        {_phase_svg(False)}
        <figcaption><b>EW_GREEN</b><br>east and west move</figcaption>
      </figure>
      <p style="flex:1 1 260px;min-width:240px">
        Four roads meet. <b>One road moves or the other does</b> &mdash; there is
        no third option and no turn arrows. Cars arrive on their own schedule,
        queue at the red light, and cross when it goes green. You are writing the
        thing that decides, second by second, which road gets the green.
      </p>
    </div>

    <div class="primer-grid">
      <div>
        <h3>Your controller</h3>
        <p>Runs <b>once every simulated second</b> and answers one question by
           returning <code>"NS_GREEN"</code> or <code>"EW_GREEN"</code>. Returning
           the phase that is already green means &ldquo;leave it alone&rdquo;.</p>
      </div>
      <div>
        <h3>What it can see</h3>
        <p>For each of north, south, east and west: <b>how many cars are queued</b>
           and <b>how long the front car has been waiting</b>. Plus which phase is
           green now and how long it has been green. It cannot see the future, and
           it does not know which scenario it is running.</p>
      </div>
      <div>
        <h3>What switching costs</h3>
        <p>A green must hold <b>6 seconds</b> before it can change. Every change
           then burns <b>6 more seconds</b> in which nobody moves &mdash; 3s yellow,
           1s all-red, 2s for traffic to get going again. Switch 50 times in a
           10-minute run and you have thrown away <b>5 minutes of green</b>.</p>
      </div>
      <div>
        <h3>What has to be true</h3>
        <p>Checked on every scenario. Miss one and you rank below everyone who
           missed none, however good your averages are.</p>
        <ul class="gate-list">
          <li><span class="num">90%</span><span>of cars get through</span></li>
          <li><span class="num">45s</span><span>average wait, at most</span></li>
          <li><span class="num">140s</span><span>longest wait by anyone, at most</span></li>
        </ul>
      </div>
    </div>
  </div>
"""


AI_CARD = """
  <div class="card">
    <div class="ai-head">
      <h2 style="margin:0">Your AI engineer</h2>
      <div class="budget">
        <div class="figure"><b id="budget-pct">--</b> of your AI budget left</div>
        <div class="budget-bar"><div class="budget-fill" id="budget-fill"></div></div>
        <div class="figure" id="budget-detail"></div>
      </div>
    </div>
    <p class="hint">You do not write the controller - you direct the engineer that
       writes it. Say what the policy should do and why. Whatever is in the box
       below is sent along, so you can ask for changes to what you already have.</p>
    <label for="prompt">Tell the AI what to build</label>
    <textarea id="prompt" spellcheck="true" rows="5"
      placeholder="Example -- change it, this is only to show you the shape:\n\nGive the green to whichever road has more cars waiting. Do not change the light unless the other road has at least 4 more cars than the one moving now, because every change wastes 6 seconds. But if anyone on the red road has been waiting more than 70 seconds, switch anyway."></textarea>
    <div class="ai-actions">
      <button class="btn secondary" type="button" id="ask">Ask
        <span class="cost">~1,200</span></button>
      <button class="btn" type="button" id="build">Build
        <span class="cost">~1,900</span></button>
      <span class="ai-note" id="ai-note"></span>
    </div>
    <div id="ai-answer"></div>
  </div>
"""

AI_SCRIPT = """
const promptBox  = document.getElementById("prompt");
const askBtn     = document.getElementById("ask");
const buildBtn   = document.getElementById("build");
const note       = document.getElementById("ai-note");
const codeBox    = document.querySelector("textarea[name=code]");
const budgetPct  = document.getElementById("budget-pct");
const budgetFill = document.getElementById("budget-fill");
const budgetInfo = document.getElementById("budget-detail");

function paintBudget(b) {
  if (!b) return;
  budgetPct.textContent = b.percent + "%";
  budgetFill.style.width = Math.max(0, Math.min(100, b.percent)) + "%";
  budgetFill.className = "budget-fill" +
    (b.percent <= 0 ? " gone" : b.percent < 25 ? " low" : "");
  budgetInfo.textContent =
    b.remaining.toLocaleString() + " of " + b.granted.toLocaleString() + " tokens";
  askBtn.disabled = b.remaining <= 0;
  buildBtn.disabled = b.remaining <= 0;
  if (b.remaining <= 0) {
    say("Your budget is spent. What you have now is what you ship.", "err");
  }
}

function say(text, kind) {
  note.className = "ai-note" + (kind ? " " + kind : "");
  note.textContent = text;
}

async function loadBudget() {
  try {
    const r = await fetch("/api/budget", {cache: "no-store"});
    if (r.ok) paintBudget((await r.json()).budget);
  } catch (err) { /* the page still works without the meter */ }
}

async function send(mode, btn) {
  const prompt = promptBox.value.trim();
  if (!prompt) {
    say(mode === "ask" ? "Ask the AI something first." : "Tell the AI what to build first.", "err");
    promptBox.focus();
    return;
  }

  askBtn.disabled = true; buildBtn.disabled = true;
  note.className = "ai-note";
  note.innerHTML = '<span class="spinner"></span> ' +
    (mode === "ask" ? "Thinking\u2026" : "Writing the controller\u2026");

  let res, payload;
  try {
    res = await fetch("/api/generate", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({mode: mode, prompt: prompt, code: codeBox.value || null}),
    });
    payload = await res.json();
  } catch (err) {
    askBtn.disabled = false; buildBtn.disabled = false;
    return say("Could not reach the server. Nothing was charged.", "err");
  }

  if (payload.budget) paintBudget(payload.budget);
  const broke = payload.budget ? payload.budget.remaining <= 0 : false;
  askBtn.disabled = broke; buildBtn.disabled = broke;

  if (!res.ok) {
    return say(payload.error || "The AI could not be reached.", "err");
  }

  if (payload.mode === "ask") {
    const box = document.createElement("div");
    box.className = "ai-answer";
    const who = document.createElement("span");
    who.className = "who";
    who.textContent = "Your AI engineer";
    box.appendChild(who);
    box.appendChild(document.createTextNode(payload.answer || ""));
    document.getElementById("ai-answer").replaceChildren(box);
    say("Answered - " + payload.charged.toLocaleString() +
        " tokens. That was a controller you didn't generate.", "ok");
    return;
  }

  codeBox.value = payload.code;
  document.getElementById("ai-answer").replaceChildren();
  codeBox.scrollIntoView({behavior: "smooth", block: "center"});
  const extra = payload.note ? " (" + payload.note + ")" : "";
  say("Controller updated - " + payload.charged.toLocaleString() +
      " tokens spent." + extra + " Read it before you submit.", "ok");
}

askBtn.addEventListener("click", function () { send("ask", askBtn); });
buildBtn.addEventListener("click", function () { send("build", buildBtn); });

loadBudget();
"""

REPLAY_CARD = """
  <div class="card" id="replay-card" hidden>
    <div class="replay-head">
      <h2 style="margin:0">Watch it run</h2>
      <div class="replay-pick" id="replay-pick"></div>
    </div>
    <p class="hint" id="replay-hint">Your last submission, replayed. Vehicles turn amber
       after 45 seconds and red after 90 &mdash; a red car is somebody filing a complaint.</p>
    <canvas id="replay-canvas" width="1120" height="620"
            aria-label="Replay of your controller running the intersection"></canvas>
    <div class="replay-foot">
      <span id="replay-clock">0:00</span>
      <span class="replay-key">
        <span><i style="background:#7f8cb5"></i> waiting</span>
        <span><i style="background:#ffb84d"></i> over 45s</span>
        <span><i style="background:#ff6b81"></i> over 90s</span>
      </span>
    </div>
    <div class="verdict-row" id="replay-verdict"></div>
  </div>
"""

REPLAY_SCRIPT = """
const PHASE_LANES = {
  NS_GREEN: ["north", "south"], EW_GREEN: ["east", "west"]
};
const APPROACH = {
  north: {dx: 0, dy: -1}, south: {dx: 0, dy: 1},
  east:  {dx: 1, dy: 0},  west:  {dx: -1, dy: 0}
};
const rcv = document.getElementById("replay-canvas");
const rctx = rcv.getContext("2d");
const RW = rcv.width, RH = rcv.height, RCX = RW / 2, RCY = RH / 2;
const ROAD = 132, CAR = 15, CGAP = 5;

let replayData = null, frameAt = 0, replayTimer = null, lastSubId = null;

function drawFrame(d, f) {
  rctx.fillStyle = "#070b16"; rctx.fillRect(0, 0, RW, RH);
  rctx.fillStyle = "#101728";
  rctx.fillRect(0, RCY - ROAD / 2, RW, ROAD);
  rctx.fillRect(RCX - ROAD / 2, 0, ROAD, RH);
  rctx.strokeStyle = "#1b2440"; rctx.lineWidth = 2;
  rctx.strokeRect(RCX - ROAD / 2, RCY - ROAD / 2, ROAD, ROAD);
  rctx.strokeStyle = "#243050"; rctx.setLineDash([12, 14]);
  rctx.beginPath();
  rctx.moveTo(0, RCY); rctx.lineTo(RCX - ROAD / 2, RCY);
  rctx.moveTo(RCX + ROAD / 2, RCY); rctx.lineTo(RW, RCY);
  rctx.moveTo(RCX, 0); rctx.lineTo(RCX, RCY - ROAD / 2);
  rctx.moveTo(RCX, RCY + ROAD / 2); rctx.lineTo(RCX, RH);
  rctx.stroke(); rctx.setLineDash([]);

  const phase = d.phases[f[0]], inTrans = f[1] === 1;
  const open = PHASE_LANES[phase] || [];

  d.lanes.forEach(function (lane, idx) {
    const a = APPROACH[lane], lat = 0, gap = ROAD / 2 + 14;
    const isOpen = !inTrans && open.indexOf(lane) !== -1;

    rctx.fillStyle = isOpen ? "#2ee6a8" : (inTrans ? "#ffb84d" : "#ff6b81");
    rctx.globalAlpha = isOpen ? 1 : 0.55;
    rctx.beginPath();
    rctx.arc(RCX + a.dx * gap, RCY + a.dy * gap, 5.5, 0, 6.284);
    rctx.fill(); rctx.globalAlpha = 1;

    const n = Math.min(f[2][idx], 26), oldest = f[3][idx];
    for (let i = 0; i < n; i++) {
      const dd = gap + 12 + i * (CAR + CGAP);
      const x = RCX + a.dx * dd - CAR / 2;
      const y = RCY + a.dy * dd - CAR / 2;
      // the front vehicle's wait is known exactly; those behind it waited less
      const w = oldest * (1 - i / Math.max(n, 1));
      rctx.fillStyle = w > 90 ? "#ff6b81" : w > 45 ? "#ffb84d" : "#7f8cb5";
      rctx.beginPath();
      if (rctx.roundRect) rctx.roundRect(x, y, CAR, CAR, 3); else rctx.rect(x, y, CAR, CAR);
      rctx.fill();
    }
    if (f[2][idx] > 26) {
      const dd = gap + 12 + 26 * (CAR + CGAP);
      rctx.fillStyle = "#ff6b81"; rctx.font = "600 13px monospace"; rctx.textAlign = "center";
      rctx.fillText("+" + (f[2][idx] - 26),
        RCX + a.dx * dd, RCY + a.dy * dd + 4);
    }
  });

  rctx.fillStyle = "#8b93b0"; rctx.font = "500 12px monospace"; rctx.textAlign = "center";
  rctx.fillText(inTrans ? "CHANGING" : phase.replace("_", " "), RCX, RCY + 4);

  const secs = frameAt * d.stride;
  document.getElementById("replay-clock").textContent =
    Math.floor(secs / 60) + ":" + String(secs % 60).padStart(2, "0");
}

function showVerdict(m) {
  const box = document.getElementById("replay-verdict");
  box.replaceChildren();
  (m.requirements || []).forEach(function (r) {
    const row = document.createElement("div");
    row.className = "vr " + (r.passed ? "pass" : "fail");
    const l = document.createElement("span");
    l.className = "lbl"; l.textContent = r.label + " \u2014 " + r.detail;
    const o = document.createElement("span");
    o.className = "out";
    const dot = document.createElement("span"); dot.className = "dot";
    o.appendChild(dot);
    o.appendChild(document.createTextNode(r.actual));
    row.appendChild(l); row.appendChild(o);
    box.appendChild(row);
  });
}

function playReplay(d) {
  replayData = d; frameAt = 0;
  if (replayTimer) clearInterval(replayTimer);
  showVerdict(d.metrics);
  replayTimer = setInterval(function () {
    if (!replayData || !replayData.frames.length) return;
    drawFrame(replayData, replayData.frames[frameAt]);
    frameAt = (frameAt + 1) % replayData.frames.length;
  }, 50);
}

async function loadReplay(subId, scenario) {
  try {
    const r = await fetch("/api/replay/" + subId + "/" + scenario, {cache: "no-store"});
    if (!r.ok) return;
    playReplay(await r.json());
  } catch (err) { /* the page is fine without it */ }
}

function offerReplay(sub) {
  if (!sub || sub.status !== "scored" || !sub.scenario_scores) return;
  const card = document.getElementById("replay-card");
  const names = Object.keys(sub.scenario_scores);
  if (!names.length) return;
  card.hidden = false;
  if (String(sub.id) === String(lastSubId)) return;   // already showing this one
  lastSubId = sub.id;

  const pick = document.getElementById("replay-pick");
  pick.replaceChildren();
  names.forEach(function (name, i) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "pick";
    b.textContent = name.replace(/_/g, " ");
    b.setAttribute("aria-pressed", i === names.length - 1 ? "true" : "false");
    b.addEventListener("click", function () {
      pick.querySelectorAll(".pick").forEach(function (o) {
        o.setAttribute("aria-pressed", "false");
      });
      b.setAttribute("aria-pressed", "true");
      loadReplay(sub.id, name);
    });
    pick.appendChild(b);
  });
  loadReplay(sub.id, names[names.length - 1]);
}
"""

ACT_BOARD = """
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:baseline;gap:14px;flex-wrap:wrap">
      <h2 style="margin:0">The contract</h2>
      <span class="hint" id="act-clock">&nbsp;</span>
    </div>
    <div class="acts" id="act-board"></div>
  </div>
"""

ACT_SCRIPT = """
const ACT_COPY = [
  ["act1", "Act 1 \u2014 The pilot", "Monday, 6:40 a.m.",
   "Keep traffic moving and do not leave people sitting there. Switching the lights costs a few seconds each time."],
  ["act2", "Act 2 \u2014 The dashboard was fine", "Thursday, 4:15 p.m.",
   "Two complaints this week. The avenue backs up in the evening rush, and the side street says they never get a green. Nobody waits over 140 seconds. Ever. And the morning traffic still counts."],
  ["deployment", "Act 3 \u2014 Eight hundred intersections", "Six weeks later",
   "The pilot cleared review. Your controller ships to every intersection in the program - including four you have never seen. There is no per-site tuning in this contract."],
];

let shownAct = null;

// A short rising arpeggio, synthesised so there is no audio file to ship or
// fail to load. Browsers only allow this after a user gesture, which a
// submission always is, so by the time an act unlocks the context is live.
function fanfare() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    [523.25, 659.25, 783.99, 1046.5].forEach(function (hz, i) {
      const osc = ctx.createOscillator(), gain = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.value = hz;
      const t = ctx.currentTime + i * 0.11;
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(0.22, t + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.42);
      osc.connect(gain); gain.connect(ctx.destination);
      osc.start(t); osc.stop(t + 0.45);
    });
    setTimeout(function () { ctx.close(); }, 1400);
  } catch (err) { /* sound is a bonus, never a requirement */ }
}

function celebrate(title, line) {
  fanfare();
  const veil = document.createElement("div");
  veil.className = "unlock-veil";
  const card = document.createElement("div");
  card.className = "unlock-card";
  const h = document.createElement("div");
  h.className = "unlock-title";
  h.textContent = title;
  const p = document.createElement("p");
  p.textContent = line;
  const btn = document.createElement("button");
  btn.className = "btn";
  btn.textContent = "Read the contract";
  btn.addEventListener("click", function () { veil.remove(); });
  card.appendChild(h); card.appendChild(p); card.appendChild(btn);
  veil.appendChild(card);
  veil.addEventListener("click", function (e) {
    if (e.target === veil) veil.remove();
  });
  document.body.appendChild(veil);
  document.body.classList.add("flash-pass");
  setTimeout(function () { document.body.classList.remove("flash-pass"); }, 900);
}

async function paintActs() {
  let data;
  try {
    data = await (await fetch("/api/act", {cache: "no-store"})).json();
  } catch (err) { return; }
  const cur = data.act, cleared = data.cleared || [];

  const board = document.getElementById("act-board");
  if (cur === shownAct && board.children.length) return;

  // Only celebrate a real advance seen in THIS tab, and remember it so a
  // reload does not replay the fanfare.
  const seen = sessionStorage.getItem("vcc-act");
  const advanced = shownAct !== null && cur !== shownAct;
  const firstSight = shownAct === null && seen && seen !== cur;
  shownAct = cur;
  try { sessionStorage.setItem("vcc-act", cur); } catch (err) {}

  const idx = ACT_COPY.findIndex(a => a[0] === cur);
  board.replaceChildren();
  ACT_COPY.forEach(function (a, i) {
    const done = cleared.indexOf(a[0]) !== -1;
    const card = document.createElement("div");
    card.className = "act " + (done ? "done" : i === idx ? "live" : "locked");
    const tag = document.createElement("div");
    tag.className = "tag";
    tag.textContent = (done ? "cleared" : i === idx ? "now" : "locked") + " \u00b7 " + a[2];
    const h = document.createElement("h3");
    h.textContent = i > idx ? "Locked" : a[1];
    const p = document.createElement("p");
    p.className = "client";
    p.textContent = i > idx
      ? "Clear " + ACT_COPY[i - 1][1].split(" \u2014 ")[0] + " to open this."
      : a[3];
    card.appendChild(tag); card.appendChild(h); card.appendChild(p);
    board.appendChild(card);
  });

  document.getElementById("act-clock").textContent = idx === 0
    ? "Pass every requirement to unlock the next act."
    : "Scored on this act's traffic plus every earlier act's.";

  if (advanced || firstSight) {
    celebrate(
      cur === "act2" ? "ACT 1 CLEARED" : "ACT 2 CLEARED",
      cur === "act2"
        ? "The pilot works. The client has been in touch \u2014 there are two complaints."
        : "The pilot cleared review. Your controller is going to eight hundred intersections."
    );
  }
}

paintActs();
setInterval(paintActs, 3000);
"""

ME_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>My submissions - Traffic Flow Challenge</title>
<style>{BASE_CSS}{PRIMER_CSS}</style>
</head>
<body>
<div class="wrap" style="max-width: 860px">
{_HEADER}
{ACT_BOARD}
{PRIMER_CARD}
{AI_CARD}
{REPLAY_CARD}
  <div class="card">
    <h2 id="hello">My submissions</h2>
    <div id="banner"></div>
    <p class="hint">This is your personal upload page. You stay signed in on
       this device until you log out (click your name, top right); from another
       device just <a href="/login">log in</a> again. Every upload is
       automatically run against every scenario in the current act, on 3 traffic
       seeds each. Requirements are checked before averages, and your best run is
       what shows on the <a href="/">live leaderboard</a>.</p>
    <form method="post" enctype="multipart/form-data" id="upload-form">
      <label>Upload your <code>policy.py</code> (must define <code>class Policy</code> with <code>decide(self, obs)</code>)</label>
      <input type="file" name="file" accept=".py,text/x-python">
      <label>&hellip;or paste the code here</label>
      <textarea name="code" spellcheck="false" placeholder="class Policy:&#10;    def decide(self, obs):&#10;        ..."></textarea>
      <p style="margin-top:16px"><button class="btn" type="submit">Submit for evaluation</button></p>
    </form>
  </div>
  <div class="card">
    <h2>History</h2>
    <table>
      <thead><tr>
        <th class="left">When</th><th>Status</th><th>Total</th><th class="left">Details</th>
      </tr></thead>
      <tbody id="history"><tr><td class="empty" colspan="4">No submissions yet.</td></tr></tbody>
    </table>
  </div>
</div>
<script>
const token = location.pathname.split("/")[2];
document.getElementById("upload-form").action = "/p/" + token + "/upload";

const params = new URLSearchParams(location.search);
if (params.get("msg")) {{
  const kind = params.get("kind") === "err" ? "err" : "ok";
  const banner = document.createElement("div");
  banner.className = "msg " + kind;
  banner.textContent = params.get("msg");
  document.getElementById("banner").replaceChildren(banner);
}}

const el = (tag, cls, text) => {{
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}};

async function refresh() {{
  let payload;
  try {{
    payload = await (await fetch("/api/participant/" + token, {{cache: "no-store"}})).json();
  }} catch (err) {{ return; }}
  if (payload.error) return;
  document.getElementById("hello").textContent =
    payload.name + (payload.best_score === null
      ? " \\u2014 nothing submitted yet"
      : " \\u2014 best run: " + payload.best_score.toFixed(2));
  const body = document.getElementById("history");
  body.replaceChildren();
  if (!payload.submissions.length) {{
    const tr = el("tr");
    const td = el("td", "empty", "No submissions yet.");
    td.colSpan = 4;
    tr.appendChild(td);
    body.appendChild(tr);
    return;
  }}
  const newest = payload.submissions.find(s => s.status === "scored");
  if (newest) offerReplay(newest);
  for (const sub of payload.submissions) {{
    const tr = el("tr");
    tr.appendChild(el("td", "left", new Date(sub.created_at * 1000).toLocaleTimeString()));
    const statusTd = el("td");
    if (sub.status === "scored") statusTd.appendChild(el("span", "status-scored", "scored"));
    else if (sub.status === "error") statusTd.appendChild(el("span", "status-error", "error"));
    else statusTd.appendChild(el("span", "status-busy", sub.status + "\\u2026"));
    tr.appendChild(statusTd);
    tr.appendChild(el("td", "total", sub.total_score === null ? "-" : sub.total_score.toFixed(2)));
    let detail = sub.error || "";
    if (sub.status === "scored" && sub.scenario_scores) {{
      detail = Object.entries(sub.scenario_scores)
        .map(([name, score]) => name + " " + score.toFixed(1)).join(" \\u00b7 ")
        + (sub.error ? "  (" + sub.error + ")" : "");
    }}
    tr.appendChild(el("td", "left hint", detail));
    body.appendChild(tr);
  }}
}}
refresh();
setInterval(refresh, 3000);
{AI_SCRIPT}
{REPLAY_SCRIPT}
{ACT_SCRIPT}
</script>
{USERMENU_SNIPPET}
</body>
</html>
"""


LOGIN_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Log in - Traffic Flow Challenge</title>
<style>{BASE_CSS}</style>
</head>
<body>
<div class="wrap" style="max-width: 640px">
{_HEADER}
  <div class="card">
    <h2>Log in</h2>
    __ERROR__
    <form method="post" action="/login">
      <label for="name">Name (as shown on the leaderboard)</label>
      <input type="text" id="name" name="name" maxlength="40" required autofocus>
      <label for="password">Password</label>
      <input type="password" id="password" name="password" maxlength="64" required>
      <p style="margin-top:18px"><button class="btn" type="submit">Log in</button>
         <a class="btn secondary" href="/signup" style="margin-left:8px">Create an account</a></p>
    </form>
    <p class="hint">Logging in takes you back to your personal upload page.
       Forgot your password? Ask an organizer &mdash; or if you still have your
       upload page bookmarked, that link keeps working.</p>
  </div>
</div>
</body>
</html>
"""


NOT_FOUND_HTML = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Not found</title>
<style>{BASE_CSS}</style></head>
<body><div class="wrap" style="max-width:640px">
{_HEADER}
<div class="card"><h2>Page not found</h2>
<p class="hint">That link doesn't exist (or the secret token is wrong).
Go back to the <a href="/">leaderboard</a> or <a href="/signup">sign up</a>.</p></div>
</div></body></html>
"""




def signup_page(error: str = "") -> str:
    block = f'<div class="msg err">{error}</div>' if error else ""
    return SIGNUP_HTML.replace("__ERROR__", block)


def login_page(error: str = "") -> str:
    block = f'<div class="msg err">{error}</div>' if error else ""
    return LOGIN_HTML.replace("__ERROR__", block)
