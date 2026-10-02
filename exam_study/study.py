"""Study helpers built on study.toml: exam study packs, a calendar file, and a what's-next digest."""

import hashlib
import re
import shutil
import tomllib
from datetime import date, datetime, timedelta
from pathlib import Path

from exam_study.export import EXPORT, MATERIALS, ROOT, choose

CONFIG = ROOT / "study.toml"
STUDY = ROOT / "study"


def load(config: Path = CONFIG) -> tuple[list[dict], list[dict]]:
    if not config.exists():
        raise SystemExit("No study.toml yet. Copy study.example.toml to study.toml and fill it in.")
    data = tomllib.loads(config.read_text())
    return data.get("exam", []), data.get("deadline", [])


def label(item: dict) -> str:
    return f"{item['course']} {item['name']}"


def pack_files(exam: dict, materials: Path = MATERIALS) -> list[Path]:
    """Study material (same filter as the NotebookLM export) that falls inside the exam's coverage."""
    course_dir = materials / exam["course"]
    if not course_dir.is_dir():
        return []
    patterns = [re.compile(p) for p in exam["covers"]]
    kept, _ = choose(course_dir)
    return [f for f in kept if any(p.search(f.relative_to(course_dir).as_posix()) for p in patterns)]


def pack(query: str | None) -> None:
    exams, _ = load()
    wanted = [e for e in exams if query and query.lower() in label(e).lower()]
    if not wanted:
        print("Which exam? Use part of a name, for example: exam-study pack \"302 exam 2\"\n")
        for e in exams:
            print(f"  {e['date']}  {label(e)}")
        return
    for exam in wanted:
        files = pack_files(exam)
        out = STUDY / label(exam)
        if out.exists():
            shutil.rmtree(out)  # derived copy; rebuilt from materials/ every run
        out.mkdir(parents=True)
        used = set()
        for f in files:
            name = f.name if f.name not in used else f"{f.parent.name} - {f.name}"
            used.add(name)
            shutil.copy2(f, out / name)
        print(f"{label(exam)} ({exam['date']}): {len(files)} files in {out.relative_to(ROOT)}/")


def ics(exams: list[dict], deadlines: list[dict]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//exam-study//EN"]
    for kind, item in [("Exam", e) for e in exams] + [("Due", d) for d in deadlines]:
        day = date.fromisoformat(item["date"])
        # A stable UID means re-importing updates an event instead of duplicating it.
        uid = hashlib.sha1(f"{kind}{label(item)}".encode()).hexdigest()
        lines += ["BEGIN:VEVENT", f"UID:{uid}@exam-study", f"DTSTAMP:{day:%Y%m%d}T000000Z"]
        if item.get("time"):
            start = datetime.fromisoformat(f"{item['date']}T{item['time']}")
            lines += [f"DTSTART:{start:%Y%m%dT%H%M%S}", f"DTEND:{start + timedelta(hours=item.get('hours', 1.5)):%Y%m%dT%H%M%S}"]
        else:
            lines += [f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}"]
        title = f"{label(item)}" if kind == "Due" else f"EXAM: {label(item)}"
        lines.append(f"SUMMARY:{title}")
        if item.get("where"):
            lines.append(f"LOCATION:{item['where']}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def calendar() -> None:
    exams, _ = load()  # exams only; deadlines stay in the digest
    STUDY.mkdir(exist_ok=True)
    out = STUDY / "calendar.ics"
    out.write_text(ics(exams, []))
    print(f"{len(exams)} exams written to {out.relative_to(ROOT)}. Open the file to add them to your calendar.")


def digest(today: date | None = None, days: int = 14) -> list[str]:
    """What arrived in this update and what is due soon."""
    today = today or date.today()
    exams, deadlines = load()
    lines = ["", f"# This week ({today:%b %d})", "", "New material:"]
    new_dir = EXPORT / "_new"
    courses = sorted(p for p in new_dir.iterdir() if p.is_dir()) if new_dir.exists() else []
    for course in courses:
        lines += [f"- {course.name}: {f.name}" for f in sorted(course.iterdir())]
    if not courses:
        lines.append("- nothing new")
    lines += ["", f"Coming up in the next {days} days:"]
    soon = sorted((date.fromisoformat(i["date"]), kind, i)
                  for kind, items in (("EXAM", exams), ("due", deadlines)) for i in items
                  if today <= date.fromisoformat(i["date"]) <= today + timedelta(days=days))
    for day, kind, item in soon:
        extra = " ".join(filter(None, [item.get("time"), item.get("where")]))
        prefix = "EXAM: " if kind == "EXAM" else ""
        lines.append(f"- {day:%a %b %d} ({(day - today).days}d): {prefix}{label(item)}" + (f" [{extra}]" if extra else ""))
    if not soon:
        lines.append("- nothing scheduled")
    return lines
