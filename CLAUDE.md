# Exam Study

Read `PLAN.md` first: it holds the full plan, the user's decisions, the current state and the next steps.
Keep it up to date when features are added or priorities change.

**Standing rule:** whenever the user suggests a new feature or a change to how something should work, add it to
`PLAN.md` in the same turn (under decisions, features built, open items or parked ideas, whichever fits), even
if it is not built yet.

Pulls class files from Canvas into `materials/<COURSE>/<module>/`. Weekly command: `uv run exam-study update` (sync + export);
each run writes a checklist to `reports/`. Videos are skipped (listed in the report, not downloaded). `state.db` tracks what has been downloaded.

UIUC blocks self-service Canvas tokens, so auth is a browser login saved in `.session.json`
(`uv run exam-study login`). When it expires, a sync opens Chrome to log in again; if nobody does,
it writes an ACTION NEEDED reminder to the report instead of failing.

`uv run exam-study export` rebuilds `notebooklm/<COURSE>/`: a filtered copy (slides, practice, study guides,
readings; no cases, graded work or page text; Excel converted to Markdown, files over 8 MB split into parts) for uploading to NotebookLM. Filter rules are at the top of
`exam_study/export.py`. `notebooklm/_new/` holds only files not yet uploaded; `exam-study uploaded` marks them done.
Tests: `uv run pytest`.

## Study features
`study.toml` lists exams (with the material each one covers) and deadlines.
- `uv run exam-study pack "<exam>"` builds `study/<exam>/` with just that exam's material.
- `uv run exam-study calendar` writes `study/calendar.ics` (exams only); `digest` shows new material and what is due soon.
- `uv run exam-study explain "<deck>"` renders a PDF deck into `study/explained/<course>/<deck>/` and builds
  `index.html`: each slide beside a plain-language explanation from `notes.json` (written by the `explain-slides` skill).
- `uv run exam-study study` serves the dashboard and study pages on port 8765 and records each tapped answer in
  `study/progress.jsonl`; `uv run exam-study progress` prints readiness. The formula is at the top of `exam_study/progress.py`.
- Skills: `quiz` (interactive practice quiz) and `big-question` (new long multi-part problem with a
  verified solution). Generated problems go in `study/generated/`.

## Answering questions about class material
- `study/LEVELS.md` holds the user's self-rated understanding per topic. Read it before teaching or quizzing,
  ask for a rating if the topic is missing, and match the depth to the level (see the skills).
- Homework on McGraw-Hill Connect (ACCY 301), PrairieLearn (BADM 210) and Canvas quizzes (ACCY 302) is not in
  `materials/`. When the user asks for a study guide or exam prep for those courses, mention once that they can
  save those pages into `materials/<course>/Homework/` (or paste them) to have them included, then continue.
- Read `materials/COURSE_GUIDE.md` first: it has each course's grading weights and key dates. The user uses this project for studying only (explanations, practice questions, exam review).
- Read the original files under `materials/` (pptx, xlsx, pdf, docx) before answering; do not answer from memory.
- Cite the course, file, and slide/page/sheet each claim comes from.
- If the materials do not cover something, say so rather than filling in from general knowledge.
- Never print or commit the contents of `.env` or `.session.json`.
