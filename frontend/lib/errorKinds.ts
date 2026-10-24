// All wording for failures lives here: the API sends kinds and safe fields only, and no
// component renders server text (FR-022, research R10).

import type { UploadJob } from "@/lib/types";

export interface FailureCopy {
  message: string;
  next: string;
}

/** Why an upload or re-process failed, and what to try next (FR-018). */
export const UPLOAD_FAILURES: Record<string, FailureCopy> = {
  not_pdf: { message: "This file isn't a PDF.", next: "Choose a .pdf file of a research paper." },
  too_large: {
    message: "This PDF is larger than 25 MB.",
    next: "Try a smaller copy of the paper, for example one without embedded images.",
  },
  no_text: {
    message: "This PDF has no text PaperPilot can read.",
    next: "It may be a scanned image. Try a text-based version of the paper.",
  },
  unreadable: { message: "This PDF couldn't be opened.", next: "It may be damaged. Download it again and add the new copy." },
  password: { message: "This PDF is password-protected.", next: "Remove the password, then add the file again." },
  storage: { message: "PaperPilot couldn't save this paper.", next: "Check that the disk has free space, then add it again." },
};

const GONE: FailureCopy = {
  message: "This paper is no longer in your library.",
  next: "Add its PDF again to bring it back.",
};

const UNKNOWN_FAILURE: FailureCopy = {
  message: "Something went wrong with this file.",
  next: "Try adding it again. If it keeps failing, the server log has the details.",
};

/** The copy for a failed job's row. */
export function uploadFailure(error: UploadJob["error"]): FailureCopy {
  const copy = error?.kind === "upload_invalid" && error.reason ? UPLOAD_FAILURES[error.reason] : undefined;
  if (copy) return copy;
  if (error?.kind === "unknown_paper" || error?.kind === "pdf_missing") return GONE;
  return UNKNOWN_FAILURE;
}
