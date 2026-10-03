"""Slide-by-slide study view: each slide image next to a plain-language explanation.

`prepare` renders a PDF deck to images and extracts each slide's text. The explanations themselves
are written to notes.json (by the `explain-slides` skill), and `build` turns both into one HTML page.
"""

import html
import json
from pathlib import Path

from exam_study.export import MATERIALS, ROOT

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
.timer {{ position:fixed; right:16px; bottom:16px; z-index:10; background:var(--card); color:var(--ink);
          border:1px solid var(--line); border-radius:999px; padding:8px 14px; font-size:.9rem;
          box-shadow:0 2px 10px rgba(0,0,0,.18); font-variant-numeric:tabular-nums; }}
.timer.paused {{ opacity:.55; }}
.slide .ask {{ grid-column:1 / -1; border-top:none; padding:0; }}
.slide .ask .text {{ font-weight:400; }}
.slide .ask .askimg {{ display:block; max-width:760px; width:100%; margin:8px 0 12px; }}
.slide.hidden-answer > img, .slide.hidden-answer > .note {{ display:none; }}
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
</main>
<div class="timer" id="timer">0:00 on this deck</div>{script}</body></html>
"""


SCRIPT = """<script>
(function () {
  var body = document.body.dataset;
  var KEY = 'exam-study:' + body.course + '/' + body.deck;
  // The project used to be called canvas-sync. Carry over anything this browser saved under the old name.
  ['', ':seconds'].forEach(function (tail) {
    var before = KEY.replace('exam-study:', 'canvas-sync:') + tail;
    try { if (!localStorage.getItem(KEY + tail) && localStorage.getItem(before)) localStorage.setItem(KEY + tail, localStorage.getItem(before)); } catch (e) {}
  });
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
    function unhide() { var sec = box.closest('.slide'); if (sec) sec.classList.remove('hidden-answer'); }
    if (show) show.addEventListener('click', function () { box.classList.add('open'); show.disabled = true; unhide(); });
    box.querySelectorAll('.grade button').forEach(function (b) {
      b.addEventListener('click', function () {
        box.querySelectorAll('.grade button').forEach(function (x) { x.classList.remove('picked'); });
        b.classList.add('picked');
        record(q, 'self', b.dataset.outcome);
      });
    });
    if (was) {
      if (was.kind === 'mc') showChoice(box, was.choice);
      else { box.classList.add('open'); if (show) show.disabled = true; unhide();
             var g = box.querySelector('.grade button[data-outcome="' + was.outcome + '"]'); if (g) g.classList.add('picked'); }
    }
  });
  tally();
  // --- Study timer ---------------------------------------------------------------------------------
  // Counts one second at a time, but only while this tab is in front and you have moved, scrolled, clicked
  // or typed in the last two minutes. So leaving the page open while you are away does not add time.
  var TKEY = KEY + ':seconds', IDLE_AFTER = 120, SEND_EVERY = 15;
  var total = Number(localStorage.getItem(TKEY) || 0), today = 0, unsent = 0, lastActive = Date.now();
  var pill = document.getElementById('timer');
  ['scroll', 'mousemove', 'keydown', 'click', 'touchstart'].forEach(function (name) {
    window.addEventListener(name, function () { lastActive = Date.now(); }, {passive: true});
  });
  function clock(sec) {
    var h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s2 = sec % 60;
    return (h ? h + ':' + (m < 10 ? '0' : '') : '') + m + ':' + (s2 < 10 ? '0' : '') + s2;
  }
  function currentSlide() {   // the slide sitting at the middle of the screen
    var mid = window.innerHeight / 2, found = '';
    document.querySelectorAll('.slide').forEach(function (el) {
      var r = el.getBoundingClientRect();
      if (r.top <= mid && r.bottom >= mid) found = el.id.replace('slide-', '');
    });
    return found;
  }
  function payload() {
    return JSON.stringify({course: body.course, deck: body.deck, topic: body.topic, seconds: unsent, slide: currentSlide()});
  }
  function send() {
    if (!served || !unsent) return;
    fetch('/api/time', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: payload(), keepalive: true});
    unsent = 0;
  }
  function draw(active) {
    if (!pill) return;
    pill.textContent = clock(total) + ' on this deck' + (today ? ' \u00b7 ' + clock(today) + ' today in total' : '') + (active ? '' : ' (paused)');
    pill.classList.toggle('paused', !active);
  }
  if (served) fetch('/api/time?course=' + encodeURIComponent(body.course) + '&deck=' + encodeURIComponent(body.deck))
    .then(function (r) { return r.json(); })
    .then(function (d) { total = Math.max(total, d.deck); today = d.today; draw(true); }).catch(function () {});
  setInterval(function () {
    var active = document.visibilityState === 'visible' && (Date.now() - lastActive) / 1000 < IDLE_AFTER;
    if (active) {
      total += 1; unsent += 1; if (today || served) today += 1;
      try { localStorage.setItem(TKEY, String(total)); } catch (e) {}
      if (unsent >= SEND_EVERY) send();
    }
    draw(active);
  }, 1000);
  window.addEventListener('pagehide', send);
  document.addEventListener('visibilitychange', function () { if (document.visibilityState !== 'visible') send(); });
  draw(true);

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
    """The study page folder for a deck: study/explained/<course>/<deck name>.

    Two decks in different chapters can have the same file name (both chapters had a "Lecture Sept 16").
    If the plain name is already taken by another deck, the chapter is added: "<deck name> (Chapter 7)".
    """
    rel = deck.relative_to(MATERIALS)
    plain = EXPLAINED / rel.parts[0] / deck.stem
    taken = plain / "slides.json"
    if taken.exists() and json.loads(taken.read_text())["deck"] != str(rel):
        chapter = rel.parts[1].split("-")[0].strip() if len(rel.parts) > 2 else rel.parts[1]
        return EXPLAINED / rel.parts[0] / f"{deck.stem} ({chapter})"
    return plain


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


def slide_frames(page):
    """The top and bottom slide boxes on a handout page (two slides per page)."""
    import pymupdf as fitz

    boxes = sorted((d["rect"] for d in page.get_drawings()
                    if 300 < d["rect"].width < page.rect.width * 0.9 and d["rect"].height > 200), key=lambda r: r.y0)
    if len(boxes) >= 2 and boxes[-1].y0 > boxes[0].y1:
        return boxes[0], boxes[-1]
    w, h = page.rect.width, page.rect.height  # usual handout layout, used when the boxes cannot be found
    return fitz.Rect(0.108 * w, 0.119 * h, 0.892 * w, 0.46 * h), fitz.Rect(0.108 * w, 0.54 * h, 0.892 * w, 0.881 * h)


def render_question(out: Path, name: str, spec: dict, deck: str) -> None:
    """Save one slide as a picture, exactly as the professor drew it, to use as the question.

    `spec` says where the question slide is: which file (default: this deck), which page, and whether it is
    the top or bottom slide on that page. `cover_from` (0 to 1) paints the slide white from that height down,
    for slides that print the answer underneath the question. `covers` paints any other boxes white.
    """
    import pymupdf as fitz

    with fitz.open(MATERIALS / spec.get("file", deck)) as doc:
        page = doc[spec["page"] - 1]
        top, bottom = slide_frames(page)
        frame = top if spec.get("part", "top") == "top" else bottom
        # Areas to paint white, as fractions of the slide: (left, top, right, bottom).
        # "cover_from" is the simple case: everything from that height down.
        areas = [tuple(a) for a in spec.get("covers", [])]
        if spec.get("cover_from"):
            areas.append((0, spec["cover_from"], 1, 1))
        for left, top_, right, bottom_ in areas:
            hide = fitz.Rect(frame.x0 + frame.width * left, frame.y0 + frame.height * top_,
                             frame.x0 + frame.width * right, frame.y0 + frame.height * bottom_) & (frame + (2, 2, -2, -2))
            page.draw_rect(hide, color=(1, 1, 1), fill=(1, 1, 1))
        zoom = IMAGE_WIDTH / frame.width
        page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=frame + (-3, -3, 3, 3)).save(out / name)


def paragraphs(text: str) -> str:
    return "".join(f"<p>{html.escape(part.strip())}</p>" for part in text.split("\n\n") if part.strip())


def build(out: Path) -> Path:
    """Write index.html from the slide images and whatever is in notes.json so far."""
    deck_info = json.loads((out / "slides.json").read_text())
    slides, deck_path = deck_info["slides"], deck_info["deck"]
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
        # A slide that is an exercise or concept check has a "question" in notes.json. The post-lecture slides
        # print the answer right on the picture, so the picture and explanation are hidden until the user has
        # tried the question and pressed Reveal. After that they tap how it went, which feeds the progress tracker.
        ask, hidden = "", ""
        if note and note.get("question"):
            hidden = " hidden-answer"
            pictures = ""
            for i, spec in enumerate(note.get("ask", []), 1):
                name = f'ask-{slide["n"]:03}-{i}.png'
                render_question(out, name, spec, deck_path)
                pictures += f'<img class="askimg" src="{name}" alt="Question for slide {slide["n"]}">'
            ask = (f'<div class="q ask" data-q="slide-{slide["n"]}"><div class="num">Slide {slide["n"]} · Try it first{badge}</div>'
                   f'<div class="text">{paragraphs(note["question"])}</div>{pictures}'
                   '<button class="show">Reveal the slide and the answer</button>'
                   '<div class="grade">How did you do? <button data-outcome="right">Got it</button>'
                   '<button data-outcome="partly">Partly</button><button data-outcome="wrong">Missed it</button></div></div>')
        blocks.append(f'<section class="slide {focus}{hidden}" id="slide-{slide["n"]}">{ask}<img loading="lazy" src="slide-{slide["n"]:03}.png" '
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
