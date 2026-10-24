"""Upload and re-process jobs (data-model.md UploadJob, spec FR-016–FR-018a).

One worker thread processes jobs in arrival order, so ingestion never competes with itself and
never blocks questions. Uploads are read in chunks into <LIBRARY_DIR>/tmp/<job id>/ and checked
for size and the PDF signature before they are queued; a rejected file still gets a job, failed
at once, so every dropped file has a row. Every change is fanned out to the SSE subscribers of
GET /api/jobs/events. Jobs live in memory only.
"""

import asyncio
import logging
import queue
import re
import shutil
import threading
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile

from api.errors import ApiError, iso_utc
from paperpilot import ingest, library
from paperpilot.errors import (
    NoTextError,
    PaperPilotError,
    PasswordProtectedError,
    PdfMissingError,
    PdfReadError,
    StorageError,
    UnknownPaperError,
)

logger = logging.getLogger("api")

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # enforced while reading (contracts/web-api.md)
READ_CHUNK_BYTES = 1024 * 1024
PDF_SIGNATURE = b"%PDF-"
KEEP_FINISHED_SECONDS = 3600  # finished jobs older than this are dropped
TMP_FOLDER = "tmp"
STOP_TIMEOUT_SECONDS = 10.0


@dataclass
class Job:
    """One upload or re-process, as shown in the Library's upload list."""

    job_id: str
    kind: str  # "upload" or "reprocess"
    file_name: str  # display only; never used as a path
    phase: str = "queued"
    percent: int | None = None
    outcome: str | None = None
    highlights: str | None = None
    paper_id: str | None = None
    error: dict | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: Path | None = field(default=None, repr=False)  # the temporary upload file

    @property
    def finished(self) -> bool:
        return self.phase in ("ready", "failed")

    def body(self) -> dict:
        """The UploadJob payload sent to the browser."""
        return {
            "job_id": self.job_id, "kind": self.kind, "file_name": self.file_name, "phase": self.phase,
            "percent": self.percent, "outcome": self.outcome, "highlights": self.highlights,
            "paper_id": self.paper_id, "error": self.error, "created_at": iso_utc(self.created_at),
        }


def _safe_name(file_name: str) -> str:
    """A plain file name for the temporary copy (it becomes the paper's source_file)."""
    name = re.sub(r"[^A-Za-z0-9._ ()-]", "_", file_name.replace("\\", "/").rsplit("/", 1)[-1])[:120]
    return name.lstrip(". ") or "upload.pdf"


def _failure(error: PaperPilotError, job: Job) -> dict:
    """The error shown on a failed job's row."""
    if isinstance(error, PasswordProtectedError):
        return {"kind": "upload_invalid", "reason": "password"}
    if isinstance(error, PdfReadError):
        return {"kind": "upload_invalid", "reason": "unreadable"}
    if isinstance(error, NoTextError):
        return {"kind": "upload_invalid", "reason": "no_text"}
    if isinstance(error, StorageError):
        return {"kind": "upload_invalid", "reason": "storage"}
    if isinstance(error, PdfMissingError):
        return {"kind": "pdf_missing", "paper_id": job.paper_id}
    if isinstance(error, UnknownPaperError):  # deleted while its re-process was queued
        return {"kind": "unknown_paper", "paper_id": job.paper_id}
    logger.error("Job %s failed", job.job_id, exc_info=error)
    return {"kind": "internal"}


class JobRegistry:
    """The jobs, the single ingest worker and the subscribers of the jobs event stream."""

    def __init__(self, library_dir: Path) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._queue: queue.Queue[Job | None] = queue.Queue()
        self._subscribers: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []
        self._tmp = Path(library_dir) / TMP_FOLDER
        self._worker: threading.Thread | None = None

    # --- lifecycle ---

    def start(self) -> None:
        self._worker = threading.Thread(target=self._run, name="paperpilot-ingest", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        """End every event stream and let the worker finish its current job."""
        self.close_streams()
        self._queue.put(None)
        if self._worker is not None:
            self._worker.join(timeout=STOP_TIMEOUT_SECONDS)

    # --- adding jobs ---

    async def add_upload(self, upload: UploadFile) -> Job:
        """Copy an uploaded file to a temporary folder in chunks, check it and queue it."""
        job = Job(uuid.uuid4().hex, "upload", upload.filename or "upload.pdf")
        folder = self._tmp / job.job_id
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / _safe_name(job.file_name)
        size, head, reason = 0, b"", None
        with target.open("wb") as out:
            while chunk := await upload.read(READ_CHUNK_BYTES):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    reason = "too_large"
                    break
                head += chunk[: len(PDF_SIGNATURE) - len(head)]
                out.write(chunk)
        if reason is None and head != PDF_SIGNATURE:
            reason = "not_pdf"
        if reason is not None:
            shutil.rmtree(folder, ignore_errors=True)
            job.phase, job.outcome = "failed", "failed"
            job.error = {"kind": "upload_invalid", "reason": reason}
            self._register(job)
            return job
        job.source = target
        job.paper_id = ingest.paper_id_for(target.read_bytes())
        self._register(job)
        self._queue.put(job)
        return job

    def add_reprocess(self, paper_id: str, title: str) -> Job:
        """Queue a re-process; 409 busy_job if a job for the paper is already queued or running."""
        with self._lock:
            if any(job.paper_id == paper_id and not job.finished for job in self._jobs.values()):
                raise ApiError("busy_job", paper_id=paper_id)
            job = Job(uuid.uuid4().hex, "reprocess", title, paper_id=paper_id)
            self._jobs[job.job_id] = job
            body = job.body()
        self._publish(body)
        self._queue.put(job)
        return job

    def _register(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.job_id] = job
            body = job.body()
        self._publish(body)

    # --- reading jobs ---

    def snapshot(self) -> list[dict]:
        """Every job in arrival order; finished jobs older than an hour are dropped."""
        cutoff = time.time() - KEEP_FINISHED_SECONDS
        with self._lock:
            for job_id, job in list(self._jobs.items()):
                if job.finished and job.created_at.timestamp() < cutoff:
                    del self._jobs[job_id]
            return [job.body() for job in self._jobs.values()]

    async def events(self) -> AsyncIterator[dict]:
        """Unfinished jobs first, then every change, until close_streams() or disconnect."""
        loop = asyncio.get_running_loop()
        inbox: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._subscribers.append((loop, inbox))
            pending = [job.body() for job in self._jobs.values() if not job.finished]
        try:
            for body in pending:
                yield body
            while (body := await inbox.get()) is not None:
                yield body
        finally:
            with self._lock:
                self._subscribers.remove((loop, inbox))

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def close_streams(self) -> None:
        """End every open event stream (shutdown)."""
        self._publish(None)

    def _publish(self, body: dict | None) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for loop, inbox in subscribers:
            try:
                loop.call_soon_threadsafe(inbox.put_nowait, body)
            except RuntimeError:  # the subscriber's loop has closed
                pass

    def _update(self, job: Job, **changes: object) -> None:
        with self._lock:
            for name, value in changes.items():
                setattr(job, name, value)
            body = job.body()
        self._publish(body)

    # --- the worker ---

    def _run(self) -> None:
        while (job := self._queue.get()) is not None:
            try:
                self._process(job)
            except Exception as error:  # never let one job stop the worker
                logger.error("Job %s failed unexpectedly", job.job_id, exc_info=error)
                self._update(job, phase="failed", percent=None, outcome="failed", error={"kind": "internal"})
            finally:
                if job.source is not None:
                    shutil.rmtree(job.source.parent, ignore_errors=True)

    def _process(self, job: Job) -> None:
        def report(phase: str, percent: int | None) -> None:
            if phase != "ready":  # the final state is set from the result below
                self._update(job, phase=phase, percent=percent)

        try:
            if job.kind == "upload":
                result = library.add_paper(job.source, on_progress=report)
            else:
                result = library.reprocess_paper(job.paper_id, on_progress=report)
        except PaperPilotError as error:
            self._update(job, phase="failed", percent=None, outcome="failed", error=_failure(error, job))
            return
        self._update(job, phase="ready", percent=None, outcome=result.outcome, highlights=result.highlights,
                     paper_id=result.paper_id)
