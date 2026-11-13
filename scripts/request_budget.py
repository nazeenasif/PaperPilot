"""Request budget checks shared by the checkpoint scripts (no side effects on import).

A checkpoint plans a number of model calls. Planned requests (first attempts) above the plan
mean the script made a call it did not plan: FAIL. Retries are expected on free tiers and are
reported; the run fails on them only when all requests together exceed SAFETY_FACTOR × plan.
"""

from paperpilot.llm import RequestCounts

SAFETY_FACTOR = 2


def _retries(n: int) -> str:
    return f"{n} retry" if n == 1 else f"{n} retries"


def budget_checks(label: str, used: RequestCounts, plan: int) -> list[tuple[bool, str]]:
    """Return (passed, description) for the planned-request limit and the total safety cap."""
    cap = SAFETY_FACTOR * plan
    return [
        (used.planned <= plan, f"{label}: {used.planned} planned requests (plan {plan})"),
        (used.total <= cap,
         f"{label}: {used.total} requests in total, {_retries(used.retries)} (safety cap {cap})"),
    ]
