from pathlib import Path
from types import SimpleNamespace

from canvas_sync.cli import Scan, folder_names, safe_name
from canvas_sync.export import choose


def test_safe_name_strips_path_characters():
    assert safe_name("Week 1: Intro/Overview") == "Week 1- Intro-Overview"
    assert safe_name("  ...  ") == "untitled"


def test_folder_names_shorten_canvas_codes():
    courses = [
        {"id": 1, "course_code": "ACCY 301", "name": "x"},
        {"id": 2, "course_code": "badm_210_120268_264540", "name": "x"},
        {"id": 3, "course_code": "accy_302_fall2026", "name": "x"},
        {"id": 4, "course_code": "accy_302_lyceum", "name": "x"},
        {"id": 5, "course_code": "Orientation", "name": "x"},
    ]
    assert folder_names(courses) == {
        1: "ACCY 301", 2: "BADM 210", 3: "ACCY 302", 4: "ACCY 302 - lyceum", 5: "Orientation",
    }


def make(course: Path, *names: str) -> None:
    for name in names:
        path = course / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name)


def test_export_keeps_study_material_and_drops_graded_work(tmp_path):
    make(tmp_path,
         "Day 5/Day 5 LECTURE Case 1 & ABC Basics.pdf",    # lecture wins over "case 1"
         "Day 5/Day 5 CASE 1 Job Order Costing Part A.docx",
         "Day 5/Day 5 CASE 1 Template.xlsx",
         "Week 1/LabA_netid.xlsx",
         "Week 1/badm210_01_excel_basics_DATA.xlsx",
         "Week 1/Reading 1.01.pdf",
         "Week 1/demo.twbx",
         "Week 1/Lecture Materials.md",
         "Week 4/Exam 1 Study Guide.pdf")
    kept, dropped = choose(tmp_path)
    assert [f.name for f in kept] == [
        "Day 5 LECTURE Case 1 & ABC Basics.pdf",
        "badm210_01_excel_basics_DATA.xlsx",
        "Exam 1 Study Guide.pdf",
    ]
    assert len(dropped) == 6


def test_export_prefers_the_fuller_version_within_a_folder(tmp_path):
    make(tmp_path,
         "Day 3/Day 3 LECTURE Costing.pdf",
         "Day 3/Day 3 LECTURE INSTRUCTOR Costing.pdf",
         "Ch 2/Lecture Aug 24 - Pre-lecture Slide Deck.pdf",
         "Ch 2/Lecture Aug 24 - Post-lecture Slide Deck.pdf",
         "Ch 2/Practice - Solutions.docx",
         "Ch 3/Practice - Solutions.docx")  # same name, different chapter: both stay
    kept, _ = choose(tmp_path)
    assert sorted(str(f.relative_to(tmp_path)) for f in kept) == [
        "Ch 2/Lecture Aug 24 - Post-lecture Slide Deck.pdf",
        "Ch 2/Practice - Solutions.docx",
        "Ch 3/Practice - Solutions.docx",
        "Day 3/Day 3 LECTURE INSTRUCTOR Costing.pdf",
    ]


def test_sharepoint_links_are_named_from_surrounding_text():
    sp = "https://example-my.sharepoint.com"
    html = f"""
      <p><strong>Chapter 6: Revenue Recognition</strong></p>
      <p><strong>Lecture:</strong> Sept 9 (<a href="{sp}/:b:/g/personal/prof/AAA?e=1">Pre-lecture Slide Deck</a>, <a href="{sp}/:b:/g/personal/prof/BBB?e=2">Post-lecture Slide Deck</a>)</p>
      <p><strong>Extra:</strong> <a href="{sp}/:v:/g/personal/prof/CCC?e=3">A video</a></p>
    """
    scan = Scan(SimpleNamespace(base="https://canvas.example.edu"), 1)
    scan._name_sharepoint_links(html, "Home")
    assert list(scan.sharepoint.values()) == [
        (f"{sp}/:b:/g/personal/prof/AAA?e=1", "Chapter 6- Revenue Recognition", "Lecture Sept 9 - Pre-lecture Slide Deck"),
        (f"{sp}/:b:/g/personal/prof/BBB?e=2", "Chapter 6- Revenue Recognition", "Lecture Sept 9 - Post-lecture Slide Deck"),
    ]


def test_study_pack_only_takes_material_the_exam_covers(tmp_path):
    from canvas_sync.study import pack_files
    make(tmp_path / "ACCY 302",
         "Day 11 (Tuesday)/Midterm1 Practice Problems.docx",
         "Day 13 (Tuesday)/Day 13 LECTURE CVP.pdf",
         "Day 13 (Tuesday)/Day 13 CASE 4 Template.xlsx",
         "Day 19 (Tuesday)/Day 19 LECTURE Constraints.pdf")
    exam = {"course": "ACCY 302", "name": "Exam 2", "date": "2026-10-27", "covers": ["^Day 1[2-8] "]}
    assert [f.name for f in pack_files(exam, tmp_path)] == ["Day 13 LECTURE CVP.pdf"]


def test_calendar_has_timed_exams_and_all_day_deadlines():
    from canvas_sync.study import ics
    text = ics([{"course": "ACCY 302", "name": "Exam 2", "date": "2026-10-27", "time": "19:00", "where": "CIF 3039"}],
               [{"course": "PSYC 475", "name": "Assignment 2 due", "date": "2026-11-13"}])
    assert "SUMMARY:EXAM: ACCY 302 Exam 2" in text and "DTSTART:20261027T190000" in text
    assert "LOCATION:CIF 3039" in text and "DTSTART;VALUE=DATE:20261113" in text
    assert text.count("BEGIN:VEVENT") == 2


def test_excel_becomes_markdown_with_values_and_formulas(tmp_path):
    from openpyxl import Workbook
    from canvas_sync.convert import render
    book = Workbook()
    sheet = book.active
    sheet.title = "Costs"
    sheet.append(["Item", "Cost"])
    sheet.append(["Labor", 29000])
    sheet.append(["Materials", 19000])
    sheet["B4"] = "=SUM(B2:B3)"
    book.save(tmp_path / "data.xlsx")
    assert render(tmp_path / "data.xlsx", tmp_path, "data.xlsx") == ["data (Excel).md"]
    text = (tmp_path / "data (Excel).md").read_text()
    assert "## Sheet: Costs" in text and "| Labor | 29000 |" in text and "- B4: `=SUM(B2:B3)`" in text


def test_big_pdf_is_split_into_parts(tmp_path, monkeypatch):
    from pypdf import PdfReader, PdfWriter
    from canvas_sync import convert
    writer = PdfWriter()
    for _ in range(6):
        writer.add_blank_page(width=200, height=200)
    with open(tmp_path / "deck.pdf", "wb") as fh:
        writer.write(fh)
    size = (tmp_path / "deck.pdf").stat().st_size
    monkeypatch.setattr(convert, "PART_MB", size * 0.6 / 1_000_000)  # force a split
    names = convert.render(tmp_path / "deck.pdf", tmp_path, "deck.pdf")
    assert len(names) >= 2 and names[0].startswith("deck (part 1 of ")
    assert sum(len(PdfReader(tmp_path / n).pages) for n in names) == 6


def test_mastery_starts_at_self_rating_and_follows_the_answers():
    from canvas_sync.progress import mastery, scored_answers
    assert mastery(0.4, []) == (0.4, 0.0)
    score, evidence = mastery(0.0, [(1.0, 1.0)] * 6)          # six tap answers, all right, from a 0% start
    assert round(score, 2) == 0.75 and evidence == 6.0
    events = [{"ts": "1", "deck": "d", "q": "1", "kind": "mc", "outcome": "wrong"},
              {"ts": "2", "deck": "d", "q": "1", "kind": "mc", "outcome": "right"},     # retry: counts half
              {"ts": "3", "deck": "d", "q": "2", "kind": "self", "outcome": "partly"}]  # self-graded: counts 60%
    assert sorted(scored_answers(events)) == [(0.5, 0.6), (1.0, 0.5)]


def test_readiness_weights_topics_by_their_share_of_the_exam():
    from canvas_sync.progress import readiness
    topics = [{"weight": 75, "mastery": 0.4, "evidence": 5.0}, {"weight": 25, "mastery": 0.8, "evidence": 0.0}]
    ready, covered = readiness(topics)
    assert round(ready, 2) == 0.5 and covered == 0.75
