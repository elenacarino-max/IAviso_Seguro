import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const riskMatrix = {
  version: "1.0.0",
  disclaimer: "Matriz sintética para demostración.",
  rules: [{
    rule_id: "RM-ELEC-001",
    category: "riesgo_electrico",
    conditions: ["cable expuesto", "cuadro abierto"],
    recommended_urgency: "alta",
    department: "mantenimiento",
    evidence: "Aislar la zona y revisar la instalación.",
  }],
};

const knowledgeBase = {
  version: "1.0.0",
  disclaimer: "Corpus sintético para demostración.",
  source_format: "versioned_json",
  document_count: 2,
  sources: [
    {
      source_id: "PRL-EL-04",
      title: "Procedimiento interno de riesgo eléctrico",
      section: "Apartado 3.2",
      categories: ["riesgo_electrico"],
    },
    {
      source_id: "GUIA-CUADROS-02",
      title: "Guía interna de cuadros eléctricos",
      section: "Inspección preventiva",
      categories: ["riesgo_electrico"],
    },
  ],
};

const catalogs = {
  categories: [
    "riesgo_electrico",
    "caidas_obstaculos",
    "incendio",
    "maquinaria",
    "sustancias_peligrosas",
    "problemas_estructurales",
    "falta_epi",
    "ergonomia",
    "otros",
  ],
  urgencies: ["baja", "media", "alta", "critica"],
  departments: ["prevencion", "mantenimiento", "seguridad", "limpieza"],
};

const basicTriageResponse = {
  notice_id: "n-direct",
  triage_run_id: "r-direct",
  status: "pending_review",
  version: 0,
  provider: "local",
  model: "llama3.2:3b",
  created_at: "2026-09-13T10:00:00Z",
  category: "riesgo_electrico",
  urgency: "alta",
  summary: "Humo visible requiere aislar zona y activar revisión profesional inmediata.",
  department: "mantenimiento",
  justification: "Propuesta sintética.",
  metrics: { evidence: [] },
  privacy: { redacted: false, redaction_count: 0, redaction_types: [] },
  similarity: { available: false, has_similar: false, match_count: 0, matches: [] },
  uncertainty: { level: "medium", reasons: ["provider_output_repaired"] },
  review_priority: { level: "high", reasons: ["high_urgency"] },
  review_policy_version: "v1",
};

const preventiveAnalytics = {
  period: { window: "30", start_at: "2026-08-15T12:00:00Z", end_at: "2026-09-14T12:00:00Z", granularity: "day" },
  totals: { confirmed_notices: 5, pending_notices: 4, rejected_notices: 1 },
  pending_by_priority: {
    levels: [
      { level: "low", total: 0 },
      { level: "medium", total: 1 },
      { level: "high", total: 2 },
      { level: "critical", total: 1 },
    ],
    policy_unavailable: 0,
  },
  by_location: [
    { location: "Almacén", total: 3, high_or_critical_urgency: 2 },
    { location: "Taller", total: 2, high_or_critical_urgency: 0 },
  ],
  by_category: [
    { category: "caidas_obstaculos", total: 3 },
    { category: "maquinaria", total: 2 },
  ],
  by_urgency: [{ urgency: "alta", total: 2 }, { urgency: "media", total: 3 }],
  location_category_hotspots: [
    { location: "Almacén", category: "caidas_obstaculos", total: 3, high_or_critical_urgency: 2 },
  ],
  timeline: [
    { period: "2026-09-12", total_notices: 3, confirmed_notices: 2, pending_notices: 1, rejected_notices: 0 },
    { period: "2026-09-13", total_notices: 2, confirmed_notices: 1, pending_notices: 0, rejected_notices: 1 },
  ],
  hotspot_minimum: 2,
  enough_data_for_trends: true,
};

const emptyPreventiveAnalytics = {
  ...preventiveAnalytics,
  totals: { confirmed_notices: 0, pending_notices: 0, rejected_notices: 0 },
  pending_by_priority: {
    levels: [
      { level: "low", total: 0 },
      { level: "medium", total: 0 },
      { level: "high", total: 0 },
      { level: "critical", total: 0 },
    ],
    policy_unavailable: 0,
  },
  by_location: [],
  by_category: [],
  by_urgency: [],
  location_category_hotspots: [],
  timeline: [],
  enough_data_for_trends: false,
};

const emptyProviderMetrics = { models: [], runs: 0, reviewed_runs: 0, mean_latency_ms: null, mean_provider_attempts: null, repair_rate: null, mean_repair_attempts: null, success_rate: null, json_valid_rate: null, json_valid_observations: 0, human_agreement_rate: null, mean_total_tokens: null, token_observations: 0, mean_api_cost: null, api_cost_currency: null, cost_observations: 0, temperatures: [], top_p_values: [] };
const emptyMetricsSummary = {
  total_notices: 0, total_runs: 0, pending_review: 0, reviewed: 0,
  approved: 0, modified: 0, rejected: 0, acceptance_rate: null,
  correction_rate: null, rejection_rate: null, review_policy_observations: 0,
  pending_high_priority: 0, pending_critical_priority: 0,
  uncertainty: [
    { level: "low", runs: 0, rate: null, reviewed_runs: 0, human_correction_rate: null },
    { level: "medium", runs: 0, rate: null, reviewed_runs: 0, human_correction_rate: null },
    { level: "high", runs: 0, rate: null, reviewed_runs: 0, human_correction_rate: null },
  ],
  providers: [
    { ...emptyProviderMetrics, provider: "local" },
    { ...emptyProviderMetrics, provider: "external" },
  ],
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("IAviso Seguro", () => {
  it("muestra la arquitectura y distingue Gemini no configurado", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/health") {
        return new Response(JSON.stringify({
          status: "ok",
          services: [
            { id: "api", label: "API FastAPI", status: "available", detail: null },
            { id: "ollama", label: "Ollama · llama3.2:3b", status: "available", detail: null },
            { id: "gemini", label: "Gemini", status: "not_configured", detail: "no configurado" },
            { id: "sqlite", label: "SQLite", status: "available", detail: null },
          ],
        }), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    render(<App />);

    const services = await screen.findByLabelText("Estado de servicios");
    expect(within(services).getByText("API FastAPI")).toBeInTheDocument();
    expect(within(services).getByText("Ollama · llama3.2:3b")).toBeInTheDocument();
    expect(within(services).getByText(/no configurado/)).toBeInTheDocument();
    expect(within(services).getByText("SQLite")).toBeInTheDocument();
  });

  it("mantiene visible que la revisión humana es obligatoria", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify([]), { status: 200 }));
    render(<App />);
    expect(screen.getByText("Revisión obligatoria")).toBeInTheDocument();
    expect(screen.getByText(/La IA propone/)).toBeInTheDocument();
    expect(screen.getByText("Los datos permanecen en local")).toBeInTheDocument();
    expect(screen.getByText("La petición se envía al proveedor")).toBeInTheDocument();
  });

  it("permite navegar a la bandeja", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/v1/catalogs") {
        return new Response(JSON.stringify(catalogs), { status: 200 });
      }
      if (String(input).startsWith("/api/v1/notices")) {
        return new Response(JSON.stringify({ items: [], page: 1, limit: 20, total: 0, pages: 0 }), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Bandeja/ }));
    expect(await screen.findByRole("heading", { name: "Bandeja de decisión técnica" })).toBeInTheDocument();
  });

  it("respeta 4000 caracteres tanto en alta como en comparación", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify([]), { status: 200 }),
    );
    render(<App />);
    const input = screen.getByRole("textbox", { name: "¿Qué has observado?" });
    expect(input).toHaveAttribute("maxlength", "4000");
    expect(input).toHaveAttribute("minlength", "1");
    await userEvent.click(screen.getByRole("button", { name: /Comparación/ }));
    expect(screen.getByRole("textbox", { name: "Caso sintético" })).toHaveAttribute("maxlength", "4000");
  });

  it("envía un aviso breve directamente al triaje sin preguntas previas", async () => {
    const postCalls: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      if (path === "/api/v1/triage" && init?.method === "POST") {
        postCalls.push(path);
        return new Response(JSON.stringify(basicTriageResponse), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });
    render(<App />);

    await userEvent.type(
      screen.getByRole("textbox", { name: "¿Qué has observado?" }),
      "Fuego en cuadro eléctrico.",
    );
    await userEvent.click(screen.getByRole("button", { name: /Generar propuesta/ }));

    expect(await screen.findByText("Propuesta creada")).toBeInTheDocument();
    expect(postCalls).toEqual(["/api/v1/triage"]);
    expect(screen.queryByText(/Necesitamos un poco más de información/i)).not.toBeInTheDocument();
  });

  it("separa prioridad de revisión e incertidumbre sin mostrar confianza", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/v1/triage" && init?.method === "POST") {
        return new Response(JSON.stringify(basicTriageResponse), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });
    render(<App />);

    await userEvent.type(screen.getByRole("textbox", { name: "¿Qué has observado?" }), "Cable expuesto en el taller.");
    await userEvent.click(screen.getByRole("button", { name: /Generar propuesta/ }));

    const policy = await screen.findByLabelText("Prioridad e incertidumbre técnica");
    expect(within(policy).getByText("Prioridad de revisión")).toBeInTheDocument();
    expect(within(policy).getByText("Incertidumbre técnica")).toBeInTheDocument();
    expect(within(policy).getByText("La salida necesitó una corrección automática.")).toBeInTheDocument();
    expect(within(policy).getByText(/No es confianza del modelo/i)).toBeInTheDocument();
    expect(screen.queryByText(/Confianza IA/i)).not.toBeInTheDocument();
  });

  it("informa de forma discreta cuando el backend anonimiza el aviso", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/v1/triage" && init?.method === "POST") {
        return new Response(JSON.stringify({
          notice_id: "n-private",
          triage_run_id: "r-private",
          status: "pending_review",
          version: 0,
          provider: "local",
          model: "llama3.2:3b",
          created_at: "2026-09-13T10:00:00Z",
          category: "otros",
          urgency: "media",
          summary: "Aviso anonimizado preparado correctamente para posterior revisión humana técnica.",
          department: "prevencion",
          justification: "Propuesta sintética.",
          metrics: { evidence: [] },
          privacy: {
            redacted: true,
            redaction_count: 2,
            redaction_types: ["DNI_NIE", "EMAIL"],
          },
          similarity: {
            available: false,
            has_similar: false,
            match_count: 0,
            matches: [],
          },
        }), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });
    render(<App />);

    await userEvent.type(
      screen.getByRole("textbox", { name: "¿Qué has observado?" }),
      "DNI 12345678Z y correo juan@email.com",
    );
    await userEvent.click(screen.getByRole("button", { name: /Generar propuesta/ }));

    expect(await screen.findByText(
      "Se anonimizaron 2 datos personales antes de analizar el aviso.",
    )).toBeInTheDocument();
    expect(screen.getByText("DNI/NIE · correo electrónico")).toBeInTheDocument();
    expect(screen.queryByLabelText("Posibles avisos relacionados")).not.toBeInTheDocument();
  });

  it("muestra coincidencias como similitud semántica y no como confianza", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/v1/triage" && init?.method === "POST") {
        return new Response(JSON.stringify({
          notice_id: "n-current",
          triage_run_id: "r-current",
          status: "pending_review",
          version: 0,
          provider: "local",
          model: "llama3.2:3b",
          created_at: "2026-09-13T10:00:00Z",
          category: "riesgo_electrico",
          urgency: "alta",
          summary: "Cable atravesando pasillo requiere aislamiento preventivo y revisión técnica inmediata.",
          department: "mantenimiento",
          justification: "Propuesta sintética.",
          metrics: { evidence: [] },
          privacy: { redacted: false, redaction_count: 0, redaction_types: [] },
          similarity: {
            available: true,
            has_similar: true,
            match_count: 1,
            matches: [{
              notice_id: "n-previous",
              score: 0.87,
              same_location: true,
              location: "Almacén",
              created_at: "2026-09-12T10:00:00Z",
              category: "riesgo_electrico",
              urgency: "alta",
            }],
          },
        }), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });
    render(<App />);

    await userEvent.type(
      screen.getByRole("textbox", { name: "¿Qué has observado?" }),
      "Cable atravesando el pasillo",
    );
    await userEvent.click(screen.getByRole("button", { name: /Generar propuesta/ }));

    const related = await screen.findByLabelText("Posibles avisos relacionados");
    expect(within(related).getByText("Posible riesgo recurrente")).toBeInTheDocument();
    expect(within(related).getByText("Se ha encontrado 1 aviso similar.")).toBeInTheDocument();
    expect(within(related).getByText("1 pertenece también a esta zona.")).toBeInTheDocument();
    expect(within(related).getByText("87% similar")).toHaveAttribute(
      "title",
      "Similitud semántica; no es probabilidad ni confianza del modelo.",
    );
    expect(within(related).getByText(/no confirma que sea el mismo incidente/i)).toBeInTheDocument();
  });

  it("no ocupa espacio cuando la similitud está disponible pero no hay coincidencias", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/v1/triage" && init?.method === "POST") {
        return new Response(JSON.stringify({
          notice_id: "n-without-matches",
          triage_run_id: "r-without-matches",
          status: "pending_review",
          version: 0,
          provider: "local",
          model: "llama3.2:3b",
          created_at: "2026-09-13T10:00:00Z",
          category: "otros",
          urgency: "media",
          summary: "Aviso sintético preparado correctamente para una posterior revisión humana técnica.",
          department: "prevencion",
          justification: "Propuesta sintética.",
          metrics: { evidence: [] },
          privacy: { redacted: false, redaction_count: 0, redaction_types: [] },
          similarity: {
            available: true,
            has_similar: false,
            match_count: 0,
            matches: [],
          },
        }), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });
    render(<App />);

    await userEvent.type(
      screen.getByRole("textbox", { name: "¿Qué has observado?" }),
      "Aviso sin coincidencias históricas",
    );
    await userEvent.click(screen.getByRole("button", { name: /Generar propuesta/ }));

    expect(await screen.findByText("Propuesta creada")).toBeInTheDocument();
    expect(screen.queryByLabelText("Posibles avisos relacionados")).not.toBeInTheDocument();
  });

  it("muestra propuestas, costes y fallos de una comparación", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/v1/catalogs") {
        return new Response(JSON.stringify(catalogs), { status: 200 });
      }
      if (String(input) === "/api/v1/risk-matrix") {
        return new Response(JSON.stringify(riskMatrix), { status: 200 });
      }
      if (String(input) === "/api/v1/comparisons" && init?.method === "POST") {
        return new Response(JSON.stringify({
          comparison_id: "c-1",
          created_at: "2026-09-11T15:00:00Z",
          results: [
            {
              provider: "local",
              result: {
                category: "riesgo_electrico",
                urgency: "alta",
                summary: "Cable expuesto requiere aislamiento inmediato y una revisión técnica prioritaria.",
                department: "mantenimiento",
                justification: "Regla sintética.",
              },
              error_code: null,
              metrics: {
                provider: "local",
                model: "llama3.2:3b",
                latency_ms: 25,
                repair_attempts: 0,
                total_tokens: 42,
                api_cost: "0",
                api_cost_currency: "USD",
                evidence: [
                  {
                    source_id: "RM-ELEC-001",
                    title: "Matriz de riesgos PRL",
                    section: "Regla RM-ELEC-001",
                    category: "riesgo_electrico",
                    excerpt: "Regla de matriz sintética.",
                    source_type: "risk_matrix",
                    version: "1.0.0",
                    score: 1,
                  },
                  {
                    source_id: "PRL-EL-04",
                    title: "Procedimiento interno de riesgo eléctrico",
                    section: "Apartado 3.2 · Aislamiento de la zona",
                    category: "riesgo_electrico",
                    excerpt: "Fragmento preventivo sintético.",
                    source_type: "preventive_document",
                    version: "1.0.0",
                    score: 9,
                  },
                ],
              },
            },
            {
              provider: "external",
              result: null,
              error_code: "provider_unavailable",
              metrics: {
                provider: "external",
                model: "gemini-prueba",
                latency_ms: 10,
                repair_attempts: 0,
                total_tokens: null,
                api_cost: null,
                api_cost_currency: null,
              },
            },
          ],
          review: null,
        }), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /Comparación/ }));
    await user.type(screen.getByRole("textbox", { name: "Caso sintético" }), "Cable expuesto");
    await user.click(screen.getByRole("button", { name: "Ejecutar ambos motores" }));

    expect(await screen.findByRole("heading", { name: "Riesgo eléctrico" })).toBeInTheDocument();
    expect(screen.getByText("0 USD")).toBeInTheDocument();
    expect(screen.getByText("Código: provider_unavailable")).toBeInTheDocument();
    expect(screen.getByText("Explicación del modelo")).toBeInTheDocument();
    expect(screen.getAllByText(/RM-ELEC-001/).length).toBeGreaterThan(0);
    expect(screen.getByText("Ver JSON estructurado")).toBeInTheDocument();
    expect(screen.getByText("Procedimiento interno de riesgo eléctrico")).toBeInTheDocument();
    expect(screen.getByText(/Apartado 3.2/)).toBeInTheDocument();
  });

  it("muestra calidad, latencia y coste medios del benchmark", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/v1/risk-matrix") {
        return new Response(JSON.stringify(riskMatrix), { status: 200 });
      }
      if (String(input) === "/api/v1/evaluations" && init?.method === "POST") {
        return new Response(JSON.stringify({
          dataset_version: "1.0.0",
          generated_at: "2026-09-12T10:00:00Z",
          disclaimer: "Resultados académicos sobre datos sintéticos.",
          summaries: [
            {
              provider: "local",
              cases: 14,
              category_accuracy: 0.8,
              urgency_accuracy: 0.7,
              department_accuracy: 0.6,
              json_valid_rate: 1,
              mean_latency_ms: 120,
              mean_api_cost: "0",
              api_cost_currency: null,
              reviewed_notices: 0,
              human_correction_rate: null,
            },
            {
              provider: "external",
              cases: 14,
              category_accuracy: 0.9,
              urgency_accuracy: 0.8,
              department_accuracy: 0.7,
              json_valid_rate: 1,
              mean_latency_ms: 240,
              mean_api_cost: "0.0012",
              api_cost_currency: "USD",
              reviewed_notices: 0,
              human_correction_rate: null,
            },
          ],
        }), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /Comparación/ }));
    await user.click(screen.getByRole("button", { name: "Ejecutar benchmark" }));

    expect(await screen.findByText("Ollama · local")).toBeInTheDocument();
    expect(screen.getByText("Gemini · externo")).toBeInTheDocument();
    expect(screen.getByText("120 ms")).toBeInTheDocument();
    expect(screen.getByText("0.0012 USD")).toBeInTheDocument();
    expect(screen.getAllByText("80%").length).toBeGreaterThan(0);
  });

  it("evalúa el historial por proveedor desde el resumen de la API", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/v1/metrics/summary") {
        return new Response(JSON.stringify({
          total_notices: 12,
          total_runs: 12,
          pending_review: 2,
          reviewed: 10,
          approved: 8,
          modified: 2,
          rejected: 0,
          acceptance_rate: 0.8,
          correction_rate: 0.2,
          rejection_rate: 0,
          review_policy_observations: 12,
          pending_high_priority: 1,
          pending_critical_priority: 1,
          uncertainty: [
            { level: "low", runs: 6, rate: 0.5, reviewed_runs: 5, human_correction_rate: 0.1 },
            { level: "medium", runs: 4, rate: 0.3333, reviewed_runs: 3, human_correction_rate: 0.3333 },
            { level: "high", runs: 2, rate: 0.1667, reviewed_runs: 2, human_correction_rate: 0.5 },
          ],
          providers: [
            { provider: "local", models: ["llama3.2:3b"], runs: 6, reviewed_runs: 5, mean_latency_ms: 2180, mean_provider_attempts: 2.2, repair_rate: 0.14, mean_repair_attempts: 0.14, success_rate: 1, json_valid_rate: 1, human_agreement_rate: 0.8, mean_total_tokens: 120, token_observations: 6, mean_api_cost: "0", api_cost_currency: null, cost_observations: 6, temperatures: [0], top_p_values: [0.9] },
            { provider: "external", models: ["gemini-prueba"], runs: 6, reviewed_runs: 5, mean_latency_ms: 740, mean_provider_attempts: 2, repair_rate: 0.02, mean_repair_attempts: 0.02, success_rate: 1, json_valid_rate: 1, human_agreement_rate: 0.94, mean_total_tokens: 100, token_observations: 6, mean_api_cost: "0.0004", api_cost_currency: "USD", cost_observations: 6, temperatures: [0], top_p_values: [0.9] },
          ],
        }), { status: 200 });
      }
      if (String(input) === "/api/v1/metrics/preventive?window_days=30") {
        return new Response(JSON.stringify(preventiveAnalytics), { status: 200 });
      }
      if (String(input) === "/api/v1/catalogs") return new Response(JSON.stringify(catalogs), { status: 200 });
      if (String(input) === "/api/v1/risk-matrix") return new Response(JSON.stringify(riskMatrix), { status: 200 });
      return new Response(JSON.stringify([]), { status: 200 });
    });

    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Panel/ }));

    expect(await screen.findByRole("heading", { name: "Qué modelo funciona mejor, medido con datos." })).toBeInTheDocument();
    expect(screen.getByText("2.18 s")).toBeInTheDocument();
    expect(screen.getByText("740 ms")).toBeInTheDocument();
    expect(screen.getByText("0.0004 USD")).toBeInTheDocument();
    expect(screen.getByText("94%")).toBeInTheDocument();
    expect(screen.getAllByText("Acuerdo con técnico")).toHaveLength(2);
    expect(screen.getAllByText("Salidas reparadas")).toHaveLength(2);
    expect(screen.getByText("Aprobadas sin cambios")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Incertidumbre técnica y corrección" })).toBeInTheDocument();
    expect(screen.getByText("Incertidumbre Alta")).toBeInTheDocument();
    expect(screen.getAllByText("50%").length).toBeGreaterThanOrEqual(2);
    expect(await screen.findByRole("heading", { name: "Panorama preventivo" })).toBeInTheDocument();
    expect(screen.getByText("Zona con más avisos confirmados")).toBeInTheDocument();
    expect(screen.getAllByText("Almacén").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Caídas y obstáculos").length).toBeGreaterThan(0);
    expect(screen.getByText("Almacén · Caídas y obstáculos")).toBeInTheDocument();
    expect(screen.getByText("4 pendientes totales")).toBeInTheDocument();
  });

  it("muestra N/A cuando no existen propuestas con política versionada", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/v1/metrics/summary") {
        const emptyProvider = { models: [], runs: 0, reviewed_runs: 0, mean_latency_ms: null, mean_provider_attempts: null, repair_rate: null, mean_repair_attempts: null, success_rate: null, json_valid_rate: null, json_valid_observations: 0, human_agreement_rate: null, mean_total_tokens: null, token_observations: 0, mean_api_cost: null, api_cost_currency: null, cost_observations: 0, temperatures: [], top_p_values: [] };
        return new Response(JSON.stringify({
          total_notices: 0, total_runs: 0, pending_review: 0, reviewed: 0,
          approved: 0, modified: 0, rejected: 0, acceptance_rate: null,
          correction_rate: null, rejection_rate: null,
          review_policy_observations: 0, pending_high_priority: 0,
          pending_critical_priority: 0,
          uncertainty: [
            { level: "low", runs: 0, rate: null, reviewed_runs: 0, human_correction_rate: null },
            { level: "medium", runs: 0, rate: null, reviewed_runs: 0, human_correction_rate: null },
            { level: "high", runs: 0, rate: null, reviewed_runs: 0, human_correction_rate: null },
          ],
          providers: [
            { ...emptyProvider, provider: "local" },
            { ...emptyProvider, provider: "external" },
          ],
        }), { status: 200 });
      }
      if (String(input) === "/api/v1/metrics/preventive?window_days=30") {
        return new Response(JSON.stringify(emptyPreventiveAnalytics), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Panel/ }));

    expect(await screen.findByText(/N\/A · Aún no hay propuestas/i)).toBeInTheDocument();
    expect(await screen.findByText(/Datos insuficientes para identificar una tendencia/i)).toBeInTheDocument();
    expect(screen.getByText("Sin avisos confirmados en este periodo.")).toBeInTheDocument();
  });

  it("cambia la ventana del panorama sin ocultar las métricas IA", async () => {
    const requested: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      requested.push(url);
      if (url === "/api/v1/metrics/summary") {
        const emptyProvider = { models: [], runs: 0, reviewed_runs: 0, mean_latency_ms: null, mean_provider_attempts: null, repair_rate: null, mean_repair_attempts: null, success_rate: null, json_valid_rate: null, json_valid_observations: 0, human_agreement_rate: null, mean_total_tokens: null, token_observations: 0, mean_api_cost: null, api_cost_currency: null, cost_observations: 0, temperatures: [], top_p_values: [] };
        return new Response(JSON.stringify({
          total_notices: 0, total_runs: 0, pending_review: 0, reviewed: 0,
          approved: 0, modified: 0, rejected: 0, acceptance_rate: null,
          correction_rate: null, rejection_rate: null, review_policy_observations: 0,
          pending_high_priority: 0, pending_critical_priority: 0,
          uncertainty: [
            { level: "low", runs: 0, rate: null, reviewed_runs: 0, human_correction_rate: null },
            { level: "medium", runs: 0, rate: null, reviewed_runs: 0, human_correction_rate: null },
            { level: "high", runs: 0, rate: null, reviewed_runs: 0, human_correction_rate: null },
          ],
          providers: [{ ...emptyProvider, provider: "local" }, { ...emptyProvider, provider: "external" }],
        }), { status: 200 });
      }
      if (url.startsWith("/api/v1/metrics/preventive")) {
        const selected = url.endsWith("=7") ? "7" : "30";
        return new Response(JSON.stringify({ ...preventiveAnalytics, period: { ...preventiveAnalytics.period, window: selected } }), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Panel/ }));
    await screen.findByRole("heading", { name: "Panorama preventivo" });
    await userEvent.click(screen.getByRole("button", { name: "7 días" }));

    expect(requested).toContain("/api/v1/metrics/preventive?window_days=7");
    expect(screen.getByText("Incertidumbre técnica y corrección")).toBeInTheDocument();
  });

  it("mantiene el bloque IA cuando el panorama preventivo no está disponible", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/v1/metrics/summary") {
        return new Response(JSON.stringify(emptyMetricsSummary), { status: 200 });
      }
      if (String(input).startsWith("/api/v1/metrics/preventive")) {
        return new Response(
          JSON.stringify({ error: { message: "Panorama preventivo no disponible." } }),
          { status: 503 },
        );
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Panel/ }));

    expect(await screen.findByText("Panorama preventivo no disponible.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Incertidumbre técnica y corrección" })).toBeInTheDocument();
  });

  it("contrasta ambos modelos y registra la decisión humana", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      if (String(input) === "/api/v1/catalogs") return new Response(JSON.stringify(catalogs), { status: 200 });
      if (String(input) === "/api/v1/risk-matrix") return new Response(JSON.stringify(riskMatrix), { status: 200 });
      if (String(input) === "/api/v1/comparisons" && init?.method === "POST") {
        const common = { provider_attempts: 2, total_tokens: 80, api_cost_currency: "USD", parameters: {}, started_at: "2026-09-12T10:00:00Z", completed_at: "2026-09-12T10:00:01Z", input_tokens: 50, output_tokens: 30, success: true, json_valid: true, error_type: null, computational_cost: null, pricing: null };
        return new Response(JSON.stringify({ comparison_id: "comparison-1", created_at: "2026-09-12T10:00:00Z", review: null, results: [
          { provider: "local", error_code: null, result: { category: "riesgo_electrico", urgency: "alta", department: "mantenimiento", summary: "Cable expuesto requiere aislamiento inmediato y una revisión técnica prioritaria.", justification: "Regla local." }, metrics: { ...common, provider: "local", model: "llama3.2:3b", latency_ms: 2200, repair_attempts: 1, api_cost: "0" } },
          { provider: "external", error_code: null, result: { category: "riesgo_electrico", urgency: "media", department: "mantenimiento", summary: "Cable expuesto requiere revisión preventiva y comprobación técnica del área.", justification: "Regla externa." }, metrics: { ...common, provider: "external", model: "gemini-prueba", latency_ms: 700, repair_attempts: 0, api_cost: "0.0004" } },
        ] }), { status: 200 });
      }
      if (String(input) === "/api/v1/comparisons/comparison-1/review" && init?.method === "POST") {
        return new Response(JSON.stringify({ id: "review-1", comparison_id: "comparison-1", category: "riesgo_electrico", urgency: "alta", department: "mantenimiento", reviewer: "Técnica demo", comment: "Referencia comprobada.", created_at: "2026-09-12T10:01:00Z" }), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /Comparación/ }));
    await user.type(screen.getByRole("textbox", { name: "Caso sintético" }), "Cable expuesto");
    await user.click(screen.getByRole("button", { name: "Ejecutar ambos motores" }));

    expect(await screen.findAllByText("✓ Coinciden")).toHaveLength(2);
    expect(screen.getByText("⚠ Discrepan")).toBeInTheDocument();
    expect(screen.getByText("1.50 s de diferencia")).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Persona revisora" }), "Técnica demo");
    await user.type(screen.getByRole("textbox", { name: "Comentario" }), "Referencia comprobada.");
    await user.click(screen.getByRole("button", { name: "Registrar referencia humana" }));

    expect(await screen.findByText("Referencia humana registrada")).toBeInTheDocument();
    const verdict = screen.getByRole("table", { name: "Coincidencia de cada modelo con la referencia humana" });
    expect(within(verdict).getByText("100%")).toBeInTheDocument();
    expect(within(verdict).getByText("67%")).toBeInTheDocument();
    expect(within(verdict).getByText("Departamento")).toBeInTheDocument();
  });

  it("permite consultar la matriz de riesgos activa", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/v1/risk-matrix") {
        return new Response(JSON.stringify(riskMatrix), { status: 200 });
      }
      if (String(input) === "/api/v1/knowledge-base") {
        return new Response(JSON.stringify(knowledgeBase), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Matriz/ }));

    expect(await screen.findByRole("heading", { name: "Matriz de riesgos visible y auditable." })).toBeInTheDocument();
    expect(screen.getByText("RM-ELEC-001")).toBeInTheDocument();
    expect(screen.getByText(/ubicación es contexto libre opcional/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "RAG preventivo" })).toBeInTheDocument();
    expect(screen.getByText("data/knowledge/prevention_docs.v1.json")).toBeInTheDocument();
    expect(screen.getByText(/PDF y DOCX no se leen directamente todavía/i)).toBeInTheDocument();
    await userEvent.click(screen.getByText("Ver inventario de fuentes"));
    expect(screen.getByText("Procedimiento interno de riesgo eléctrico")).toBeInTheDocument();
  });

  it("muestra los avisos cerrados y su decisión en el registro", async () => {
    const reviewedNotice = {
      id: "n-reviewed",
      text: "Cable recalentado junto al cuadro principal.",
      location: "Taller",
      created_at: "2026-09-11T10:42:00Z",
      triage_runs: [{
        id: "r-reviewed",
        request_id: "request-reviewed",
        provider: "local",
        model: "llama3.2:3b",
        status: "modified",
        version: 1,
        created_at: "2026-09-11T10:42:10Z",
        metrics: null,
        similarity: {
          available: true,
          has_similar: true,
          match_count: 1,
          matches: [{
            notice_id: "n-related",
            score: 0.91,
            same_location: true,
            location: "Taller",
            created_at: "2026-09-10T10:00:00Z",
            category: "riesgo_electrico",
            urgency: "alta",
          }],
        },
        uncertainty: { level: "high", reasons: ["generic_category", "incomplete_evidence"] },
        review_priority: { level: "high", reasons: ["high_urgency", "high_uncertainty", "recurrent_same_location"] },
        review_policy_version: "v1",
        proposal: { category: "riesgo_electrico", urgency: "alta", summary: "Cable recalentado que requiere revisión técnica prioritaria.", department: "mantenimiento", justification: "Regla sintética." },
        review: { id: "review-1", decision: "modified", final_classification: { category: "riesgo_electrico", urgency: "critica", department: "seguridad" }, reviewer: "Técnica PRL", comment: "Se eleva la prioridad.", created_at: "2026-09-11T10:48:00Z" },
      }],
    };
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/v1/catalogs") return new Response(JSON.stringify(catalogs), { status: 200 });
      if (url === "/api/v1/risk-matrix") return new Response(JSON.stringify(riskMatrix), { status: 200 });
      if (url === "/api/v1/notices/n-reviewed/audit-events") return new Response(JSON.stringify([
        { id: 1, notice_id: "n-reviewed", triage_run_id: "r-reviewed", event_type: "triage_created", previous_status: null, new_status: "pending_review", actor: null, created_at: "2026-09-11T10:42:10Z" },
        { id: 2, notice_id: "n-reviewed", triage_run_id: "r-reviewed", event_type: "review_completed", previous_status: "pending_review", new_status: "modified", actor: "Técnica PRL", created_at: "2026-09-11T10:48:00Z" },
      ]), { status: 200 });
      if (url.startsWith("/api/v1/notices")) {
        const params = new URL(`http://test${url}`).searchParams;
        const items = params.get("closed") === "true" ? [reviewedNotice] : [];
        return new Response(JSON.stringify({ items, page: 1, limit: 20, total: items.length, pages: items.length ? 1 : 0 }), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /Registro/ }));
    expect(await screen.findByRole("heading", { name: "Registro de decisiones cerradas" })).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: /Cable recalentado/ }));

    expect(await screen.findByText("Revisado por Técnica PRL")).toBeInTheDocument();
    expect(screen.getByText("Clasificación corregida")).toBeInTheDocument();
    expect(screen.getByText("Urgencia: Alta → Crítica")).toBeInTheDocument();
    expect(screen.getByText(/Clasificación final: Riesgo eléctrico · Crítica · Seguridad/)).toBeInTheDocument();
    expect(screen.getByLabelText("Posibles avisos relacionados")).toBeInTheDocument();
    expect(screen.getByText("La propuesta presenta incertidumbre técnica alta.")).toBeInTheDocument();
    expect(screen.getByText("Existen avisos similares en la misma zona.")).toBeInTheDocument();
    expect(screen.getByText("Política v1")).toBeInTheDocument();
    expect(fetchSpy.mock.calls.some(([input]) => String(input).includes("closed=true"))).toBe(true);
  });

  it("limita las correcciones humanas a los catálogos del backend", async () => {
    const notices = [{
      id: "n-1",
      text: "Cable atravesando una zona de paso.",
      location: "Taller",
      created_at: "2026-09-11T15:00:00Z",
      triage_runs: [{
        id: "r-1",
        provider: "local",
        status: "pending_review",
        version: 0,
        proposal: {
          category: "caidas_obstaculos",
          urgency: "critica",
          summary: "Cable atravesando zona de paso requiere revisión preventiva técnica prioritaria.",
          department: "mantenimiento",
          justification: "Regla sintética.",
        },
        uncertainty: { level: "low", reasons: [] },
        review_priority: { level: "critical", reasons: ["critical_urgency"] },
        review_policy_version: "v1",
      }],
    }];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/v1/catalogs") {
        return new Response(JSON.stringify(catalogs), { status: 200 });
      }
      if (String(input) === "/api/v1/risk-matrix") {
        return new Response(JSON.stringify(riskMatrix), { status: 200 });
      }
      if (String(input) === "/api/v1/notices/n-1/audit-events") {
        return new Response(JSON.stringify([{ id: 1, notice_id: "n-1", triage_run_id: "r-1", event_type: "triage_created", previous_status: null, new_status: "pending_review", actor: null, created_at: "2026-09-11T15:00:00Z" }]), { status: 200 });
      }
      if (String(input).startsWith("/api/v1/notices")) {
        return new Response(JSON.stringify({ items: notices, page: 1, limit: 20, total: 1, pages: 1 }), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /Bandeja/ }));
    await user.click(await screen.findByRole("button", { name: /Cable atravesando/ }));
    expect(document.querySelector(".priority-critical")).toHaveTextContent("Crítica");
    expect(document.querySelector(".urgency.danger")).toHaveTextContent("Crítica");
    expect(await screen.findByText("Auditoría HITL")).toBeInTheDocument();
    expect(screen.getByText("Ollama · local propone")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Corregir" }));

    const category = screen.getAllByRole("combobox", { name: "Categoría" })[1];
    const urgency = screen.getAllByRole("combobox", { name: "Urgencia" })[1];
    const department = screen.getAllByRole("combobox", { name: "Departamento" })[0];
    expect(category).toHaveDisplayValue("Caídas y obstáculos");
    expect(category.querySelectorAll("option")).toHaveLength(9);
    expect(urgency.querySelectorAll("option")).toHaveLength(4);
    expect(department.querySelectorAll("option")).toHaveLength(4);
  });

  it("filtra y ordena la bandeja por prioridad de revisión", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/v1/catalogs") return new Response(JSON.stringify(catalogs), { status: 200 });
      if (String(input).startsWith("/api/v1/notices")) {
        return new Response(JSON.stringify({ items: [], page: 1, limit: 20, total: 0, pages: 0 }), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Bandeja/ }));

    await userEvent.selectOptions(await screen.findByRole("combobox", { name: "Prioridad" }), "high");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Orden" }), "review_priority");

    expect(fetchSpy.mock.calls.some(([input]) => {
      const url = String(input);
      return url.includes("review_priority=high") && url.includes("order=review_priority");
    })).toBe(true);
  });
});
