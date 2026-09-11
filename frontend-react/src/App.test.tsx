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
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify([]), { status: 200 }));
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
                latency_ms: 25,
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
                latency_ms: 10,
                total_tokens: null,
                api_cost: null,
                api_cost_currency: null,
              },
            },
          ],
        }), { status: 200 });
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /Comparación/ }));
    await user.type(screen.getByRole("textbox", { name: "Caso sintético" }), "Cable expuesto");
    await user.click(screen.getByRole("button", { name: "Ejecutar ambos motores" }));

    expect(await screen.findByText("riesgo electrico")).toBeInTheDocument();
    expect(screen.getByText("0 USD")).toBeInTheDocument();
    expect(screen.getByText("Código: provider_unavailable")).toBeInTheDocument();
    expect(screen.getByText("Explicación del modelo")).toBeInTheDocument();
    expect(screen.getByText(/RM-ELEC-001/)).toBeInTheDocument();
    expect(screen.getByText("Ver JSON estructurado")).toBeInTheDocument();
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
    vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify(notices), { status: 200 }),
    );

    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /Bandeja/ }));
    await user.click(await screen.findByRole("button", { name: /Cable atravesando/ }));
    await user.click(screen.getByRole("radio", { name: "Corregir" }));

    const category = screen.getByRole("combobox", { name: "Categoría" });
    const urgency = screen.getByRole("combobox", { name: "Urgencia" });
    const department = screen.getByRole("combobox", { name: "Departamento" });
    expect(category).toHaveDisplayValue("caidas obstaculos");
    expect(category.querySelectorAll("option")).toHaveLength(9);
    expect(urgency.querySelectorAll("option")).toHaveLength(4);
    expect(department.querySelectorAll("option")).toHaveLength(4);
  });
});
