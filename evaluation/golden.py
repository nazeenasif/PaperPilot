"""The golden set: loading, normalised evidence matching and the check (research R1, R2).

`eval/golden.json` is JSON with full-line `//` comments allowed. Papers are named by arXiv ID and
evidence by phrase, paper and page, never by passage ID, so the set survives re-chunking. The
check makes no model request.
"""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from paperpilot import ingest, library, store

GOLDEN_FILE = Path("eval") / "golden.json"
# The researcher's target counts (spec FR-001, amended 2026-11-11).
TARGETS = {"single": 20, "cross": 5, "near_miss": 4, "off_topic": 3, "follow_up": 4}
ANSWERABLE = ("single", "cross", "follow_up")
NOT_FOUND_KINDS = ("near_miss", "off_topic")
SCOPES = ("library", "paper")
MAX_QUESTIONS = 50
_PASSAGE_ID = re.compile(r"\b[0-9a-f]{12}-\d+\b")
_COMMENT = re.compile(r"^\s*//.*$", re.MULTILINE)
_HYPHENS = re.compile(r"[-­‐‑]")
_OTHER = re.compile(r"[^\w%.,±×]+")


def normalise(text: str) -> str:
    """Text for matching: ingest's cleaning (line-break hyphens, whitespace), then NFKC (PDF
    ligatures), lower case, hyphens removed (ingest drops some real ones at line breaks), and only
    letters, digits and % . , ± × kept, separated by single spaces."""
    text = unicodedata.normalize("NFKC", ingest.clean(text)).lower()
    return " ".join(_OTHER.sub(" ", _HYPHENS.sub("", text)).replace("_", " ").split())


@dataclass(frozen=True)
class GoldenSet:
    """The loaded file: its version, the papers it covers, its questions and the file's hash."""

    version: int
    papers: list[str]
    questions: list[dict]
    sha256: str
    path: Path


def load_golden(path: Path | str = GOLDEN_FILE) -> GoldenSet:
    """Read the golden set, removing full-line // comments. Raises ValueError for bad JSON."""
    path = Path(path)
    raw = path.read_bytes()
    try:
        data = json.loads(_COMMENT.sub("", raw.decode("utf-8")))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path} is not valid JSON once comments are removed: {error}") from None
    return GoldenSet(version=data.get("version"), papers=list(data.get("papers", [])),
                     questions=list(data.get("questions", [])), sha256=hashlib.sha256(raw).hexdigest(), path=path)


@dataclass
class CheckReport:
    """What the check found: failures, things still to do in drafts mode, and counts per kind."""

    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


class _Library:
    """Stored passages and PDF pages per paper, read once."""

    def __init__(self) -> None:
        self.by_arxiv = {p.arxiv_id: p.paper_id for p in library.list_papers() if p.arxiv_id}
        self._passages: dict[str, list[tuple[str, str]]] = {}
        self._pages: dict[str, list[str]] = {}

    def passages(self, paper_id: str) -> list[tuple[str, str]]:
        """(normalised text, kind) of every stored passage."""
        if paper_id not in self._passages:
            got = store.get_collection().get(where={"paper_id": paper_id}, include=["documents", "metadatas"])
            self._passages[paper_id] = [(normalise(text), meta.get("kind", "text"))
                                        for text, meta in zip(got["documents"], got["metadatas"])]
        return self._passages[paper_id]

    def pages(self, paper_id: str) -> list[str]:
        """Normalised text of every PDF page; empty when the PDF is not stored."""
        if paper_id not in self._pages:
            try:
                with pymupdf.open(library.pdf_path(paper_id)) as doc:
                    self._pages[paper_id] = [normalise(page.get_text()) for page in doc]
            except Exception:  # missing PDF: reported by the caller
                self._pages[paper_id] = []
        return self._pages[paper_id]


def _check_evidence(q: dict, lib: _Library, report: CheckReport) -> None:
    qid = q.get("id")
    in_table = False
    for ev in q.get("evidence", []):
        arxiv, page, phrase = ev.get("paper"), ev.get("page"), normalise(str(ev.get("phrase", "")))
        paper_id = lib.by_arxiv.get(arxiv)
        if arxiv not in q.get("papers", []):
            report.errors.append(f"{qid}: evidence names paper {arxiv}, which the question does not list")
        if paper_id is None:
            continue  # reported with the question's papers
        if not phrase:
            report.errors.append(f"{qid}: an evidence phrase is empty")
            continue
        matches = [kind for text, kind in lib.passages(paper_id) if phrase in text]
        if not matches:
            report.errors.append(f"{qid}: evidence {ev.get('phrase')!r} matches no stored passage of {arxiv}")
        in_table = in_table or "table" in matches
        pages = lib.pages(paper_id)
        if not pages:
            report.errors.append(f"{qid}: the PDF of {arxiv} is not stored, so the page cannot be checked")
        elif not isinstance(page, int) or not 1 <= page <= len(pages) or phrase not in pages[page - 1]:
            report.errors.append(f"{qid}: evidence {ev.get('phrase')!r} is not on page {page} of {arxiv} "
                                 f"(the PDF has {len(pages)} pages)")
    if q.get("table") and q.get("evidence") and not in_table:
        report.errors.append(f"{qid}: marked table, but no evidence phrase is in a table passage")
    if q.get("kind") == "cross":
        covered = {ev.get("paper") for ev in q.get("evidence", [])}
        missing = [p for p in q.get("papers", []) if p not in covered]
        if q.get("evidence") and missing:
            report.errors.append(f"{qid}: cross-paper evidence covers no phrase from {', '.join(missing)}")


def _check_question(q: dict, lib: _Library, drafts: bool, cross_min_papers: int, report: CheckReport) -> None:
    qid = q.get("id") or "(no id)"
    kind, scope, papers = q.get("kind"), q.get("scope", "library"), q.get("papers", [])
    if _PASSAGE_ID.search(json.dumps(q)):
        report.errors.append(f"{qid}: holds a passage ID; name evidence by phrase, paper and page instead")
    if kind not in TARGETS:
        report.errors.append(f"{qid}: unknown kind {kind!r}; use one of {', '.join(TARGETS)}")
    if scope not in SCOPES:
        report.errors.append(f"{qid}: unknown scope {scope!r}; use library or paper")
    elif scope == "paper" and len(papers) != 1:
        report.errors.append(f"{qid}: scope paper needs exactly one paper")
    for arxiv in papers:
        if arxiv not in lib.by_arxiv:
            report.errors.append(f"{qid}: paper {arxiv} is not in the library")
    if not str(q.get("question", "")).strip():
        report.errors.append(f"{qid}: the question is empty")
    if kind in ANSWERABLE:
        if not papers:
            report.errors.append(f"{qid}: an answerable question needs its paper(s)")
        if q.get("expected") in (None, "", "not_found"):
            report.errors.append(f"{qid}: an answerable question needs its expected answer")
        if not q.get("evidence"):
            (report.notes if drafts else report.errors).append(f"{qid}: no evidence yet")
    if kind in NOT_FOUND_KINDS:
        if q.get("expected") != "not_found" or q.get("evidence"):
            report.errors.append(f'{qid}: a {kind} question expects "not_found" and has no evidence')
    if kind == "single" and len(papers) > 1:
        report.errors.append(f"{qid}: a single-paper question lists {len(papers)} papers")
    if kind == "cross" and len(papers) < cross_min_papers:
        report.errors.append(f"{qid}: a cross-paper question needs at least {cross_min_papers} papers")
    if kind == "follow_up" and (not q.get("turns") or not str(q.get("standalone", "")).strip()):
        report.errors.append(f"{qid}: a follow-up needs its earlier turns and a standalone wording")
    if not q.get("confirmed"):
        (report.notes if drafts else report.errors).append(f"{qid}: not confirmed against the PDF yet")
    _check_evidence(q, lib, report)


def check(golden: GoldenSet, drafts: bool = False, cross_min_papers: int = 2) -> CheckReport:
    """Validate the golden set against the library and its PDFs (FR-001-FR-005). With `drafts`,
    unconfirmed items and missing evidence are listed as notes instead of failures."""
    report = CheckReport()
    lib = _Library()
    if not isinstance(golden.version, int):
        report.errors.append("the set needs a whole-number version")
    for arxiv in golden.papers:
        if arxiv not in lib.by_arxiv:
            report.errors.append(f"paper {arxiv} is not in the library")
    ids = [q.get("id") for q in golden.questions]
    for duplicate in sorted({i for i in ids if ids.count(i) > 1}, key=str):
        report.errors.append(f"{duplicate}: the id is used twice")
    for q in golden.questions:
        _check_question(q, lib, drafts, cross_min_papers, report)

    report.counts = {kind: sum(q.get("kind") == kind for q in golden.questions) for kind in TARGETS}
    for kind, target in TARGETS.items():
        if report.counts[kind] < target:
            report.errors.append(f"{kind}: {report.counts[kind]} of {target} questions")
    if len(golden.questions) > MAX_QUESTIONS:
        report.errors.append(f"the set has {len(golden.questions)} questions; at most {MAX_QUESTIONS}")
    for arxiv in golden.papers:
        if not any(q.get("kind") == "single" and q.get("table") and arxiv in q.get("papers", [])
                   for q in golden.questions):
            report.errors.append(f"{arxiv}: no single-paper question with a table answer")
    return report
