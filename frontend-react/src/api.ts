import type {
  ApiFailure,
  CatalogsResponse,
  ComparisonResponse,
  ComparisonReviewInput,
  ComparisonReviewRecord,
  CreateTriageInput,
  ErrorCode,
  EvaluationReport,
  HealthResponse,
  InputAssessmentResponse,
  KnowledgeBaseSummary,
  MetricsSummary,
  AuditEventRecord,
  NoticePage,
  NoticeQuery,
  ReviewInput,
  ReviewResponse,
  RiskMatrixDocument,
  TriageProposalResponse,
} from "./types";

const API_ROOT = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";
const ERROR_CODES: readonly ErrorCode[] = [
  "comparison_not_found",
  "comparison_review_conflict",
  "notice_not_found",
  "persistence_error",
  "review_conflict",
  "invalid_provider_output",
  "provider_unavailable",
  "provider_rate_limited",
  "invalid_tool_arguments",
  "invalid_risk_matrix",
  "invalid_knowledge_base",
  "required_tool_not_executed",
  "tool_step_limit_exceeded",
];

type JsonObject = Record<string, unknown>;

const asObject = (value: unknown): JsonObject | null =>
  value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as JsonObject
    : null;

const isErrorCode = (value: unknown): value is ErrorCode =>
  typeof value === "string" && ERROR_CODES.some((code) => code === value);

export class ApiError extends Error {
  code?: ErrorCode;
  requestId?: string;
  status: number;

  constructor(failure: ApiFailure, status = 0) {
    super(failure.message);
    this.name = "ApiError";
    this.status = status;
    this.code = failure.code;
    this.requestId = failure.requestId;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError({
      message: "No se puede conectar con FastAPI. Comprueba que el backend esté iniciado.",
    });
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const container = asObject(payload);
    const detail = asObject(container?.error) ?? asObject(container?.detail) ?? container;
    const messageValue = detail?.message ?? detail?.detail;
    const codeValue = detail?.code;
    const requestIdValue = container?.request_id;
    throw new ApiError(
      {
        message: typeof messageValue === "string"
          ? messageValue
          : response.status === 422
            ? "Revisa los campos introducidos."
            : `La API respondió con estado ${response.status}.`,
        code: isErrorCode(codeValue) ? codeValue : undefined,
        requestId: typeof requestIdValue === "string"
          ? requestIdValue
          : response.headers.get("X-Request-ID") ?? undefined,
      },
      response.status,
    );
  }
  return payload as T;
}

export const api = {
  async health(): Promise<HealthResponse> {
    return request<HealthResponse>("/health");
  },

  async getCatalogs(): Promise<CatalogsResponse> {
    return request<CatalogsResponse>("/api/v1/catalogs");
  },

  async precheckTriage(input: CreateTriageInput): Promise<InputAssessmentResponse> {
    return request<InputAssessmentResponse>("/api/v1/triage/precheck", {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  async createTriage(input: CreateTriageInput): Promise<TriageProposalResponse> {
    return request<TriageProposalResponse>("/api/v1/triage", {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  async listNotices(query: NoticeQuery = {}): Promise<NoticePage> {
    const params = new URLSearchParams();
    if (query.search?.trim()) params.set("search", query.search.trim());
    if (query.status) params.set("status", query.status);
    if (query.closed !== undefined) params.set("closed", String(query.closed));
    if (query.urgency) params.set("urgency", query.urgency);
    if (query.provider) params.set("provider", query.provider);
    if (query.category) params.set("category", query.category);
    if (query.review_priority) params.set("review_priority", query.review_priority);
    if (query.order) params.set("order", query.order);
    if (query.page !== undefined) params.set("page", String(query.page));
    if (query.limit !== undefined) params.set("limit", String(query.limit));
    const suffix = params.size ? `?${params.toString()}` : "";
    return request<NoticePage>(`/api/v1/notices${suffix}`);
  },

  async getAuditEvents(noticeId: string): Promise<AuditEventRecord[]> {
    return request<AuditEventRecord[]>(`/api/v1/notices/${encodeURIComponent(noticeId)}/audit-events`);
  },

  async getRiskMatrix(): Promise<RiskMatrixDocument> {
    return request<RiskMatrixDocument>("/api/v1/risk-matrix");
  },

  async getKnowledgeBase(): Promise<KnowledgeBaseSummary> {
    return request<KnowledgeBaseSummary>("/api/v1/knowledge-base");
  },

  async reviewNotice(noticeId: string, input: ReviewInput): Promise<ReviewResponse> {
    return request<ReviewResponse>(`/api/v1/notices/${encodeURIComponent(noticeId)}/reviews`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  async compare(text: string, location: string | null): Promise<ComparisonResponse> {
    return request<ComparisonResponse>("/api/v1/comparisons", {
      method: "POST",
      body: JSON.stringify({ text, location }),
    });
  },

  async reviewComparison(comparisonId: string, input: ComparisonReviewInput): Promise<ComparisonReviewRecord> {
    return request<ComparisonReviewRecord>(`/api/v1/comparisons/${encodeURIComponent(comparisonId)}/review`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  async getMetricsSummary(): Promise<MetricsSummary> {
    return request<MetricsSummary>("/api/v1/metrics/summary");
  },

  async runEvaluation(): Promise<EvaluationReport> {
    return request<EvaluationReport>("/api/v1/evaluations", { method: "POST" });
  },
};
