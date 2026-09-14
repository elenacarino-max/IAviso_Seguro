export type Provider = "local" | "external";
export type View = "new" | "inbox" | "history" | "dashboard" | "matrix" | "compare";
export type ReviewDecision = "approved" | "modified" | "rejected";
export type ProposalStatus = "pending_review" | ReviewDecision;
export type AuditEventType = "triage_created" | "review_completed";
export type ServiceId = "api" | "ollama" | "gemini" | "sqlite";
export type ServiceStatus = "available" | "unavailable" | "not_configured";
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
export type UncertaintyLevel = "low" | "medium" | "high";
export type ReviewPriorityLevel = UncertaintyLevel | "critical";
export type NoticeOrder = "newest" | "review_priority";
export type UncertaintyReason =
  | "provider_output_repaired"
  | "multiple_repairs"
  | "generic_category"
  | "incomplete_evidence"
  | "provider_retry";
export type ReviewPriorityReason =
  | "low_urgency"
  | "medium_urgency"
  | "high_urgency"
  | "critical_urgency"
  | "high_uncertainty"
  | "recurrent_risk"
  | "recurrent_same_location";
export type Department = "prevencion" | "mantenimiento" | "seguridad" | "limpieza";
export type ErrorCode =
  | "comparison_not_found"
  | "comparison_review_conflict"
  | "notice_not_found"
  | "persistence_error"
  | "review_conflict"
  | "invalid_provider_output"
  | "provider_unavailable"
  | "provider_rate_limited"
  | "invalid_tool_arguments"
  | "invalid_risk_matrix"
  | "invalid_knowledge_base"
  | "required_tool_not_executed"
  | "tool_step_limit_exceeded";

export interface CatalogsResponse {
  categories: Category[];
  urgencies: Urgency[];
  departments: Department[];
}

export interface ServiceHealth {
  id: ServiceId;
  label: string;
  status: ServiceStatus;
  detail: string | null;
}

export interface HealthResponse {
  status: "ok";
  services: ServiceHealth[];
}

export interface TriageProposal {
  category: Category;
  urgency: Urgency;
  summary: string;
  department: Department;
  justification: string;
}

export interface PricingReference {
  model: string;
  currency: string;
  input_per_million_tokens: string;
  output_per_million_tokens: string;
  source: string;
  checked_on: string;
}

export interface ExecutionMetrics {
  provider: Provider;
  model: string | null;
  parameters: Record<string, number>;
  started_at: string;
  completed_at: string;
  latency_ms: number;
  provider_attempts: number;
  repair_attempts: number;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  success: boolean;
  json_valid: boolean | null;
  error_type: string | null;
  api_cost: string | null;
  api_cost_currency: string | null;
  computational_cost: string | null;
  pricing: PricingReference | null;
  evidence: KnowledgeEvidence[];
}

export interface KnowledgeEvidence {
  source_id: string;
  title: string;
  section: string;
  category: Category;
  excerpt: string;
  source_type: "risk_matrix" | "preventive_document";
  version: string;
  score: number;
}

export interface KnowledgeSourceSummary {
  source_id: string;
  title: string;
  section: string;
  categories: Category[];
}

export interface KnowledgeBaseSummary {
  version: string;
  disclaimer: string;
  source_format: "versioned_json";
  document_count: number;
  sources: KnowledgeSourceSummary[];
}

export type RedactionType = "EMAIL" | "PHONE" | "DNI_NIE" | "IBAN";

export interface PrivacyMetadata {
  redacted: boolean;
  redaction_count: number;
  redaction_types: RedactionType[];
}

export interface SimilarityMatch {
  notice_id: string;
  score: number;
  same_location: boolean;
  location: string | null;
  created_at: string;
  category: Category;
  urgency: Urgency;
}

export interface SimilarityResult {
  available: boolean;
  has_similar: boolean;
  match_count: number;
  matches: SimilarityMatch[];
}

export interface UncertaintyAssessment {
  level: UncertaintyLevel;
  reasons: UncertaintyReason[];
}

export interface ReviewPriorityAssessment {
  level: ReviewPriorityLevel;
  reasons: ReviewPriorityReason[];
}

export interface TriageProposalResponse extends TriageProposal {
  notice_id: string;
  triage_run_id: string;
  status: "pending_review";
  version: number;
  provider: Provider;
  model: string | null;
  created_at: string;
  metrics: ExecutionMetrics;
  privacy: PrivacyMetadata;
  similarity: SimilarityResult;
  uncertainty: UncertaintyAssessment;
  review_priority: ReviewPriorityAssessment;
  review_policy_version: string;
}

export interface ClassificationDecision {
  category: Category;
  urgency: Urgency;
  department: Department;
}

export interface ReviewRecord {
  id: string;
  decision: ReviewDecision;
  final_classification: ClassificationDecision | null;
  comment: string;
  reviewer: string;
  created_at: string;
}

export interface TriageRunRecord {
  id: string;
  request_id: string;
  provider: Provider;
  model: string | null;
  status: ProposalStatus;
  version: number;
  proposal: TriageProposal;
  created_at: string;
  metrics: ExecutionMetrics | null;
  similarity: SimilarityResult;
  uncertainty: UncertaintyAssessment | null;
  review_priority: ReviewPriorityAssessment | null;
  review_policy_version: string | null;
  review: ReviewRecord | null;
}

export interface NoticeRecord {
  id: string;
  text: string;
  location: string | null;
  created_at: string;
  triage_runs: TriageRunRecord[];
}

export interface NoticeQuery {
  search?: string;
  status?: ProposalStatus;
  closed?: boolean;
  urgency?: Urgency;
  provider?: Provider;
  category?: Category;
  review_priority?: ReviewPriorityLevel;
  order?: NoticeOrder;
  page?: number;
  limit?: number;
}

export interface NoticePage {
  items: NoticeRecord[];
  page: number;
  limit: number;
  total: number;
  pages: number;
}

export interface AuditEventRecord {
  id: number;
  notice_id: string;
  triage_run_id: string;
  event_type: AuditEventType;
  previous_status: ProposalStatus | null;
  new_status: ProposalStatus;
  actor: string | null;
  created_at: string;
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

export interface ReviewResponse {
  notice_id: string;
  triage_run: TriageRunRecord;
}

export interface ComparisonProviderResult {
  provider: Provider;
  result: TriageProposal | null;
  error_code: ErrorCode | null;
  metrics: ExecutionMetrics;
}

export interface ComparisonResponse {
  comparison_id: string;
  created_at: string;
  results: ComparisonProviderResult[];
  review: ComparisonReviewRecord | null;
  privacy: PrivacyMetadata;
}

export interface ComparisonReviewInput {
  category: Category;
  urgency: Urgency;
  department: Department;
  reviewer: string;
  comment: string;
}

export interface ComparisonReviewRecord extends ComparisonReviewInput {
  id: string;
  comparison_id: string;
  created_at: string;
}

export interface ProviderMetricsSummary {
  provider: Provider;
  models: string[];
  runs: number;
  reviewed_runs: number;
  mean_latency_ms: number | null;
  mean_provider_attempts: number | null;
  repair_rate: number | null;
  mean_repair_attempts: number | null;
  success_rate: number | null;
  json_valid_rate: number | null;
  json_valid_observations: number;
  human_agreement_rate: number | null;
  mean_total_tokens: number | null;
  token_observations: number;
  mean_api_cost: string | null;
  api_cost_currency: string | null;
  cost_observations: number;
  temperatures: number[];
  top_p_values: number[];
}

export interface MetricsSummary {
  total_notices: number;
  total_runs: number;
  pending_review: number;
  reviewed: number;
  approved: number;
  modified: number;
  rejected: number;
  acceptance_rate: number | null;
  correction_rate: number | null;
  rejection_rate: number | null;
  review_policy_observations: number;
  pending_high_priority: number;
  pending_critical_priority: number;
  uncertainty: UncertaintyLevelSummary[];
  providers: ProviderMetricsSummary[];
}

export type PreventiveWindow = "7" | "30" | "90" | "all";
export type TimelineGranularity = "day" | "week" | "month";

export interface PreventiveAnalytics {
  period: {
    window: PreventiveWindow;
    start_at: string | null;
    end_at: string;
    granularity: TimelineGranularity;
  };
  totals: {
    confirmed_notices: number;
    pending_notices: number;
    rejected_notices: number;
  };
  pending_by_priority: {
    levels: Array<{ level: ReviewPriorityLevel; total: number }>;
    policy_unavailable: number;
  };
  by_location: Array<{
    location: string;
    total: number;
    high_or_critical_urgency: number;
  }>;
  by_category: Array<{ category: Category; total: number }>;
  by_urgency: Array<{ urgency: Urgency; total: number }>;
  location_category_hotspots: Array<{
    location: string;
    category: Category;
    total: number;
    high_or_critical_urgency: number;
  }>;
  timeline: Array<{
    period: string;
    total_notices: number;
    confirmed_notices: number;
    pending_notices: number;
    rejected_notices: number;
  }>;
  hotspot_minimum: 2;
  enough_data_for_trends: boolean;
}

export interface UncertaintyLevelSummary {
  level: UncertaintyLevel;
  runs: number;
  rate: number | null;
  reviewed_runs: number;
  human_correction_rate: number | null;
}

export interface ProviderEvaluationSummary {
  provider: Provider;
  cases: number;
  category_accuracy: number | null;
  urgency_accuracy: number | null;
  department_accuracy: number | null;
  json_valid_rate: number | null;
  mean_latency_ms: number | null;
  mean_api_cost: string | null;
  api_cost_currency: string | null;
  reviewed_notices: number;
  human_correction_rate: number | null;
}

export interface EvaluationReport {
  dataset_version: string;
  generated_at: string;
  disclaimer: string;
  summaries: ProviderEvaluationSummary[];
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
  code?: ErrorCode;
  requestId?: string;
}
