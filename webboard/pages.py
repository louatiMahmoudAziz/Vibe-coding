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
  <p style="margin: 0 0 18px"><a class="btn" href="/signup">Join the challenge</a>
     <a class="btn secondary" href="/login" style="margin-left:8px">Log in</a>
     <span class="hint" style="margin-left:12px">Create an account, upload your policy as often as you like &mdash; your best score counts.</span></p>
  <table>
    <thead><tr id="head-row"></tr></thead>
    <tbody id="rows"><tr><td class="empty" id="empty-cell">Waiting for the first participant&hellip;</td></tr></tbody>
  </table>
  <footer>
    Per-scenario score = <code>60 &times; throughput</code> + <code>40 &times; latency</code>
    &minus; <code>starvation penalty</code>; total is the average across scenarios.
    Ranked by best submission; ties go to whoever got there first. Updates automatically.
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
    " scenarios per evaluation \\u00b7 max score 100 \\u00b7 " +
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
