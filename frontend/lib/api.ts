// Typed client for the PaperPilot API. Errors are reported as kinds only; the UI owns all
// wording and never shows server text (FR-022, research R10).

const DEFAULT_API_URL = "http://127.0.0.1:8000";

/** Sent on every write: the API refuses state-changing requests without it (FR-002b). A custom
 *  header forces a CORS preflight, which only PaperPilot's own origins pass. */
export const WRITE_HEADERS = { "X-PaperPilot": "1" } as const;

/** An error from the API (or the network), identified by its kind. */
export class ApiError extends Error {
  readonly kind: string;
  readonly status: number;
  readonly fields: Record<string, unknown>;

  constructor(kind: string, status: number, fields: Record<string, unknown> = {}) {
    super(`PaperPilot API error: ${kind}`);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.fields = fields;
  }
}

/** Absolute URL for an API path, from NEXT_PUBLIC_API_URL (default http://127.0.0.1:8000). */
export function apiUrl(path: string): string {
  const base = (process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL).replace(/\/+$/, "");
  return `${base}${path}`;
}

/** fetch() that turns a network failure into ApiError("unreachable"). */
export async function apiFetch(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(apiUrl(path), init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("unreachable", 0);
  }
}

/** Build an ApiError from a non-OK response: its JSON kind, or "internal" for anything else. */
export async function errorFrom(response: Response): Promise<ApiError> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && typeof (body as { kind?: unknown }).kind === "string") {
      const { kind, ...fields } = body as { kind: string } & Record<string, unknown>;
      return new ApiError(kind, response.status, fields);
    }
  } catch {
    // Not JSON: fall through. The text is never shown.
  }
  return new ApiError("internal", response.status);
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, headers: { Accept: "application/json" } };
  if (method !== "GET") {
    init.headers = { ...init.headers, ...WRITE_HEADERS };
  }
  if (body !== undefined) {
    init.headers = { ...init.headers, "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const response = await apiFetch(path, init);
  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as T;
}

/** GET a JSON resource. */
export function apiGet<T>(path: string): Promise<T> {
  return request<T>("GET", path);
}

/** POST a JSON body and return the JSON response. */
export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>("POST", path, body);
}

/** DELETE a resource and return the JSON response. */
export function apiDelete<T>(path: string): Promise<T> {
  return request<T>("DELETE", path);
}

/** POST /api/papers: every file in one multipart request; each gets its own job (FR-016). */
export async function uploadPapers(files: File[]): Promise<{ jobs: { job_id: string; file_name: string }[] }> {
  const body = new FormData();
  for (const file of files) body.append("files", file);
  const response = await apiFetch("/api/papers", {
    method: "POST",
    headers: { Accept: "application/json", ...WRITE_HEADERS },
    body,
  });
  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as { jobs: { job_id: string; file_name: string }[] };
}
