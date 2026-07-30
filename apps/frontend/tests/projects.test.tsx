/**
 * Projects, end to end against the documented API.
 *
 * The headline case is the first one: before this EPIC the creation form
 * submitted `status: "active"` and an optional customer, so a project
 * could not be created at all without editing the payload by hand.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ProjectsPage from "@/app/projects/page";
import NewProjectPage from "@/app/projects/new/page";
import { PROJECT_STATUSES } from "@/lib/contracts";

import { aPage, aProject, stubBackend } from "./_backend";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useParams: () => ({}),
  usePathname: () => "/projects",
}));

async function fillRequiredFields(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/Codice progetto/), "CP-GAMMA-2026");
  await user.type(screen.getByLabelText(/Nome progetto/), "Cabina Gamma");
  await user.type(screen.getByLabelText(/Committente/), "Distributore Nazionale");
}

describe("project creation", () => {
  it("sends a payload the backend accepts and navigates to the project", async () => {
    const backend = stubBackend({
      "GET /projects/": { body: aPage([]) },
      "POST /projects/": { status: 201, body: aProject({ id: 42 }) },
    });

    const user = userEvent.setup();
    render(<NewProjectPage />);

    await fillRequiredFields(user);
    await user.click(screen.getByRole("button", { name: /Crea progetto/ }));

    await waitFor(() => {
      expect(backend.requestsFor("POST", "/projects/")).toHaveLength(1);
    });

    expect(backend.requestsFor("POST", "/projects/")[0].body).toEqual({
      name: "Cabina Gamma",
      code: "CP-GAMMA-2026",
      customer: "Distributore Nazionale",
      status: "planning",
    });

    await waitFor(() => expect(push).toHaveBeenCalledWith("/projects/42"));
  });

  it("offers only statuses the backend declares", () => {
    stubBackend({ "GET /projects/": { body: aPage([]) } });

    render(<NewProjectPage />);

    const options = screen
      .getAllByRole("option")
      .map((option) => (option as HTMLOptionElement).value);

    expect(options).toEqual([...PROJECT_STATUSES]);

    // The four statuses the previous frontend offered and the backend
    // never accepted.
    for (const invented of ["active", "on_hold", "completed", "cancelled"]) {
      expect(options).not.toContain(invented);
    }
  });

  it("refuses to submit without the customer the backend requires", async () => {
    const backend = stubBackend({ "GET /projects/": { body: aPage([]) } });

    const user = userEvent.setup();
    render(<NewProjectPage />);

    await user.type(screen.getByLabelText(/Codice progetto/), "CP-1");
    await user.type(screen.getByLabelText(/Nome progetto/), "Cabina");
    await user.click(screen.getByRole("button", { name: /Crea progetto/ }));

    expect(await screen.findByText("Campo obbligatorio.")).toBeVisible();
    expect(backend.requestsFor("POST", "/projects/")).toHaveLength(0);
  });

  it("shows a 422 from the backend against the field it names", async () => {
    stubBackend({
      "GET /projects/": { body: aPage([]) },
      "POST /projects/": {
        status: 422,
        body: {
          detail: [
            {
              loc: ["body", "code"],
              msg: "String should have at least 2 characters",
              type: "string_too_short",
            },
          ],
        },
      },
    });

    const user = userEvent.setup();
    render(<NewProjectPage />);

    await fillRequiredFields(user);
    await user.click(screen.getByRole("button", { name: /Crea progetto/ }));

    expect(
      await screen.findByText("Deve contenere almeno 2 caratteri."),
    ).toBeVisible();

    // The form stays open with the user's input intact.
    expect(screen.getByLabelText(/Nome progetto/)).toHaveValue(
      "Cabina Gamma",
    );

    expect(push).not.toHaveBeenCalledWith(expect.stringMatching(/^\/projects\/\d/));
  });

  it("reports a duplicate code with the backend's own words", async () => {
    stubBackend({
      "GET /projects/": { body: aPage([]) },
      "POST /projects/": {
        status: 409,
        body: { detail: "Project code 'CP-GAMMA-2026' already exists" },
      },
    });

    const user = userEvent.setup();
    render(<NewProjectPage />);

    await fillRequiredFields(user);
    await user.click(screen.getByRole("button", { name: /Crea progetto/ }));

    expect(
      await screen.findByText(
        "Project code 'CP-GAMMA-2026' already exists",
      ),
    ).toBeVisible();
  });

  it("surfaces a 500 without pretending the project was created", async () => {
    stubBackend({
      "GET /projects/": { body: aPage([]) },
      "POST /projects/": { status: 500, body: { detail: "boom" } },
    });

    const user = userEvent.setup();
    render(<NewProjectPage />);

    await fillRequiredFields(user);
    await user.click(screen.getByRole("button", { name: /Crea progetto/ }));

    expect(
      await screen.findByText(/il backend ha risposto con un errore interno/i),
    ).toBeVisible();

    expect(push).not.toHaveBeenCalledWith(
      expect.stringMatching(/^\/projects\/\d/),
    );
  });
});

describe("project listing", () => {
  it("renders the projects the backend returned", async () => {
    stubBackend({
      "GET /projects/": {
        body: aPage([
          aProject({ id: 1, name: "Cabina Gamma", code: "CP-1" }),
          aProject({
            id: 2,
            name: "Cabina Nord",
            code: "CP-2",
            status: "commissioning",
          }),
        ]),
      },
    });

    render(<ProjectsPage />);

    expect(await screen.findByText("Cabina Gamma")).toBeVisible();
    expect(screen.getByText("Cabina Nord")).toBeVisible();

    // The label appears on the card and in the status filter's options.
    expect(
      screen.getAllByText("Messa in servizio").length,
    ).toBeGreaterThan(1);
  });

  it("shows an empty state rather than an error when there are none", async () => {
    stubBackend({ "GET /projects/": { body: aPage([]) } });

    render(<ProjectsPage />);

    expect(
      await screen.findByText("Nessun progetto disponibile"),
    ).toBeVisible();
  });

  it("flags a project whose lifecycle state makes it read-only", async () => {
    stubBackend({
      "GET /projects/": {
        body: aPage([aProject({ lifecycle_state: "archived" })]),
      },
    });

    render(<ProjectsPage />);

    expect(await screen.findByText("Archiviato")).toBeVisible();
  });

  it("offers a retry when the backend cannot be reached", async () => {
    const backend = stubBackend({
      "GET /projects/": [
        { networkFailure: true },
        { networkFailure: true },
        { body: aPage([aProject()]) },
      ],
    });

    const user = userEvent.setup();
    render(<ProjectsPage />);

    expect(
      await screen.findByText(/il backend SubstationOS non risponde/i),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: /Riprova/ }));

    expect(await screen.findByText("Cabina Primaria Gamma")).toBeVisible();

    // Two attempts on the first load (one retry), one on the manual retry.
    expect(backend.requestsFor("GET", "/projects/")).toHaveLength(3);
  });
});
