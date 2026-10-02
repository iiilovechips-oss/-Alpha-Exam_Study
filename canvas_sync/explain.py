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
.check {{ background:var(--card); border:1px solid var(--line); border-left:5px solid var(--accent);
          border-radius:10px; padding:16px 20px; margin-top:28px; }}
.check h2 {{ margin:0 0 4px; font-size:1.15rem; color:var(--accent); }}
.check details {{ border-top:1px solid var(--line); padding:10px 0; }}
.check summary {{ cursor:pointer; font-weight:600; }}
.check .answer {{ margin:8px 0 0 18px; }}
.check .options {{ margin:8px 0 0 4px; }}
.check details[open] summary {{ margin-bottom:4px; }}
.check .from {{ color:var(--soft); font-size:.85rem; }}
@media (max-width:820px) {{ .slide {{ grid-template-columns:1fr; }} }}
</style></head><body><main>
<h1>{title}</h1>
<p class="sub">{course} · {done} of {total} slides explained in plain words</p>
{story}
{slides}
{check}
</main></body></html>
"""


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
    blocks = []
    for slide in slides:
        note = by_slide.get(str(slide["n"]))
        if note:
            terms = "".join(f"<div><b>{html.escape(word)}</b>: {html.escape(meaning)}</div>"
                            for word, meaning in note.get("terms", {}).items())
            body = (f"<h3>{html.escape(note.get('title', ''))}</h3>{paragraphs(note['explain'])}"
                    + (f'<div class="terms">{terms}</div>' if terms else ""))
        else:
            body = '<p class="empty">No explanation yet.</p>'
        blocks.append(f'<section class="slide"><img loading="lazy" src="slide-{slide["n"]:03}.png" '
                      f'alt="Slide {slide["n"]}"><div class="note"><div class="num">Slide {slide["n"]}</div>{body}</div></section>')
    story = (f'<div class="story"><h2>The whole story in plain words</h2>{paragraphs(notes["story"])}</div>'
             if notes.get("story") else "")
    questions = ""
    for i, item in enumerate(notes.get("check", []), 1):
        options = "".join(f"<li>{html.escape(o)}</li>" for o in item.get("options", []))
        questions += (
            f'<details><summary>{i}. {html.escape(item["q"])}</summary>'
            + (f'<ol type="A" class="options">{options}</ol>' if options else "")
            + f'<div class="answer">{paragraphs(item["a"])}'
            + (f'<div class="from">Why it is likely on the exam: {html.escape(item["seen"])}</div>' if item.get("seen") else "")
            + (f'<div class="from">To review: slide {item["slide"]}</div>' if item.get("slide") else "")
            + "</div></details>")
    check = (f'<div class="check"><h2>Check yourself</h2><p>Exam-style questions on the ideas in this deck, built from what the practice exam and '
             f'review material test. Work each one out before opening it.</p>{questions}</div>' if questions else "")
    page = PAGE.format(title=html.escape(out.name), course=html.escape(out.parent.name), done=len(by_slide),
                       total=len(slides), story=story, slides="\n".join(blocks), check=check)
    (out / "index.html").write_text(page)
    return out / "index.html"


def explain(query: str) -> None:
    out = prepare(find_deck(query))
    page = build(out)
    notes = json.loads((out / "notes.json").read_text()) if (out / "notes.json").exists() else {}
    total = len(json.loads((out / "slides.json").read_text())["slides"])
    print(f"{out.relative_to(ROOT)}: {len(notes.get('slides', {}))} of {total} slides explained")
    print(f"Open {page.relative_to(ROOT)}")
