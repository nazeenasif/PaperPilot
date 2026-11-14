"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

import { useUsage } from "@/components/app/UsageMeter";
import { useAsk } from "@/lib/useAsk";

export interface AskSession extends ReturnType<typeof useAsk> {
  /** The question being typed but not sent yet. */
  draft: string;
  setDraft: (text: string) => void;
}

const AskContext = createContext<AskSession | null>(null);

/** Holds the Ask screen's conversation (with any answer still streaming) and the unsent question
 *  above the pages, so they are still there after visiting another page. */
export function AskProvider({ children }: { children: ReactNode }) {
  const usage = useUsage();
  const asking = useAsk({
    // The meter follows each answer's figure; after a failure it asks the server (FR-024).
    onAnswer: (answer) => answer.usage && usage?.report(answer.usage),
    onFailure: () => void usage?.refresh(),
  });
  const [draft, setDraft] = useState("");
  return <AskContext.Provider value={{ ...asking, draft, setDraft }}>{children}</AskContext.Provider>;
}

/** The Ask session, or null outside an AskProvider. */
export function useAskSession(): AskSession | null {
  return useContext(AskContext);
}
