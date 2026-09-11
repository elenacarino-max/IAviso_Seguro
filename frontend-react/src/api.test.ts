import { afterEach, describe, expect, it, vi } from "vitest";
import { api, normalizeTriageResponse } from "./api";

afterEach(() => vi.restoreAllMocks());

describe("cliente de FastAPI", () => {
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

  it("normaliza los identificadores y la propuesta devueltos por el backend", () => {
    expect(normalizeTriageResponse({
      id: "r-1",
      provider: "local",
      status: "pending_review",
      version: 0,
      category: "caidas",
      urgency: "alta",
      summary: "Cable sin proteger.",
      department: "mantenimiento",
    })).toMatchObject({
      triage_run_id: "r-1",
      proposal: { category: "caidas", urgency: "alta", department: "mantenimiento" },
    });
  });

  it("normaliza la propuesta anidada de una comparación", () => {
    expect(normalizeTriageResponse({
      provider: "external",
      result: {
        category: "incendio",
        urgency: "critica",
        summary: "Humo visible junto a salida requiere revisión técnica inmediata preventiva.",
        department: "seguridad",
        justification: "Caso sintético.",
      },
      metrics: {
        latency_ms: 25,
        total_tokens: 42,
        api_cost: "0.001",
        api_cost_currency: "USD",
      },
    })).toMatchObject({
      provider: "external",
      proposal: {
        category: "incendio",
        urgency: "critica",
        department: "seguridad",
      },
    });
  });
});
