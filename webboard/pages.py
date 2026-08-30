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
     <span class="hint" id="cta-hint" style="margin-left:12px">Create an account, upload your policy as often as you like &mdash; your best score counts.</span></p>
  <table>
    <thead><tr id="head-row"></tr></thead>
    <tbody id="rows"><tr><td class="empty" id="empty-cell">Waiting for the first participant&hellip;</td></tr></tbody>
  </table>
  <footer>
    Three requirements have to hold on every scenario: <code>traffic keeps moving</code>,
    <code>the typical trip is reasonable</code>, and <code>nobody is stranded</code>.
    Miss one and you rank below everyone who missed none, whatever your averages say.
    Among those who pass, lowest waiting time wins. Updates automatically.
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
    " scenarios per evaluation \\u00b7 requirements before score \\u00b7 " +
    payload.standings.length + " participant(s)" +
    (payload.backlog > 0 ? " \\u00b7 " + payload.backlog + " evaluation(s) queued" : "");

  const head = document.getElementById("head-row");
  head.replaceChildren(el("th", "left", "#"), el("th", "left", "Participant"), el("th", "", "Best"));
  for (const s of payload.scenarios) head.appendChild(el("th", "", s.title));
  head.appendChild(el("th", "", "Tries"));
  head.appendChild(el("th", "", "Last upload"));
  head.appendChild(el("th", "", "Status"));

  const body = document.getElementById("rows");
  body.replaceChildren();
  if (!payload.standings.length) {{
    const tr = el("tr");
    const td = el("td", "empty", "Waiting for the first participant\\u2026");
    td.colSpan = 6 + payload.scenarios.length;
    tr.appendChild(td);
    body.appendChild(tr);
    return;
  }}
  payload.standings.forEach((entry, index) => {{
    const rank = index + 1;
    const tr = el("tr", rank <= 3 && entry.best_score !== null ? "p" + rank : "");
    const rankTd = el("td", "left");
    rankTd.appendChild(el("span", "badge", String(rank)));
    tr.appendChild(rankTd);
    tr.appendChild(el("td", "name", entry.name));
    tr.appendChild(el("td", "total", entry.best_score === null ? "-" : entry.best_score.toFixed(2)));
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
    "Upload a new version of your policy \\u2014 your best score is what counts.";
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
       policy as often as you like; your <b>best</b> score is what ranks on the
       <a href="/">leaderboard</a>. Lost the tab? Just <a href="/login">log in</a> again.</p>
  </div>
</div>
</body>
</html>
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
      placeholder="Think about what the client actually asked for, then say what the policy must guarantee and what it should optimise."></textarea>
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
  NS_STRAIGHT: ["N_straight", "S_straight"], NS_LEFT: ["N_left", "S_left"],
  EW_STRAIGHT: ["E_straight", "W_straight"], EW_LEFT: ["E_left", "W_left"]
};
const APPROACH = {
  N: {dx: 0, dy: -1, ox: 1, oy: 0}, S: {dx: 0, dy: 1, ox: -1, oy: 0},
  E: {dx: 1, dy: 0, ox: 0, oy: 1},  W: {dx: -1, dy: 0, ox: 0, oy: -1}
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
    const dir = lane[0], isLeft = lane.indexOf("left") > 0;
    const a = APPROACH[dir], lat = isLeft ? 30 : -30, gap = ROAD / 2 + 14;
    const isOpen = !inTrans && open.indexOf(lane) !== -1;

    rctx.fillStyle = isOpen ? "#2ee6a8" : (inTrans ? "#ffb84d" : "#ff6b81");
    rctx.globalAlpha = isOpen ? 1 : 0.55;
    rctx.beginPath();
    rctx.arc(RCX + a.dx * gap + a.ox * lat, RCY + a.dy * gap + a.oy * lat, 5.5, 0, 6.284);
    rctx.fill(); rctx.globalAlpha = 1;

    const n = Math.min(f[2][idx], 26), oldest = f[3][idx];
    for (let i = 0; i < n; i++) {
      const dd = gap + 12 + i * (CAR + CGAP);
      const x = RCX + a.dx * dd + a.ox * lat - CAR / 2;
      const y = RCY + a.dy * dd + a.oy * lat - CAR / 2;
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
        RCX + a.dx * dd + a.ox * lat, RCY + a.dy * dd + a.oy * lat + 4);
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
  ["act1", "Act 1 — The pilot", "Monday, 6:40 a.m.",
   "Keep traffic moving and do not leave people sitting there. Switching the lights costs a few seconds each time."],
  ["act2", "Act 2 — The dashboard was fine", "Thursday, 4:15 p.m.",
   "Your numbers look great. Eleven complaints from one block — people turning left sit through six cycles. Nobody waits over 140 seconds. Ever. And the morning traffic still counts."],
  ["deployment", "Act 3 — Eight hundred intersections", "Six weeks later",
   "The pilot cleared review. Your controller ships as-is to every intersection in the program. There is no per-site tuning in this contract."],
];

let shownAct = null;

async function paintActs() {
  let cur = "act1";
  try {
    cur = (await (await fetch("/api/act", {cache: "no-store"})).json()).act;
  } catch (err) { return; }

  const board = document.getElementById("act-board");
  if (cur === shownAct && board.children.length) return;
  const advanced = shownAct !== null && cur !== shownAct;
  shownAct = cur;

  const idx = ACT_COPY.findIndex(a => a[0] === cur);
  board.replaceChildren();
  ACT_COPY.forEach(function (a, i) {
    const card = document.createElement("div");
    card.className = "act " + (i < idx ? "done" : i === idx ? "live" : "locked");
    const tag = document.createElement("div");
    tag.className = "tag";
    tag.textContent = (i > idx ? "locked" : i === idx ? "now" : "done") + " · " + a[2];
    const h = document.createElement("h3");
    h.textContent = i > idx ? "Not yet" : a[1];
    const p = document.createElement("p");
    p.className = "client";
    p.textContent = a[3];
    card.appendChild(tag); card.appendChild(h); card.appendChild(p);
    board.appendChild(card);
  });

  const frozen = cur === "deployment";
  document.getElementById("act-clock").textContent = frozen
    ? "AI access is closed. Your last submission is what ships."
    : "Scored on this act's traffic plus every earlier act's.";
  if (typeof askBtn !== "undefined" && askBtn) askBtn.disabled = frozen;
  if (typeof buildBtn !== "undefined" && buildBtn) buildBtn.disabled = frozen;

  if (advanced && typeof say === "function") {
    say(frozen
      ? "The city exercised the rollout option. No more generations."
      : "The client has been in touch - read the contract above.", "ok");
  }
}

paintActs();
setInterval(paintActs, 4000);
"""

ME_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>My submissions - Traffic Flow Challenge</title>
<style>{BASE_CSS}</style>
</head>
<body>
<div class="wrap" style="max-width: 860px">
{_HEADER}
{ACT_BOARD}
{AI_CARD}
{REPLAY_CARD}
  <div class="card">
    <h2 id="hello">My submissions</h2>
    <div id="banner"></div>
    <p class="hint">This is your personal upload page. You stay signed in on
       this device until you log out (click your name, top right); from another
       device just <a href="/login">log in</a> again. Every upload is
       automatically evaluated on 5 scenarios &times; 3 seeds; your best total
       ranks on the <a href="/">live leaderboard</a>.</p>
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
    payload.name + " \\u2014 best score: " +
    (payload.best_score === null ? "none yet" : payload.best_score.toFixed(2));
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



CONTROL_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Run the room - Traffic Flow Challenge</title>
<style>{BASE_CSS}
  .act-btn {{ display: block; width: 100%; text-align: left; margin-bottom: 10px;
             background: var(--panel-2); border: 1px solid var(--line); color: var(--text);
             padding: 16px 18px; border-radius: 12px; cursor: pointer; font: inherit; }}
  .act-btn:hover {{ border-color: var(--accent); }}
  .act-btn[aria-current="true"] {{ border-color: var(--accent); background: #ffd1661a; }}
  .act-btn b {{ display: block; font-size: 16px; margin-bottom: 3px; }}
  .act-btn span {{ color: var(--muted); font-size: 13.5px; }}
  .act-btn .now {{ color: var(--accent); font-weight: 700; font-size: 12px;
                   letter-spacing: .1em; text-transform: uppercase; }}
  input[type=password] {{ width: 100%; background: #0a0f1e; color: var(--text);
    border: 1px solid var(--line); border-radius: 10px; padding: 11px 13px;
    font-family: ui-monospace, monospace; font-size: 14px; }}
</style>
</head>
<body>
<div class="wrap" style="max-width: 620px">
{_HEADER}
  <div class="card">
    <h2>Run the room</h2>
    <p class="hint">Everyone moves together. Advancing the act changes what every
       participant's next submission is scored against, and unlocks the client's
       message on their page.</p>
    <div id="banner"></div>
    <label for="pw">Organiser password</label>
    <input type="password" id="pw" autocomplete="current-password"
           placeholder="VCC_ADMIN_PASSWORD">
    <div style="margin-top:18px" id="acts"></div>
  </div>
</div>
<script>
const ACTS = [
  ["act1", "Act 1 - The pilot",
   "Monday morning. Moderate traffic. A lazy prompt passes, and it should."],
  ["act2", "Act 2 - The dashboard was fine",
   "The 311 complaints land. Nobody may wait over 140s - and Act 1 still counts."],
  ["deployment", "Act 3 - Eight hundred intersections",
   "Freeze the code. Four sites nobody has seen. Close the AI budget."],
];

function banner(text, kind) {{
  const b = document.createElement("div");
  b.className = "msg " + kind;
  b.textContent = text;
  document.getElementById("banner").replaceChildren(b);
}}

async function paint() {{
  let cur = "act1";
  try {{
    cur = (await (await fetch("/api/act", {{cache: "no-store"}})).json()).act;
  }} catch (err) {{ /* show the buttons anyway */ }}
  const box = document.getElementById("acts");
  box.replaceChildren();
  ACTS.forEach(function (a) {{
    const btn = document.createElement("button");
    btn.className = "act-btn";
    btn.type = "button";
    btn.setAttribute("aria-current", a[0] === cur ? "true" : "false");
    const t = document.createElement("b"); t.textContent = a[1];
    const d = document.createElement("span"); d.textContent = a[2];
    btn.appendChild(t); btn.appendChild(d);
    if (a[0] === cur) {{
      const n = document.createElement("div");
      n.className = "now"; n.textContent = "Live now";
      btn.appendChild(n);
    }}
    btn.addEventListener("click", function () {{ advance(a[0], a[1]); }});
    box.appendChild(btn);
  }});
}}

async function advance(act, label) {{
  const pw = document.getElementById("pw").value;
  if (!pw) {{ banner("Enter the organiser password first.", "err"); return; }}
  const body = new URLSearchParams({{act: act, password: pw}});
  const res = await fetch("/admin/act", {{
    method: "POST",
    headers: {{"Content-Type": "application/x-www-form-urlencoded"}},
    body: body.toString(),
  }});
  const payload = await res.json();
  if (!res.ok) {{ banner(payload.error || "Could not advance.", "err"); return; }}
  banner("The room is now on " + label + ".", "ok");
  paint();
}}

paint();
setInterval(paint, 5000);
</script>
</body>
</html>
"""


def control_page() -> str:
    return CONTROL_HTML


def signup_page(error: str = "") -> str:
    block = f'<div class="msg err">{error}</div>' if error else ""
    return SIGNUP_HTML.replace("__ERROR__", block)


def login_page(error: str = "") -> str:
    block = f'<div class="msg err">{error}</div>' if error else ""
    return LOGIN_HTML.replace("__ERROR__", block)
