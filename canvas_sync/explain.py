"""Slide-by-slide study view: each slide image next to a plain-language explanation.

`prepare` renders a PDF deck to images and extracts each slide's text. The explanations themselves
are written to notes.json (by the `explain-slides` skill), and `build` turns both into one HTML page.
"""

import html
import json
from pathlib import Path

from canvas_sync.export import MATERIALS, ROOT

EXPLAINED = ROOT / "study" / "explained"
IMAGE_WIDTH = 1100
LETTERS = "ABCDEFGH"

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ --bg:#f6f5f1; --card:#fff; --ink:#1d1d1f; --soft:#5b5b63; --line:#dedcd5; --accent:#2f5d8a; --term:#eef3f8; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#17181b; --card:#22242a; --ink:#ececee; --soft:#a5a7b0; --line:#34363d; --accent:#8fb8e0; --term:#2a3038; }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:17px/1.6 -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width:1280px; margin:0 auto; padding:24px 16px 80px; }}
h1 {{ font-size:1.5rem; margin:0 0 4px; }}
.sub {{ color:var(--soft); margin:0 0 20px; }}
.story {{ background:var(--card); border:1px solid var(--line); border-left:5px solid var(--accent);
          border-radius:10px; padding:16px 20px; margin-bottom:28px; }}
.story h2 {{ margin:0 0 6px; font-size:1.05rem; color:var(--accent); }}
.story p {{ margin:0 0 8px; }}
.slide {{ display:grid; grid-template-columns:minmax(0,3fr) minmax(0,2fr); gap:20px; align-items:start;
          background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px; margin-bottom:20px; }}
.slide img {{ width:100%; height:auto; border:1px solid var(--line); border-radius:6px; background:#fff; }}
.num {{ font-size:.8rem; letter-spacing:.06em; text-transform:uppercase; color:var(--soft); }}
.note h3 {{ margin:2px 0 8px; font-size:1.1rem; }}
.note p {{ margin:0 0 10px; }}
.terms {{ margin:10px 0 0; padding:10px 14px; background:var(--term); border-radius:8px; font-size:.95rem; }}
.terms div {{ margin:3px 0; }}
.terms b {{ color:var(--accent); }}
.empty {{ color:var(--soft); font-style:italic; }}
.slide.high {{ border-left:6px solid #d08a00; }}
.slide.skim {{ opacity:.6; }}
.badge {{ display:inline-block; font-size:.75rem; font-weight:700; letter-spacing:.04em; text-transform:uppercase;
          padding:2px 8px; border-radius:20px; margin-left:8px; }}
.badge.high {{ background:#d08a00; color:#fff; }}
.badge.skim {{ background:var(--line); color:var(--soft); }}
.why {{ font-size:.9rem; color:var(--soft); margin:0 0 8px; }}
.focus {{ background:var(--card); border:1px solid var(--line); border-left:6px solid #d08a00; border-radius:10px;
          padding:14px 20px; margin-bottom:24px; }}
.focus h2 {{ margin:0 0 6px; font-size:1.05rem; }}
.focus a {{ color:var(--accent); margin-right:10px; white-space:nowrap; }}
.focus button {{ font:inherit; margin-top:10px; padding:6px 12px; border-radius:8px; border:1px solid var(--line);
                 background:var(--bg); color:var(--ink); cursor:pointer; }}
body.only-high .slide:not(.high) {{ display:none; }}
.check {{ background:var(--card); border:1px solid var(--line); border-left:5px solid var(--accent);
          border-radius:10px; padding:16px 20px; margin-top:28px; }}
.check h2 {{ margin:0 0 4px; font-size:1.15rem; color:var(--accent); }}
.q {{ border-top:1px solid var(--line); padding:14px 0; }}
.q .text {{ font-weight:600; margin:0 0 8px; }}
.q button {{ font:inherit; color:var(--ink); background:var(--bg); border:1px solid var(--line); border-radius:8px;
            padding:8px 12px; margin:4px 6px 4px 0; cursor:pointer; text-align:left; }}
.q .opt {{ display:block; width:100%; }}
.q button:hover:not(:disabled) {{ border-color:var(--accent); }}
.q button.right {{ border-color:#2e8b57; background:rgba(46,139,87,.16); }}
.q button.wrong {{ border-color:#c0392b; background:rgba(192,57,43,.14); }}
.q button.picked {{ border-color:var(--accent); background:var(--term); }}
.q .answer {{ display:none; margin:10px 0 0; padding:10px 14px; background:var(--term); border-radius:8px; }}
.q.open .answer {{ display:block; }}
.q .grade {{ display:none; margin-top:8px; }}
.q.open .grade {{ display:block; }}
.q .from {{ color:var(--soft); font-size:.85rem; margin-top:6px; }}
.score {{ color:var(--soft); margin:6px 0 0; }}
.home {{ display:inline-block; margin-bottom:12px; color:var(--accent); text-decoration:none; }}
@media (max-width:820px) {{ .slide {{ grid-template-columns:1fr; }} }}
</style></head><body data-course="{course}" data-deck="{title}" data-topic="{topic}"><main>
<a class="home" href="/">&larr; Progress dashboard</a>
<h1>{title}</h1>
<p class="sub">{course} · {done} of {total} slides explained in plain words</p>
{story}
{focus}
{slides}
{check}
</main>{script}</body></html>
"""


SCRIPT = """<script>
(function () {
  var body = document.body.dataset;
  var KEY = 'canvas-sync:' + body.course + '/' + body.deck;
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}
  var served = location.protocol.indexOf('http') === 0;
  if (!served) { var home = document.querySelector('.home'); if (home) home.style.display = 'none'; }

  function record(q, kind, outcome, choice) {
    saved[q] = {kind: kind, outcome: outcome, choice: choice};
    try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {}
    if (served) fetch('/api/answer', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({course: body.course, deck: body.deck, topic: body.topic, q: q, kind: kind, outcome: outcome})});
    tally();
  }
  function tally() {
    var all = document.querySelectorAll('.q').length, done = Object.keys(saved).length, pts = 0;
    Object.keys(saved).forEach(function (k) { pts += {right: 1, partly: 0.5, wrong: 0}[saved[k].outcome]; });
    var el = document.querySelector('.score');
    if (el) el.textContent = done ? 'Answered ' + done + ' of ' + all + ' \u00b7 score ' + pts + ' / ' + done : '';
  }
  function showChoice(box, choice) {
    var correct = Number(box.dataset.correct);
    box.querySelectorAll('.opt').forEach(function (b, i) {
      b.disabled = true;
      if (i === correct) b.classList.add('right');
      else if (i === choice) b.classList.add('wrong');
    });
    box.classList.add('open');
  }
  document.querySelectorAll('.q').forEach(function (box) {
    var q = box.dataset.q, was = saved[q];
    box.querySelectorAll('.opt').forEach(function (b, i) {
      b.addEventListener('click', function () {
        showChoice(box, i);
        record(q, 'mc', i === Number(box.dataset.correct) ? 'right' : 'wrong', i);
      });
    });
    var show = box.querySelector('.show');
    if (show) show.addEventListener('click', function () { box.classList.add('open'); show.disabled = true; });
    box.querySelectorAll('.grade button').forEach(function (b) {
      b.addEventListener('click', function () {
        box.querySelectorAll('.grade button').forEach(function (x) { x.classList.remove('picked'); });
        b.classList.add('picked');
        record(q, 'self', b.dataset.outcome);
      });
    });
    if (was) {
      if (was.kind === 'mc') showChoice(box, was.choice);
      else { box.classList.add('open'); if (show) show.disabled = true;
             var g = box.querySelector('.grade button[data-outcome="' + was.outcome + '"]'); if (g) g.classList.add('picked'); }
    }
  });
  tally();
  var toggle = document.getElementById('only-high');
  if (toggle) toggle.addEventListener('click', function () {
    var on = document.body.classList.toggle('only-high');
    toggle.textContent = on ? 'Show all slides' : 'Show only high-focus slides';
  });
})();
</script>"""


def find_deck(query: str) -> Path:
    decks = sorted(p for p in MATERIALS.rglob("*.pdf") if query.lower() in str(p.relative_to(MATERIALS)).lower())
    if len(decks) != 1:
        listing = "\n".join(f"  {p.relative_to(MATERIALS)}" for p in decks[:30]) or "  (none)"
        raise SystemExit(f"Need exactly one matching PDF deck for {query!r}; found {len(decks)}:\n{listing}")
    return decks[0]


def deck_dir(deck: Path) -> Path:
    return EXPLAINED / deck.relative_to(MATERIALS).parts[0] / deck.stem


def prepare(deck: Path) -> Path:
    """Render every slide to an image and save its text, ready for explanations to be written."""
    import pymupdf as fitz

    out = deck_dir(deck)
    out.mkdir(parents=True, exist_ok=True)
    slides = []
    with fitz.open(deck) as doc:
        for index, page in enumerate(doc, 1):
            image = out / f"slide-{index:03}.png"
            if not image.exists():
                page.get_pixmap(matrix=fitz.Matrix(*[IMAGE_WIDTH / page.rect.width] * 2)).save(image)
            slides.append({"n": index, "text": " ".join(page.get_text().split())})
    (out / "slides.json").write_text(json.dumps({"deck": str(deck.relative_to(MATERIALS)), "slides": slides}, indent=1))
    return out


def paragraphs(text: str) -> str:
    return "".join(f"<p>{html.escape(part.strip())}</p>" for part in text.split("\n\n") if part.strip())


def build(out: Path) -> Path:
    """Write index.html from the slide images and whatever is in notes.json so far."""
    slides = json.loads((out / "slides.json").read_text())["slides"]
    notes_file = out / "notes.json"
    notes = json.loads(notes_file.read_text()) if notes_file.exists() else {}
    by_slide = notes.get("slides", {})
    blocks, high = [], []
    for slide in slides:
        note = by_slide.get(str(slide["n"]))
        if note:
            terms = "".join(f"<div><b>{html.escape(word)}</b>: {html.escape(meaning)}</div>"
                            for word, meaning in note.get("terms", {}).items())
            body = (f"<h3>{html.escape(note.get('title', ''))}</h3>{paragraphs(note['explain'])}"
                    + (f'<div class="terms">{terms}</div>' if terms else ""))
        else:
            body = '<p class="empty">No explanation yet.</p>'
        # "focus" in notes.json is "high" (study this closely) or "skim" (safe to glance at). Anything else is normal.
        focus = (note or {}).get("focus", "")
        badge = {"high": '<span class="badge high">High focus</span>', "skim": '<span class="badge skim">Skim</span>'}.get(focus, "")
        why = f'<p class="why">{html.escape(note["focus_why"])}</p>' if note and note.get("focus_why") else ""
        if focus == "high":
            high.append(slide["n"])
        blocks.append(f'<section class="slide {focus}" id="slide-{slide["n"]}"><img loading="lazy" src="slide-{slide["n"]:03}.png" '
                      f'alt="Slide {slide["n"]}"><div class="note"><div class="num">Slide {slide["n"]}{badge}</div>{why}{body}</div></section>')
    # The box at the top: which slides matter most, with links to jump to them and a switch to hide the rest.
    links = "".join(f'<a href="#slide-{n}">Slide {n}</a>' for n in high)
    focus_box = (f'<div class="focus"><h2>If you are short on time: {len(high)} of {len(slides)} slides matter most</h2>'
                 f'<div>{links}</div><button id="only-high">Show only high-focus slides</button></div>' if high else "")
    story = (f'<div class="story"><h2>The whole story in plain words</h2>{paragraphs(notes["story"])}</div>'
             if notes.get("story") else "")
    questions = ""
    for i, item in enumerate(notes.get("check", []), 1):
        why = (f'<div class="from">Why it is likely on the exam: {html.escape(item["seen"])}</div>' if item.get("seen") else "")
        review = f'<div class="from">To review: slide {item["slide"]}</div>' if item.get("slide") else ""
        answer = f'<div class="answer">{paragraphs(item["a"])}{why}{review}</div>'
        options = item.get("options", [])
        if options and item.get("correct") in LETTERS[:len(options)]:
            # One tap answers it and it grades itself.
            buttons = "".join(f'<button class="opt">{LETTERS[n]}. {html.escape(o)}</button>' for n, o in enumerate(options))
            body = f'{buttons}{answer}'
            attrs = f' data-correct="{LETTERS.index(item["correct"])}"'
        else:
            # Worked problem: think it through, reveal, then one tap to say how it went.
            listed = "".join(f"<li>{html.escape(o)}</li>" for o in options)
            body = ((f'<ol type="A">{listed}</ol>' if listed else "")
                    + '<button class="show">Show answer</button>' + answer
                    + '<div class="grade">How did you do? <button data-outcome="right">Got it</button>'
                      '<button data-outcome="partly">Partly</button><button data-outcome="wrong">Missed it</button></div>')
            attrs = ""
        questions += f'<div class="q" data-q="{i}"{attrs}><p class="text">{i}. {html.escape(item["q"])}</p>{body}</div>'
    check = (f'<div class="check"><h2>Check yourself</h2><p>Exam-style questions on the ideas in this deck, built from '
             f'what the practice exam and review material test. Tap an answer, or work the problem and then say how it '
             f'went. Your results feed the progress dashboard.</p><p class="score"></p>{questions}</div>' if questions else "")
    topic = Path(json.loads((out / "slides.json").read_text())["deck"]).parts[1]
    page = PAGE.format(title=html.escape(out.name), course=html.escape(out.parent.name), done=len(by_slide),
                       total=len(slides), story=story, focus=focus_box, slides="\n".join(blocks), check=check,
                       topic=html.escape(topic), script=SCRIPT)
    (out / "index.html").write_text(page)
    return out / "index.html"


def explain(query: str) -> None:
    out = prepare(find_deck(query))
    page = build(out)
    notes = json.loads((out / "notes.json").read_text()) if (out / "notes.json").exists() else {}
    total = len(json.loads((out / "slides.json").read_text())["slides"])
    print(f"{out.relative_to(ROOT)}: {len(notes.get('slides', {}))} of {total} slides explained")
    print(f"Open {page.relative_to(ROOT)}")
