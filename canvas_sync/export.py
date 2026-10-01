"""Build notebooklm/<COURSE>/: a small, study-only copy of materials/ to upload to NotebookLM."""

import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MATERIALS = ROOT / "materials"
EXPORT = ROOT / "notebooklm"
UPLOADED = ROOT / ".uploaded.json"  # what the user has confirmed is in NotebookLM
SOURCE_LIMIT = 50  # NotebookLM free tier: sources per notebook

# Edit these lists to change what gets exported. All match the file name, ignoring case.
ALLOWED_EXT = {".pdf", ".pptx", ".docx", ".xlsx", ".txt"}
# Always left out: graded work, admin paperwork, per-student lab files.
NEVER = re.compile(
    r"netid|playbook|template|response sheet|rubric|instructions|mini-?project|secnumber|"
    r"group assignment|extra credit|sona|research participation|student success|"
    r"^reading[ _]\d+\.\d+", re.I)  # BADM 210 weekly readings: the full textbook is included instead
# Study material: kept even if it also looks like case work.
KEEP = re.compile(
    r"lecture|practice|review|study guide|midterm|exam|chapter|reading|notes|tips|formulas|"
    r"guide|syll|_data", re.I)
# Case/homework files: left out unless they matched KEEP.
SKIP = re.compile(r"\bcase[ -]?\d|sweeten|supporting materials", re.I)
# When the same deck exists in two versions, keep only the fuller one.
PREFERRED = re.compile(r"instructor|complete|post-lecture", re.I)
VARIANT_WORDS = re.compile(r"instructor|upload|complete version|complete|note-?taking version|(pre|post)-lecture", re.I)


def variant_key(path: Path) -> str:
    name = VARIANT_WORDS.sub("", path.stem)
    name = re.sub(r"-\d+\s*$", "", name.strip())
    # Same name in different week folders is a different file, so the folder is part of the key.
    return path.parent.name + "/" + re.sub(r"[^a-z0-9]", "", name.lower())


def choose(course_dir: Path) -> tuple[list[Path], list[tuple[Path, str]]]:
    kept, dropped, groups = [], [], {}
    for f in sorted(p for p in course_dir.rglob("*") if p.is_file()):
        name = f.name
        if f.suffix.lower() not in ALLOWED_EXT:
            dropped.append((f, "Canvas page text" if f.suffix == ".md" else "file type NotebookLM can't use"))
        elif NEVER.search(name):
            dropped.append((f, "graded work or admin"))
        elif SKIP.search(name) and not KEEP.search(name):
            dropped.append((f, "case or homework file"))
        else:
            groups.setdefault(variant_key(f), []).append(f)
    for files in groups.values():
        best = [f for f in files if PREFERRED.search(f.name)] or files
        kept.append(best[-1])
        dropped += [(f, f"duplicate of {best[-1].name}") for f in files if f != best[-1]]
    return sorted(kept), dropped


def digest(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def export() -> None:
    """Rebuild notebooklm/<COURSE>/ (everything) and notebooklm/_new/<COURSE>/ (not uploaded yet)."""
    uploaded = json.loads(UPLOADED.read_text()) if UPLOADED.exists() else {}
    if EXPORT.exists():
        shutil.rmtree(EXPORT)  # derived copy; rebuilt from materials/ every run
    report = ["# NotebookLM export", ""]
    for course_dir in sorted(p for p in MATERIALS.iterdir() if p.is_dir()):
        course = course_dir.name
        kept, dropped = choose(course_dir)
        out = EXPORT / course
        out.mkdir(parents=True, exist_ok=True)
        before, current, add, replace = uploaded.get(course, {}), {}, [], []
        for f in kept:
            name = f.name if f.name not in current else f"{f.parent.name} - {f.name}"
            shutil.copy2(f, out / name)
            current[name] = digest(f)
            if name not in before:
                add.append(name)
            elif before[name] != current[name]:
                replace.append(name)
        remove = sorted(set(before) - set(current))
        for name in add + replace:
            (EXPORT / "_new" / course).mkdir(parents=True, exist_ok=True)
            shutil.copy2(out / name, EXPORT / "_new" / course / name)

        over = f"  ** over the {SOURCE_LIMIT}-source limit **" if len(kept) > SOURCE_LIMIT else ""
        print(f"{course}: {len(kept)} files; to upload: {len(add)} new, {len(replace)} changed, "
              f"{len(remove)} to remove{over}")
        report += [f"## {course}", f"{len(kept)} files in the notebook folder{over}", ""]
        report += [f"- [ ] ADD: {n}" for n in add]
        report += [f"- [ ] REPLACE (delete the old source, add this one): {n}" for n in replace]
        report += [f"- [ ] REMOVE from the notebook: {n}" for n in remove]
        report += ["", "Left out of the export:"]
        report += [f"- {f.relative_to(course_dir)} ({why})" for f, why in dropped if f.suffix != ".md"]
        report += [f"- {sum(f.suffix == '.md' for f, _ in dropped)} Canvas page text files", ""]
    (EXPORT / "EXPORT_REPORT.md").write_text("\n".join(report) + "\n")
    print("\nDrag the files in notebooklm/_new/<COURSE>/ into that course's notebook, then run "
          "`canvas-sync uploaded`.\nChecklist: notebooklm/EXPORT_REPORT.md")


def mark_uploaded() -> None:
    """Record the current export as being in NotebookLM, so later exports only list what changed."""
    state = {}
    for course_dir in sorted(p for p in EXPORT.iterdir() if p.is_dir() and p.name != "_new"):
        state[course_dir.name] = {f.name: digest(f) for f in sorted(course_dir.iterdir()) if f.is_file()}
    UPLOADED.write_text(json.dumps(state, indent=1))
    if (EXPORT / "_new").exists():
        shutil.rmtree(EXPORT / "_new")
    print(f"Marked {sum(len(v) for v in state.values())} files as uploaded.")
