---
name: explain-slides
description: Build a slide-by-slide study page for a lecture deck, with each slide next to a plain-language explanation and an easy-words summary of the whole deck. Use when the user asks to explain or simplify slides, wants "easy wording" for a lecture, or says "/explain-slides PSYC 475 Chapter 5".
---

# Explain a slide deck in easy words

Arguments: a course and a deck (chapter, week or file name). Optionally a slide range.

## Steps
1. Run `uv run canvas-sync explain "<part of the deck's path>"`. It renders every slide to an image under
   `study/explained/<course>/<deck>/` and writes `slides.json` with each slide's text. It only handles PDF
   decks; if there are two versions, use the fuller one ("Complete", "INSTRUCTOR", "Post-lecture").
2. Read `slides.json`. For any slide whose text is empty or thin (charts, diagrams, formulas), open its
   `slide-NNN.png` and look at it before writing about it.
3. Write `notes.json` in the same folder:
   `{"story": "...", "slides": {"1": {"title": "...", "explain": "...", "terms": {"word": "meaning"}}}}`.
   If `notes.json` already exists, add to it; do not rewrite slides that are already explained.
4. Run the same command again to rebuild `index.html`, then open it for the user with `open`.

## What to write
- `story`: three short paragraphs covering what the deck is about, the order it goes in, and the one
  thing to remember. Write it after reading the whole deck, so it tells the whole story, not a list.
- Each slide: a short title in everyday words, then 2 to 5 sentences saying what the slide means and why
  it is there in the story. Add one everyday example when the idea is abstract.
- `terms`: every technical word on the slide with a plain meaning of a few words. Keep the real term,
  since the exam will use it, but always explain it.
- For worked examples and formulas, walk through the steps in words and check any arithmetic with a
  script before stating it.
- For housekeeping slides (reminders, road maps), one sentence is enough; say it is not exam content.

## Easy wording rules
- Short sentences. Common words. Write the way you would explain it to a friend outside the class.
- No jargon unless it is in `terms`. Never define a hard word with another hard word.
- Only explain what is on the slide or elsewhere in the course materials. If a slide is unclear or has
  blanks (note-taking versions), say so; do not fill gaps from general knowledge without saying it.
- If a slide has a mistake or typo that could confuse, point it out.
- Long decks: do them in sections of about 30 slides, rebuilding the page after each, so the user can
  start reading early.
