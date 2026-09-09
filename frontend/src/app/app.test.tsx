/**
 * Phase 1 frontend tests: the app shell renders and routing works.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { routes } from "./router";

function renderAt(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("app shell", () => {
  it("renders the shell with the brand heading on the patient welcome route", () => {
    renderAt("/patient/welcome");
    expect(
      screen.getByRole("heading", { name: "MediKiosk" }),
    ).toBeInTheDocument();
  });

  it("redirects the root path to the patient welcome screen", () => {
    renderAt("/");
    expect(
      screen.getByRole("heading", { name: "MediKiosk" }),
    ).toBeInTheDocument();
  });

  it("renders the doctor dashboard route", () => {
    renderAt("/doctor/dashboard");
    expect(
      screen.getByRole("heading", { name: "Dashboard" }),
    ).toBeInTheDocument();
  });

  it("renders the doctor case route with a route param", async () => {
    renderAt("/doctor/case/abc-123");
    expect(
      await screen.findByRole("heading", { name: "Case" }),
    ).toBeInTheDocument();
  });

  it("renders the backend health badge when connected", async () => {
    renderAt("/patient/welcome");
    expect(await screen.findByText("Backend connected")).toBeInTheDocument();
  });
});