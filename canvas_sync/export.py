"""Build notebooklm/<COURSE>/: a small, study-only copy of materials/ to upload to NotebookLM."""

import hashlib
import json
import re
import shutil
from pathlib import Path

from canvas_sync.convert import render

ROOT = Path(__file__).resolve().parent.parent
MATERIALS = ROOT / "materials"
EXPORT = ROOT / "notebooklm"
UPLOADED = ROOT / ".uploaded.json"  # what the user has confirmed is in NotebookLM
CACHE = ROOT / ".export_cache"  # converted and split files, reused until the source changes
MANIFEST = EXPORT / ".manifest.json"  # the current export: {course: {file name: source digest}}
SOURCE_LIMIT = 50  # NotebookLM free tier: sources per notebook

# Edit these lists to change what gets exported. All match the file name, ignoring case.
ALLOWED_EXT = {".pdf", ".pptx", ".docx", ".xlsx", ".txt"}
# Always left out: graded work, admin paperwork, per-student lab files.
NEVER = re.compile(
    r"netid|playbook|template|response sheet|rubric|instructions|secnumber|"
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
    if not MATERIALS.is_dir():
        raise SystemExit("No materials/ folder yet. Run `canvas-sync sync` first to download your course files.")
    uploaded = json.loads(UPLOADED.read_text()) if UPLOADED.exists() else {}
    if EXPORT.exists():
        shutil.rmtree(EXPORT)  # derived copy; rebuilt from materials/ every run
    report, manifest = ["# NotebookLM export", ""], {}
    for course_dir in sorted(p for p in MATERIALS.iterdir() if p.is_dir()):
        course = course_dir.name
        kept, dropped = choose(course_dir)
        out = EXPORT / course
        out.mkdir(parents=True, exist_ok=True)
        before, current, add, replace = uploaded.get(course, {}), {}, [], []
        for f in kept:
            name = f.name if f.name not in current else f"{f.parent.name} - {f.name}"
            name = " ".join(name.split())  # no odd whitespace (non-breaking spaces) in upload names
            source = digest(f)
            # Excel becomes Markdown and oversized files become several parts, so one source
            # file can produce more than one upload.
            for made in render(f, out, name, CACHE / f"{source}-{Path(name).stem[:40]}"):
                current[made] = source
                if made not in before:
                    add.append(made)
                elif before[made] != source:
                    replace.append(made)
        remove = sorted(set(before) - set(current))
        for name in add + replace:
            (EXPORT / "_new" / course).mkdir(parents=True, exist_ok=True)
            shutil.copy2(out / name, EXPORT / "_new" / course / name)

        manifest[course] = current
        over = f"  ** over the {SOURCE_LIMIT}-source limit **" if len(current) > SOURCE_LIMIT else ""
        print(f"{course}: {len(current)} files; to upload: {len(add)} new, {len(replace)} changed, "
              f"{len(remove)} to remove{over}")
        report += [f"## {course}", f"{len(current)} files in the notebook folder{over}", ""]
        report += [f"- [ ] ADD: {n}" for n in add]
        report += [f"- [ ] REPLACE (delete the old source, add this one): {n}" for n in replace]
        report += [f"- [ ] REMOVE from the notebook: {n}" for n in remove]
        report += ["", "Left out of the export:"]
        report += [f"- {f.relative_to(course_dir)} ({why})" for f, why in dropped if f.suffix != ".md"]
        report += [f"- {sum(f.suffix == '.md' for f, _ in dropped)} Canvas page text files", ""]
    (EXPORT / "EXPORT_REPORT.md").write_text("\n".join(report) + "\n")
    MANIFEST.write_text(json.dumps(manifest, indent=1))
    if (EXPORT / "_new").exists():
        print("\nDrag the files in notebooklm/_new/<COURSE>/ into that course's notebook, then run "
              "`canvas-sync uploaded`.\nChecklist: notebooklm/EXPORT_REPORT.md")
    else:
        print("\nNothing new to upload to NotebookLM.")


def mark_uploaded() -> None:
    """Record the current export as being in NotebookLM, so later exports only list what changed."""
    if not MANIFEST.exists():
        raise SystemExit("Run `canvas-sync export` first.")
    state = json.loads(MANIFEST.read_text())
    UPLOADED.write_text(json.dumps(state, indent=1))
    if (EXPORT / "_new").exists():
        shutil.rmtree(EXPORT / "_new")
    print(f"Marked {sum(len(v) for v in state.values())} files as uploaded.")
