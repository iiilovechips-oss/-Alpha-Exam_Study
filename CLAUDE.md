# canvas-sync

Pulls class files from Canvas into `materials/<COURSE>/<module>/`. Weekly command: `uv run canvas-sync update` (sync + export);
each run writes a checklist to `reports/`. Videos are skipped (listed in the report, not downloaded). `state.db` tracks what has been downloaded.

UIUC blocks self-service Canvas tokens, so auth is a browser login saved in `.session.json`
(`uv run canvas-sync login`). When it expires, a sync opens Chrome to log in again; if nobody does,
it writes an ACTION NEEDED reminder to the report instead of failing.

`uv run canvas-sync export` rebuilds `notebooklm/<COURSE>/`: a filtered copy (slides, practice, study guides,
readings; no cases, graded work or page text; Excel converted to Markdown, files over 8 MB split into parts) for uploading to NotebookLM. Filter rules are at the top of
`canvas_sync/export.py`. `notebooklm/_new/` holds only files not yet uploaded; `canvas-sync uploaded` marks them done.
Tests: `uv run pytest`.

## Study features
`study.toml` lists exams (with the material each one covers) and deadlines.
- `uv run canvas-sync pack "<exam>"` builds `study/<exam>/` with just that exam's material.
- `uv run canvas-sync calendar` writes `study/calendar.ics` (exams only); `digest` shows new material and what is due soon.
- `uv run canvas-sync explain "<deck>"` renders a PDF deck into `study/explained/<course>/<deck>/` and builds
  `index.html`: each slide beside a plain-language explanation from `notes.json` (written by the `explain-slides` skill).
- Skills: `quiz` (interactive practice quiz) and `big-question` (new long multi-part problem with a
  verified solution). Generated problems go in `study/generated/`.

## Answering questions about class material
- Homework on McGraw-Hill Connect (ACCY 301), PrairieLearn (BADM 210) and Canvas quizzes (ACCY 302) is not in
  `materials/`. When the user asks for a study guide or exam prep for those courses, mention once that they can
  save those pages into `materials/<course>/Homework/` (or paste them) to have them included, then continue.
- Read `materials/COURSE_GUIDE.md` first: it has each course's grading weights and key dates. The user uses this project for studying only (explanations, practice questions, exam review).
- Read the original files under `materials/` (pptx, xlsx, pdf, docx) before answering; do not answer from memory.
- Cite the course, file, and slide/page/sheet each claim comes from.
- If the materials do not cover something, say so rather than filling in from general knowledge.
- Never print or commit the contents of `.env` or `.session.json`.
