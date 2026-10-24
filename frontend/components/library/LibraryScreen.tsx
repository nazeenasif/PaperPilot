"use client";

import { useCallback, useEffect, useState } from "react";

import { DropZone } from "@/components/library/DropZone";
import { LibraryHeader } from "@/components/library/LibraryHeader";
import { PaperCard } from "@/components/library/PaperCard";
import { UploadRow } from "@/components/library/UploadRow";
import { apiGet, uploadPapers } from "@/lib/api";
import type { PaperCard as Paper } from "@/lib/types";
import { useJobs } from "@/lib/useJobs";

interface Library {
  papers: Paper[];
  total_passages: number;
}

/** The Library screen: summary, drop zone, upload rows and paper cards (User Story 3). */
export function LibraryScreen() {
  const [library, setLibrary] = useState<Library | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLibrary(await apiGet<Library>("/api/papers"));
    } catch {
      setProblem("Couldn't load your library. It will appear once PaperPilot can be reached.");
    }
  }, []);

  const { jobs, track } = useJobs(() => void load());

  useEffect(() => {
    void load();
  }, [load]);

  async function upload(files: File[]) {
    setProblem(null);
    try {
      track((await uploadPapers(files)).jobs);
    } catch {
      setProblem("Couldn't send the files. Check that PaperPilot is running, then try again.");
    }
  }

  return (
    <main className="mx-auto w-full max-w-6xl space-y-8 px-4 pt-10 pb-16 sm:px-6">
      <LibraryHeader papers={library?.papers.length ?? 0} passages={library?.total_passages ?? 0} />
      <DropZone onFiles={upload} />
      {problem && (
        <p role="alert" className="rounded-xl border border-amber/40 bg-panel px-4 py-3 text-text">
          {problem}
        </p>
      )}
      {jobs.length > 0 && (
        <ul aria-label="Uploads" className="space-y-3">
          {jobs.map((job) => (
            <UploadRow key={job.job_id} job={job} />
          ))}
        </ul>
      )}
      {library && library.papers.length === 0 && (
        <p className="text-muted-foreground">Your library is empty. Drop a paper above to begin.</p>
      )}
      {library && library.papers.length > 0 && (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {library.papers.map((paper) => (
            <PaperCard key={paper.paper_id} paper={paper} onDeleted={() => void load()} onReprocessing={(job) => track([job])} />
          ))}
        </div>
      )}
    </main>
  );
}
