export type Provider = "local" | "external";
export type View = "new" | "inbox" | "dashboard" | "compare";
export type ReviewDecision = "approved" | "modified" | "rejected";

export interface TriageProposal {
  category: string;
  urgency: string;
  summary: string;
  department: string;
  justification?: string;
}

export interface TriageRun {
  triage_run_id: string;
  provider: string;
  model?: string;
  status: string;
  version: number;
  created_at?: string;
  proposal: TriageProposal;
  review?: Record<string, unknown> | null;
}

export interface Notice {
  notice_id: string;
  text: string;
  location?: string | null;
  created_at?: string;
  triage_runs: TriageRun[];
}

export interface CreateTriageInput {
  text: string;
  provider: Provider;
  location: string | null;
}

export interface ReviewInput {
  expected_version: number;
  decision: ReviewDecision;
  reviewer: string;
  comment: string;
  category?: string;
  urgency?: string;
  department?: string;
}

export interface ApiFailure {
  message: string;
  code?: string;
  requestId?: string;
}
