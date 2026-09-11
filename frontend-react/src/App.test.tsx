import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

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
});
