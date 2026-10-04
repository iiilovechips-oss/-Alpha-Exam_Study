"""How well the user knows each topic, and how ready they are for each exam.

Understanding is measured from what the user does, not from what they read: every tap on a check
question is recorded. Reading a page or its summary moves nothing. See PLAN.md for the reasoning.
"""

import html
import json
import re
import tomllib
import webbrowser
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from exam_study.explain import EXPLAINED
from exam_study.export import ROOT

LOG = ROOT / "study" / "progress.jsonl"   # one line per answer
TIME_LOG = ROOT / "study" / "time.jsonl"   # one line per few seconds of active study time
LEVELS = ROOT / "study" / "LEVELS.md"     # self-ratings, used only as a starting guess
CONFIG = ROOT / "study.toml"
THEME_ART = ROOT / "study" / "themes"       # optional pictures for themes, e.g. twilight.jpg (kept out of git)
ART_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "svg": "image/svg+xml"}
PORT = 8765

# --- The formula (version 1, a heuristic; tune it against real exam scores) ---
PRIOR_WEIGHT = 2.0      # the self-rating counts like two answered questions, so real answers soon outweigh it
DEFAULT_PRIOR = 0.2     # assumed level for a topic with no self-rating
KIND_WEIGHT = {"mc": 1.0, "self": 0.6}   # self-graded answers count less: people are generous with themselves
RETRY_FACTOR = 0.5      # a question answered before counts half: some of it is memory of the answer
OUTCOME = {"right": 1.0, "partly": 0.5, "wrong": 0.0}
SOLID_EVIDENCE = 3.0    # weighted answers needed before a topic's number is trusted


def norm(topic: str) -> str:
    """'Chapter 6- Revenue Recognition' and 'Chapter 6: Revenue...' both become 'chapter6'."""
    return re.sub(r"[^a-z0-9]", "", re.split(r"[:\-]", topic, maxsplit=1)[0].lower())


def scored_answers(events: list[dict]) -> list[tuple[float, float]]:
    """(outcome, weight) for the latest attempt at each question."""
    attempts: dict[tuple, list[dict]] = {}
    for event in sorted(events, key=lambda e: e["ts"]):
        attempts.setdefault((event["deck"], event["q"]), []).append(event)
    scored = []
    for tries in attempts.values():
        last = tries[-1]
        weight = KIND_WEIGHT.get(last["kind"], 0.6) * (RETRY_FACTOR if len(tries) > 1 else 1.0)
        scored.append((OUTCOME[last["outcome"]], weight))
    return scored


def mastery(prior: float, answers: list[tuple[float, float]]) -> tuple[float, float]:
    """Return (mastery 0-1, evidence). A weighted average of the answers, pulled toward the self-rating
    when there are few of them."""
    evidence = sum(weight for _, weight in answers)
    score = (PRIOR_WEIGHT * prior + sum(outcome * weight for outcome, weight in answers)) / (PRIOR_WEIGHT + evidence)
    return score, evidence


def readiness(topics: list[dict]) -> tuple[float, float]:
    """Return (expected share of the exam the user would get right, share of the exam backed by solid evidence)."""
    total = sum(t["weight"] for t in topics) or 1
    ready = sum(t["weight"] * t["mastery"] for t in topics) / total
    covered = sum(t["weight"] for t in topics if t["evidence"] >= SOLID_EVIDENCE) / total
    return ready, covered


def load_events() -> list[dict]:
    if not LOG.exists():
        return []
    return [json.loads(line) for line in LOG.read_text().splitlines() if line.strip()]


def load_time() -> list[dict]:
    if not TIME_LOG.exists():
        return []
    return [json.loads(line) for line in TIME_LOG.read_text().splitlines() if line.strip()]


def seconds_for(entries: list[dict], course: str | None = None, deck: str | None = None, day: str | None = None) -> int:
    """Add up study seconds, optionally for one course, one deck, or one day ("2026-10-01")."""
    return sum(e["seconds"] for e in entries
               if (course is None or e["course"] == course) and (deck is None or e["deck"] == deck)
               and (day is None or e["ts"].startswith(day)))


def duration(seconds: int) -> str:
    hours, minutes = seconds // 3600, seconds % 3600 // 60
    return f"{hours}h {minutes:02}m" if hours else f"{minutes}m"


def load_levels() -> dict[tuple[str, str], float]:
    levels = {}
    if LEVELS.exists():
        for line in LEVELS.read_text().splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and cells[2].rstrip("%").isdigit():
                levels[(cells[0], norm(cells[1]))] = int(cells[2].rstrip("%")) / 100
    return levels


def exam_report(exam: dict, events: list[dict], levels: dict) -> dict | None:
    weights = exam.get("weights")
    if not weights:
        return None
    topics = []
    for name, weight in weights.items():
        mine = [e for e in events if e["course"] == exam["course"] and norm(e["topic"]) == norm(name)]
        prior = levels.get((exam["course"], norm(name)), DEFAULT_PRIOR)
        score, evidence = mastery(prior, scored_answers(mine))
        topics.append({"name": name, "weight": weight, "mastery": score, "evidence": evidence, "prior": prior})
    ready, covered = readiness(topics)
    return {"exam": exam, "topics": topics, "readiness": ready, "covered": covered}


def all_reports(today: date | None = None) -> list[dict]:
    today = today or date.today()
    exams = tomllib.loads(CONFIG.read_text()).get("exam", []) if CONFIG.exists() else []
    events, levels = load_events(), load_levels()
    reports = [exam_report(e, events, levels) for e in exams if date.fromisoformat(e["date"]) >= today]
    return sorted((r for r in reports if r), key=lambda r: r["exam"]["date"])


def decks(events: list[dict]) -> list[dict]:
    found, times = [], load_time()
    for slides_file in sorted(EXPLAINED.glob("*/*/slides.json")):
        folder = slides_file.parent
        notes = json.loads((folder / "notes.json").read_text()) if (folder / "notes.json").exists() else {}
        course, deck = folder.parent.name, folder.name
        answered = {e["q"] for e in events if e["course"] == course and e["deck"] == deck}
        found.append({"course": course, "deck": deck, "name": notes.get("name") or deck,
                      "topic": Path(json.loads(slides_file.read_text())["deck"]).parts[1],
                      "slides": len(json.loads(slides_file.read_text())["slides"]),
                      "explained": len(notes.get("slides", {})),
                      "questions": len(notes.get("check", [])) + sum(1 for s in notes.get("slides", {}).values() if s.get("question")),
                      "answered": len(answered), "seconds": seconds_for(times, course, deck), "url": f"/explained/{course}/{deck}/index.html"})
    return sorted(found, key=deck_order)


def deck_order(deck: dict) -> tuple:
    """Where a study page goes in the dashboard list: by course, then chapter number, then part number.

    The numbers are read from the display name, such as "Chapter 6, Part 3 - Long-term contracts".
    Pages whose name has no chapter number (an exam review, for example) go after the chapters.
    """
    chapter = re.search(r"Chapters? (\d+)", deck["name"])
    part = re.search(r"Part (\d+)", deck["name"])
    return (deck["course"], int(chapter.group(1)) if chapter else 999, int(part.group(1)) if part else 0, deck["name"])


def trust(evidence: float) -> str:
    if evidence == 0:
        return "your own guess, no answers yet"
    return f"{'early estimate' if evidence < SOLID_EVIDENCE else 'solid'}, from {evidence:.1f} answers' worth"


def text_summary() -> str:
    lines = []
    for r in all_reports():
        exam = r["exam"]
        lines.append(f"{exam['course']} {exam['name']} ({exam['date']}): readiness {r['readiness']:.0%}, "
                     f"{r['covered']:.0%} of the exam backed by solid evidence")
        lines += [f"  {t['name']:<16} {t['mastery']:>4.0%}  (exam weight {t['weight']}, {trust(t['evidence'])})"
                  for t in r["topics"]]
    times = load_time()
    if times:
        lines.append(f"Study time: {duration(seconds_for(times, day=date.today().isoformat()))} today, {duration(seconds_for(times))} in total")
    return "\n".join(lines) or "No upcoming exam in study.toml has a [exam.weights] table yet."


# The look of the dashboard. Every colour, font and size is a named setting, so a theme is only a short list
# of different values. The layout: one big readiness number, the exam and what to study next beside it, a
# row of chapter tiles sized by exam weight, three plain totals, then the study pages in one drop-down per class.
DASHBOARD = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Study progress</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@500;600&display=swap">
<style>
:root {{
  /* Nightfall, the default: near-black with a purple tint, bright text, one lavender accent. */
  --bg:#0d0b14; --card:#15121f; --ink:#f3f1f8; --soft:#aaa4bd; --line:#2a2539; --muted:#1c182a;
  --primary:#c2b2ff; --on-primary:#15102b; --primary-soft:#2a2344; --track:#2a2539;
  --good:#5fe3b0; --mid:#f6c962; --low:#ff8f8f; --none:#8f89a6;
  --radius:14px; --shadow:0 1px 0 rgba(255,255,255,.04) inset, 0 12px 32px rgba(0,0,0,.35);
  --sans:"Geist", -apple-system, "Segoe UI", sans-serif; --mono:"Geist Mono", ui-monospace, "SF Mono", Menlo, monospace;
}}
/* Lilac: the light purple look from the first redesign. */
:root[data-theme="lilac"] {{
  --bg:#faf5ff; --card:#ffffff; --ink:#0f172a; --soft:#475569; --line:#e9defa; --muted:#f4eefd;
  --primary:#6d28d9; --on-primary:#ffffff; --primary-soft:#ede4fd; --track:#ece6f6;
  --good:#047857; --mid:#a85a00; --low:#b91c1c; --none:#64748b;
  --shadow:0 1px 2px rgba(15,23,42,.05), 0 8px 24px rgba(124,58,237,.07);
}}
/* --- Themes. Each one is only a different set of the named settings above. The page picks one by putting
   data-theme="..." on the <html> element; with no data-theme it is the default "Nightfall". --- */
/* Twilight: the dusk sky and comet from the film "Your Name" (colours only, drawn here; no film artwork). */
:root[data-theme="twilight"] {{
  --page:linear-gradient(180deg, #0a1040 0%, #25267a 28%, #6d3d9c 52%, #d9628f 76%, #ffb07a 100%);
  --bg:#0a1040; --card:rgba(16,18,62,.74); --ink:#f7f4ff; --soft:#d3cdee; --line:rgba(255,255,255,.17); --muted:rgba(255,255,255,.09);
  --primary:#ff9ac1; --on-primary:#2a0f3d; --primary-soft:rgba(255,154,193,.2); --track:rgba(255,255,255,.17);
  --good:#7df0cf; --mid:#ffd68a; --low:#ff9c9c; --none:#bdb8dc;
  --shadow:0 10px 30px rgba(6,8,40,.35);
}}
/* Blue sky: the bright daytime sky of the "Your Name" poster: deep blue down to pale blue, white clouds,
   the comet, and a touch of pink and grass green (colours only, drawn here; no film artwork). */
:root[data-theme="sky"] {{
  --page:linear-gradient(180deg, #0a3fa8 0%, #1565d8 28%, #2c93ec 56%, #7ccaf7 82%, #dcf3ff 100%);
  --bg:#1565d8; --card:rgba(255,255,255,.9); --ink:#0b2545; --soft:#3b5676; --line:rgba(11,60,140,.16); --muted:rgba(21,101,216,.08);
  --primary:#1260d6; --on-primary:#ffffff; --primary-soft:#ffe1ec; --track:#d9e6f5;
  --good:#0a7a4b; --mid:#a05a00; --low:#c0264a; --none:#5b7088;
  --shadow:0 10px 30px rgba(8,50,130,.25); --head:#ffffff; --head-soft:#e4f1ff;
}}
:root[data-theme="sky"] .pill {{ color:#c2255c; }}
/* Paper: the calm beige-and-blue look the dashboard had before the redesign. */
:root[data-theme="paper"] {{
  --bg:#f6f5f1; --card:#ffffff; --ink:#1d1d1f; --soft:#55555d; --line:#dedcd5; --muted:#f0eee7;
  --primary:#2f5d8a; --on-primary:#ffffff; --primary-soft:#e1eaf3; --track:#e6e4dc;
  --good:#1f7a4a; --mid:#9a6200; --low:#b3261e; --none:#6b6b73;
  --shadow:none; --font:Georgia, "Times New Roman", serif;
}}
/* Midnight: near-black with a mint accent, for studying late. */
:root[data-theme="midnight"] {{
  --bg:#0b0d12; --card:#151821; --ink:#e8eaf0; --soft:#9aa1b2; --line:#262b38; --muted:#1b1f2b;
  --primary:#5eead4; --on-primary:#06231f; --primary-soft:#12332f; --track:#252a36;
  --good:#4ade80; --mid:#facc15; --low:#f87171; --none:#8891a5;
  --shadow:0 1px 2px rgba(0,0,0,.5);
}}

* {{ box-sizing:border-box; }}
body {{ margin:0; min-height:100dvh; background:var(--page, var(--bg)) fixed; color:var(--ink); font:16px/1.5 var(--font, var(--sans)); -webkit-font-smoothing:antialiased; }}
main {{ position:relative; z-index:1; max-width:1080px; margin:0 auto; padding:36px 20px 96px; }}
h1 {{ font-size:1.5rem; font-weight:650; letter-spacing:-.02em; margin:0; color:var(--head, var(--ink)); }}
h2 {{ font-size:1.05rem; font-weight:600; letter-spacing:-.01em; margin:0; }}
p {{ margin:0; }}
.small {{ color:var(--soft); font-size:.86rem; }}
.label {{ color:var(--soft); font-size:.72rem; font-weight:600; letter-spacing:.09em; text-transform:uppercase; }}
.num {{ font-family:var(--mono); font-variant-numeric:tabular-nums; letter-spacing:-.04em; }}
a:focus-visible, button:focus-visible, summary:focus-visible {{ outline:2px solid var(--primary); outline-offset:3px; border-radius:8px; }}

/* Top row: title on the left, theme buttons on the right. */
.head {{ display:flex; justify-content:space-between; align-items:flex-end; gap:16px 24px; flex-wrap:wrap; margin-bottom:28px; }}
.head .sub {{ color:var(--head-soft, var(--soft)); max-width:36em; margin-top:2px; }}
.head .label {{ color:var(--head-soft, var(--soft)); }}
.themes {{ display:flex; align-items:center; gap:4px; flex-wrap:wrap; padding:4px; border:1px solid var(--line); border-radius:999px; background:var(--card); }}
.themes button {{ min-height:36px; padding:0 13px; border-radius:999px; border:0; background:transparent; color:var(--soft); font:inherit; font-size:.84rem; font-weight:500; cursor:pointer; transition:background .15s ease-out, color .15s ease-out; }}
.themes button:hover {{ color:var(--ink); background:var(--muted); }}
.themes button[aria-pressed="true"] {{ background:var(--primary); color:var(--on-primary); }}

/* The exam block. Left: the one big number. Right: which exam, and what to study next. */
.card {{ background:var(--card); border:1px solid var(--line); border-radius:var(--radius); box-shadow:var(--shadow); -webkit-backdrop-filter:blur(12px); backdrop-filter:blur(12px); }}
.exam {{ padding:28px; margin-bottom:20px; }}
.lead {{ display:grid; grid-template-columns:minmax(0, 5fr) minmax(0, 7fr); gap:28px 40px; align-items:end; }}
.score .big {{ display:flex; align-items:baseline; line-height:.86; }}
.score .big b {{ font:600 clamp(5rem, 13vw, 8.5rem)/.86 var(--mono); letter-spacing:-.07em; font-variant-numeric:tabular-nums; }}
.score .big span {{ font:500 clamp(1.6rem, 4vw, 2.6rem)/1 var(--mono); color:var(--soft); margin-left:6px; }}
.score p {{ margin-top:14px; max-width:26em; }}
.which h2 {{ font-size:1.55rem; letter-spacing:-.025em; line-height:1.15; margin-top:4px; }}
.when {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-top:8px; }}
.pill {{ background:var(--primary-soft); color:var(--primary); font-weight:600; font-size:.8rem; padding:3px 10px; border-radius:999px; }}
.next {{ display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; margin-top:22px; padding-top:18px; border-top:1px solid var(--line); }}
.btn {{ display:inline-flex; align-items:center; min-height:44px; padding:0 20px; border-radius:999px; background:var(--primary); color:var(--on-primary); font-weight:600; text-decoration:none; white-space:nowrap; transition:transform .15s ease-out, filter .15s ease-out; }}
.btn:hover {{ filter:brightness(1.08); }} .btn:active {{ transform:translateY(1px) scale(.98); }}

/* The exam map: one tile per chapter, and a tile is as wide as that chapter's share of the exam. */
.map {{ display:grid; gap:10px; margin-top:28px; }}
.tile {{ position:relative; min-width:0; padding:16px 16px 18px; border-radius:10px; background:var(--muted); border:1px solid var(--line); overflow:hidden; }}
.tile .name {{ font-weight:600; line-height:1.25; }}
.tile .val {{ font:600 2.1rem/1 var(--mono); letter-spacing:-.05em; font-variant-numeric:tabular-nums; margin:18px 0 6px; }}
.tile .val span {{ font-size:1rem; color:var(--soft); margin-left:2px; }}
.tile .tag {{ font-size:.82rem; font-weight:600; }}
.tile .meter {{ position:absolute; left:0; right:0; bottom:0; height:4px; background:var(--track); }}
.tile .meter i {{ display:block; height:100%; }}
.maphint {{ margin-top:10px; }}


/* Three layouts of the exam block, to compare. All three are on the page; the Layout buttons show one. */
.lay {{ display:none; }}
:root[data-layout="gauge"] .lay-gauge, :root[data-layout="number"] .lay-number, :root[data-layout="focus"] .lay-focus {{ display:block; }}
.switches {{ display:flex; flex-direction:column; align-items:flex-end; gap:8px; }}
.themes .label {{ padding:0 6px 0 10px; }}

/* Layout "Gauge": a round gauge beside the exam, then one row per chapter. */
.g-top {{ display:grid; grid-template-columns:auto 1fr; gap:28px; align-items:center; }}
.ring {{ position:relative; width:148px; height:148px; }}
.ring svg {{ width:100%; height:100%; transform:rotate(-90deg); }}
.ring circle {{ fill:none; stroke-width:11; stroke-linecap:round; }}
.ring .back {{ stroke:var(--track); }}
.ring .in {{ position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; }}
.ring .in b {{ font:600 2.3rem/1 var(--mono); letter-spacing:-.05em; }}
.g-rows {{ margin-top:24px; border-top:1px solid var(--line); }}
.g-row {{ display:grid; grid-template-columns:minmax(130px, 1.1fr) 2fr 4.2em; gap:16px; align-items:center; padding:14px 0; }}
.g-row + .g-row {{ border-top:1px solid var(--line); }}
.g-row .pct {{ font:600 1.1rem var(--mono); text-align:right; letter-spacing:-.03em; }}
.g-row .bar {{ height:8px; margin:0; }}
.g-row .tag {{ font-size:.82rem; font-weight:600; }}

/* Layout "Focus list": one bar split by chapter, then the chapters ranked by exam points still to gain. */
.f-head {{ display:flex; justify-content:space-between; align-items:flex-end; gap:20px; flex-wrap:wrap; }}
.f-score {{ text-align:right; }} .f-score b {{ font:600 3.4rem/1 var(--mono); letter-spacing:-.06em; }} .f-score span {{ color:var(--soft); margin-left:6px; }}
.seg {{ display:grid; gap:4px; margin-top:22px; }}
.seg .part {{ min-width:0; }}
.seg .part i {{ display:block; height:14px; border-radius:4px; background:var(--track); overflow:hidden; }}
.seg .part i u {{ display:block; height:100%; }}
.seg .part span {{ display:block; margin-top:6px; font-size:.78rem; color:var(--soft); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.rank {{ list-style:none; margin:26px 0 0; padding:0; counter-reset:rank; }}
.rank li {{ display:grid; grid-template-columns:2.2rem 1fr auto auto; gap:16px; align-items:center; padding:14px 0; border-top:1px solid var(--line); counter-increment:rank; }}
.rank li::before {{ content:counter(rank); font:600 1rem var(--mono); color:var(--soft); }}
.rank li:first-child::before {{ color:var(--primary); }}
.rank .gain {{ text-align:right; }} .rank .gain b {{ display:block; font:600 1.25rem/1.1 var(--mono); letter-spacing:-.04em; }} .rank .gain span {{ font-size:.78rem; color:var(--soft); }}
.btn.quiet {{ background:transparent; color:var(--ink); border:1px solid var(--line); }}
.rank li:first-child .btn.quiet {{ background:var(--primary); color:var(--on-primary); border-color:var(--primary); }}
.f-title {{ margin-top:26px; font-size:.95rem; font-weight:600; }}

/* Three plain numbers, separated by thin lines. No boxes. */
.strip {{ display:grid; grid-template-columns:repeat(3, 1fr); margin:0 0 36px; border-top:1px solid var(--line); border-bottom:1px solid var(--line); }}
.strip div {{ padding:16px 20px; }} .strip div + div {{ border-left:1px solid var(--line); }}
.strip b {{ display:block; font:600 1.45rem/1.2 var(--mono); letter-spacing:-.04em; font-variant-numeric:tabular-nums; margin-top:2px; }}
.strip b span {{ font-size:.86rem; color:var(--soft); font-weight:500; letter-spacing:0; }}

/* Study pages: one drop-down per class. Rows are separated by space and a hover tint, not lines. */
.pages > .small {{ margin-top:2px; }}
.course {{ margin-top:14px; border:1px solid var(--line); border-radius:var(--radius); background:var(--card); overflow:hidden; -webkit-backdrop-filter:blur(12px); backdrop-filter:blur(12px); }}
.course summary {{ display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; min-height:52px; padding:0 18px; cursor:pointer; list-style:none; }}
.course summary::-webkit-details-marker {{ display:none; }}
.course summary::before {{ content:""; width:7px; height:7px; border-right:2px solid var(--soft); border-bottom:2px solid var(--soft); transform:rotate(-45deg); margin-right:6px; transition:transform .15s ease-out; flex:none; }}
.course[open] summary::before {{ transform:rotate(45deg); }}
.course summary > b {{ flex:1; font-weight:600; }}
.course .rows {{ padding:0 8px 8px; }}
.page {{ display:grid; grid-template-columns:1fr 150px 72px; gap:16px; align-items:center; padding:10px; border-radius:10px; color:inherit; text-decoration:none; transition:background .15s ease-out; }}
.page:hover {{ background:var(--muted); }}
.page .title {{ font-weight:550; }}
.page .time {{ text-align:right; font-family:var(--mono); font-variant-numeric:tabular-nums; }}
.bar {{ height:4px; background:var(--track); border-radius:999px; overflow:hidden; margin-bottom:5px; }}
.bar i {{ display:block; height:100%; border-radius:999px; }}
.done {{ color:var(--good); font-weight:600; }}
.how {{ margin-top:28px; max-width:60em; }}

/* Themes with a picture or a sky behind the page put the loose text on panels too, so it stays readable. */
:root[data-theme="twilight"] .strip, :root[data-theme="sky"] .strip, :root[data-theme="twilight"] .pages, :root[data-theme="sky"] .pages,
:root[data-theme="twilight"] .how, :root[data-theme="sky"] .how {{ background:var(--card); border:1px solid var(--line); border-radius:var(--radius); -webkit-backdrop-filter:blur(12px); backdrop-filter:blur(12px); }}
:root[data-theme="twilight"] .pages, :root[data-theme="sky"] .pages, :root[data-theme="twilight"] .how, :root[data-theme="sky"] .how {{ padding:18px; }}
@media (max-width:760px) {{
  main {{ padding:24px 16px 72px; }}
  .exam {{ padding:20px; }}
  .lead {{ grid-template-columns:1fr; align-items:start; }}
  .map {{ grid-template-columns:1fr 1fr !important; }}
  .g-top {{ grid-template-columns:1fr; }} .g-row {{ grid-template-columns:1fr auto; }} .g-row .bar {{ grid-column:1 / -1; grid-row:2; }}
  .rank li {{ grid-template-columns:1.6rem 1fr auto; }} .rank .btn {{ grid-column:2 / -1; justify-self:start; }}
  .switches {{ align-items:flex-start; }}
  .strip div {{ padding:14px 12px; }} .strip b {{ font-size:1.15rem; }}
  .page {{ grid-template-columns:1fr auto; }} .page .q {{ grid-column:1 / -1; grid-row:2; }}
}}
@media (prefers-reduced-motion: reduce) {{ * {{ transition:none !important; animation:none !important; }} }}
/* The night sky behind the Twilight theme: a few stars and a comet that splits in two. Hidden in other themes. */
.sky {{ display:none; }}
:root[data-theme="twilight"] .sky {{ display:block; position:fixed; inset:0; z-index:0; pointer-events:none; overflow:hidden;
  background-image:radial-gradient(1.6px 1.6px at 8% 12%, #fff 50%, transparent 52%), radial-gradient(1.2px 1.2px at 21% 31%, #fff 50%, transparent 52%),
    radial-gradient(1.8px 1.8px at 34% 9%, #fff 50%, transparent 52%), radial-gradient(1.2px 1.2px at 47% 22%, #fff 50%, transparent 52%),
    radial-gradient(1.5px 1.5px at 63% 6%, #fff 50%, transparent 52%), radial-gradient(1.2px 1.2px at 78% 27%, #fff 50%, transparent 52%),
    radial-gradient(1.7px 1.7px at 91% 15%, #fff 50%, transparent 52%), radial-gradient(1.1px 1.1px at 15% 44%, #fff 50%, transparent 52%),
    radial-gradient(1.3px 1.3px at 86% 40%, #fff 50%, transparent 52%), radial-gradient(1.1px 1.1px at 55% 38%, #fff 50%, transparent 52%); }}
:root[data-theme="twilight"] .sky::before, :root[data-theme="twilight"] .sky::after {{ content:""; position:absolute; right:6%; top:9%; height:3px; width:52vw; border-radius:3px;
  transform-origin:right center; transform:rotate(-17deg); background:linear-gradient(90deg, transparent, rgba(160,215,255,.35) 55%, #d9f1ff 92%, #fff); box-shadow:0 0 14px rgba(170,220,255,.7); }}
:root[data-theme="twilight"] .sky::after {{ width:34vw; height:2px; transform:rotate(-24deg); background:linear-gradient(90deg, transparent, rgba(255,170,205,.4) 55%, #ffd3e4 92%, #fff); box-shadow:0 0 12px rgba(255,160,200,.6); }}
:root[data-theme="twilight"] h1::after {{ content:""; display:block; width:84px; height:4px; margin-top:8px; border-radius:4px; background:repeating-linear-gradient(135deg, #ff6b6b 0 6px, #ffb07a 6px 12px, #ff9ac1 12px 18px); }}
/* Blue sky draws its scene as a picture made of shapes (the <svg> inside .sky): painted clouds, a curved comet
   with a second pink fragment, sparkles, a pale moon, a city on the left and a green hill on the right. */
.sky svg {{ display:none; }}
:root[data-theme="sky"] .sky {{ display:block; position:fixed; inset:0; z-index:0; pointer-events:none; overflow:hidden; }}
:root[data-theme="sky"] .sky svg {{ display:block; width:100%; height:100%; }}
:root[data-theme="sky"] main {{ padding-top:64px; }}
@media (prefers-reduced-motion: no-preference) {{
  :root[data-theme="sky"] .twinkle {{ animation:twinkle 3.2s ease-in-out infinite; }}
  :root[data-theme="sky"] .twinkle:nth-child(2n) {{ animation-delay:1.1s; }} :root[data-theme="sky"] .twinkle:nth-child(3n) {{ animation-delay:2s; }}
}}
@keyframes twinkle {{ 0%, 100% {{ opacity:.25; }} 50% {{ opacity:1; }} }}
:root[data-theme="sky"] h1::after {{ content:""; display:block; width:84px; height:4px; margin-top:8px; border-radius:4px; background:repeating-linear-gradient(135deg, #e11d48 0 6px, #ff8fb1 6px 12px, #fff 12px 18px); }}
</style>{art}
<script>
// Put the saved theme on the page before anything is drawn, so the page does not flash the default colours.
try {{ var saved = localStorage.getItem('exam-study:theme'); if (saved && saved !== 'nightfall' && saved !== 'purple') document.documentElement.setAttribute('data-theme', saved); }} catch (e) {{}}
// Same for the layout of the exam block. "gauge" is the starting choice.
var layout = 'gauge'; try {{ layout = localStorage.getItem('exam-study:layout') || 'gauge'; }} catch (e) {{}}
document.documentElement.setAttribute('data-layout', layout);
</script></head><body><div class="sky" aria-hidden="true"><svg viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
<defs>
<filter id="paint" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" baseFrequency=".013" numOctaves="3" seed="7"/><feDisplacementMap in="SourceGraphic" scale="26"/></filter>
<filter id="soft"><feGaussianBlur stdDeviation="14"/></filter><filter id="glow"><feGaussianBlur stdDeviation="5"/></filter>
<linearGradient id="tailA" gradientUnits="userSpaceOnUse" x1="1400" y1="-60" x2="760" y2="470"><stop offset="0" stop-color="#bfe6ff" stop-opacity="0"/><stop offset=".45" stop-color="#cfeeff" stop-opacity=".55"/><stop offset="1" stop-color="#fff"/></linearGradient>
<linearGradient id="tailB" gradientUnits="userSpaceOnUse" x1="1330" y1="-60" x2="1150" y2="430"><stop offset="0" stop-color="#ff9fc6" stop-opacity="0"/><stop offset=".5" stop-color="#ff8fbd" stop-opacity=".6"/><stop offset="1" stop-color="#ffe3ef"/></linearGradient>
<linearGradient id="tailC" gradientUnits="userSpaceOnUse" x1="1440" y1="60" x2="1010" y2="250"><stop offset="0" stop-color="#b7a6ff" stop-opacity="0"/><stop offset="1" stop-color="#e8e1ff" stop-opacity=".7"/></linearGradient>
<radialGradient id="head"><stop offset="0" stop-color="#fff"/><stop offset=".25" stop-color="#e6f6ff" stop-opacity=".9"/><stop offset="1" stop-color="#bfe6ff" stop-opacity="0"/></radialGradient>
<radialGradient id="headB"><stop offset="0" stop-color="#fff"/><stop offset=".3" stop-color="#ffc2da" stop-opacity=".9"/><stop offset="1" stop-color="#ff8fbd" stop-opacity="0"/></radialGradient>
<linearGradient id="hill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8fd94f"/><stop offset=".45" stop-color="#3fa844"/><stop offset="1" stop-color="#1d6b35"/></linearGradient>
<linearGradient id="tower" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#9fc0ee"/><stop offset=".5" stop-color="#6f95d6"/><stop offset="1" stop-color="#4c6fb5"/></linearGradient>
<g id="cloud"><g fill="#9fcdf4"><circle cx="70" cy="152" r="50"/><circle cx="135" cy="124" r="64"/><circle cx="205" cy="104" r="80"/><circle cx="278" cy="130" r="62"/><circle cx="336" cy="154" r="46"/><ellipse cx="204" cy="166" rx="170" ry="40"/></g>
<g fill="#d9eeff"><circle cx="70" cy="144" r="50"/><circle cx="135" cy="114" r="64"/><circle cx="205" cy="92" r="80"/><circle cx="278" cy="120" r="62"/><circle cx="336" cy="146" r="46"/><ellipse cx="204" cy="156" rx="168" ry="36"/></g>
<g fill="#fff"><circle cx="64" cy="134" r="44"/><circle cx="128" cy="100" r="58"/><circle cx="198" cy="76" r="72"/><circle cx="268" cy="106" r="54"/><circle cx="326" cy="136" r="38"/><ellipse cx="196" cy="140" rx="150" ry="26"/></g></g>
</defs>
<g opacity=".5" filter="url(#soft)" fill="#fff"><ellipse cx="330" cy="120" rx="260" ry="16"/><ellipse cx="620" cy="210" rx="200" ry="10"/><ellipse cx="1180" cy="560" rx="220" ry="12"/></g>
<g opacity=".8"><circle cx="1010" cy="150" r="17" fill="#eaf5ff"/><circle cx="1003" cy="145" r="16" fill="#1d6fdc"/></g>
<path d="M1440,60 C1300,120 1150,190 1010,250" stroke="url(#tailC)" stroke-width="2" fill="none" stroke-linecap="round"/>
<path d="M1400,-60 C1250,110 1040,330 760,470" stroke="url(#tailA)" stroke-width="26" fill="none" stroke-linecap="round" filter="url(#soft)" opacity=".7"/>
<path d="M1400,-60 C1250,110 1040,330 760,470" stroke="url(#tailA)" stroke-width="5" fill="none" stroke-linecap="round"/>
<path d="M1384,-60 C1238,104 1030,322 760,470" stroke="#fff" stroke-opacity=".35" stroke-width="1.5" fill="none" stroke-dasharray="2 14" stroke-linecap="round"/>
<path d="M1330,-60 C1290,120 1230,290 1150,430" stroke="url(#tailB)" stroke-width="18" fill="none" stroke-linecap="round" filter="url(#soft)" opacity=".7"/>
<path d="M1330,-60 C1290,120 1230,290 1150,430" stroke="url(#tailB)" stroke-width="3.5" fill="none" stroke-linecap="round"/>
<circle cx="760" cy="470" r="46" fill="url(#head)"/><circle cx="760" cy="470" r="4.5" fill="#fff"/>
<circle cx="1150" cy="430" r="38" fill="url(#headB)"/><circle cx="1150" cy="430" r="4" fill="#fff"/>
<g stroke="#fff" stroke-linecap="round" opacity=".9"><path d="M1150,392 V468 M1112,430 H1188" stroke-width="1.6"/><path d="M1128,408 L1172,452 M1172,408 L1128,452" stroke-width=".9" opacity=".7"/></g>
<g fill="#fff"><circle class="twinkle" cx="1290" cy="60" r="2.2"/><circle class="twinkle" cx="1215" cy="150" r="1.8"/><circle class="twinkle" cx="1120" cy="236" r="2.4"/><circle class="twinkle" cx="1040" cy="300" r="1.6"/><circle class="twinkle" cx="960" cy="372" r="2"/><circle class="twinkle" cx="880" cy="398" r="1.5"/><circle class="twinkle" cx="1262" cy="210" r="1.8"/><circle class="twinkle" cx="1218" cy="312" r="1.5"/><circle class="twinkle" cx="1340" cy="150" r="1.4"/><circle class="twinkle" cx="1088" cy="190" r="1.3"/><circle class="twinkle" cx="836" cy="452" r="1.4"/><circle class="twinkle" cx="1180" cy="372" r="1.6"/></g>
<g><g filter="url(#paint)">
<use href="#cloud" transform="translate(-150 250) scale(1.5)"/><use href="#cloud" transform="translate(130 210) scale(.62)"/>
<use href="#cloud" transform="translate(1030 330) scale(1.45)"/><use href="#cloud" transform="translate(1250 300) scale(.6)"/>
<use href="#cloud" transform="translate(-200 520) scale(2.1)"/><use href="#cloud" transform="translate(900 560) scale(1.9)"/>
<use href="#cloud" transform="translate(360 640) scale(1.7)"/><use href="#cloud" transform="translate(620 690) scale(1.3)"/>
</g></g>
<g><rect x="30" y="700" width="46" height="200" fill="url(#tower)"/><rect x="84" y="640" width="60" height="260" fill="url(#tower)"/><rect x="92" y="652" width="6" height="240" fill="#cfe1fb" opacity=".6"/>
<rect x="152" y="730" width="50" height="170" fill="#587fc6"/><rect x="210" y="676" width="38" height="224" fill="url(#tower)"/><path d="M262,900 V610 Q292,590 322,610 V900 Z" fill="url(#tower)"/><rect x="270" y="620" width="5" height="270" fill="#d7e6fc" opacity=".6"/>
<rect x="332" y="760" width="64" height="140" fill="#5d83c8"/><rect x="404" y="720" width="34" height="180" fill="#7ea2dc"/>
<g fill="#dcebff" opacity=".55"><rect x="38" y="716" width="30" height="3"/><rect x="38" y="736" width="30" height="3"/><rect x="38" y="756" width="30" height="3"/><rect x="160" y="746" width="34" height="3"/><rect x="160" y="766" width="34" height="3"/><rect x="340" y="776" width="48" height="3"/><rect x="340" y="796" width="48" height="3"/></g>
<path d="M0,830 Q120,800 240,826 T460,838 L460,900 L0,900 Z" fill="#2f8a44"/><circle cx="60" cy="822" r="30" fill="#2a7d3f"/><circle cx="110" cy="832" r="24" fill="#369a4c"/></g>
<path d="M760,900 C900,820 1080,720 1230,650 C1320,612 1400,600 1440,596 L1440,900 Z" fill="url(#hill)"/>
<path d="M900,900 C1040,840 1200,770 1440,720 L1440,900 Z" fill="#1d6b35" opacity=".55"/>
<g stroke="#b9ef7a" stroke-width="1.6" stroke-linecap="round" opacity=".8"><path d="M1180,690 l4,-16 M1200,682 l6,-18 M1250,660 l3,-15 M1300,640 l6,-17 M1360,622 l4,-16 M1100,736 l5,-16 M1040,768 l4,-15 M1400,612 l5,-15"/></g>
<g stroke="#c0392b" stroke-width="3" fill="none" stroke-linecap="round"><path d="M1352,612 V588 M1376,606 V582 M1346,590 H1382 M1350,597 H1378"/></g>
</svg></div><main>
<header class="head"><div><h1>Study progress</h1>
<p class="sub">Measured from the questions you answer, not from what you have read.</p></div>
<div class="switches"><div class="themes" role="group" aria-label="Theme">
<button type="button" data-pick="nightfall">Nightfall</button><button type="button" data-pick="twilight">Twilight</button><button type="button" data-pick="sky">Blue sky</button>
<button type="button" data-pick="midnight">Midnight</button><button type="button" data-pick="paper">Paper</button><button type="button" data-pick="lilac">Lilac</button></div>
<div class="themes" role="group" aria-label="Layout"><span class="label">Layout</span><button type="button" data-layout-pick="gauge">Gauge</button><button type="button" data-layout-pick="number">Big number</button><button type="button" data-layout-pick="focus">Focus list</button></div></div></header>
{exams}
<section class="strip" aria-label="Study totals">
<div><span class="label">Today</span><b>{today}</b></div>
<div><span class="label">All time</span><b>{total}</b></div>
<div><span class="label">Questions</span><b>{answered} <span>of {questions}</span></b></div>
</section>
<section class="pages"><h2>Study pages</h2>
<p class="small">Time counts only while a page is in front and you are active on it.</p>{decks}</section>
<p class="small how">How the numbers work: each topic starts at your own rating. Every question you answer moves it.
Tap-to-answer questions count fully, self-graded ones count 60%, and a repeat of a question counts half. Readiness
is the topics combined by how much of the exam each one is. It is an estimate, not a promise.</p>
</main>
<script>
// The theme buttons. A click switches the colours at once and remembers the choice in this browser.
(function () {{
  var root = document.documentElement, buttons = document.querySelectorAll('[data-pick]');
  function show(theme) {{
    if (theme === 'nightfall') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', theme);
    buttons.forEach(function (b) {{ b.setAttribute('aria-pressed', String(b.dataset.pick === theme)); }});
  }}
  show(root.getAttribute('data-theme') || 'nightfall');
  // The layout buttons work the same way.
  var layouts = document.querySelectorAll('[data-layout-pick]');
  function lay(name) {{
    root.setAttribute('data-layout', name);
    layouts.forEach(function (b) {{ b.setAttribute('aria-pressed', String(b.dataset.layoutPick === name)); }});
  }}
  lay(root.getAttribute('data-layout') || 'gauge');
  layouts.forEach(function (b) {{
    b.addEventListener('click', function () {{
      lay(b.dataset.layoutPick);
      try {{ localStorage.setItem('exam-study:layout', b.dataset.layoutPick); }} catch (e) {{}}
    }});
  }});
  buttons.forEach(function (b) {{
    b.addEventListener('click', function () {{
      show(b.dataset.pick);
      try {{ localStorage.setItem('exam-study:theme', b.dataset.pick); }} catch (e) {{}}
    }});
  }});
}})();
</script></body></html>"""


def color(value: float) -> str:
    return "var(--good)" if value >= 0.8 else "var(--mid)" if value >= 0.5 else "var(--low)"


def status(value: float, evidence: float = 1.0) -> str:
    """A word to go with the colour, so the meaning never depends on colour alone."""
    if evidence == 0:
        return "Not tested yet"
    return "Strong" if value >= 0.8 else "Getting there" if value >= 0.5 else "Needs work"


def bar(value: float, shade: str | None = None) -> str:
    return f'<div class="bar"><i style="width:{value:.0%};background:{shade or color(value)}"></i></div>'


def exam_map(topics: list[dict]) -> str:
    """The row of chapter tiles. A tile's width is that chapter's share of the exam, so the eye goes to
    the chapters that are worth the most. Each tile shows the percentage, a status word and a thin meter."""
    columns = " ".join(f'minmax(9.5rem, {t["weight"]}fr)' for t in topics)   # never narrower than its text
    tiles = ""
    for t in topics:
        tone = color(t["mastery"]) if t["evidence"] else "var(--none)"
        tiles += (f'<div class="tile"><div class="name">{html.escape(t["name"])}</div>'
                  f'<div class="small">{t["weight"]}% of the exam</div>'
                  f'<div class="val">{t["mastery"] * 100:.0f}<span>%</span></div>'
                  f'<div class="tag" style="color:{tone}">{status(t["mastery"], t["evidence"])}</div>'
                  f'<div class="small">{html.escape(trust(t["evidence"]))}</div>'
                  f'<div class="meter"><i style="width:{t["mastery"]:.0%};background:{tone}"></i></div></div>')
    return (f'<div class="map" style="grid-template-columns:{columns}">{tiles}</div>'
            f'<p class="small maphint">A wider tile is a bigger part of the exam.</p>')


def page_for(exam: dict, topic: dict, pages: list[dict]) -> dict | None:
    """The study page to open for a chapter: the first one that still has unanswered questions."""
    mine = [p for p in pages if p["course"] == exam["course"] and norm(p["topic"]) == norm(topic["name"])]
    return next((p for p in mine if p["answered"] < p["questions"]), mine[0] if mine else None)


def ring(value: float) -> str:
    """The round readiness gauge: a circle whose coloured part is as long as the percentage."""
    around = 2 * 3.14159 * 62
    return (f'<div class="ring" role="img" aria-label="Estimated readiness {value:.0%}"><svg viewBox="0 0 148 148">'
            f'<circle class="back" cx="74" cy="74" r="62"/><circle cx="74" cy="74" r="62" stroke="{color(value)}" '
            f'stroke-dasharray="{around * value:.1f} {around:.1f}"/></svg>'
            f'<div class="in"><b>{value * 100:.0f}%</b><span class="small">ready</span></div></div>')


def exam_heading(exam: dict, today: date) -> str:
    when = date.fromisoformat(exam["date"])
    days = (when - today).days
    left = "today" if days == 0 else f'{days} day{"s" if days != 1 else ""} left'
    return (f'<span class="label">Next exam</span><h2>{html.escape(exam["course"])} {html.escape(exam["name"])}</h2>'
            f'<div class="when"><span class="small">{when.strftime("%a, %b")} {when.day}</span><span class="pill">{left}</span></div>')


def layout_gauge(r: dict, pages: list[dict], today: date) -> str:
    """Layout 1: round gauge, exam and next step beside it, then one row with a bar per chapter."""
    rows = ""
    for t in r["topics"]:
        tone = color(t["mastery"]) if t["evidence"] else "var(--none)"
        rows += (f'<div class="g-row"><div><b>{html.escape(t["name"])}</b><div class="small">{t["weight"]}% of the exam</div>'
                 f'<div class="small"><span class="tag" style="color:{tone}">{status(t["mastery"], t["evidence"])}</span>, '
                 f'{html.escape(trust(t["evidence"]))}</div></div>{bar(t["mastery"], tone)}<div class="pct">{t["mastery"]:.0%}</div></div>')
    return (f'<div class="lay lay-gauge"><div class="g-top">{ring(r["readiness"])}'
            f'<div class="which">{exam_heading(r["exam"], today)}{next_step(r, pages)}</div></div>'
            f'<div class="g-rows">{rows}</div></div>')


def layout_number(r: dict, pages: list[dict], today: date) -> str:
    """Layout 2: one very large readiness number, then chapter tiles as wide as their share of the exam."""
    return (f'<div class="lay lay-number"><div class="lead"><div class="score">'
            f'<div class="big" role="img" aria-label="Estimated readiness {r["readiness"]:.0%}">'
            f'<b>{r["readiness"] * 100:.0f}</b><span>%</span></div>'
            f'<p class="small">Estimated readiness. {r["covered"]:.0%} of the exam is backed by enough answers to trust.</p></div>'
            f'<div class="which">{exam_heading(r["exam"], today)}{next_step(r, pages)}</div></div>{exam_map(r["topics"])}</div>')


def layout_focus(r: dict, pages: list[dict], today: date) -> str:
    """Layout 3: one bar split by chapter, then the chapters in order of exam points still to gain,
    each with its own button. Points to gain = the chapter's share of the exam times how far it is from 100%."""
    columns = " ".join(f'minmax(0, {t["weight"]}fr)' for t in r["topics"])
    parts = "".join(
        f'<div class="part"><i><u style="width:{t["mastery"]:.0%};background:{color(t["mastery"]) if t["evidence"] else "var(--none)"}"></u></i>'
        f'<span>{html.escape(t["name"])}</span></div>' for t in r["topics"])
    items = ""
    for t in sorted(r["topics"], key=lambda t: t["weight"] * (1 - t["mastery"]), reverse=True):
        page = page_for(r["exam"], t, pages)
        tone = color(t["mastery"]) if t["evidence"] else "var(--none)"
        button = f'<a class="btn quiet" href="{html.escape(page["url"])}">Study</a>' if page else "<span></span>"
        items += (f'<li><div><b>{html.escape(t["name"])}</b><div class="small">{t["weight"]}% of the exam, you are at '
                  f'{t["mastery"]:.0%}. <span style="color:{tone};font-weight:600">{status(t["mastery"], t["evidence"])}</span></div></div>'
                  f'<div class="gain"><b>{t["weight"] * (1 - t["mastery"]):.0f}</b><span>points to gain</span></div>{button}</li>')
    return (f'<div class="lay lay-focus"><div class="f-head"><div class="which">{exam_heading(r["exam"], today)}</div>'
            f'<div class="f-score"><b>{r["readiness"] * 100:.0f}</b><span>% ready</span></div></div>'
            f'<div class="seg" style="grid-template-columns:{columns}">{parts}</div>'
            f'<p class="f-title">Where the points are, biggest first</p><ol class="rank">{items}</ol></div>')


def next_step(report: dict, pages: list[dict]) -> str:
    """The "what should I study next?" line: the topic where studying gains the most exam points.

    Gain = how much of the exam the topic is, times how far the topic is from 100%. The button goes to the
    first study page of that topic that still has unanswered questions.
    """
    exam = report["exam"]
    topic = max(report["topics"], key=lambda t: t["weight"] * (1 - t["mastery"]))
    page = page_for(exam, topic, pages)
    why = (f'<div><div><b>Study next: {html.escape(topic["name"])}</b></div>'
           f'<div class="small">{topic["weight"]}% of the exam and you are at {topic["mastery"]:.0%}'
           + (f', so start with {html.escape(page["name"])}' if page else "") + "</div></div>")
    button = f'<a class="btn" href="{html.escape(page["url"])}">Continue</a>' if page else ""
    return f'<div class="next">{why}{button}</div>'


def theme_art() -> str:
    """Extra styling for every theme that has its own picture in study/themes/.

    A file named after a theme (twilight.jpg, sky.png, paper.webp, midnight.jpg, lilac.jpg or nightfall.jpg) is shown twice:
    sharp, as a wide banner behind the page title, and blurred, filling the page behind the cards. A theme
    with no picture keeps its drawn background. The picture stays on this computer; it is never put in git.
    """
    rules = ""
    for picture in sorted(THEME_ART.glob("*")) if THEME_ART.exists() else []:
        if picture.suffix.lstrip(".").lower() not in ART_TYPES:
            continue
        theme = picture.stem.lower()
        on = ":root:not([data-theme])" if theme == "nightfall" else f':root[data-theme="{theme}"]'
        # The file's last-changed time is added to the address, so a replaced picture shows up on reload.
        address = f"/themes/{picture.name}?v={int(picture.stat().st_mtime)}"
        rules += f"""
{on} .sky {{ display:block; position:fixed; inset:-60px; z-index:0; pointer-events:none;
  background:url("{address}") center / cover no-repeat; filter:blur(28px) saturate(1.15) brightness(.82); }}
{on} .sky::before, {on} .sky::after, {on} .sky svg {{ display:none; }}
{on} main {{ padding-top:28px; }}
{on} .head {{ min-height:340px; flex-direction:column; justify-content:flex-end; align-items:flex-start; padding:24px; border-radius:var(--radius); overflow:hidden; box-shadow:var(--shadow);
  background:linear-gradient(180deg, rgba(6,8,30,0) 40%, rgba(6,8,30,.78) 100%), url("{address}") center / cover no-repeat;
  --head:#ffffff; --head-soft:#eef0ff; }}
{on} .strip, {on} .pages, {on} .how {{ background:var(--card); border:1px solid var(--line); border-radius:var(--radius);
  -webkit-backdrop-filter:blur(12px); backdrop-filter:blur(12px); }}
{on} .pages, {on} .how {{ padding:18px; }}
{on} .head h1 {{ font-size:2rem; text-shadow:0 2px 12px rgba(0,0,0,.45); }}
{on} .head .sub {{ text-shadow:0 1px 8px rgba(0,0,0,.5); }}
"""
    return f"<style>{rules}</style>" if rules else ""


def dashboard(today: date | None = None) -> str:
    today = today or date.today()
    pages = decks(load_events())
    reports = all_reports(today)
    cards = ""
    for r in reports:   # each layout is built for each exam; the Layout buttons decide which one is shown
        cards += (f'<section class="card exam">{layout_gauge(r, pages, today)}{layout_number(r, pages, today)}'
                  f'{layout_focus(r, pages, today)}</section>')
    if not cards:
        cards = ('<section class="card exam">No upcoming exam has topic weights yet. Add an '
                 '<code>[exam.weights]</code> table in study.toml.</section>')
    # One drop-down per class. The class with the nearest exam starts open; the others start closed.
    open_course = reports[0]["exam"]["course"] if reports else (pages[0]["course"] if pages else None)
    listing = ""
    for course in dict.fromkeys(d["course"] for d in pages):   # each class once, in the order they appear
        mine = [d for d in pages if d["course"] == course]
        rows = ""
        for d in mine:
            share = d["answered"] / d["questions"] if d["questions"] else 0
            count = (f'<span class="done">All {d["questions"]} answered</span>' if d["questions"] and share == 1
                     else f'{d["answered"]} of {d["questions"]} questions' if d["questions"] else "No questions yet")
            rows += (f'<a class="page" href="{html.escape(d["url"])}"><div><div class="title">{html.escape(d["name"])}</div>'
                     f'<div class="small">{html.escape(d["deck"])}, {d["explained"]} of {d["slides"]} pages explained</div></div>'
                     f'<div class="q">{bar(share, "var(--primary)")}<div class="small">{count}</div></div>'
                     f'<div class="time small">{duration(d["seconds"]) if d["seconds"] >= 60 else "-"}</div></a>')
        seconds = sum(d["seconds"] for d in mine)
        listing += (f'<details class="course"{" open" if course == open_course else ""}><summary>'
                    f'<b>{html.escape(course)}</b>'
                    f'<span class="small">{len(mine)} page{"s" if len(mine) != 1 else ""}, '
                    f'{sum(d["answered"] for d in mine)} of {sum(d["questions"] for d in mine)} questions'
                    f'{", " + duration(seconds) if seconds >= 60 else ""}</span></summary><div class="rows">{rows}</div></details>')
    times = load_time()
    return DASHBOARD.format(art=theme_art(), exams=cards, decks=listing or '<p class="small">No study pages yet.</p>',
                            today=duration(seconds_for(times, day=today.isoformat())), total=duration(seconds_for(times)),
                            answered=sum(d["answered"] for d in pages), questions=sum(d["questions"] for d in pages))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the terminal quiet
        pass

    def send(self, status: int, body: bytes, kind: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = unquote(self.path.split("?")[0])
        if path == "/api/time":  # the timer on a study page asks how long has been spent so far
            query = parse_qs(urlparse(self.path).query)
            times = load_time()
            answer = {"deck": seconds_for(times, query.get("course", [""])[0], query.get("deck", [""])[0]),
                      "today": seconds_for(times, day=date.today().isoformat())}
            return self.send(200, json.dumps(answer).encode(), "application/json")
        if path == "/":
            return self.send(200, dashboard().encode())
        if path.startswith("/explained/"):
            target = (EXPLAINED / path.removeprefix("/explained/")).resolve()
            if target.is_file() and EXPLAINED.resolve() in target.parents:
                kind = {"html": "text/html; charset=utf-8", "png": "image/png"}.get(target.suffix.lstrip("."), "application/octet-stream")
                return self.send(200, target.read_bytes(), kind)
        if path.startswith("/themes/"):   # a theme's own picture, from study/themes/
            target = (THEME_ART / path.removeprefix("/themes/")).resolve()
            kind = ART_TYPES.get(target.suffix.lstrip(".").lower())
            if kind and target.is_file() and THEME_ART.resolve() in target.parents:
                return self.send(200, target.read_bytes(), kind)
        self.send(404, b"Not found")

    def do_POST(self):
        if self.path == "/api/time":  # the timer reports a few more seconds of active study
            try:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                seconds = int(data["seconds"])
                if not 0 < seconds <= 300:
                    raise ValueError("seconds")
                entry = {"ts": datetime.now().isoformat(timespec="seconds"), "course": str(data["course"]),
                         "deck": str(data["deck"]), "topic": str(data["topic"]), "slide": str(data.get("slide", "")),
                         "seconds": seconds}
            except (ValueError, KeyError, TypeError):
                return self.send(400, b"Bad request")
            TIME_LOG.parent.mkdir(parents=True, exist_ok=True)
            with TIME_LOG.open("a") as log:
                log.write(json.dumps(entry) + "\n")
            return self.send(200, b"{}", "application/json")
        if self.path != "/api/answer":
            return self.send(404, b"Not found")
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            event = {"ts": datetime.now().isoformat(timespec="seconds"), "course": str(data["course"]),
                     "deck": str(data["deck"]), "topic": str(data["topic"]), "q": str(data["q"]),
                     "kind": data["kind"] if data["kind"] in KIND_WEIGHT else "self", "outcome": data["outcome"]}
            if event["outcome"] not in OUTCOME:
                raise ValueError("outcome")
        except (ValueError, KeyError, TypeError):
            return self.send(400, b"Bad request")
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as log:
            log.write(json.dumps(event) + "\n")
        self.send(200, b"{}", "application/json")


def serve() -> None:
    url = f"http://127.0.0.1:{PORT}/"
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        # Something is already using the port. Almost always that is the dashboard, started earlier in
        # another terminal tab, so just open it instead of failing.
        print(f"The dashboard is already running at {url} - opening it.\n"
              "(If that page does not load, another program is using port 8765; close it and try again.)")
        webbrowser.open(url)
        return
    print(f"Study dashboard at {url}  (Ctrl+C to stop)")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
