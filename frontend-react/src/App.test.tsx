import { cleanup, render, screen } from "@testing-library/react";
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

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("IAviso Seguro", () => {
  it("mantiene visible que la revisión humana es obligatoria", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify([]), { status: 200 }));
    render(<App />);
    expect(screen.getByText("Revisión obligatoria")).toBeInTheDocument();
    expect(screen.getByText(/La IA propone/)).toBeInTheDocument();
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

  it("respeta el contrato de longitud de los avisos", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify([]), { status: 200 }),
    );
    render(<App />);
    const input = screen.getByRole("textbox", { name: "¿Qué has observado?" });
    expect(input).toHaveAttribute("maxlength", "4000");
    expect(input).toHaveAttribute("minlength", "1");
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
    expect(screen.getByText(/RM-ELEC-001/)).toBeInTheDocument();
    expect(screen.getByText("Ver JSON estructurado")).toBeInTheDocument();
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
          providers: [
            { provider: "local", models: ["llama3.2:3b"], runs: 6, reviewed_runs: 5, mean_latency_ms: 2180, mean_provider_attempts: 2.2, repair_rate: 0.14, mean_repair_attempts: 0.14, success_rate: 1, json_valid_rate: 1, human_agreement_rate: 0.8, mean_total_tokens: 120, token_observations: 6, mean_api_cost: "0", api_cost_currency: null, cost_observations: 6, temperatures: [0], top_p_values: [0.9] },
            { provider: "external", models: ["gemini-prueba"], runs: 6, reviewed_runs: 5, mean_latency_ms: 740, mean_provider_attempts: 2, repair_rate: 0.02, mean_repair_attempts: 0.02, success_rate: 1, json_valid_rate: 1, human_agreement_rate: 0.94, mean_total_tokens: 100, token_observations: 6, mean_api_cost: "0.0004", api_cost_currency: "USD", cost_observations: 6, temperatures: [0], top_p_values: [0.9] },
          ],
        }), { status: 200 });
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
    expect(screen.getByText("✓ 3/3")).toBeInTheDocument();
    expect(screen.getByText("2/3")).toBeInTheDocument();
  });

  it("permite consultar la matriz de riesgos activa", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/v1/risk-matrix") {
        return new Response(JSON.stringify(riskMatrix), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /Matriz/ }));

    expect(await screen.findByRole("heading", { name: "Matriz de riesgos visible y auditable." })).toBeInTheDocument();
    expect(screen.getByText("RM-ELEC-001")).toBeInTheDocument();
    expect(screen.getByText(/ubicación es contexto libre opcional/i)).toBeInTheDocument();
  });

  it("filtra la bandeja y muestra la corrección en la auditoría", async () => {
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
        const status = new URL(`http://test${url}`).searchParams.get("status");
        const items = status === "modified" ? [reviewedNotice] : [];
        return new Response(JSON.stringify({ items, page: 1, limit: 20, total: items.length, pages: items.length ? 1 : 0 }), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /Bandeja/ }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Estado" }), "modified");
    await user.click(await screen.findByRole("button", { name: /Cable recalentado/ }));

    expect(await screen.findByText("Revisado por Técnica PRL")).toBeInTheDocument();
    expect(screen.getByText("Clasificación corregida")).toBeInTheDocument();
    expect(screen.getByText("Urgencia: Alta → Crítica")).toBeInTheDocument();
    expect(fetchSpy.mock.calls.some(([input]) => String(input).includes("status=modified"))).toBe(true);
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
          urgency: "alta",
          summary: "Cable atravesando zona de paso requiere revisión preventiva técnica prioritaria.",
          department: "mantenimiento",
          justification: "Regla sintética.",
        },
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
});
