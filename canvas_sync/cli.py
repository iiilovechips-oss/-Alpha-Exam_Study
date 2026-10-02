"""Pull course files from Canvas into materials/, tracking what has been seen."""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from markdownify import markdownify
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
MATERIALS = ROOT / "materials"
REPORTS = ROOT / "reports"
DB_PATH = ROOT / "state.db"
SESSION_FILE = ROOT / ".session.json"  # saved browser login; treat like a password

# Links to these hosts are probably course material the sync cannot fetch itself.
DOC_HOSTS = ("sharepoint.com", "box.com", "drive.google.com", "docs.google.com",
             "mediaspace.illinois.edu", "youtube.com", "youtu.be")

# Lecture recordings are large and not needed for Q&A; they are listed, not downloaded.
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".wmv"}

# SharePoint share links: ":b:" pdf, ":w:" Word, ":p:" PowerPoint, ":x:" Excel (":v:" video is skipped).
SHAREPOINT_KINDS = {":b:": ".pdf", ":w:": ".docx", ":p:": ".pptx", ":x:": ".xlsx"}
CONTENT_TYPE_EXT = {"pdf": ".pdf", "wordprocessingml": ".docx", "presentationml": ".pptx",
                    "spreadsheetml": ".xlsx", "msword": ".doc"}
MD_LINK = re.compile(r'\[([^\]]+)\]\((https?://[^)\s]+)(?: "[^"]*")?\)')

LOGIN_REMINDER = (
    "Canvas login needed: your saved session has expired and nobody logged in "
    "in time. Run `uv run canvas-sync login`, sign in in the Chrome window that "
    "opens, then run `uv run canvas-sync sync` again. Nothing was downloaded."
)


class CanvasError(Exception):
    pass


def safe_name(name: str) -> str:
    name = " ".join(name.split())  # also turns non-breaking spaces into plain ones
    return re.sub(r'[\\/:*?"<>|]+', "-", name).strip(" .") or "untitled"


def notify(message: str) -> None:
    """Best-effort macOS notification so scheduled runs don't fail silently."""
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{message}" with title "canvas-sync"'],
            check=False, capture_output=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        pass


class Canvas:
    """Canvas REST API over either an access token or a logged-in browser session."""

    def __init__(self, pw):
        load_dotenv(ROOT / ".env")
        self.base = (os.getenv("CANVAS_API_URL") or "").rstrip("/")
        if not self.base or "youruniversity" in self.base:
            sys.exit("Open the .env file and set CANVAS_API_URL to your school's Canvas address, "
                     "for example https://canvas.illinois.edu (copy .env.example to .env if you have not yet).")
        self.pw = pw
        self.token = os.getenv("CANVAS_API_TOKEN") or ""
        self.login_timeout = int(os.getenv("CANVAS_LOGIN_TIMEOUT") or 300)
        self.browser = None
        if self.token:
            self.request = pw.request.new_context(
                extra_http_headers={"Authorization": f"Bearer {self.token}"}
            )
        else:
            self._open_browser(headless=True)

    def _open_browser(self, headless: bool) -> None:
        if self.browser:
            self.browser.close()
        self.browser = self.pw.chromium.launch(channel="chrome", headless=headless)
        state = str(SESSION_FILE) if SESSION_FILE.exists() else None
        self.context = self.browser.new_context(storage_state=state)
        self.request = self.context.request

    def logged_in(self) -> bool:
        try:
            return self.request.get(f"{self.base}/api/v1/users/self").ok
        except PlaywrightError:
            return False

    def ensure_login(self) -> bool:
        """Return True once authenticated; opens a Chrome window to log in if needed."""
        if self.logged_in():
            return True
        if self.token:
            print("Canvas rejected CANVAS_API_TOKEN (expired or revoked). Update it in .env.")
            return False

        reason = "Canvas session expired." if SESSION_FILE.exists() else "Not logged in to Canvas yet."
        print(f"{reason} Log in in the Chrome window that just opened "
              f"(waiting up to {self.login_timeout}s) ...")
        notify("Canvas session expired - log in in the Chrome window to continue the sync.")
        try:
            self._open_browser(headless=False)
            page = self.context.new_page()
            page.goto(self.base)
            deadline = time.time() + self.login_timeout
            while time.time() < deadline:
                page.wait_for_timeout(3000)
                if self.logged_in():
                    self.save_session()
                    page.close()
                    print("Logged in.")
                    return True
        except PlaywrightError:
            pass  # window closed by the user, or Chrome failed to start
        return False

    def save_session(self) -> None:
        if not self.token:
            self.context.storage_state(path=str(SESSION_FILE))
            SESSION_FILE.chmod(0o600)

    def _json(self, response, what: str):
        if not response.ok:
            raise CanvasError(f"{what}: HTTP {response.status}")
        # Cookie-authenticated responses are prefixed with "while(1);".
        return json.loads(response.text().removeprefix("while(1);"))

    def get(self, path: str):
        return self._json(self.request.get(f"{self.base}/api/v1{path}"), path)

    def get_list(self, path: str, **params):
        url, params = f"{self.base}/api/v1{path}", {"per_page": 100, **params}
        while url:
            response = self.request.get(url, params=params)
            yield from self._json(response, path)
            nxt = re.search(r'<([^>]+)>;\s*rel="next"', response.headers.get("link", ""))
            url, params = (nxt.group(1) if nxt else None), None

    def fetch_sharepoint(self, url: str) -> tuple[bytes, str]:
        """Return (content, extension) for a SharePoint share link."""
        kind = url.split("/")[3] if url.count("/") > 3 else ""
        response = self.request.get(url + ("&" if "?" in url else "?") + "download=1", timeout=300_000)
        ctype = response.headers.get("content-type", "")
        if not response.ok or "text/html" in ctype or "login" in urlparse(response.url).netloc:
            raise CanvasError("SharePoint would not hand over the file (it may need a Microsoft login)")
        ext = next((e for k, e in CONTENT_TYPE_EXT.items() if k in ctype), SHAREPOINT_KINDS.get(kind, ""))
        return response.body(), ext

    def download(self, url: str, dest: Path) -> None:
        response = self.request.get(url, timeout=300_000)
        if not response.ok:
            raise CanvasError(f"HTTP {response.status}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.body())


def selected_courses(canvas: Canvas) -> list[dict]:
    wanted = {int(i) for i in os.getenv("CANVAS_COURSE_IDS", "").split(",") if i.strip()}
    courses = [c for c in canvas.get_list("/courses", enrollment_state="active") if c.get("name")]
    return [c for c in courses if not wanted or c["id"] in wanted]


def folder_names(courses: list[dict]) -> dict[int, str]:
    """Short folder name per course: 'badm_210_120268_264540' -> 'BADM 210'."""
    names = {}
    for c in courses:
        code = c.get("course_code") or c["name"]
        m = re.search(r"([A-Za-z]{2,5})[ _](\d{3})", code)
        if not m:
            names[c["id"]] = safe_name(code)
            continue
        short = f"{m.group(1).upper()} {m.group(2)}"
        # Keep a distinguishing word ("lyceum") but drop term and section-id noise.
        rest = [w for w in re.split(r"[ _]+", code[m.end():])
                if w and not re.fullmatch(r"\d+|(fall|spring|summer|winter)\d*", w, re.I)]
        names[c["id"]] = safe_name(f"{short} - {' '.join(rest)}" if rest else short)
    return names


def open_db() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.execute("CREATE TABLE IF NOT EXISTS files ("
               "file_id INTEGER PRIMARY KEY, course_id INTEGER, updated_at TEXT, path TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS docs (key TEXT PRIMARY KEY, hash TEXT, path TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS links ("
               "course_id INTEGER, url TEXT, PRIMARY KEY (course_id, url))")
    return db


class Scan:
    """Everything one course offers: uploaded files, page text, and outside links."""

    def __init__(self, canvas: Canvas, course_id: int):
        self.canvas, self.cid = canvas, course_id
        self.host = urlparse(canvas.base).netloc
        self.files = {}      # file_id -> (file json, subfolder)
        self.docs = []       # (key, title, html, subfolder)
        self.externals = []  # (source title, link text, url)
        self.sharepoint = {}  # url without query -> (url, subfolder, file name without extension)
        self.problems = []
        self._failed = set()

    def run(self) -> "Scan":
        assignment_folder = self._modules()
        self._files_tab()
        self._assignments(assignment_folder)
        self._home()
        return self

    def _add_doc(self, key: str, title: str, html: str | None, sub: str) -> None:
        if not html or not html.strip():
            return
        self.docs.append((key, title, html, sub))
        for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
            href, text = a["href"], a.get_text(" ", strip=True) or a["href"]
            if urlparse(href).netloc in ("", self.host):
                m = re.search(r"/files/(\d+)", href)
                if m:
                    self._add_file(int(m.group(1)), sub, f"{text} (linked from {title})")
            elif href.startswith("http"):
                self.externals.append((title, text, href))
        self._name_sharepoint_links(html, sub)

    def _name_sharepoint_links(self, html: str, sub: str) -> None:
        """Share links carry no file name, so build one from the text around the link:
        the last bold heading line becomes the folder, the bold label before the link the name."""
        heading = None
        for line in markdownify(html).splitlines():
            m = re.fullmatch(r"\s*\*\*([^*\[\]]{4,})\*\*\s*", line)
            if m:
                heading = safe_name(m.group(1).strip())
                continue
            for link in MD_LINK.finditer(line):
                text, url = link.group(1), link.group(2)
                kind = url.split("/")[3] if url.count("/") > 3 else ""
                if "sharepoint.com" not in urlparse(url).netloc or kind not in SHAREPOINT_KINDS:
                    continue
                before = line[:link.start()]
                labels = list(re.finditer(r"\*\*([^*]+?):?\s*\*\*", before))
                label, tail = (labels[-1].group(1), before[labels[-1].end():]) if labels else ("", before)
                hint = re.sub(r"[^\w &-]+", " ", f"{label} {MD_LINK.sub('', tail)}")
                hint = " ".join(hint.split()).strip(" -")
                name = safe_name(f"{hint} - {text}" if hint else text)
                self.sharepoint.setdefault(url.split("?")[0], (url, heading or sub, name))

    def _add_file(self, file_id: int, sub: str, label: str) -> None:
        if file_id in self.files or file_id in self._failed:
            return
        try:
            try:
                f = self.canvas.get(f"/courses/{self.cid}/files/{file_id}")
            except CanvasError:
                f = self.canvas.get(f"/files/{file_id}")  # file copied from another course
            self.files[file_id] = (f, sub)
        except CanvasError as e:
            self._failed.add(file_id)
            self.problems.append(f"{label}: {e}")

    def _modules(self) -> dict[int, str]:
        """Module names ("Week 3", "Unit 2") make the best folders."""
        assignment_folder = {}
        try:
            for module in self.canvas.get_list(f"/courses/{self.cid}/modules"):
                sub = safe_name(module["name"])
                for item in self.canvas.get_list(f"/courses/{self.cid}/modules/{module['id']}/items"):
                    kind, title = item.get("type"), item.get("title") or "untitled"
                    if kind == "File":
                        self._add_file(item["content_id"], sub, f"{title} (in module {module['name']})")
                    elif kind == "Assignment":
                        assignment_folder[item["content_id"]] = sub
                    elif kind == "Page":
                        try:
                            page = self.canvas.get(f"/courses/{self.cid}/pages/{item['page_url']}")
                            self._add_doc(f"page:{self.cid}:{page['page_id']}", page["title"], page.get("body"), sub)
                        except CanvasError as e:
                            self.problems.append(f"Page {title} (in module {module['name']}): {e}")
                    elif kind == "ExternalUrl" and item.get("external_url"):
                        self.externals.append((module["name"], title, item["external_url"]))
        except CanvasError as e:
            self.problems.append(f"Could not read Modules: {e}")
        return assignment_folder

    def _files_tab(self) -> None:
        # Often hidden from students, so a failure here is expected.
        try:
            folders = {f["id"]: f["full_name"] for f in self.canvas.get_list(f"/courses/{self.cid}/folders")}
            for f in self.canvas.get_list(f"/courses/{self.cid}/files"):
                folder = folders.get(f.get("folder_id"), "").removeprefix("course files").strip("/")
                sub = Path("Files", *[safe_name(p) for p in folder.split("/") if p])
                self.files.setdefault(f["id"], (f, str(sub)))
        except CanvasError:
            pass

    def _assignments(self, assignment_folder: dict[int, str]) -> None:
        try:
            for a in self.canvas.get_list(f"/courses/{self.cid}/assignments"):
                sub = assignment_folder.get(a["id"], "Assignments")
                self._add_doc(f"assignment:{a['id']}", f"Assignment - {a['name']}", a.get("description"), sub)
        except CanvasError as e:
            self.problems.append(f"Could not read Assignments: {e}")

    def _home(self) -> None:
        try:
            page = self.canvas.get(f"/courses/{self.cid}/front_page")
            self._add_doc(f"front:{self.cid}", f"Home - {page['title']}", page.get("body"), "Home")
        except CanvasError:
            pass  # course has no front page
        try:
            course = self.canvas.get(f"/courses/{self.cid}?include[]=syllabus_body")
            self._add_doc(f"syllabus:{self.cid}", "Syllabus", course.get("syllabus_body"), "Home")
        except CanvasError:
            pass


def write_report(lines: list[str]) -> None:
    REPORTS.mkdir(exist_ok=True)
    report = REPORTS / f"sync-{datetime.now():%Y-%m-%d-%H%M}.md"
    report.write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))
    print(f"\nReport saved to {report.relative_to(ROOT)}")


def sync(canvas: Canvas) -> None:
    lines = [f"# Canvas sync — {datetime.now():%Y-%m-%d %H:%M}", ""]
    if not canvas.ensure_login():
        notify("Canvas sync skipped - login needed. Run: uv run canvas-sync login")
        write_report(lines + [f"- [ ] ACTION NEEDED: {LOGIN_REMINDER}"])
        return

    db = open_db()
    courses = selected_courses(canvas)
    names = folder_names(courses)
    for course in courses:
        code = names[course["id"]]
        base = MATERIALS / code
        print(f"Checking {code} ...")
        scan = Scan(canvas, course["id"]).run()
        problems = scan.problems
        new, updated, unchanged, videos = [], [], 0, []

        for file_id, (f, sub) in scan.files.items():
            name = f.get("display_name") or f.get("filename") or str(file_id)
            dest = base / sub / safe_name(name)
            if dest.suffix.lower() in VIDEO_EXTS:
                key = f"video:{file_id}"
                if not db.execute("SELECT 1 FROM links WHERE course_id=? AND url=?", (course["id"], key)).fetchone():
                    videos.append(dest.relative_to(base))
                    db.execute("INSERT INTO links VALUES (?,?)", (course["id"], key))
                continue
            row = db.execute("SELECT updated_at, path FROM files WHERE file_id=?", (file_id,)).fetchone()
            if row and row[0] == f.get("updated_at") and Path(row[1]).exists():
                unchanged += 1
                continue
            if not f.get("url"):
                problems.append(f"{name}: locked or not downloadable yet")
                continue
            try:
                canvas.download(f["url"], dest)
            except (CanvasError, PlaywrightError, OSError) as e:
                problems.append(f"{name}: download failed ({e})")
                continue
            db.execute("INSERT OR REPLACE INTO files VALUES (?,?,?,?)",
                       (file_id, course["id"], f.get("updated_at"), str(dest)))
            db.commit()
            (updated if row else new).append(dest.relative_to(base))

        # Canvas pages and assignment descriptions, saved as Markdown.
        for key, title, html, sub in scan.docs:
            text = f"# {title}\n\n{markdownify(html, heading_style='ATX').strip()}\n"
            digest = hashlib.sha1(text.encode()).hexdigest()
            dest = base / sub / f"{safe_name(title)}.md"
            row = db.execute("SELECT hash, path FROM docs WHERE key=?", (key,)).fetchone()
            if row and row[0] == digest and Path(row[1]).exists():
                unchanged += 1
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)
            db.execute("INSERT OR REPLACE INTO docs VALUES (?,?,?)", (key, digest, str(dest)))
            db.commit()
            (updated if row else new).append(dest.relative_to(base))

        # Files the professor keeps on SharePoint: fetched through their share links.
        for key, (url, sub, name) in scan.sharepoint.items():
            row = db.execute("SELECT hash, path FROM docs WHERE key=?", (f"sp:{key}",)).fetchone()
            try:
                body, ext = canvas.fetch_sharepoint(url)
            except (CanvasError, PlaywrightError) as e:
                if not (row and Path(row[1]).exists()):
                    problems.append(f"{name} ({url}): {e}")
                continue
            digest = hashlib.sha1(body).hexdigest()
            if row and row[0] == digest and Path(row[1]).exists():
                unchanged += 1
                continue
            dest = Path(row[1]) if row else base / sub / f"{name}{ext}"
            while not row and dest.exists():
                dest = dest.with_stem(dest.stem + " (2)")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(body)
            db.execute("INSERT OR REPLACE INTO docs VALUES (?,?,?)", (f"sp:{key}", digest, str(dest)))
            db.commit()
            (updated if row else new).append(dest.relative_to(base))

        # Other links to material hosted outside Canvas: listed for manual download.
        seen, new_links = set(), []
        for source, text, url in scan.externals:
            if url.split("?")[0] in scan.sharepoint:
                continue
            if url in seen or not any(h in urlparse(url).netloc for h in DOC_HOSTS):
                continue
            seen.add(url)
            if not db.execute("SELECT 1 FROM links WHERE course_id=? AND url=?", (course["id"], url)).fetchone():
                new_links.append((source, text, url))
                db.execute("INSERT INTO links VALUES (?,?)", (course["id"], url))
        db.commit()
        if scan.externals:
            base.mkdir(parents=True, exist_ok=True)
            listing = [f"# External links - {code}", ""]
            listing += [f"- [{text}]({url}) (from: {source})" for source, text, url in scan.externals]
            (base / "External links.md").write_text("\n".join(listing) + "\n")

        # Report each problem once, so a permanently broken link doesn't nag every week.
        fresh = []
        for problem in problems:
            key = "problem:" + problem
            if not db.execute("SELECT 1 FROM links WHERE course_id=? AND url=?", (course["id"], key)).fetchone():
                fresh.append(problem)
                db.execute("INSERT INTO links VALUES (?,?)", (course["id"], key))
        db.commit()
        problems = fresh

        lines.append(f"## {code}")
        lines.append(f"{len(new)} new, {len(updated)} updated, {unchanged} unchanged, "
                     f"{len(new_links)} outside Canvas, {len(problems)} need attention")
        lines += [f"- [ ] NEW: {p}" for p in new]
        lines += [f"- [ ] UPDATED: {p}" for p in updated]
        lines += [f"- SKIPPED VIDEO (watch on Canvas): {p}" for p in videos]
        lines += [f"- [ ] DOWNLOAD MANUALLY: [{text}]({url}) (from: {source})" for source, text, url in new_links]
        lines += [f"- [ ] NEEDS MANUAL CHECK: {p}" for p in problems]
        lines.append("")

    canvas.save_session()
    write_report(lines)


def list_courses(canvas: Canvas) -> None:
    if not canvas.ensure_login():
        print(LOGIN_REMINDER)
        return
    courses = selected_courses(canvas)
    names = folder_names(courses)
    for c in courses:
        print(f"{c['id']}\t{names[c['id']]}\t{c['name']}")
    canvas.save_session()


def login(canvas: Canvas) -> None:
    print("Logged in; session saved." if canvas.ensure_login() else LOGIN_REMINDER)


def main() -> None:
    parser = argparse.ArgumentParser(prog="canvas-sync", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="open Chrome to sign in to Canvas and save the session").set_defaults(func=login)
    sub.add_parser("courses", help="list your active Canvas courses and their IDs").set_defaults(func=list_courses)
    sub.add_parser("sync", help="download new and updated files").set_defaults(func=sync)
    sub.add_parser("export", help="build notebooklm/: a filtered, study-only copy for NotebookLM")
    sub.add_parser("update", help="sync, then export: the one command to run each week").set_defaults(func=sync)
    sub.add_parser("uploaded", help="mark the current export as uploaded to NotebookLM")
    pack_parser = sub.add_parser("pack", help="build study/<exam>/ with just the material one exam covers")
    pack_parser.add_argument("exam", nargs="?", help='part of an exam name, e.g. "302 exam 2"')
    explain_parser = sub.add_parser("explain", help="build a slide-by-slide study page for one PDF deck")
    explain_parser.add_argument("deck", help='part of the path of the deck, e.g. "475/Files/Week 5/Chapter 2"')
    sub.add_parser("study", help="open the progress dashboard and study pages; records your answers")
    sub.add_parser("progress", help="print exam readiness and topic mastery")
    sub.add_parser("calendar", help="write study/calendar.ics with exams and deadlines")
    sub.add_parser("digest", help="show new material and what is due in the next two weeks")
    args = parser.parse_args()
    from canvas_sync import study
    from canvas_sync.export import export, mark_uploaded
    if args.command == "export":
        return export()
    if args.command == "uploaded":
        return mark_uploaded()
    if args.command == "pack":
        return study.pack(args.exam)
    if args.command == "explain":
        from canvas_sync.explain import explain
        return explain(args.deck)
    if args.command == "study":
        from canvas_sync.progress import serve
        return serve()
    if args.command == "progress":
        from canvas_sync.progress import text_summary
        return print(text_summary())
    if args.command == "calendar":
        return study.calendar()
    if args.command == "digest":
        return print("\n".join(study.digest()))
    with sync_playwright() as pw:
        args.func(Canvas(pw))
    if args.command == "update":
        export()
        if study.CONFIG.exists():
            print("\n".join(study.digest()))


if __name__ == "__main__":
    main()
