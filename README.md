# canvas-sync

Pulls my course materials out of Canvas into an organized local folder, then builds a small,
study-only copy of each course to load into NotebookLM or Claude.

I built it because every professor organizes Canvas differently (files in modules, files buried in
pages, slides on SharePoint) and I wanted one folder per class that stays current without
re-downloading things by hand each week.

## How it works

```
Canvas ──► sync ──► materials/<COURSE>/<week or chapter>/   (everything, original formats)
                        │
                        ▼
                    export ──► notebooklm/<COURSE>/          (slides, practice, study guides)
                               notebooklm/_new/<COURSE>/     (only what isn't uploaded yet)
```

- **sync** walks each course's modules, pages, assignments, home page and syllabus through the
  Canvas REST API. It downloads uploaded files, saves page text as Markdown, follows file links
  inside pages, and fetches documents the professor shares through SharePoint links.
- **export** filters that down to study material: lecture slides, practice problems and solutions,
  exam reviews, study guides and readings. Case assignments, graded work, lab files and duplicate
  versions of the same deck are left out, which keeps each course under NotebookLM's 50-source limit.
  Excel workbooks, which NotebookLM does not accept, are converted to Markdown (cell values as tables
  plus the formulas behind them), and PDFs or slide decks over 8 MB are split into parts.
- Every run writes a checklist (`reports/` and `notebooklm/EXPORT_REPORT.md`) of what is new, what
  changed, what was skipped and what needs a manual look. The last step, adding files to a notebook,
  is deliberately left to a person.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Google Chrome.

```bash
uv sync
cp .env.example .env      # set CANVAS_API_URL, and optionally CANVAS_COURSE_IDS
uv run canvas-sync login  # sign in to Canvas in the Chrome window that opens
uv run canvas-sync courses
```

## Weekly use

```bash
uv run canvas-sync update    # sync + export
# drag notebooklm/_new/<COURSE>/ into that course's notebook
uv run canvas-sync uploaded  # so next week only lists what changed
```

| Command | What it does |
|---|---|
| `login` | Open Chrome to sign in and save the session |
| `courses` | List active courses and their IDs |
| `sync` | Download new and updated material into `materials/` |
| `export` | Rebuild `notebooklm/` from `materials/` |
| `update` | `sync` then `export` |
| `uploaded` | Record the current export as uploaded |

## Study features

`study.toml` (copy `study.example.toml`) lists exams, what each one covers, and deadlines.

| Command | What it does |
|---|---|
| `pack "<exam>"` | Build `study/<exam>/` with only the slides, practice and guides that exam covers |
| `calendar` | Write `study/calendar.ics` with exam dates |
| `explain "<deck>"` | Build a study page for one PDF deck: every slide next to a plain-language explanation |
| `digest` | New material from the last update and what is due in the next two weeks (also printed by `update`) |

Three Claude Code skills in `.claude/skills/` work from the downloaded files: `explain-slides` writes the
easy-wording explanations shown on the study page, `quiz` runs an interactive
practice quiz in the course's exam format, and `big-question` writes a new long multi-part problem
modeled on the course's own practice exams, checks the solution with a script, and grades an attempt.

## Design notes

- **Authentication.** Canvas normally uses a personal access token (`CANVAS_API_TOKEN`). My school
  does not let students create one, so without a token the tool uses a browser session you sign in
  to yourself, saved in `.session.json`. It only reads what your account can already see. When the
  session expires it opens Chrome and waits; if nobody signs in, it writes an "action needed" line to
  the report instead of failing. Check your own institution's policy before automating your session.
- **Safe to rerun.** A SQLite file (`state.db`) records each file's Canvas timestamp or content
  hash, so a second run only fetches what changed.
- **Readable rules.** The export filter is a few word lists at the top of `canvas_sync/export.py`.
- **Private by default.** `.env`, `.session.json`, `materials/`, `notebooklm/` and `reports/` are
  git-ignored; course content never enters the repository.

## Limits

- Announcements, quizzes and discussion posts are not collected.
- Videos are listed in the report, not downloaded.
- SharePoint files are named from the text around their link, which can be awkward.
- Links to Box, Google Drive and YouTube are listed for manual download.

## Tests

```bash
uv run pytest
```
