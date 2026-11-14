"use client";

import { useState, type ReactNode } from "react";

import { SummaryStoresContext, type SummaryStore } from "@/lib/useSummary";

/** Keeps every paper's summary (a running one included) above the pages, so it is still there
 *  after visiting another page. */
export function SummaryProvider({ children }: { children: ReactNode }) {
  const [stores] = useState(() => new Map<string, SummaryStore>());
  return <SummaryStoresContext.Provider value={stores}>{children}</SummaryStoresContext.Provider>;
}
