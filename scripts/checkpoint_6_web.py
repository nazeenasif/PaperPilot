"""Checkpoint 6: the web app end to end over HTTP (Feature 3).

Talks to the running API (http://127.0.0.1:8000) and frontend (http://127.0.0.1:3000). Each part
states its planned model requests; the run fails on unplanned requests or when all requests,
retries included, exceed twice the plan (scripts/request_budget.py, Feature 2 budget rule).

Usage: python scripts/checkpoint_6_web.py [part ...] [--new-pdf PATH]   (default: every part)
Parts: boundary, ask, viewer (viewer opens the citations of part ask), library (--new-pdf PATH
also adds a paper that is not in the library yet, then deletes it), states (in-process over a
temporary library with a scripted model; needs no server), usage, scope (a BERT-only question
and a follow-up; reuses part ask's LoRA answer as history when ask ran), secrets (builds the
frontend and looks for the API key everywhere; run it last)

Start the servers first (quickstart): `python -m api` and `npm --prefix frontend run dev`.
"""

import json
import re
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from unittest import mock
from pathlib import Path

# Allow `python scripts/checkpoint_6_web.py` from the repo root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
# Print Unicode (−, ﬁ, Θ) on a Windows console without PYTHONIOENCODING.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import httpx  # noqa: E402

from paperpilot.config import load_settings  # noqa: E402
from paperpilot.llm import RequestCounts  # noqa: E402
from request_budget import budget_checks  # noqa: E402

API = "http://127.0.0.1:8000"
API_PORT = 8000
FRONTEND_PORT = 3000
# A cold start (importing torch and sentence-transformers) took ~3 minutes when it shared the
# CPU with the frontend's first compile, versus ~25 s alone.
READY_TIMEOUT = 300.0
CONNECT_TIMEOUT = 2.0


@dataclass
class Run:
    """Results and model request counts collected across the selected parts."""

    results: list[tuple[bool, str]]
    used: RequestCounts
    answer: dict | None = None  # the last answer from part "ask", reused by part "viewer"
    captured: list[bytes] | None = None  # every API response body of this run, for part "secrets"

    def check(self, passed: bool, description: str) -> None:
        """Print and record one PASS/FAIL line."""
        print(f"{'PASS' if passed else 'FAIL'}: {description}")
        self.results.append((passed, description))

    def info(self, text: str) -> None:
        """Print an INFO line (never a pass/fail result)."""
        print(f"INFO: {text}")

    def add_requests(self, requests: dict) -> None:
        """Add an answer's `requests {planned, retries}` to the run's counts."""
        self.used = RequestCounts(
            self.used.planned + int(requests.get("planned", 0)),
            self.used.retries + int(requests.get("retries", 0)),
        )


@dataclass(frozen=True)
class Part:
    """One checkpoint part: its planned model requests and the function that runs it."""

    plan: int
    run: Callable[[Run, httpx.Client], None]


def wait_until_ready(client: httpx.Client) -> dict | None:
    """Poll /api/status until ready; None if the API can't be reached or never gets ready."""
    start = time.monotonic()
    body: dict | None = None
    announced = 0
    while time.monotonic() - start < READY_TIMEOUT:
        try:
            body = client.get("/api/status").json()
        except httpx.HTTPError:
            body = None
        if body and body.get("state") in ("ready", "error"):
            return body
        waited = int(time.monotonic() - start)
        if waited >= announced + 15:
            announced = waited
            print(f"INFO: waiting for the API ({'loading' if body else 'not reachable yet'}, {waited} s)")
        time.sleep(1.0)
    return body


def lan_address() -> str | None:
    """This machine's address on its main network, or None if it only has loopback.

    A UDP connect picks the outgoing interface without sending any packet.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("192.0.2.1", 9))  # TEST-NET-1: never routed, nothing is sent
            address = probe.getsockname()[0]
        except OSError:
            return None
    return None if address.startswith("127.") or address == "0.0.0.0" else address


def accepts_connection(host: str, port: int) -> bool:
    """True if a TCP connection to host:port succeeds."""
    try:
        with socket.create_connection((host, port), timeout=CONNECT_TIMEOUT):
            return True
    except OSError:
        return False


def part_boundary(run: Run, client: httpx.Client) -> None:
    """Localhost only, allowed origins only, and cross-site writes refused (FR-002a, FR-002b,
    SC-012). 0 model requests; the write probes are refused before any endpoint runs."""
    for origin in load_settings().frontend_origins:
        allowed = client.get("/api/status", headers={"Origin": origin})
        run.check(allowed.headers.get("access-control-allow-origin") == origin, f"CORS allows {origin}")
        preflight = client.options("/api/status", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-paperpilot"})
        run.check(preflight.status_code == 200 and preflight.headers.get("access-control-allow-origin") == origin
                  and "x-paperpilot" in preflight.headers.get("access-control-allow-headers", "").lower(),
                  f"a preflight from {origin} may send X-PaperPilot")

    foreign = "http://evil.example"
    refused = client.get("/api/status", headers={"Origin": foreign})
    run.check(refused.status_code == 403 and refused.json() == {"kind": "forbidden", "reason": "origin"}
              and "access-control-allow-origin" not in refused.headers, f"a request from {foreign} is refused (403)")
    simple_post = client.post("/api/papers", content="files=paper.pdf",
                              headers={"Origin": foreign, "Content-Type": "text/plain"})
    run.check(simple_post.status_code == 403 and simple_post.json().get("reason") == "origin",
              "a cross-origin simple POST is refused before any endpoint runs")
    no_header = client.post("/api/papers", json={}, headers={"Origin": load_settings().frontend_origins[0]})
    run.check(no_header.status_code == 403 and no_header.json().get("reason") == "header",
              "a write without X-PaperPilot: 1 is refused, even from an allowed origin")

    # Feature 4's model-spending writes are refused the same way, before any request (T052).
    used_before = client.get("/api/usage").json()["used"]
    allowed_origin = load_settings().frontend_origins[0]
    for path, body in [("/api/summaries/000000000000", {}), ("/api/comparisons", {"paper_ids": ["a", "b"], "aspects": ["method"]})]:
        unmarked = client.post(path, json=body, headers={"Origin": allowed_origin})
        run.check(unmarked.status_code == 403 and unmarked.json().get("reason") == "header",
                  f"POST {path.split('/0')[0]} without X-PaperPilot: 1 is refused")
        cross = client.post(path, json=body, headers={"Origin": foreign, **WRITE_HEADERS})
        run.check(cross.status_code == 403 and cross.json().get("reason") == "origin",
                  f"POST {path.split('/0')[0]} from {foreign} is refused")
    used_after = client.get("/api/usage").json()["used"]
    run.check(used_after == used_before, f"the refused summary and comparison writes sent no model request ({used_before} -> {used_after})")

    foreign_host = client.get("/api/status", headers={"Host": "192.168.1.20"})
    run.check(foreign_host.status_code == 400, "a foreign Host header is rejected (trusted hosts)")

    run.check(accepts_connection("127.0.0.1", API_PORT), f"the API accepts connections on 127.0.0.1:{API_PORT}")
    frontend_up = accepts_connection("127.0.0.1", FRONTEND_PORT)
    run.check(frontend_up, f"the frontend accepts connections on 127.0.0.1:{FRONTEND_PORT}"
              + ("" if frontend_up else " (start it with: npm --prefix frontend run dev)"))
    if frontend_up:
        page = httpx.get(f"http://127.0.0.1:{FRONTEND_PORT}/", timeout=60.0)
        run.check(page.status_code == 200, "the frontend serves the app page")

    address = lan_address()
    if address is None:
        run.info("no network address besides loopback; the LAN check is not applicable")
        return
    run.info(f"network address checked: {address}")
    for port, name in ((API_PORT, "API"), (FRONTEND_PORT, "frontend")):
        run.check(not accepts_connection(address, port), f"the {name} refuses connections on {address}:{port}")


WRITE_HEADERS = {"X-PaperPilot": "1"}  # every state-changing request needs it (FR-002b)
ASK_QUESTION = "What is LoRA?"
ASK_TIMEOUT = 300.0  # a free-model answer with retries can take minutes


def parse_events(text: str) -> list[tuple[str, object]]:
    """(event, data) pairs from an event-stream body; ping comments are skipped."""
    events: list[tuple[str, object]] = []
    for chunk in text.replace("\r\n", "\n").split("\n\n"):
        name, data = "message", []
        for line in chunk.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
        if data:
            events.append((name, json.loads("\n".join(data))))
    return events


def part_ask(run: Run, client: httpx.Client) -> None:
    """US1: a question streams progress, then a checked answer with valid citations (1 request)."""
    print(f"Question: {ASK_QUESTION}")
    start = time.monotonic()
    with client.stream("POST", "/api/ask", json={"question": ASK_QUESTION}, headers=WRITE_HEADERS,
                       timeout=ASK_TIMEOUT) as response:
        body = "".join(response.iter_text())
    seconds = time.monotonic() - start
    if response.status_code != 200:
        run.check(False, f"POST /api/ask answered {response.status_code}: {body[:200]}")
        return
    events = parse_events(body)
    for name, data in events:
        if name == "progress":
            extra = {k: v for k, v in data.items() if k != "step"}
            print(f"  progress: {data['step']}" + (f" {extra}" if extra else ""))
        elif name == "retry_wait":
            print(f"  retry_wait: attempt {data['attempt']} of {data['max_attempts']}, "
                  f"{data['wait_seconds']:.0f} s ({data['reason']})")
    final_name, final = events[-1] if events else ("", {})
    if final_name == "error":
        run.check(False, f"the question ended with an error event: {final}")
        return
    run.check(final_name == "answer", "the stream ends with an answer event")
    if final_name != "answer":
        return
    answer = final
    run.answer = answer
    run.add_requests(answer["requests"])
    print(f"\nAnswer ({answer['word_count']} words):\n  {answer['text']}")
    print("\nPassages:")
    for p in answer["passages"]:
        print(f"  [{p['number']}] {p['score']:.3f}  {p['title'][:50]} — {p['section']}, p. {p['page']}")
    citations = answer["citations"]
    print(f"\nCitations: valid {citations['valid']}, invalid {citations['invalid']}; verified {answer['verified']}")
    if answer["warning"]:
        print(f"Warning: {answer['warning']}")
    timings = answer["timings"]
    print(f"Timings: rewrite {timings['rewrite']:.2f} s, retrieve {timings['retrieve']:.2f} s, "
          f"generate {timings['generate']:.2f} s; whole request {seconds:.1f} s")
    print(f"Requests for this answer: {answer['requests']['planned']} planned, {answer['requests']['retries']} retries")

    steps = [data["step"] for name, data in events if name == "progress"]
    run.check(steps[:1] == ["searching"] and steps[-1:] == ["checking"],
              f"progress steps were streamed before the answer ({', '.join(steps)})")
    before_answer = json.dumps([data for name, data in events[:-1]])
    run.check(answer["text"] not in before_answer, "no answer text was sent before the answer event")
    run.check(not citations["invalid"], "every citation maps to a provided passage")
    run.check(answer["verified"] == (not answer["not_found"] and not citations["invalid"]),
              "the verified flag matches the citation check")
    if answer["not_found"]:
        run.info(f"not-found answer ({answer['fallback_reason']}): no citations to open in part viewer")


HIGHLIGHT_TARGET = 0.90  # SC-002
_WORD = re.compile(r"[\w-]+")


def words_under_regions(pdf_bytes: bytes, page: int, regions: list[dict]) -> list[str]:
    """The PDF words whose centres fall inside any region on that page, in reading order."""
    import pymupdf  # engine dependency; only needed to verify highlights

    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        words = doc[page - 1].get_text("words")
    boxes = [r for r in regions if r["page"] == page]
    inside = []
    for x0, y0, x1, y1, text, *_ in words:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if any(b["x0"] <= cx <= b["x1"] and b["y0"] <= cy <= b["y1"] for b in boxes):
            inside.append(text)
    return inside


def part_viewer(run: Run, client: httpx.Client) -> None:
    """US2: every cited passage opens its paper at the cited page, highlighted (SC-001, SC-002). 0 requests."""
    import pymupdf

    if run.answer is None:
        run.check(False, "part viewer needs part ask in the same run (it opens that answer's citations)")
        return
    passages = {p["number"]: p for p in run.answer["passages"]}
    numbers = run.answer["citations"]["valid"]
    if not numbers:
        numbers = sorted(passages)
        run.info("the answer cites nothing; checking every passage it read instead")
    pdfs: dict[str, bytes] = {}
    opened = highlighted = 0
    precisions: list[float] = []
    for number in numbers:
        passage = passages[number]
        response = client.get(f"/api/passages/{passage['passage_id']}")
        if response.status_code != 200:
            print(f"  [{number}] {passage['passage_id']}: GET passage answered {response.status_code}")
            continue
        view = response.json()
        if view["paper_id"] not in pdfs:
            pdf = client.get(f"/api/papers/{view['paper_id']}/pdf")
            pdfs[view["paper_id"]] = pdf.content if pdf.status_code == 200 and pdf.content.startswith(b"%PDF") else b""
        pdf_bytes = pdfs[view["paper_id"]]
        page_ok = False
        if pdf_bytes:
            with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
                page_ok = 1 <= view["page"] <= doc.page_count == view["page_count"]
        opened += page_ok
        layout = view["layout"]
        on_page = [r for r in layout["regions"] if r["page"] == view["page"]] if layout else []
        line = f"  [{number}] {view['title'][:40]} — {view['section']}, page {view['page']} of {view['page_count']}: "
        if not page_ok:
            print(line + "PDF or page missing")
            continue
        if not on_page:
            print(line + f"opens, not highlighted ({view['layout_reason']})")
            continue
        highlighted += 1
        under = words_under_regions(pdf_bytes, view["page"], on_page)
        passage_words = {w.lower() for w in _WORD.findall(view["text"])}
        found = [w for w in under if any(t.lower() in passage_words for t in _WORD.findall(w))]
        precision = len(found) / len(under) if under else 0.0
        precisions.append(precision)
        print(line + f"highlighted ({len(on_page)} line boxes, {len(under)} words; "
                     f"{precision:.0%} of them belong to the passage)")

    total = len(numbers)
    rate = highlighted / total if total else 0.0
    print(f"\nHighlight success rate: {highlighted} of {total} cited passages ({rate:.0%}); target {HIGHLIGHT_TARGET:.0%}")
    run.check(total > 0 and opened == total, f"every cited passage opens its PDF at the cited page ({opened}/{total}, SC-001)")
    run.check(total > 0 and rate >= HIGHLIGHT_TARGET, f"at least 90% of cited passages are highlighted ({rate:.0%}, SC-002)")
    if precisions:
        average = sum(precisions) / len(precisions)
        run.check(average >= 0.9, f"highlighted words belong to their passage ({average:.0%} on average)")


ATTACH_LIMIT = 10.0  # SC-004: attaching a PDF to a known paper
DUPLICATE_LIMIT = 3.0  # a renamed duplicate is recognised at once
NEW_PAPER_LIMIT = 60.0
JOB_POLL = 0.1
new_pdf: Path | None = None  # set by --new-pdf


class JobWatcher:
    """Reads GET /api/jobs/events on a thread and records each job's phases as they stream."""

    def __init__(self) -> None:
        self.phases: dict[str, list[str]] = {}
        self.connected = threading.Event()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._read, daemon=True)

    def _read(self) -> None:
        try:
            with httpx.Client(base_url=API, timeout=None) as client:
                with client.stream("GET", "/api/jobs/events") as response:
                    self.connected.set()
                    name = ""
                    for line in response.iter_lines():
                        if self.stop.is_set():
                            return
                        if line.startswith("event:"):
                            name = line[6:].strip()
                        elif line.startswith("data:") and name == "job":
                            job = json.loads(line[5:])
                            seen = self.phases.setdefault(job["job_id"], [])
                            if not seen or seen[-1] != job["phase"]:
                                seen.append(job["phase"])
        except httpx.HTTPError:
            pass

    def __enter__(self) -> "JobWatcher":
        self.thread.start()
        self.connected.wait(10.0)
        return self

    def __exit__(self, *exc) -> None:
        self.stop.set()  # the daemon thread ends at the next ping or with the script


def upload_and_wait(client: httpx.Client, name: str, data: bytes, timeout: float) -> tuple[dict | None, float]:
    """Upload one file and poll its job until ready or failed; return (job, or None on timeout; seconds)."""
    start = time.monotonic()
    response = client.post("/api/papers", files=[("files", (name, data, "application/pdf"))], headers=WRITE_HEADERS)
    if response.status_code != 202:
        print(f"  POST /api/papers answered {response.status_code}: {response.text[:200]}")
        return None, time.monotonic() - start
    job_id = response.json()["jobs"][0]["job_id"]
    while time.monotonic() - start < timeout:
        for job in client.get("/api/jobs").json()["jobs"]:
            if job["job_id"] == job_id and job["phase"] in ("ready", "failed"):
                return job, time.monotonic() - start
        time.sleep(JOB_POLL)
    return None, time.monotonic() - start


def describe(job: dict | None, watcher: JobWatcher) -> str:
    """A job's result and the phases streamed for it, for the log."""
    if job is None:
        return "no result (timed out)"
    phases = " → ".join(watcher.phases.get(job["job_id"], [])) or "no events seen"
    result = job["error"] if job["phase"] == "failed" else f"{job['outcome']}, highlights {job['highlights']}"
    return f"{result} [{phases}]"


def part_library(run: Run, client: httpx.Client) -> None:
    """US3: attach the PDFs of the existing papers, reject a non-PDF and spot a renamed
    duplicate (SC-004). 0 model requests."""
    pdfs = sorted((ROOT / "papers").glob("*.pdf"))
    if not pdfs:
        run.check(False, "there are PDFs in papers/ to upload")
        return
    with JobWatcher() as watcher:
        run.check(watcher.connected.is_set(), "GET /api/jobs/events is streaming")
        print(f"Uploading the {len(pdfs)} PDFs in papers/ one at a time:")
        for path in pdfs:
            job, seconds = upload_and_wait(client, path.name, path.read_bytes(), ATTACH_LIMIT + 20)
            print(f"  {path.name}: {describe(job, watcher)} in {seconds:.1f} s")
            ok = job is not None and (
                (job["outcome"] == "pdf_attached" and job["highlights"] == "exact")
                or job["outcome"] == "already_present"
            )
            run.check(ok and seconds <= ATTACH_LIMIT,
                      f"{path.name} ends pdf_attached (exact) or already_present within {ATTACH_LIMIT:.0f} s")

        print("Rejected and duplicate uploads:")
        job, seconds = upload_and_wait(client, "notes.pdf", b"These are plain-text notes, not a PDF.", 10.0)
        print(f"  notes.pdf (generated text): {describe(job, watcher)} in {seconds:.1f} s")
        run.check(job is not None and job["error"] == {"kind": "upload_invalid", "reason": "not_pdf"},
                  "a non-PDF file gives upload_invalid with reason not_pdf")
        copy_name = f"renamed copy of {pdfs[0].name}"
        job, seconds = upload_and_wait(client, copy_name, pdfs[0].read_bytes(), 10.0)
        print(f"  {copy_name}: {describe(job, watcher)} in {seconds:.1f} s")
        run.check(job is not None and job["outcome"] == "already_present" and seconds <= DUPLICATE_LIMIT,
                  f"a renamed duplicate gives already_present within {DUPLICATE_LIMIT:.0f} s")

        if new_pdf is not None:
            print(f"New paper: {new_pdf.name}")
            job, seconds = upload_and_wait(client, new_pdf.name, new_pdf.read_bytes(), NEW_PAPER_LIMIT + 30)
            print(f"  {new_pdf.name}: {describe(job, watcher)} in {seconds:.1f} s")
            phases = watcher.phases.get(job["job_id"], []) if job else []
            run.check(job is not None and job["outcome"] == "added" and seconds <= NEW_PAPER_LIMIT,
                      f"the new paper reaches Ready (added) within {NEW_PAPER_LIMIT:.0f} s")
            run.check(len(phases) - 1 >= 3, f"at least 3 phase changes were streamed ({max(len(phases) - 1, 0)})")
            if job is not None and job["outcome"] == "added":
                deleted = client.delete(f"/api/papers/{job['paper_id']}", headers=WRITE_HEADERS)
                run.check(deleted.status_code == 200,
                          f"the new paper is deleted again ({deleted.json().get('removed_passages')} passages)")

    papers = client.get("/api/papers").json()
    print(f"Library: {len(papers['papers'])} papers, {papers['total_passages']} passages")
    for card in papers["papers"]:
        print(f"  {card['title'][:60]}: {card['passage_count']} passages ({card['table_passages']} tables), "
              f"{card['section_count']} sections, arXiv {card['arxiv_id']}, highlights {card['highlights']}")
    run.check(all(card["has_pdf"] and card["highlights"] == "exact" for card in papers["papers"]),
              "every paper has its PDF with exact highlights")


STATES_KEY = "sk-checkpoint-states-not-a-real-key"
STATES_ENV = {
    "LLM_PROVIDER": "openrouter", "LLM_BASE_URL": "", "LLM_API_KEY": STATES_KEY,
    "LLM_MODEL": "checkpoint/scripted:free", "LLM_REASONING_EFFORT": "", "RELEVANCE_THRESHOLD": "0.0",
    "DAILY_REQUEST_LIMIT": "50", "CHUNK_WORDS": "220", "CHUNK_OVERLAP": "40", "MIN_CHUNK_WORDS": "30", "TOP_K": "6",
}
STATES_QUESTION = "Which evaluation dataset was used?"


def _blocked(*args, **kwargs):
    raise AssertionError("part states tried to reach the model or the provider")


def part_states(run: Run, client: httpx.Client) -> None:
    """US5: every error and answer state the API can produce, with its kind and safe fields.

    Runs the API in-process (TestClient) over a temporary library, with a scripted model and a
    fake embedder; real clients and the provider's key endpoint are blocked. 0 model requests.
    """
    sys.path.insert(0, str(ROOT / "tests"))
    import openai
    from fastapi.testclient import TestClient

    import fake_llm
    from conftest import ScriptedLLM, fake_vector, write_pdf
    from paperpilot import llm, prompts, store
    from paperpilot.errors import LLMError, RateLimitedError

    real_generate = llm.generate
    scripted = ScriptedLLM()
    bodies: list[str] = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder, ExitStack() as stack:
        library_dir = Path(folder) / "library"
        stack.enter_context(mock.patch.dict(os.environ, {**STATES_ENV, "LIBRARY_DIR": str(library_dir)}))
        for target, name, value in [
            (openai, "OpenAI", _blocked), (llm, "_make_client", _blocked), (llm, "_fetch_key_info", _blocked),
            (llm, "generate", scripted), (store, "load_model", lambda: 0.0), (store, "embed_query", fake_vector),
            (store, "embed_passages", lambda texts, on_progress=None: [fake_vector(t) for t in texts]),
        ]:
            stack.enter_context(mock.patch.object(target, name, value))
        store.reset_cache()
        stack.callback(store.reset_cache)
        from api.main import create_app
        from paperpilot.library import add_paper

        add_paper(write_pdf(Path(folder) / "paper.pdf"))
        before = llm.request_counts()
        with TestClient(create_app(), base_url=API) as app:
            deadline = time.monotonic() + 30
            while app.get("/api/status").json()["state"] != "ready" and time.monotonic() < deadline:
                time.sleep(0.05)

            def ask(*replies) -> tuple[str, dict, list]:
                scripted.add(*replies)
                with app.stream("POST", "/api/ask", json={"question": STATES_QUESTION}, headers=WRITE_HEADERS) as r:
                    text = "".join(r.iter_text())
                bodies.append(text)
                events = parse_events(text)
                name, data = events[-1]
                return name, data, events

            def show(state: str, name: str, data: dict) -> None:
                shown = {k: v for k, v in data.items() if k in (
                    "kind", "reason", "attempts", "used", "limit", "resets_at", "until", "daily", "passage_id",
                    "fallback_reason", "verified", "rejected_answer", "warning")}
                if name == "answer":
                    shown["uncited_sentences"] = data["citations"]["uncited_sentences"]
                print(f"  {state}: {name} {json.dumps(shown, ensure_ascii=False)}")

            name, data, _ = ask(prompts.NOT_FOUND)
            show("not found", name, data)
            run.check(name == "answer" and data["not_found"] and not data["verified"]
                      and data["fallback_reason"] == "model_not_found",
                      "not found: an unverified answer event with fallback_reason model_not_found")

            notice = llm.RetryNotice(attempt=1, max_attempts=4, wait_seconds=8.0, reason="rate_limited")
            name, data, events = ask(notice, LLMError("provider text that must not leak", reason="busy"))
            waits = [d for n, d in events if n == "retry_wait"]
            print(f"  retry wait: retry_wait {json.dumps(waits[0]) if waits else None}")
            show("model busy", name, data)
            run.check(waits == [{"attempt": 1, "max_attempts": 4, "wait_seconds": 8.0, "reason": "rate_limited"}],
                      "retry wait: the countdown's attempt, wait and reason are streamed")
            run.check((name, data) == ("error", {"kind": "model_busy", "attempts": llm.MAX_ATTEMPTS}),
                      "model busy: error model_busy with attempts")

            with mock.patch.dict(os.environ, {"DAILY_REQUEST_LIMIT": "1"}):
                llm.count_request()  # the temporary library's counter only
                fake_client = fake_llm.FakeClient([fake_llm.ok("never sent [1].")])
                with mock.patch.object(llm, "_make_client", lambda settings: fake_client), \
                        mock.patch.object(llm, "generate", real_generate):
                    name, data, _ = ask()
            show("daily limit", name, data)
            run.check(name == "error" and data["kind"] == "daily_limit" and (data["used"], data["limit"]) == (1, 1)
                      and data["resets_at"].endswith("T00:00:00Z"),
                      "daily limit: error daily_limit with used, limit and the next UTC midnight")
            run.check(fake_client.calls == [], "daily limit: the pre-check sent no request (0 generate calls)")

            until = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=90)
            for daily in (False, True):
                name, data, _ = ask(RateLimitedError(until, daily=daily))
                show(f"rate limited ({'daily' if daily else 'not daily'})", name, data)
                run.check(name == "error" and data == {"kind": "rate_limited", "until": until.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                       "daily": daily},
                          f"rate limited: error rate_limited with until and daily={str(daily).lower()}")

            held = "Evaluated on a benchmark [99]."
            name, data, _ = ask(held)
            show("held back", name, data)
            run.check(name == "answer" and not data["verified"] and data["rejected_answer"] == held
                      and data["citations"]["invalid"] == [99],
                      "held back: an unverified answer carrying the rejected text and invalid citation 99")

            name, data, _ = ask("Evaluated on a benchmark dataset of questions [1]. It was also very fast.")
            show("uncited sentence", name, data)
            run.check(name == "answer" and data["verified"] and data["citations"]["uncited_sentences"],
                      "uncited sentence: a verified answer that flags the sentence without a citation")

            name, data, _ = ask(LLMError(f"401 for key {STATES_KEY}", reason="bad_key"))
            show("model unavailable", name, data)
            run.check((name, data) == ("error", {"kind": "model_unavailable", "reason": "bad_key"}),
                      "model unavailable: error model_unavailable with reason bad_key")

            response = app.get("/api/passages/0000000000-1")
            bodies.append(response.text)
            print(f"  unknown passage: HTTP {response.status_code} {response.text}")
            run.check(response.status_code == 404 and response.json() == {"kind": "unknown_passage",
                                                                           "passage_id": "0000000000-1"},
                      "unknown passage: 404 unknown_passage")

            response = app.post("/api/papers", files=[("files", ("notes.pdf", b"plain text", "application/pdf"))],
                                headers=WRITE_HEADERS)
            bodies.append(response.text)
            job_id = response.json()["jobs"][0]["job_id"]
            job = next(j for j in app.get("/api/jobs").json()["jobs"] if j["job_id"] == job_id)
            print(f"  upload invalid: job {job['phase']} {json.dumps(job['error'])}")
            run.check(job["phase"] == "failed" and job["error"] == {"kind": "upload_invalid", "reason": "not_pdf"},
                      "upload invalid: a failed job with upload_invalid and reason not_pdf")

        used = llm.request_counts() - before
        leaks = [b for b in bodies if STATES_KEY in b or "Traceback" in b or "must not leak" in b]
        run.check(not leaks, f"no response carried the key, a traceback or provider text ({len(bodies)} checked)")
        run.check(used.total == 0 and scripted.queue == [],
                  f"states: {used.total} model requests counted by the engine; every scripted reply was used")


def part_usage(run: Run, client: httpx.Client) -> None:
    """US5: GET /api/usage agrees with scripts/usage.py (FR-024). 0 model requests."""
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "usage.py")], capture_output=True,
                            text=True, encoding="utf-8", timeout=60)
    print(result.stdout.rstrip())
    fields = dict(re.findall(r"^(Used today|Remaining|Resets at|Source):\s+(.*)$", result.stdout, re.MULTILINE))
    used = re.match(r"(\d+) / (\d+)", fields.get("Used today", ""))
    api = client.get("/api/usage").json()
    print(f"GET /api/usage: {api}")
    if result.returncode != 0 or used is None:
        run.check(False, f"scripts/usage.py ran (exit {result.returncode}): {result.stderr.strip()[:200]}")
        return
    resets = datetime.strptime(api["resets_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M UTC")
    source = "the provider" if api["source"] == "provider" else "PaperPilot local count"
    run.check((int(used[1]), int(used[2]), int(fields["Remaining"])) == (api["used"], api["limit"], api["remaining"]),
              f"used, limit and remaining agree ({api['used']} / {api['limit']}, {api['remaining']} left)")
    run.check(fields["Resets at"].startswith(resets) and fields["Source"] == source,
              f"reset time and source agree ({resets}, {api['source']})")


SCOPE_QUESTION = "What data was BERT pre-trained on?"
FOLLOW_UP = "What are its limitations?"
# The earlier turn when part ask did not run: the follow-up only needs a conversation to refer to.
LORA_TURN_FALLBACK = (
    "LoRA freezes the pretrained model weights and injects trainable low-rank decomposition matrices "
    "into each layer, which greatly reduces the number of trainable parameters."
)


def stream_answer(run: Run, client: httpx.Client, body: dict) -> dict | None:
    """POST /api/ask, print its progress, add its requests to the run; the answer or None."""
    start = time.monotonic()
    with client.stream("POST", "/api/ask", json=body, headers=WRITE_HEADERS, timeout=ASK_TIMEOUT) as response:
        text = "".join(response.iter_text())
    if response.status_code != 200:
        run.check(False, f"POST /api/ask answered {response.status_code}: {text[:200]}")
        return None
    events = parse_events(text)
    steps = [data["step"] for name, data in events if name == "progress"]
    waits = [data for name, data in events if name == "retry_wait"]
    print(f"  progress: {', '.join(steps)}" + (f"; {len(waits)} retry wait(s)" if waits else ""))
    name, data = events[-1] if events else ("", {})
    if name != "answer":
        run.check(False, f"the question ended with {name or 'nothing'}: {data}")
        return None
    run.add_requests(data["requests"])
    print(f"  {data['word_count']} words in {time.monotonic() - start:.1f} s; requests "
          f"{data['requests']['planned']} planned, {data['requests']['retries']} retries")
    return data


def part_scope(run: Run, client: httpx.Client) -> None:
    """US4: a question scoped to BERT cites only BERT; a follow-up is rewritten to a standalone
    question naming LoRA (FR-007–FR-009). 3 requests: 1 answer, then 1 rewrite + 1 answer."""
    papers = client.get("/api/papers").json()["papers"]
    bert = next((p for p in papers if p["title"].lower().startswith("bert")), None)
    if bert is None:
        run.check(False, "the BERT paper is in the library")
        return
    print(f"Scoped question (BERT only, {bert['paper_id']}): {SCOPE_QUESTION}")
    answer = stream_answer(run, client, {"question": SCOPE_QUESTION, "paper_ids": [bert["paper_id"]]})
    if answer is not None:
        print(f"  Answer: {answer['text']}")
        sources = {p["paper_id"] for p in answer["passages"]}
        run.check(bool(answer["passages"]) and sources == {bert["paper_id"]},
                  f"every passage comes from BERT ({len(answer['passages'])} passages from {len(sources)} paper)")
        run.check(not answer["citations"]["invalid"] and not answer["not_found"],
                  f"the scoped answer is found and its citations are valid (verified {answer['verified']})")

    if run.answer is not None:
        previous = run.answer["text"]
        run.info("the follow-up's history is part ask's LoRA answer")
    else:
        previous = LORA_TURN_FALLBACK
        run.info("part ask did not run: the follow-up's history uses a fixed LoRA summary (no request)")
    history = [{"role": "user", "text": ASK_QUESTION}, {"role": "assistant", "text": previous}]
    print(f"Follow-up after \"{ASK_QUESTION}\": {FOLLOW_UP}")
    answer = stream_answer(run, client, {"question": FOLLOW_UP, "history": history})
    if answer is None:
        return
    print(f"  Searched as: {answer['standalone_question']}")
    print(f"  Answer: {answer['text']}")
    run.check(answer["rewrite_applied"] and "lora" in answer["standalone_question"].lower(),
              "the follow-up was rewritten to a standalone question that names LoRA")
    run.check(not answer["citations"]["invalid"],
              f"the follow-up's citations are valid (valid {answer['citations']['valid']}, verified {answer['verified']})")


ALLOWED_PUBLIC_VARS = {"NEXT_PUBLIC_API_URL"}  # nothing secret may be NEXT_PUBLIC_ (inlined in the bundle)
IGNORED_PATHS = ["data/library/pdfs/x.pdf", "data/library/usage.sqlite3", "data/library/results.sqlite3"]
BUILD_TIMEOUT = 600


def files_containing(folder: Path, needle: bytes, skip: Path | None = None) -> tuple[list[Path], list[Path]]:
    """(files under folder whose bytes contain needle, files that could not be read)."""
    found, unreadable = [], []
    for path in folder.rglob("*"):
        if not path.is_file() or (skip is not None and path.is_relative_to(skip)):
            continue
        try:
            if needle in path.read_bytes():
                found.append(path)
        except OSError:
            unreadable.append(path)
    return found, unreadable


def part_secrets(run: Run, client: httpx.Client) -> None:
    """The API key never reaches the browser, a response or the logs (SC-010). 0 requests.
    Prints PASS/FAIL lines only, never the key."""
    settings = load_settings()
    key = settings.llm_api_key.encode()
    if not key:
        run.check(False, "LLM_API_KEY is set (there is nothing to look for without it)")
        return
    npm = shutil.which("npm")
    if npm is None:
        run.check(False, "npm is on PATH to build the frontend")
        return
    print("Building the frontend (npm --prefix frontend run build)…")
    start = time.monotonic()
    build = subprocess.run([npm, "--prefix", str(ROOT / "frontend"), "run", "build"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=BUILD_TIMEOUT)
    run.check(build.returncode == 0, f"the frontend builds ({time.monotonic() - start:.0f} s)")
    if build.returncode != 0:
        print(build.stdout[-2000:].replace(settings.llm_api_key, "***"))
        return

    # .next/dev is a running dev server's own workspace (locked files), not the built app.
    built = ROOT / "frontend" / ".next"
    leaked, unreadable = files_containing(built, key, skip=built / "dev")
    run.check(not leaked and not unreadable,
              f"the key is in no file of the build in frontend/.next/ ({len(leaked)} found, {len(unreadable)} unreadable)")
    captured = run.captured or []
    run.check(all(key not in body for body in captured),
              f"the key is in none of the {len(captured)} API responses captured in this run")
    log = settings.library_dir / "api.log"
    run.check(log.exists() and key not in log.read_bytes(), f"the key is not in the API log ({log.name})")
    env_local = ROOT / "frontend" / ".env.local"
    run.check(not env_local.exists() or (key not in env_local.read_bytes() and b"LLM_API_KEY" not in env_local.read_bytes()),
              "frontend/.env.local holds no key")

    used: set[str] = set()
    for folder in ("app", "components", "lib"):
        for path in (ROOT / "frontend" / folder).rglob("*.ts*"):
            used.update(re.findall(r"NEXT_PUBLIC_[A-Z0-9_]+", path.read_text(encoding="utf-8")))
    for config in (ROOT / "frontend").glob("next.config.*"):
        used.update(re.findall(r"NEXT_PUBLIC_[A-Z0-9_]+", config.read_text(encoding="utf-8")))
    run.check(used <= ALLOWED_PUBLIC_VARS, f"the only NEXT_PUBLIC_ variable in use is NEXT_PUBLIC_API_URL ({sorted(used)})")

    for path in IGNORED_PATHS:
        ignored = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode == 0
        run.check(ignored, f"git ignores {path}")


PARTS: dict[str, Part] = {
    "boundary": Part(plan=0, run=part_boundary),
    "ask": Part(plan=1, run=part_ask),
    "viewer": Part(plan=0, run=part_viewer),
    "library": Part(plan=0, run=part_library),
    "scope": Part(plan=3, run=part_scope),
    "states": Part(plan=0, run=part_states),
    "usage": Part(plan=0, run=part_usage),
    "secrets": Part(plan=0, run=part_secrets),  # last: it checks every response captured before it
}


def main() -> int:
    """Run the selected parts; return 0 if every check passes."""
    global new_pdf
    args = sys.argv[1:]
    if "--new-pdf" in args:
        index = args.index("--new-pdf")
        if index + 1 >= len(args) or not Path(args[index + 1]).is_file():
            print("--new-pdf needs the path of a PDF file")
            return 2
        new_pdf = Path(args[index + 1])
        del args[index:index + 2]
    names = [a.lower() for a in args] or list(PARTS)
    unknown = [n for n in names if n not in PARTS]
    if unknown:
        print(f"Unknown part(s) {unknown}; choose from {', '.join(PARTS)} (default: all)")
        return 2

    print("Checkpoint 6: web app")
    run = Run(results=[], used=RequestCounts(0, 0))
    run.captured = []

    def capture(response: httpx.Response) -> None:
        response.read()  # streamed bodies stay readable: httpx keeps the content once read
        run.captured.append(response.content)

    with httpx.Client(base_url=API, timeout=30.0, event_hooks={"response": [capture]}) as client:
        status = wait_until_ready(client)
        if status is None:
            run.check(False, f"the API is reachable at {API} (start it with: python -m api)")
        elif status.get("state") != "ready":
            run.check(False, f"the API is ready (state: {status.get('state')}; see data/library/api.log)")
        else:
            run.check(True, f"the API is ready (model {status['model']})")
            for name in names:
                print(f"\n=== Part: {name} (planned model requests: {PARTS[name].plan})")
                PARTS[name].run(run, client)

    plan = sum(PARTS[name].plan for name in names)
    used = run.used
    print(f"\nLLM requests: {used.total} ({used.planned} planned, {used.retries} retries; plan {plan})")
    for passed, description in budget_checks("checkpoint 6", used, plan):
        run.check(passed, description)
    all_passed = all(passed for passed, _ in run.results)
    print(f"\n{'PASS' if all_passed else 'FAIL'}: checkpoint 6 automated checks")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
