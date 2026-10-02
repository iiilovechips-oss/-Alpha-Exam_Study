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
4. Run the same command again to rebuild `index.html`. Tell the user to open it through the dashboard
   (`uv run canvas-sync study`, then http://127.0.0.1:8765), because answers are only recorded when the page is
   served that way. Opening the file directly still works for reading.

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

## Mark which slides matter most
Decks are long, so tell the user where to spend their time. Each slide in `notes.json` can carry
`"focus": "high"` or `"focus": "skim"`, plus a one-sentence `"focus_why"`. Unmarked slides are normal.
- **high:** the slide teaches something the exam evidence shows is tested (practice exam, review class, study
  guide), or it is a full worked problem of an exam type. Say which in `focus_why`.
- **skim:** title slides, goals, reminders, news stories, repeats of an earlier chart.
- Keep high focus to roughly a third of the deck or less. If everything is marked, nothing is.
The page shows a badge on each marked slide, a list of the high-focus slides at the top, and a button to hide the rest.

## End-of-deck check questions
Every finished deck gets a `check` list in `notes.json`. The page shows it at the bottom with answers hidden
until clicked. The aim is exam preparation: the user should meet questions like these on the real exam.

`"check": [{"q": "...", "options": ["...", "..."], "correct": "B", "a": "...", "seen": "...", "slide": 12}]`

- A multiple-choice item needs `options` and `correct` (the letter). On the page the user taps an option and
  it grades itself. This is the preferred kind: it takes one tap and the result is objective.
- An item without `options` is a worked problem: the user reveals the answer and taps Got it / Partly /
  Missed it. Use these for journal entries and multi-step calculations, where the exam does too.
- Aim for at least half tap-to-answer items, and never require typing. The user will not write out answers,
  and the progress tracker (`canvas_sync/progress.py`) only learns from taps.
- `seen` and `slide` are optional.

**Find out what gets tested before writing.** Read the course's practice exam, exam review deck, study guide,
in-class exercises and any homework or quiz pages for the same chapter. Note which ideas they test, in what
format (multiple choice, journal entry, multi-part problem), and how the question is usually worded. Build
the check questions around those ideas and formats, and weight them the same way. Put the evidence in
`seen`, for example "The practice exam tests this in question 13".

**Make them transferable, not slide-specific.**
- Test the idea, not the slide. A question should make sense to someone who learned the topic from a
  different lecture, and the skill it practices should work on any company or scenario.
- Use new companies, new numbers and new situations. Never ask "what did slide 9 say" or reuse a slide's example.
- Ask in the exam's own format and at the exam's difficulty.
- Include the common trap the real exam uses (extra information that is not needed, a date that does not
  count, a net figure that looks like a gross one).
- 6 to 8 questions covering the deck's main ideas. Answers are short, in easy wording, with steps shown.
- Check every number with a script. Match the difficulty to the user's level in `study/LEVELS.md`.

## Easy wording rules
- Short sentences. Common words. Write the way you would explain it to a friend outside the class.
- No jargon unless it is in `terms`. Never define a hard word with another hard word.
- Only explain what is on the slide or elsewhere in the course materials. If a slide is unclear or has
  blanks (note-taking versions), say so; do not fill gaps from general knowledge without saying it.
- If a slide has a mistake or typo that could confuse, point it out.
- Long decks: do them in sections of about 30 slides, rebuilding the page after each, so the user can
  start reading early.
