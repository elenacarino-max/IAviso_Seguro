export type Provider = "local" | "external";
export type View = "new" | "inbox" | "dashboard" | "matrix" | "compare";
export type ReviewDecision = "approved" | "modified" | "rejected";
export type Category =
  | "riesgo_electrico"
  | "caidas_obstaculos"
  | "incendio"
  | "maquinaria"
  | "sustancias_peligrosas"
  | "problemas_estructurales"
  | "falta_epi"
  | "ergonomia"
  | "otros";
export type Urgency = "baja" | "media" | "alta" | "critica";
export type Department = "prevencion" | "mantenimiento" | "seguridad" | "limpieza";

export interface TriageProposal {
  category: Category;
  urgency: Urgency;
  summary: string;
  department: Department;
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
  category?: Category;
  urgency?: Urgency;
  department?: Department;
}

export interface ExecutionMetrics {
  latency_ms: number;
  total_tokens: number | null;
  api_cost: string | number | null;
  api_cost_currency: string | null;
}

export interface ComparisonProviderResult {
  provider: Provider;
  result: TriageProposal | null;
  error_code: string | null;
  metrics: ExecutionMetrics;
}

export interface ComparisonResponse {
  comparison_id: string;
  created_at: string;
  results: ComparisonProviderResult[];
}

export interface RiskMatrixRule {
  rule_id: string;
  category: Category;
  conditions: string[];
  recommended_urgency: Urgency;
  department: Department;
  evidence: string;
}

export interface RiskMatrixDocument {
  version: string;
  disclaimer: string;
  rules: RiskMatrixRule[];
}

export interface ApiFailure {
  message: string;
  code?: string;
  requestId?: string;
}
