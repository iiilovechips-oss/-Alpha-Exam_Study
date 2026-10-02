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

from canvas_sync.explain import EXPLAINED
from canvas_sync.export import ROOT

LOG = ROOT / "study" / "progress.jsonl"   # one line per answer
TIME_LOG = ROOT / "study" / "time.jsonl"   # one line per few seconds of active study time
LEVELS = ROOT / "study" / "LEVELS.md"     # self-ratings, used only as a starting guess
CONFIG = ROOT / "study.toml"
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
        found.append({"course": course, "deck": deck,
                      "topic": Path(json.loads(slides_file.read_text())["deck"]).parts[1],
                      "slides": len(json.loads(slides_file.read_text())["slides"]),
                      "explained": len(notes.get("slides", {})),
                      "questions": len(notes.get("check", [])) + sum(1 for s in notes.get("slides", {}).values() if s.get("question")),
                      "answered": len(answered), "seconds": seconds_for(times, course, deck), "url": f"/explained/{course}/{deck}/index.html"})
    return found


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


DASHBOARD = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Study progress</title>
<style>
:root {{ --bg:#f6f5f1; --card:#fff; --ink:#1d1d1f; --soft:#5b5b63; --line:#dedcd5; --accent:#2f5d8a; --track:#e6e4dc; --good:#2e8b57; --mid:#c98a1b; --low:#c0392b; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#17181b; --card:#22242a; --ink:#ececee; --soft:#a5a7b0; --line:#34363d; --accent:#8fb8e0; --track:#30333a; }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:17px/1.55 -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width:900px; margin:0 auto; padding:24px 16px 80px; }}
h1 {{ font-size:1.5rem; margin:0 0 4px; }} h2 {{ font-size:1.15rem; margin:0; }}
.sub {{ color:var(--soft); margin:0 0 20px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px 20px; margin-bottom:20px; }}
.big {{ font-size:2.4rem; font-weight:700; line-height:1.1; margin:8px 0 2px; }}
.bar {{ height:12px; background:var(--track); border-radius:6px; overflow:hidden; margin:6px 0; }}
.bar i {{ display:block; height:100%; border-radius:6px; }}
.row {{ margin-top:14px; }} .row .top {{ display:flex; justify-content:space-between; gap:12px; }}
.small {{ color:var(--soft); font-size:.88rem; }}
table {{ width:100%; border-collapse:collapse; }} td, th {{ text-align:left; padding:8px 6px; border-top:1px solid var(--line); font-size:.95rem; }}
th {{ border-top:none; color:var(--soft); font-weight:600; }} a {{ color:var(--accent); }}
</style></head><body><main>
<h1>Study progress</h1>
<p class="sub">Measured from the questions you answer, not from what you have read. Reload after answering more.</p>
<div class="card"><h2>Study time</h2><div class="big">{today}</div><div class="small">today · {total} in total ·
counted only while a study page is in front and you are active on it</div></div>
{exams}
<div class="card"><h2>Study pages</h2><table><tr><th>Deck</th><th>Topic</th><th>Explained</th><th>Questions answered</th><th>Time spent</th></tr>{decks}</table></div>
<p class="small">How the numbers work: each topic starts at your own rating. Every question you answer moves it:
tap-to-answer questions count fully, self-graded ones count 60%, and a repeat of a question counts half. Readiness
is the topics combined by how much of the exam each one is. It is an estimate, not a promise.</p>
</main></body></html>"""


def color(value: float) -> str:
    return "var(--good)" if value >= 0.8 else "var(--mid)" if value >= 0.5 else "var(--low)"


def bar(value: float) -> str:
    return f'<div class="bar"><i style="width:{value:.0%};background:{color(value)}"></i></div>'


def dashboard(today: date | None = None) -> str:
    today = today or date.today()
    cards = ""
    for r in all_reports(today):
        exam = r["exam"]
        days = (date.fromisoformat(exam["date"]) - today).days
        rows = "".join(
            f'<div class="row"><div class="top"><span>{html.escape(t["name"])} '
            f'<span class="small">· {t["weight"]}% of the exam</span></span><b>{t["mastery"]:.0%}</b></div>'
            f'{bar(t["mastery"])}<div class="small">{html.escape(trust(t["evidence"]))}</div></div>' for t in r["topics"])
        cards += (f'<div class="card"><h2>{html.escape(exam["course"])} {html.escape(exam["name"])}</h2>'
                  f'<div class="small">{exam["date"]} · {days} day{"s" if days != 1 else ""} left</div>'
                  f'<div class="big">{r["readiness"]:.0%}</div><div class="small">estimated readiness · '
                  f'{r["covered"]:.0%} of the exam is backed by enough answers to trust</div>{bar(r["readiness"])}{rows}</div>')
    if not cards:
        cards = '<div class="card">No upcoming exam has topic weights yet. Add an <code>[exam.weights]</code> table in study.toml.</div>'
    rows = "".join(
        f'<tr><td><a href="{html.escape(d["url"])}">{html.escape(d["deck"])}</a><div class="small">{html.escape(d["course"])}</div></td>'
        f'<td>{html.escape(d["topic"])}</td><td>{d["explained"]} / {d["slides"]}</td><td>{d["answered"]} / {d["questions"]}</td>'
        f'<td>{duration(d["seconds"]) if d["seconds"] else "-"}'
        + (f'<div class="small">{d["seconds"] / 60 / d["slides"]:.1f} min per page</div>' if d["seconds"] else "") + "</td></tr>"
        for d in decks(load_events()))
    times = load_time()
    return DASHBOARD.format(exams=cards, decks=rows or "<tr><td colspan=5>No study pages yet.</td></tr>",
                            today=duration(seconds_for(times, day=today.isoformat())), total=duration(seconds_for(times)))


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
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}/"
    print(f"Study dashboard at {url}  (Ctrl+C to stop)")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
