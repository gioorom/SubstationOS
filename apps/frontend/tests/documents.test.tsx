/**
 * Documents against the hardened API (Milestone 30.1.3).
 *
 * Three properties this milestone changed, and each is asserted here:
 * lists arrive as a paged envelope; filtering and search are **sent to
 * the server** rather than applied locally; and the storage location is
 * gone from the contract entirely.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import DocumentsPage from "@/app/documents/page";

import {
  aDocument,
  aDocumentDetail,
  aPage,
  aProject,
  anUpload,
  stubBackend,
} from "./_backend";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => ({}),
  usePathname: () => "/documents",
}));

function pdf(name = "schema.pdf"): File {
  return new File([new Uint8Array([0x25, 0x50, 0x44, 0x46])], name, {
    type: "application/pdf",
  });
}

function queryOf(url: string): URLSearchParams {
  return new URL(url).searchParams;
}

// --- The paged envelope ----------------------------------------------------

describe("paginated document lists", () => {
  it("renders the items of a paged response", async () => {
    stubBackend({
      "GET /documents/": {
        body: aPage([
          aDocument({ id: 1, filename: "schema-funzionale.pdf" }),
          aDocument({
            id: 2,
            filename: "elenco-cavi.xlsx",
            file_format: "xlsx",
            category: "cable_list",
          }),
        ]),
      },
      "GET /projects/": { body: aPage([aProject()]) },
    });

    render(<DocumentsPage />);

    expect(await screen.findByText("schema-funzionale.pdf")).toBeVisible();
    expect(screen.getByText("elenco-cavi.xlsx")).toBeVisible();
  });

  it("reports the total from the server, not the page length", async () => {
    stubBackend({
      "GET /documents/": {
        body: aPage([aDocument()], { page: 1, page_size: 1, total: 42 }),
      },
      "GET /projects/": { body: aPage([aProject()]) },
    });

    render(<DocumentsPage />);

    const pagination = await screen.findByRole("navigation", {
      name: "Paginazione",
    });

    expect(within(pagination).getByText("42")).toBeVisible();
    expect(within(pagination).getByText(/1–1 di/)).toBeVisible();
  });

  it("asks the server for the next page", async () => {
    const backend = stubBackend({
      "GET /documents/": {
        body: aPage([aDocument()], { page: 1, page_size: 1, total: 3 }),
      },
      "GET /projects/": { body: aPage([aProject()]) },
    });

    const user = userEvent.setup();
    render(<DocumentsPage />);

    await user.click(
      await screen.findByRole("button", { name: /Successiva/ }),
    );

    await waitFor(() => {
      const requests = backend.requestsFor("GET", "/documents/");

      expect(
        requests.some((request) => queryOf(request.url).get("page") === "2"),
      ).toBe(true);
    });
  });

  it("hides the previous control on the first page", async () => {
    stubBackend({
      "GET /documents/": {
        body: aPage([aDocument()], { page: 1, page_size: 10, total: 30 }),
      },
      "GET /projects/": { body: aPage([aProject()]) },
    });

    render(<DocumentsPage />);

    expect(
      await screen.findByRole("button", { name: /Precedente/ }),
    ).toBeDisabled();
  });

  it("shows no pagination control for an empty registry", async () => {
    stubBackend({
      "GET /documents/": { body: aPage([]) },
      "GET /projects/": { body: aPage([aProject()]) },
    });

    render(<DocumentsPage />);

    expect(
      await screen.findByText("Nessun documento registrato."),
    ).toBeVisible();

    expect(
      screen.queryByRole("navigation", { name: "Paginazione" }),
    ).toBeNull();
  });
});

// --- Server-side filtering -------------------------------------------------

describe("filters are sent to the backend", () => {
  it("sends the search term as a query parameter", async () => {
    const backend = stubBackend({
      "GET /documents/": { body: aPage([aDocument()]) },
      "GET /projects/": { body: aPage([aProject()]) },
    });

    const user = userEvent.setup();
    render(<DocumentsPage />);

    await screen.findByText("schema-funzionale.pdf");

    await user.type(
      screen.getByPlaceholderText(/cerca/i),
      "cavi",
    );

    await waitFor(() => {
      const requests = backend.requestsFor("GET", "/documents/");

      expect(
        requests.some(
          (request) => queryOf(request.url).get("search") === "cavi",
        ),
      ).toBe(true);
    });
  });

  it("sends the category filter as a query parameter", async () => {
    const backend = stubBackend({
      "GET /documents/": { body: aPage([aDocument()]) },
      "GET /projects/": { body: aPage([aProject()]) },
    });

    const user = userEvent.setup();
    render(<DocumentsPage />);

    await user.selectOptions(
      await screen.findByLabelText("Categoria"),
      "cable_list",
    );

    await waitFor(() => {
      const requests = backend.requestsFor("GET", "/documents/");

      expect(
        requests.some(
          (request) =>
            queryOf(request.url).get("category") === "cable_list",
        ),
      ).toBe(true);
    });
  });

  it("does not filter the returned page locally", async () => {
    /**
     * The server said these two documents match; the client renders both
     * even though only one contains the search term, because filtering
     * one page would hide matches on every other.
     */

    const backend = stubBackend({
      "GET /documents/": { body: aPage([
        aDocument({ id: 1, filename: "elenco-cavi.pdf" }),
        aDocument({ id: 2, filename: "schema.pdf" }),
      ]) },
      "GET /projects/": { body: aPage([aProject()]) },
    });

    const user = userEvent.setup();
    render(<DocumentsPage />);

    await user.type(screen.getByPlaceholderText(/cerca/i), "cavi");

    await waitFor(() => {
      expect(
        backend.requestsFor("GET", "/documents/").length,
      ).toBeGreaterThan(1);
    });

    expect(await screen.findByText("schema.pdf")).toBeVisible();
    expect(screen.getByText("elenco-cavi.pdf")).toBeVisible();
  });

  it("offers every filter value the contract declares, not only those on the page", async () => {
    /**
     * Deriving options from the current page was correct only while the
     * client held the whole registry.
     */

    stubBackend({
      "GET /documents/": {
        body: aPage([aDocument({ category: "functional_schematic" })]),
      },
      "GET /projects/": { body: aPage([aProject()]) },
    });

    render(<DocumentsPage />);

    const select = await screen.findByLabelText("Categoria");
    const options = Array.from(
      select.querySelectorAll("option"),
    ).map((option) => option.getAttribute("value"));

    expect(options).toContain("cable_list");
    expect(options).toContain("relay_settings");
  });

  it("returns to page 1 when a filter changes", async () => {
    const backend = stubBackend({
      "GET /documents/": {
        body: aPage([aDocument()], { page: 2, page_size: 1, total: 5 }),
      },
      "GET /projects/": { body: aPage([aProject()]) },
    });

    const user = userEvent.setup();
    render(<DocumentsPage />);

    await user.selectOptions(
      await screen.findByLabelText("Formato"),
      "pdf",
    );

    await waitFor(() => {
      const requests = backend.requestsFor("GET", "/documents/");
      const last = requests[requests.length - 1];

      // Staying on page 4 of the previous result set would show an empty
      // page and read as "no matches".
      expect(queryOf(last.url).get("page")).toBe("1");
    });
  });
});

// --- No storage location ---------------------------------------------------

describe("the storage location is not in the contract", () => {
  it("renders no path anywhere in the registry", async () => {
    stubBackend({
      "GET /documents/": { body: aPage([aDocument()]) },
      "GET /projects/": { body: aPage([aProject()]) },
    });

    const { container } = render(<DocumentsPage />);

    await screen.findByText("schema-funzionale.pdf");

    expect(container.textContent).not.toContain("storage");
    expect(container.textContent).not.toContain("/documents/schema");
  });
});

// --- Upload ----------------------------------------------------------------

describe("upload consumes the typed response", () => {
  it("posts multipart and re-reads the page from the server", async () => {
    const backend = stubBackend({
      "GET /documents/": [
        { body: aPage([]) },
        { body: aPage([aDocument({ filename: "nuovo-schema.pdf" })]) },
      ],
      "GET /projects/": { body: aPage([aProject({ id: 3 })]) },
      "POST /documents/upload": {
        body: anUpload(
          aDocumentDetail({ id: 99, filename: "nuovo-schema.pdf" }),
        ),
      },
    });

    const user = userEvent.setup();
    render(<DocumentsPage />);

    await screen.findByLabelText(/^Documento$/);
    await user.upload(screen.getByLabelText(/^Documento$/), pdf());
    await user.click(screen.getByRole("button", { name: /Carica documento/ }));

    await waitFor(() => {
      expect(backend.requestsFor("POST", "/documents/upload")).toHaveLength(1);
    });

    expect(backend.requestsFor("POST", "/documents/upload")[0].body).toEqual({
      file: expect.anything(),
      project_id: "3",
      scope: "project",
    });

    // The position of a new document depends on the active sort and
    // filters, which only the server knows - so the page is re-read.
    expect(await screen.findByText("nuovo-schema.pdf")).toBeVisible();
  });

  it("shows the backend's 422 when the scope rules are violated", async () => {
    stubBackend({
      "GET /documents/": { body: aPage([]) },
      "GET /projects/": { body: aPage([aProject({ id: 3 })]) },
      "POST /documents/upload": {
        status: 422,
        body: { detail: "A project_id is required for scope 'project'" },
      },
    });

    const user = userEvent.setup();
    render(<DocumentsPage />);

    await screen.findByLabelText(/^Documento$/);
    await user.upload(screen.getByLabelText(/^Documento$/), pdf());
    await user.click(screen.getByRole("button", { name: /Carica documento/ }));

    expect(
      await screen.findByText(
        "A project_id is required for scope 'project'",
      ),
    ).toBeVisible();
  });

  it("explains a 409 on a read-only project", async () => {
    stubBackend({
      "GET /documents/": { body: aPage([]) },
      "GET /projects/": { body: aPage([aProject({ id: 3 })]) },
      "POST /documents/upload": {
        status: 409,
        body: { detail: "Project 'CP-1' is 'archived' and is read-only" },
      },
    });

    const user = userEvent.setup();
    render(<DocumentsPage />);

    await screen.findByLabelText(/^Documento$/);
    await user.upload(screen.getByLabelText(/^Documento$/), pdf());
    await user.click(screen.getByRole("button", { name: /Carica documento/ }));

    expect(
      await screen.findByText(
        "Project 'CP-1' is 'archived' and is read-only",
      ),
    ).toBeVisible();
  });

  it("does not offer a project the backend would refuse", async () => {
    stubBackend({
      "GET /documents/": { body: aPage([]) },
      "GET /projects/": {
        body: aPage([
          aProject({ id: 1, code: "CP-ACTIVE", lifecycle_state: "active" }),
          aProject({
            id: 2,
            code: "CP-ARCHIVED",
            lifecycle_state: "archived",
          }),
        ]),
      },
    });

    render(<DocumentsPage />);

    await screen.findByText(/CP-ACTIVE/);

    const select = document.getElementById(
      "upload-project",
    ) as HTMLSelectElement;

    const options = Array.from(select.querySelectorAll("option")).map(
      (option) => option.textContent ?? "",
    );

    expect(options.some((text) => text.includes("CP-ACTIVE"))).toBe(true);
    expect(options.some((text) => text.includes("CP-ARCHIVED"))).toBe(false);
  });
});

// --- Failures --------------------------------------------------------------

describe("list failures", () => {
  it("reports a 500 with a retry", async () => {
    stubBackend({
      "GET /documents/": { status: 500, body: { detail: "boom" } },
      "GET /projects/": { body: aPage([]) },
    });

    render(<DocumentsPage />);

    expect(
      await screen.findByText(/il backend ha risposto con un errore interno/i),
    ).toBeVisible();

    expect(screen.getByRole("button", { name: /Riprova/ })).toBeVisible();
  });

  it("reports a 422 from an invalid page request", async () => {
    stubBackend({
      "GET /documents/": {
        status: 422,
        body: {
          detail: "Page size must be between 1 and 100; received 5000.",
        },
      },
      "GET /projects/": { body: aPage([]) },
    });

    render(<DocumentsPage />);

    expect(
      await screen.findByText(/Page size must be between 1 and 100/),
    ).toBeVisible();
  });

  it("reports an unreachable backend", async () => {
    stubBackend({
      "GET /documents/": { networkFailure: true },
      "GET /projects/": { networkFailure: true },
    });

    render(<DocumentsPage />);

    // Both lists fail; the page reports it once per source.
    expect(
      (await screen.findAllByText(/il backend SubstationOS non risponde/i))
        .length,
    ).toBeGreaterThan(0);
  });
});
