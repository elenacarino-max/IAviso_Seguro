import type {
  ApiFailure,
  CreateTriageInput,
  Notice,
  ReviewInput,
  TriageProposal,
  TriageRun,
} from "./types";

const API_ROOT = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  code?: string;
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

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail ?? payload?.error ?? payload ?? {};
    throw new ApiError(
      {
        message: detail.message ?? detail.detail ?? `La API respondió con estado ${response.status}.`,
        code: detail.code,
        requestId: detail.request_id ?? response.headers.get("X-Request-ID") ?? undefined,
      },
      response.status,
    );
  }
  return payload as T;
}

const object = (value: unknown): Record<string, any> =>
  value && typeof value === "object" ? (value as Record<string, any>) : {};

const proposalFrom = (raw: unknown): TriageProposal => {
  const item = object(raw);
  return {
    category: String(item.category ?? item.categoria ?? "Sin categoría"),
    urgency: String(item.urgency ?? item.urgencia ?? "Sin determinar"),
    summary: String(item.summary ?? item.resumen ?? "Sin resumen"),
    department: String(item.department ?? item.departamento ?? "Sin asignar"),
    justification: item.justification ?? item.justificacion,
  };
};

const runFrom = (raw: unknown): TriageRun => {
  const item = object(raw);
  const proposal = item.proposal ?? item.original_proposal ?? item.classification ?? item;
  return {
    triage_run_id: String(item.triage_run_id ?? item.run_id ?? item.id ?? ""),
    provider: String(item.provider ?? "—"),
    model: item.model ? String(item.model) : undefined,
    status: String(item.status ?? "pending_review"),
    version: Number(item.version ?? 0),
    created_at: item.created_at,
    proposal: proposalFrom(proposal),
    review: item.review ?? null,
  };
};

const noticeFrom = (raw: unknown): Notice => {
  const item = object(raw);
  const rawRuns = item.triage_runs ?? item.runs ?? (item.triage_run ? [item.triage_run] : []);
  return {
    notice_id: String(item.notice_id ?? item.id ?? ""),
    text: String(item.text ?? item.description ?? item.aviso ?? ""),
    location: item.location ?? item.ubicacion ?? null,
    created_at: item.created_at,
    triage_runs: Array.isArray(rawRuns) ? rawRuns.map(runFrom) : [],
  };
};

export const api = {
  async health(): Promise<boolean> {
    try {
      await request("/health");
      return true;
    } catch {
      return false;
    }
  },

  async createTriage(input: CreateTriageInput): Promise<Record<string, any>> {
    return request("/api/v1/triage", { method: "POST", body: JSON.stringify(input) });
  },

  async listNotices(): Promise<Notice[]> {
    const payload = await request<unknown>("/api/v1/notices");
    const container = object(payload);
    const items = Array.isArray(payload) ? payload : container.items ?? container.notices ?? [];
    return Array.isArray(items) ? items.map(noticeFrom) : [];
  },

  async reviewNotice(noticeId: string, input: ReviewInput): Promise<Record<string, any>> {
    return request(`/api/v1/notices/${encodeURIComponent(noticeId)}/reviews`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  async compare(text: string, location: string | null): Promise<Record<string, any>> {
    return request("/api/v1/comparisons", {
      method: "POST",
      body: JSON.stringify({ text, location }),
    });
  },
};

export const normalizeTriageResponse = (raw: Record<string, any>): TriageRun => runFrom(raw);
