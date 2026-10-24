# ADR-0003: LLM Boundary and Retry Policy

> **Scope**: Document decision clusters, not individual technology choices. Group related decisions that work together (e.g., "Frontend Stack" not separate ADRs for framework, styling, deployment).

- **Status:** Accepted
- **Date:** 2026-10-24
- **Feature:** 002-grounded-qa-citations
- **Context:** Feature 2 is the first to call a language model. The constitution requires a
  free-tier model, selection by settings, and exactly one module that talks to the LLM
  (Principles II, III). Free tiers are rate-limited (OpenRouter `:free` models: 20 requests
  per minute, 50 per day under $10 of lifetime credits, 1,000 per day after), and current free
  models are reasoning models whose hidden reasoning counts against the output limit, so an
  answer can come back cut off or empty. The API key must never appear in output, logs,
  errors or commits (Principle VI). The first design used Google's `google-genai` SDK for
  Gemini; on 2026-10-24 it was replaced, before any code was written, by a provider-neutral
  design.

## Decision

- **Client**: one `openai.OpenAI(api_key, base_url, timeout=60 s, max_retries=0)` created
  lazily in `paperpilot/llm.py`, the only module importing `openai`. Calls are
  `chat.completions.create` with a system message (rules) and a user message (passages and
  question), `temperature=0`, `max_tokens=2048`.
- **Configuration**: `LLM_PROVIDER` (label, default `openrouter`), `LLM_BASE_URL` (default
  `https://openrouter.ai/api/v1` for `openrouter`), `LLM_API_KEY`, `LLM_MODEL` (default pinned
  free model `nvidia/nemotron-3-ultra-550b-a55b:free` since 2026-10-24, after the first real runs; first pin `google/gemma-4-31b-it:free` kept as
  the alternative for a model comparison), optional `LLM_REASONING_EFFORT` sent as
  `extra_body={"reasoning": {"effort": ...}}`. Any OpenAI-compatible provider (Groq, OpenAI,
  a local server) is used by changing settings only.
- **Retry policy** (own code, SDK retries off): up to 4 attempts; retry on 408, 429, 500,
  502, 503, 504, timeouts, connection errors, and 200 responses whose body carries an `error`
  object with a retryable code. Wait `Retry-After` seconds, else until `X-RateLimit-Reset`,
  capped at 60 s; otherwise 2, 4, 8 s. Never retry 400, 401, 403, 404, or 402 without
  `Retry-After`. `retry_wait()` is a pure function; the sleep is injectable for tests.
  Every retry is logged at WARNING with the attempt number, a short reason (HTTP 429,
  timeout, connection error, error in a 200 response with its code, or the status code) and
  the wait, never the key, prompt or provider message. First attempts and retries are counted
  separately (`request_counts()`) so checkpoints can budget them differently.
- **Cut-off output**: `finish_reason == "length"` or empty content raises `LLMError` with a
  hint (lower `LLM_REASONING_EFFORT` or change model); it is never returned as an answer and
  never retried.
- **Errors and secrets**: every failure surfaces as one readable `LLMError` or
  `SettingsError` line; messages pass through a scrubber that replaces the key; the key is a
  `repr=False` setting shown only as "set (hidden)"; prompts, headers and full answers are not
  logged; a checkpoint greps the repository for the key value.

## Consequences

### Positive

- Provider-neutral: switching to another OpenAI-compatible provider or model is a settings
  change, which satisfies the "swappable" intent of Principle III better than a vendor SDK.
- One widely used, typed client; no Google-specific code paths.
- Free-tier rate limits are handled by waiting exactly as long as the server asks, which
  short fixed backoffs cannot do for per-minute limits.
- Cut-off reasoning output fails loudly instead of producing empty or partial answers.
- The retry logic is small, pure and unit-tested offline.

### Negative

- Required amending constitution Principle III (v1.2.0, 2026-10-24) from "Gemini or Groq"
  to "any model behind an OpenAI-compatible API, free tier by default".
- OpenRouter adds a routing intermediary: occasional 502/503 from upstream providers, and
  errors that arrive as 200 responses must be checked in the body.
- Free models change often; the pinned model can disappear and must be updated in settings.
- 50 requests per day without credits limits repeated checkpoint runs; evaluation runs need
  the 1,000/day tier.
- Waiting up to 60 s per retry can make a single question slow under rate limiting.
- `X-RateLimit-Reset` units are taken from documentation and must be confirmed on a real 429.

## Alternatives Considered

- **Alternative A — `google-genai` SDK with Gemini only** (the first design): official SDK
  with server retry hints and thinking controls, but ties `llm.py` to one vendor's API and
  types; adding any other provider means a second adapter. Rejected on 2026-10-24.
- **Alternative B — provider registry with one adapter per vendor SDK** (Gemini, Groq, …):
  maximum use of vendor features, but more code and dependencies for no benefit when all
  candidates speak the OpenAI chat format.
- **Alternative C — rely on the `openai` SDK's built-in retries** (`max_retries=2`): less
  code, but its backoff is short and fixed, it ignores `X-RateLimit-Reset`, and it is harder
  to test and to report clearly.
- **Alternative D — LangChain/LiteLLM wrappers**: provider abstraction for free, but forbidden
  by Principle I (no LangChain) and hides the retry and error behaviour this project must
  explain.

## References

- Feature Spec: specs/002-grounded-qa-citations/spec.md (FR-013, FR-014, FR-014a, FR-015)
- Implementation Plan: specs/002-grounded-qa-citations/plan.md
- Related ADRs: ADR-0001 (Local Retrieval Stack), ADR-0004 (Grounding and Citation Validation)
- Evaluator Evidence: specs/002-grounded-qa-citations/research.md R1–R4, R12;
  history/prompts/002-grounded-qa-citations/5-switch-to-openai-compatible-provider.plan.prompt.md
