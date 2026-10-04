"""Slide-by-slide study view: each slide image next to a plain-language explanation.

`prepare` renders a PDF deck to images and extracts each slide's text. The explanations themselves
are written to notes.json (by the `explain-slides` skill), and `build` turns both into one HTML page.
"""

import html
import json
from pathlib import Path

from exam_study.export import MATERIALS, ROOT
from exam_study.themes import NAMES, THEMES, TOKENS

EXPLAINED = ROOT / "study" / "explained"
IMAGE_WIDTH = 1100
LETTERS = "ABCDEFGH"

# The look of a study page. The colours come from themes.py (shared with the dashboard's themes), so this
# template only says where things go: a bar that stays on top, the summary, the "short on time" box, then
# each slide with its picture on the left and the plain-words explanation on the right, then the questions.
PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{heading}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@500;600&display=swap">
<style>{theme_css}
* {{ box-sizing:border-box; }}
body {{ margin:0; min-height:100dvh; background:var(--page, var(--bg)) fixed; color:var(--ink); font:17px/1.65 var(--font, var(--sans)); -webkit-font-smoothing:antialiased; }}
a:focus-visible, button:focus-visible, select:focus-visible {{ outline:2px solid var(--primary); outline-offset:3px; border-radius:8px; }}
.mono {{ font-family:var(--mono); font-variant-numeric:tabular-nums; }}

/* The bar that stays at the top: back to the dashboard, which deck this is, and the theme. The thin
   coloured line under it grows as you scroll, so you can see how far through the deck you are. */
.bar {{ position:sticky; top:0; z-index:20; display:flex; align-items:center; gap:14px; padding:10px 20px;
       background:color-mix(in srgb, var(--bg) 80%, transparent); -webkit-backdrop-filter:blur(14px); backdrop-filter:blur(14px); border-bottom:1px solid var(--line); }}
.bar .where {{ flex:1; min-width:0; color:var(--head-soft, var(--soft)); font-size:.9rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.home {{ display:inline-flex; align-items:center; min-height:38px; padding:0 14px; border-radius:999px; border:1px solid var(--line); background:var(--card); color:var(--ink); text-decoration:none; font-size:.9rem; font-weight:550; white-space:nowrap; }}
.home:hover {{ background:var(--muted); }}
.bar label {{ color:var(--head-soft, var(--soft)); font-size:.84rem; display:flex; align-items:center; gap:8px; }}
.bar select {{ min-height:38px; padding:0 10px; border-radius:999px; border:1px solid var(--line); background:var(--card); color:var(--ink); font:inherit; font-size:.88rem; cursor:pointer; }}
.bar::after {{ content:""; position:absolute; left:0; right:0; bottom:-2px; height:2px; background:var(--primary); transform-origin:left; transform:scaleX(0); }}
@supports (animation-timeline: scroll()) {{
  .bar::after {{ animation:read linear both; animation-timeline:scroll(root); }}
  @keyframes read {{ to {{ transform:scaleX(1); }} }}
}}

main {{ max-width:1240px; margin:0 auto; padding:40px 20px 140px; }}
.intro {{ margin-bottom:28px; }}
.intro .label {{ color:var(--head-soft, var(--soft)); font-size:.74rem; font-weight:600; letter-spacing:.09em; text-transform:uppercase; }}
h1 {{ font-size:clamp(1.7rem, 3.2vw, 2.5rem); font-weight:650; letter-spacing:-.03em; line-height:1.1; margin:6px 0 8px; color:var(--head, var(--ink)); max-width:22em; }}
.sub {{ color:var(--head-soft, var(--soft)); margin:0; font-size:.95rem; }}

.panel, .story, .focus, .slide, .check {{ background:var(--card); border:1px solid var(--line); border-radius:var(--radius); box-shadow:var(--shadow); -webkit-backdrop-filter:blur(12px); backdrop-filter:blur(12px); }}
.story {{ padding:26px 28px; margin-bottom:16px; }}
.story h2, .focus h2, .check h2 {{ margin:0 0 10px; font-size:1.05rem; font-weight:600; letter-spacing:-.01em; }}
.story p {{ margin:0 0 12px; max-width:74ch; color:var(--ink); }}
.story p:first-of-type {{ font-size:1.08rem; }}
.story p:last-child {{ margin-bottom:0; }}

/* "Short on time" box: the high-focus slides as chips you can jump to, and a switch to hide the rest. */
.focus {{ padding:20px 28px; margin-bottom:28px; border-left:3px solid var(--mid); }}
.focus div {{ display:flex; flex-wrap:wrap; gap:8px; }}
.focus a {{ display:inline-flex; align-items:center; min-height:34px; padding:0 12px; border-radius:999px; background:var(--muted); border:1px solid var(--line); color:var(--ink); text-decoration:none; font-size:.86rem; font-family:var(--mono); }}
.focus a:hover {{ border-color:var(--mid); }}
.focus button {{ margin-top:14px; }}
body.only-high .slide:not(.high) {{ display:none; }}

/* One slide: the picture on the left, the plain-words explanation on the right. */
.slide {{ display:grid; grid-template-columns:minmax(0, 3fr) minmax(0, 2fr); gap:28px; align-items:start; padding:22px; margin-bottom:16px; scroll-margin-top:72px; }}
.pic {{ margin:0; }}
.pic img, .askimg {{ display:block; width:100%; height:auto; border:1px solid var(--line); border-radius:10px; background:#fff; }}
.num {{ font:500 .76rem/1.4 var(--mono); letter-spacing:.08em; text-transform:uppercase; color:var(--soft); display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
.note h3 {{ margin:8px 0 10px; font-size:1.28rem; font-weight:600; letter-spacing:-.018em; line-height:1.25; }}
.note p {{ margin:0 0 12px; max-width:62ch; white-space:pre-line; }}
.terms {{ margin-top:18px; padding-top:14px; border-top:1px solid var(--line); font-size:.92rem; }}
.terms div {{ padding:3px 0; color:var(--soft); }}
.terms b {{ color:var(--ink); font-weight:600; }}
.empty {{ color:var(--soft); font-style:italic; }}
.badge {{ font:600 .7rem/1 var(--sans); letter-spacing:.05em; text-transform:uppercase; padding:5px 9px; border-radius:999px; }}
.badge.high {{ background:color-mix(in srgb, var(--mid) 18%, transparent); color:var(--mid); }}
.badge.skim {{ background:var(--muted); color:var(--soft); }}
.why {{ font-size:.9rem; color:var(--soft); margin:8px 0 0; padding-left:12px; border-left:2px solid var(--mid); max-width:62ch; }}
.slide.high {{ border-left:3px solid var(--mid); }}
.slide.skim {{ opacity:.6; transition:opacity .15s ease-out; }} .slide.skim:hover, .slide.skim:focus-within {{ opacity:1; }}

/* A slide that is an exercise: the question first, the slide and its answer only after "Reveal". */
.slide .ask {{ grid-column:1 / -1; border-top:none; padding:0; }}
.slide .ask .text {{ font-weight:400; }}
.slide .ask .text p {{ margin:8px 0 12px; }}
.slide .ask .askimg {{ max-width:780px; margin:0 0 14px; }}
.slide.hidden-answer > .pic, .slide.hidden-answer > .note {{ display:none; }}

/* Buttons. One shape everywhere: rounded pills. */
button {{ font:inherit; }}
.q button, .focus button {{ min-height:44px; padding:0 16px; border-radius:999px; border:1px solid var(--line); background:var(--muted); color:var(--ink); cursor:pointer; transition:background .15s ease-out, border-color .15s ease-out, transform .15s ease-out; }}
.q button:hover:not(:disabled), .focus button:hover {{ border-color:var(--primary); }}
.q button:active:not(:disabled) {{ transform:translateY(1px) scale(.99); }}
.q .show {{ background:var(--primary); color:var(--on-primary); border-color:var(--primary); font-weight:600; }}
.q .show:disabled {{ opacity:.45; cursor:default; }}
.q .grade {{ display:none; margin-top:14px; color:var(--soft); font-size:.92rem; }}
.q.open .grade {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
.q button.picked {{ background:var(--primary); color:var(--on-primary); border-color:var(--primary); font-weight:600; }}

/* End-of-deck questions. An answer option is a full-width row; a word marks right and wrong, not colour alone. */
.check {{ padding:26px 28px; margin-top:28px; }}
.check > p {{ margin:0 0 6px; color:var(--soft); max-width:70ch; font-size:.95rem; }}
.score {{ font-family:var(--mono); font-size:.86rem; }}
.check .q {{ border-top:1px solid var(--line); padding:22px 0 20px; margin-top:16px; }}
.check .q .text {{ font-weight:600; margin:0 0 14px; max-width:72ch; }}
.q .opt {{ display:flex; align-items:center; justify-content:space-between; gap:12px; width:100%; min-height:48px; height:auto; padding:10px 16px; margin:0 0 8px; border-radius:12px; text-align:left; }}
.q .opt.right {{ border-color:var(--good); background:color-mix(in srgb, var(--good) 15%, transparent); }}
.q .opt.wrong {{ border-color:var(--low); background:color-mix(in srgb, var(--low) 13%, transparent); }}
.q .opt.right::after {{ content:"Correct"; color:var(--good); font-size:.8rem; font-weight:600; white-space:nowrap; }}
.q .opt.wrong::after {{ content:"Your answer"; color:var(--low); font-size:.8rem; font-weight:600; white-space:nowrap; }}
.q .opt:disabled {{ cursor:default; color:var(--ink); opacity:1; }}
.q ol {{ margin:0 0 12px; padding-left:1.4em; }}
.q .answer {{ display:none; margin:14px 0 0; padding:16px 18px; background:var(--muted); border:1px solid var(--line); border-radius:12px; max-width:78ch; }}
.q .answer p {{ margin:0 0 10px; white-space:pre-line; }} .q .answer p:last-of-type {{ margin-bottom:0; }}
.q.open .answer {{ display:block; }}
.q .from {{ color:var(--soft); font-size:.86rem; margin-top:10px; }}

.timer {{ position:fixed; right:16px; bottom:16px; z-index:10; background:var(--card); color:var(--ink); border:1px solid var(--line); border-radius:999px; padding:9px 15px; font:500 .84rem var(--mono); font-variant-numeric:tabular-nums; box-shadow:0 8px 24px rgba(0,0,0,.28); }}
.timer.paused {{ opacity:.55; }}

@media (max-width:860px) {{
  main {{ padding:24px 14px 120px; }}
  .slide {{ grid-template-columns:1fr; gap:16px; padding:16px; }}
  .story, .check, .focus {{ padding:20px 18px; }}
  .bar {{ padding:8px 12px; }} .bar label span {{ display:none; }}
}}
@media (prefers-reduced-motion: reduce) {{ * {{ transition:none !important; animation:none !important; }} html {{ scroll-behavior:auto; }} }}
</style>
<script>
// Use the theme picked on the dashboard (remembered in this browser) before anything is drawn.
try {{ var saved = localStorage.getItem('exam-study:theme'); if (saved && saved !== 'nightfall' && saved !== 'purple') document.documentElement.setAttribute('data-theme', saved); }} catch (e) {{}}
</script></head><body data-course="{course}" data-deck="{title}" data-topic="{topic}">
<header class="bar"><a class="home" href="/">&larr; Progress</a><span class="where">{course}, {heading}</span>
<label><span>Theme</span><select id="theme">{theme_options}</select></label></header>
<main>
<div class="intro"><span class="label">{course}</span><h1>{heading}</h1>
<p class="sub">{source}{done} of {total} slides explained in plain words</p></div>
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

  // The theme menu in the top bar: same themes and same remembered choice as the dashboard.
  var menu = document.getElementById('theme');
  if (menu) {
    menu.value = document.documentElement.getAttribute('data-theme') || 'nightfall';
    menu.addEventListener('change', function () {
      if (menu.value === 'nightfall') document.documentElement.removeAttribute('data-theme');
      else document.documentElement.setAttribute('data-theme', menu.value);
      try { localStorage.setItem('exam-study:theme', menu.value); } catch (e) {}
    });
  }

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
            ask = (f'<div class="q ask" data-q="slide-{slide["n"]}"><div class="num">Slide {slide["n"]:02}, try it first{badge}</div>'
                   f'<div class="text">{paragraphs(note["question"])}</div>{pictures}'
                   '<button class="show">Reveal the slide and the answer</button>'
                   '<div class="grade">How did you do? <button data-outcome="right">Got it</button>'
                   '<button data-outcome="partly">Partly</button><button data-outcome="wrong">Missed it</button></div></div>')
        blocks.append(f'<section class="slide {focus}{hidden}" id="slide-{slide["n"]}">{ask}'
                      f'<figure class="pic"><img loading="lazy" src="slide-{slide["n"]:03}.png" alt="Slide {slide["n"]}"></figure>'
                      f'<div class="note"><div class="num">Slide {slide["n"]:02}{badge}</div>{why}{body}</div></section>')
    # The box at the top: which slides matter most, with links to jump to them and a switch to hide the rest.
    links = "".join(f'<a href="#slide-{n}">Slide {n:02}</a>' for n in high)
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
    # The heading is the display name from notes.json ("Chapter 6, Part 3 - Long-term contracts"). The folder
    # name stays as the deck's identity, because recorded answers and study time are filed under it.
    heading = notes.get("name") or out.name
    source = f"{html.escape(out.name)}, " if heading != out.name else ""
    options = "".join(f'<option value="{key}">{NAMES[key]}</option>' for key in THEMES)
    page = PAGE.format(title=html.escape(out.name), heading=html.escape(heading), source=source,
                       theme_css=TOKENS, theme_options=options,
                       course=html.escape(out.parent.name), done=len(by_slide),
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
