"""The colour themes, as named settings, for the study pages.

Each block is one theme: a short list of colours and fonts. A page picks a theme by putting
data-theme="..." on its <html> element; with none, it is the default "Nightfall". The dashboard
(progress.py) has the same values in its own template for now; keep the two in step when changing a colour.
"""

THEMES = ["nightfall", "twilight", "sky", "midnight", "paper", "lilac"]
NAMES = {"nightfall": "Nightfall", "twilight": "Twilight", "sky": "Blue sky", "midnight": "Midnight", "paper": "Paper", "lilac": "Lilac"}

TOKENS = """:root {
  /* Nightfall, the default: near-black with a purple tint, bright text, one lavender accent. */
  --bg:#0d0b14; --card:#15121f; --ink:#f3f1f8; --soft:#aaa4bd; --line:#2a2539; --muted:#1c182a;
  --primary:#c2b2ff; --on-primary:#15102b; --primary-soft:#2a2344; --track:#2a2539;
  --good:#5fe3b0; --mid:#f6c962; --low:#ff8f8f; --none:#8f89a6;
  --radius:14px; --shadow:0 1px 0 rgba(255,255,255,.04) inset, 0 12px 32px rgba(0,0,0,.35);
  --sans:"Geist", -apple-system, "Segoe UI", sans-serif; --mono:"Geist Mono", ui-monospace, "SF Mono", Menlo, monospace;
}
:root[data-theme="lilac"] {
  --bg:#faf5ff; --card:#ffffff; --ink:#0f172a; --soft:#475569; --line:#e9defa; --muted:#f4eefd;
  --primary:#6d28d9; --on-primary:#ffffff; --primary-soft:#ede4fd; --track:#ece6f6;
  --good:#047857; --mid:#a85a00; --low:#b91c1c; --none:#64748b;
  --shadow:0 1px 2px rgba(15,23,42,.05), 0 8px 24px rgba(124,58,237,.07);
}
:root[data-theme="twilight"] {
  --page:linear-gradient(180deg, #0a1040 0%, #25267a 28%, #6d3d9c 52%, #d9628f 76%, #ffb07a 100%);
  --bg:#0a1040; --card:rgba(16,18,62,.74); --ink:#f7f4ff; --soft:#d3cdee; --line:rgba(255,255,255,.17); --muted:rgba(255,255,255,.09);
  --primary:#ff9ac1; --on-primary:#2a0f3d; --primary-soft:rgba(255,154,193,.2); --track:rgba(255,255,255,.17);
  --good:#7df0cf; --mid:#ffd68a; --low:#ff9c9c; --none:#bdb8dc;
  --shadow:0 10px 30px rgba(6,8,40,.35);
}
:root[data-theme="sky"] {
  --page:linear-gradient(180deg, #0a3fa8 0%, #1565d8 28%, #2c93ec 56%, #7ccaf7 82%, #dcf3ff 100%);
  --bg:#1565d8; --card:rgba(255,255,255,.9); --ink:#0b2545; --soft:#3b5676; --line:rgba(11,60,140,.16); --muted:rgba(21,101,216,.08);
  --primary:#1260d6; --on-primary:#ffffff; --primary-soft:#ffe1ec; --track:#d9e6f5;
  --good:#0a7a4b; --mid:#a05a00; --low:#c0264a; --none:#5b7088;
  --shadow:0 10px 30px rgba(8,50,130,.25); --head:#ffffff; --head-soft:#e4f1ff;
}
:root[data-theme="paper"] {
  --bg:#f6f5f1; --card:#ffffff; --ink:#1d1d1f; --soft:#55555d; --line:#dedcd5; --muted:#f0eee7;
  --primary:#2f5d8a; --on-primary:#ffffff; --primary-soft:#e1eaf3; --track:#e6e4dc;
  --good:#1f7a4a; --mid:#9a6200; --low:#b3261e; --none:#6b6b73;
  --shadow:none; --font:Georgia, "Times New Roman", serif;
}
:root[data-theme="midnight"] {
  --bg:#0b0d12; --card:#151821; --ink:#e8eaf0; --soft:#9aa1b2; --line:#262b38; --muted:#1b1f2b;
  --primary:#5eead4; --on-primary:#06231f; --primary-soft:#12332f; --track:#252a36;
  --good:#4ade80; --mid:#facc15; --low:#f87171; --none:#8891a5;
  --shadow:0 1px 2px rgba(0,0,0,.5);
}
"""
