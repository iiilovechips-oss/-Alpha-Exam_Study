---
name: explain-slides
description: Build a slide-by-slide study page for a lecture deck, with each slide next to a plain-language explanation and an easy-words summary of the whole deck. Use when the user asks to explain or simplify slides, wants "easy wording" for a lecture, or says "/explain-slides PSYC 475 Chapter 5".
---

# Explain a slide deck in easy words

Arguments: a course and a deck (chapter, week or file name). Optionally a slide range.

## Ask where the user is first
Before explaining, quizzing or writing a problem, find out how well the user already knows the topic.
1. Read `study/LEVELS.md`. If the topic has a rating there, use it and do not ask again.
2. If it is missing, ask one short question: roughly what percent of this topic do they feel they
   understand (0% = never seen it, 100% = could teach it)? Offer, as an option, a 5-question check on the
   core ideas if they are not sure. Do not force the check; a self-rating is enough to start.
3. Save the answer as a new row in `study/LEVELS.md` with today's date. Update the row when the user gives
   a new rating or when quiz results clearly show a different level.

Then match the depth to the level:
- **Under 30% (new to it):** assume nothing. Start from what the topic is for, build each idea on the one
  before, define every term, show a tiny example before the real one, and go slowly through every step of
  a calculation or journal entry. Say what must be understood before moving on.
- **30% to 70% (partly there):** a quick reminder of the basics, then spend the time on the parts that
  usually cause mistakes.
- **Over 70% (mostly solid):** keep it brief. Focus on traps, exceptions and exam-style practice.

## Check first: is this deck still going to be tested?
Explaining a deck takes real effort, so do not spend it on material that is finished. Before starting, look
at `study.toml` and today's date:
- If every exam that covers the deck is already in the past, and no later exam is cumulative, do not explain
  it. Tell the user it has already been tested and ask if they still want it.
- If the user asks for "all the slides" of a course, only do decks covered by an upcoming exam, and list the
  ones you skipped and why.
- Do one deck at a time and confirm before starting the next.

## Steps
1. Run `uv run canvas-sync explain "<part of the deck's path>"`. It renders every slide to an image under
   `study/explained/<course>/<deck>/` and writes `slides.json` with each slide's text. It only handles PDF
   decks; if there are two versions, use the fuller one ("Complete", "INSTRUCTOR", "Post-lecture").
2. Read `slides.json`. For any slide whose text is empty or thin (charts, diagrams, formulas), open its
   `slide-NNN.png` and look at it before writing about it.
3. Write `notes.json` in the same folder:
   `{"story": "...", "slides": {"1": {"title": "...", "explain": "...", "terms": {"word": "meaning"}}}, "check": [...]}`.
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

## End-of-deck check questions
Every finished deck gets a `check` list in `notes.json`:
`"check": [{"q": "...", "a": "...", "slide": 12}]`. The page shows them at the bottom with the answers hidden
until clicked. They test whether the user understood the deck, so:
- Write 6 to 8 questions that together cover the whole deck, in the order the deck teaches.
- Mix "say it in your own words" questions with small calculations or journal entries. Use new numbers
  and new scenarios, not the ones on the slides.
- Every question must be answerable from this deck alone. Give the slide to reread in `slide`.
- Answers are short and in the same easy wording, with the steps shown for anything calculated.
- Check every number with a script before writing it.
- Match the difficulty to the user's level in `study/LEVELS.md`.

## Easy wording rules
- Short sentences. Common words. Write the way you would explain it to a friend outside the class.
- No jargon unless it is in `terms`. Never define a hard word with another hard word.
- Only explain what is on the slide or elsewhere in the course materials. If a slide is unclear or has
  blanks (note-taking versions), say so; do not fill gaps from general knowledge without saying it.
- If a slide has a mistake or typo that could confuse, point it out.
- Long decks: do them in sections of about 30 slides, rebuilding the page after each, so the user can
  start reading early.
