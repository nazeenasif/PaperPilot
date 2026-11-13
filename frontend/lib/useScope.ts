"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { apiGet } from "@/lib/api";
import type { PaperCard } from "@/lib/types";

/** localStorage key for the selected paper ids (a convenience; the page works without it). */
export const SELECTION_KEY = "paperpilot.selection";

function readStored(): string[] | null {
  try {
    const value: unknown = JSON.parse(window.localStorage.getItem(SELECTION_KEY) ?? "null");
    return Array.isArray(value) && value.every((id) => typeof id === "string") ? value : null;
  } catch {
    return null;
  }
}

function store(ids: string[]): void {
  try {
    window.localStorage.setItem(SELECTION_KEY, JSON.stringify(ids));
  } catch {
    // Private window or blocked storage: the selection just isn't remembered.
  }
}

/** The first selection: ?paper=<id> alone ("Ask this paper", FR-021), else the remembered
 *  selection (papers since deleted are dropped), else every paper. */
function initialSelection(papers: PaperCard[]): string[] {
  const known = new Set(papers.map((p) => p.paper_id));
  const fromUrl = new URLSearchParams(window.location.search).get("paper");
  if (fromUrl && known.has(fromUrl)) return [fromUrl];
  const stored = readStored()?.filter((id) => known.has(id));
  return stored && stored.length > 0 ? stored : papers.map((p) => p.paper_id);
}

/** Which papers a question searches (User Story 4, FR-007, FR-008). */
export function useScope() {
  const [papers, setPapers] = useState<PaperCard[] | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [blocked, setBlocked] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiGet<{ papers?: unknown }>("/api/papers")
      .then((body) => {
        if (cancelled || !Array.isArray(body.papers)) return;
        const list = body.papers as PaperCard[];
        setPapers(list);
        setSelected(initialSelection(list));
      })
      .catch(() => {
        // Unknown library: questions search every paper, as the API does without paper_ids.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  /** Select or clear one paper; the last selected paper can't be cleared. */
  const toggle = useCallback(
    (paperId: string) => {
      if (!papers) return;
      const on = selected.includes(paperId);
      if (on && selected.length === 1) {
        setBlocked(true);
        return;
      }
      setBlocked(false);
      const next = papers.map((p) => p.paper_id).filter((id) => (id === paperId ? !on : selected.includes(id)));
      setSelected(next);
      store(next);
    },
    [papers, selected],
  );

  const selectAll = useCallback(() => {
    if (!papers) return;
    const all = papers.map((p) => p.paper_id);
    setBlocked(false);
    setSelected(all);
    store(all);
  }, [papers]);

  return useMemo(() => {
    const isAll = papers === null || selected.length === papers.length;
    return {
      papers,
      selected,
      isAll,
      /** The ids to send, or undefined to search every paper (so new papers are included). */
      paperIds: isAll ? undefined : selected,
      blocked,
      toggle,
      selectAll,
    };
  }, [papers, selected, blocked, toggle, selectAll]);
}

export type Scope = ReturnType<typeof useScope>;
