"""Checkpoint 6: the web app end to end over HTTP (Feature 3).

Talks to the running API (http://127.0.0.1:8000) and frontend (http://127.0.0.1:3000). Each part
states its planned model requests; the run fails on unplanned requests or when all requests,
retries included, exceed twice the plan (scripts/request_budget.py, Feature 2 budget rule).

Usage: python scripts/checkpoint_6_web.py [part ...]   (default: every part)
Parts: boundary, ask

Start the servers first (quickstart): `python -m api` and `npm --prefix frontend run dev`.
"""

import json
import socket
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
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


PARTS: dict[str, Part] = {
    "boundary": Part(plan=0, run=part_boundary),
    "ask": Part(plan=1, run=part_ask),
}


def main() -> int:
    """Run the selected parts; return 0 if every check passes."""
    names = [a.lower() for a in sys.argv[1:]] or list(PARTS)
    unknown = [n for n in names if n not in PARTS]
    if unknown:
        print(f"Unknown part(s) {unknown}; choose from {', '.join(PARTS)} (default: all)")
        return 2

    print("Checkpoint 6: web app")
    run = Run(results=[], used=RequestCounts(0, 0))
    with httpx.Client(base_url=API, timeout=30.0) as client:
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
