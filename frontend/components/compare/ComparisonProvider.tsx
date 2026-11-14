"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { useUsage } from "@/components/app/UsageMeter";
import { ASPECTS, selectionProblem } from "@/components/compare/CompareForm";
import type { ComparisonAspect } from "@/lib/types";
import { useComparison } from "@/lib/useComparison";

/** sessionStorage key for the chosen papers and aspects (this tab only; a convenience, not state
 *  the app relies on). */
export const STORAGE_KEY = "paperpilot.compare";

export interface ComparisonSession {
  selected: string[];
  setSelected: (ids: string[]) => void;
  aspects: ComparisonAspect[];
  setAspects: (aspects: ComparisonAspect[]) => void;
  compare: ReturnType<typeof useComparison>;
}

const ComparisonContext = createContext<ComparisonSession | null>(null);
const KNOWN = new Set<string>(ASPECTS.map((a) => a.key));

function restore(): { papers: string[]; aspects: ComparisonAspect[] } | null {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as { papers?: unknown; aspects?: unknown };
    const papers = Array.isArray(value.papers) ? value.papers.filter((p): p is string => typeof p === "string") : [];
    const aspects = Array.isArray(value.aspects)
      ? value.aspects.filter((a): a is ComparisonAspect => typeof a === "string" && KNOWN.has(a))
      : [];
    return { papers, aspects };
  } catch {
    return null; // storage blocked or unreadable: start empty
  }
}

/** Holds the Compare screen's papers, aspects and comparison above the pages, so a running or
 *  finished comparison is still there after visiting another page; the choice is also kept for
 *  this tab across a reload. */
export function ComparisonProvider({ children }: { children: ReactNode }) {
  const usage = useUsage();
  const [selected, setSelected] = useState<string[]>([]);
  const [aspects, setAspects] = useState<ComparisonAspect[]>(ASPECTS.map((a) => a.key));
  const [restored, setRestored] = useState(false);

  useEffect(() => {
    // After mount, so the server-rendered page and the first client render match.
    const saved = restore();
    if (saved) {
      setSelected(saved.papers);
      setAspects(saved.aspects);
    }
    setRestored(true);
  }, []);

  useEffect(() => {
    if (!restored) return;
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ papers: selected, aspects }));
    } catch {
      // storage unavailable: the choice just isn't remembered across a reload
    }
  }, [restored, selected, aspects]);

  const valid = selectionProblem(selected.length, aspects.length) === null;
  const compare = useComparison(selected, aspects, valid, () => void usage?.refresh());

  return (
    <ComparisonContext.Provider value={{ selected, setSelected, aspects, setAspects, compare }}>
      {children}
    </ComparisonContext.Provider>
  );
}

/** The comparison session, or null outside a ComparisonProvider. */
export function useComparisonSession(): ComparisonSession | null {
  return useContext(ComparisonContext);
}
