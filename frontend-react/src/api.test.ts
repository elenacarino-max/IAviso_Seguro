import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

afterEach(() => vi.restoreAllMocks());

describe("cliente de FastAPI", () => {
  it("recupera la salud detallada de los servicios", async () => {
    const payload = {
      status: "ok",
      services: [
        { id: "api", label: "API FastAPI", status: "available", detail: null },
      ],
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify(payload), { status: 200 }),
    );

    await expect(api.health()).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      "/health",
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it("usa los endpoints existentes y conserva el contrato de alta", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ notice_id: "n-1", id: "r-1" }), { status: 200 }),
    );

    await api.createTriage({ text: "Cable en zona de paso", provider: "local", location: "Taller" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/triage",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ text: "Cable en zona de paso", provider: "local", location: "Taller" }),
      }),
    );
  });

  it("envía una revisión sin campos ajenos al esquema", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ notice_id: "n-1" }), { status: 200 }),
    );

    await api.reviewNotice("n-1", {
      decision: "approved",
      reviewer: "Técnica demo",
      comment: "Clasificación verificada.",
      expected_version: 0,
    });

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      decision: "approved",
      reviewer: "Técnica demo",
      comment: "Clasificación verificada.",
      expected_version: 0,
    });
  });

  it("consulta la matriz mediante la API", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(
        JSON.stringify({
          version: "1.0.0",
          disclaimer: "Matriz didáctica.",
          rules: [],
        }),
        { status: 200 },
      ),
    );

    await api.getRiskMatrix();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/risk-matrix",
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it("consulta el inventario público del RAG", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(
        JSON.stringify({
          version: "1.0.0",
          disclaimer: "Corpus sintético.",
          source_format: "versioned_json",
          document_count: 0,
          sources: [],
        }),
        { status: 200 },
      ),
    );

    await api.getKnowledgeBase();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/knowledge-base",
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it("consulta los catálogos cerrados mediante la API", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({
        categories: ["riesgo_electrico"],
        urgencies: ["alta"],
        departments: ["mantenimiento"],
      }), { status: 200 }),
    );

    await api.getCatalogs();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/catalogs",
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it("envía filtros tipados y paginación a la bandeja", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ items: [], page: 2, limit: 20, total: 0, pages: 0 }), { status: 200 }),
    );

    await api.listNotices({
      search: "cuadro eléctrico",
      status: "pending_review",
      closed: false,
      urgency: "alta",
      category: "riesgo_electrico",
      provider: "local",
      review_priority: "high",
      order: "review_priority",
      page: 2,
      limit: 20,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/notices?search=cuadro+el%C3%A9ctrico&status=pending_review&closed=false&urgency=alta&provider=local&category=riesgo_electrico&review_priority=high&order=review_priority&page=2&limit=20",
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it("consulta la auditoría de un aviso", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify([]), { status: 200 }),
    );

    await api.getAuditEvents("notice/1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/notices/notice%2F1/audit-events",
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it("ejecuta el benchmark cuantitativo mediante la API", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ dataset_version: "1.0.0", summaries: [] }), { status: 200 }),
    );

    await api.runEvaluation();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/evaluations",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("consulta el resumen histórico de métricas", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ total_notices: 0, providers: [] }), { status: 200 }),
    );

    await api.getMetricsSummary();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/metrics/summary",
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it("consulta el panorama preventivo con una ventana cerrada", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ totals: { confirmed_notices: 0 } }), { status: 200 }),
    );

    await api.getPreventiveAnalytics("90");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/metrics/preventive?window_days=90",
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it("registra una referencia humana para una comparación", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ id: "review-1" }), { status: 200 }),
    );
    const input = {
      category: "incendio" as const,
      urgency: "critica" as const,
      department: "seguridad" as const,
      reviewer: "Técnica demo",
      comment: "Referencia verificada.",
    };

    await api.reviewComparison("comparison-1", input);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/comparisons/comparison-1/review",
      expect.objectContaining({ method: "POST", body: JSON.stringify(input) }),
    );
  });

});
