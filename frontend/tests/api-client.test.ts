import { describe, expect, it, vi } from "vitest";

import { ApiError, apiDelete, apiGet, apiPost, apiUrl } from "@/lib/api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("apiUrl", () => {
  it("defaults to the local API on 127.0.0.1:8000", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    expect(apiUrl("/api/status")).toBe("http://127.0.0.1:8000/api/status");
  });

  it("uses NEXT_PUBLIC_API_URL without a trailing slash", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://127.0.0.1:8100/");
    expect(apiUrl("/api/status")).toBe("http://127.0.0.1:8100/api/status");
  });
});

describe("apiGet", () => {
  it("returns the parsed JSON body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ state: "ready" }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(apiGet<{ state: string }>("/api/status")).resolves.toEqual({ state: "ready" });
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/api/status", expect.objectContaining({ method: "GET" }));
  });

  it("turns an error body into an ApiError with its kind, status and fields", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ kind: "not_ready", state: "loading" }, 503)));
    const error = await apiGet("/api/papers").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ kind: "not_ready", status: 503, fields: { state: "loading" } });
  });

  it("reports a network failure as kind unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(apiGet("/api/status")).rejects.toMatchObject({ kind: "unreachable", status: 0 });
  });

  it("reports a non-JSON error body as kind internal, never its text", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Traceback (most recent call last)", { status: 500 })));
    const error = (await apiGet("/api/status").catch((e: unknown) => e)) as ApiError;
    expect(error.kind).toBe("internal");
    expect(error.message).not.toContain("Traceback");
  });
});

describe("apiPost and apiDelete", () => {
  it("sends a JSON body with a JSON content type", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ results: [] }));
    vi.stubGlobal("fetch", fetchMock);
    await apiPost("/api/search", { query: "LoRA" });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ query: "LoRA" }));
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
  });

  it("uses DELETE for apiDelete", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ removed_passages: 3 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(apiDelete("/api/papers/abc")).resolves.toEqual({ removed_passages: 3 });
    expect((fetchMock.mock.calls[0] as [string, RequestInit])[1].method).toBe("DELETE");
  });
});
