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

// --- Ask failures and answer states (User Story 5) ---

/** The engine's not-found sentence (prompts.NOT_FOUND). */
export const NOT_FOUND_SENTENCE = "I couldn't find that in the selected papers.";

/** The researcher's local time as HH:MM (24-hour), from an ISO timestamp. */
export function localTime(iso: string): string {
  return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(iso));
}

function numberList(numbers: number[]): string {
  if (numbers.length <= 1) return String(numbers[0] ?? "");
  return `${numbers.slice(0, -1).join(", ")} and ${numbers[numbers.length - 1]}`;
}

/** Why an answer was held back, from the checked citations (never the server's wording). */
export function heldBackReason(invalid: number[], provided: number): string {
  if (invalid.length === 0) {
    return "The model's answer cited none of the provided passages, so it wasn't shown as verified.";
  }
  const cited = `passage${invalid.length === 1 ? "" : "s"} ${numberList(invalid)}`;
  return `The model cited ${cited}, but only ${provided} ${provided === 1 ? "was" : "were"} provided, so its answer wasn't shown as verified.`;
}

/** What to change when the configured model can't be used, by reason (no key is ever shown). */
export const MODEL_UNAVAILABLE_HINTS: Record<string, string> = {
  not_listed: "The provider doesn't list this model. Choose another LLM_MODEL in .env and restart the API.",
  unknown_model: "The provider doesn't know this model. Choose another LLM_MODEL in .env and restart the API.",
  bad_key: "The provider didn't accept the API key. Check LLM_API_KEY in .env and restart the API.",
  out_of_credits: "The provider account has no credits for this model. Choose a :free model in .env, or add credits.",
  cut_off: "The model's answer was cut off. Set LLM_REASONING_EFFORT=low in .env, or choose another LLM_MODEL.",
  empty: "The model returned an empty answer. Try again, or choose another LLM_MODEL in .env.",
  bad_request: "The provider refused the request. Choose another LLM_MODEL in .env and restart the API.",
};
export const MODEL_UNAVAILABLE_DEFAULT = "Check LLM_MODEL and LLM_API_KEY in .env, then restart the API.";

const BUSY_TASK: FailureCopy = {
  message: "PaperPilot is still working on another answer, summary or comparison.",
  next: "Try again when it finishes.",
};

/** Copy for failures without a dedicated state. */
export const GENERIC_FAILURES: Record<string, FailureCopy> = {
  unreachable: {
    message: "PaperPilot can't be reached right now.",
    next: "Start the API with python -m api. Your question is kept; try again once it's running.",
  },
  not_ready: { message: "PaperPilot is still getting ready.", next: "Try again in a few seconds." },
  // One model task at a time (ADR-0009).
  busy_task: BUSY_TASK,
  unknown_paper: {
    message: "One of the selected papers is no longer in your library.",
    next: "Check the selection, then try again.",
  },
};
export const GENERIC_FAILURE: FailureCopy = {
  message: "PaperPilot couldn't finish this answer.",
  next: "Please try again in a moment. If it keeps failing, the server log has the details.",
};

// --- Summary sections, TL;DR and comparison cells (Feature 4, FR-011, FR-014) ---

export const PART_NOT_REPORTED = "Not reported in the retrieved passages.";

/** "Built without Method and Data." for a TL;DR that went without those sections. */
export function builtWithout(labels: string[]): string {
  const last = labels[labels.length - 1];
  const names = labels.length > 1 ? `${labels.slice(0, -1).join(", ")} and ${last}` : last;
  return `Built without ${names}.`;
}

/** "9–12" for a run of numbers, else "3, 7 and 8". */
function passageList(numbers: number[]): string {
  const sorted = [...numbers].sort((a, b) => a - b);
  const first = sorted[0];
  const last = sorted[sorted.length - 1];
  if (sorted.length > 2 && first !== undefined && last !== undefined && last - first === sorted.length - 1) {
    return `${first}–${last}`;
  }
  return numberList(sorted);
}

/** Why a part was held back, from its own numbers (never the engine's warning). */
export function heldBackPart(noun: string, invalid: number[], provided: number[]): string {
  if (noun === "TL;DR") return "Held back: the TL;DR said something its verified sections don't support.";
  if (invalid.length === 0) return `Held back: this ${noun} didn't cite its passages correctly.`;
  const cited = `passage${invalid.length === 1 ? "" : "s"} ${numberList(invalid)}`;
  const given = provided.length === 1 ? `only passage ${provided[0]} was` : `only passages ${passageList(provided)} were`;
  return `Held back: this ${noun} cited ${cited}, but ${given} provided.`;
}

const PART_FAILED: Record<string, string> = {
  cut_off: "The model's answer was cut off before it finished.",
  empty: "The model returned an empty answer.",
  malformed: "The model's reply couldn't be read.",
};

const PART_NOT_STARTED: Record<string, string> = {
  daily_limit: "Not started: today's free requests ran out.",
  rate_limited: "Not started: the free model asked PaperPilot to wait.",
  model_busy: "Not started: the free model was busy.",
  model_unavailable: "Not started: the configured model couldn't be used.",
};

/** The line shown for a failed or not-started part. */
export function partProblem(state: "failed" | "not_started", reason: string | null, _until: string | null = null): string {
  if (state === "failed") return (reason && PART_FAILED[reason]) || "This part couldn't be written.";
  return (reason && PART_NOT_STARTED[reason]) || "Not started.";
}
