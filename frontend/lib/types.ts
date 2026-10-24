// Types mirroring specs/003-web-app/contracts/web-api.md. Keep in step with api/schemas.py.

export type ServerState = "loading" | "ready" | "error";

export interface Status {
  state: ServerState;
  model: string;
  model_is_free: boolean;
  daily_limit: number;
}

export interface Usage {
  used: number;
  limit: number;
  remaining: number;
  resets_at: string;
  source: "provider" | "local";
}

export type Highlights = "exact" | "mismatch" | "no_pdf";

export interface PaperCard {
  paper_id: string;
  title: string;
  page_count: number;
  passage_count: number;
  text_passages: number;
  table_passages: number;
  section_count: number;
  arxiv_id: string | null;
  has_pdf: boolean;
  highlights: Highlights;
}

export type JobPhase = "queued" | "parsing" | "chunking" | "embedding" | "mapping" | "ready" | "failed";
export type JobOutcome = "added" | "already_present" | "pdf_attached" | "reprocessed" | "failed";
export type UploadInvalidReason = "not_pdf" | "too_large" | "no_text" | "unreadable" | "password";

export interface UploadJob {
  job_id: string;
  kind: "upload" | "reprocess";
  file_name: string;
  phase: JobPhase;
  percent: number | null;
  outcome: JobOutcome | null;
  highlights: "exact" | "mismatch" | null;
  paper_id: string | null;
  error: { kind: string; reason?: string } | null;
}

export interface Region {
  page: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface PassageView {
  passage_id: string;
  paper_id: string;
  title: string;
  section: string;
  page: number;
  page_count: number;
  kind: "text" | "table";
  text: string;
  has_pdf: boolean;
  layout: { pages: { number: number; width: number; height: number }[]; regions: Region[] } | null;
  layout_reason: "no_pdf" | "mismatch" | "unavailable" | null;
  can_reprocess: boolean;
}

export interface NumberedPassage {
  number: number;
  passage_id: string;
  paper_id: string;
  title: string;
  section: string;
  page: number;
  score: number;
  text: string;
}

export interface SearchResult extends Omit<NumberedPassage, "number"> {
  rank: number;
}

export interface Turn {
  role: "user" | "assistant";
  text: string;
}

export type FallbackReason =
  | "no_passages"
  | "below_threshold"
  | "model_not_found"
  | "invalid_citations"
  | "no_citations";

export interface Answer {
  question: string;
  standalone_question: string;
  rewrite_applied: boolean;
  rewrite_fallback_reason: "rewrite_failed" | "rewrite_empty" | null;
  text: string;
  not_found: boolean;
  fallback_reason: FallbackReason | null;
  warning: string | null;
  rejected_answer: string | null;
  citations: { valid: number[]; invalid: number[]; uncited_sentences: string[] };
  verified: boolean;
  passages: NumberedPassage[];
  papers_read: number;
  word_count: number;
  llm_calls: number;
  requests: { planned: number; retries: number };
  timings: { rewrite: number; retrieve: number; generate: number };
  tokens: { input?: number; output?: number; reasoning?: number };
  usage: Usage;
}

export type ProgressStep = "rewriting" | "searching" | "reading" | "generating" | "checking";

export interface ProgressEvent {
  step: ProgressStep;
  passages?: number;
  papers?: number;
}

export interface RetryWaitEvent {
  attempt: number;
  max_attempts: number;
  wait_seconds: number;
  reason: "rate_limited" | "timeout" | "server_error" | "provider_error";
}

/** Error kinds from the API, plus "unreachable" for a network failure seen by the browser. */
export type ErrorKind =
  | "not_ready"
  | "empty_question"
  | "no_papers_selected"
  | "invalid_request"
  | "unknown_paper"
  | "unknown_passage"
  | "pdf_missing"
  | "not_found"
  | "busy_question"
  | "busy_job"
  | "daily_limit"
  | "rate_limited"
  | "model_busy"
  | "model_unavailable"
  | "upload_invalid"
  | "internal"
  | "unreachable";
