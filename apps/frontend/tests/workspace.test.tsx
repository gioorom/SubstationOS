/**
 * The Engineering Workspace.
 *
 * These tests are about what an engineer can and cannot be shown. The
 * hard cases are the ones a careless UI gets wrong: a stage that has not
 * run must not look like one that found nothing, a declined
 * interpretation must not appear as a claim, a semantic endpoint that
 * fails must not take the evidence explorer down with it, and a rated
 * power must reach the screen through the entity that owns the figure.
 *
 * `next/navigation` is replaced by a small router that behaves like the
 * real one for the two things this page depends on: the query string is
 * observable state, and `window.history` moves through it.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DocumentWorkspacePage from "@/app/documents/[documentId]/workspace/page";

import {
  aCanonicalPage,
  aDocumentDetail,
  aFactSet,
  aSemanticSet,
  anEntitySet,
  anEvidenceSet,
  stubBackend,
  type Routes,
} from "./_backend";

/** A stand-in for the App Router's query string and history stack. */
const router = vi.hoisted(() => {
  const listeners = new Set<() => void>();
  let stack: string[] = [""];
  let cursor = 0;

  const notify = () => listeners.forEach((listener) => listener());

  return {
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    query: () => stack[cursor],
    push(query: string) {
      stack = [...stack.slice(0, cursor + 1), query];
      cursor = stack.length - 1;
      notify();
    },
    back() {
      if (cursor > 0) {
        cursor -= 1;
        notify();
      }
    },
    forward() {
      if (cursor < stack.length - 1) {
        cursor += 1;
        notify();
      }
    },
    reset(query = "") {
      stack = [query];
      cursor = 0;
      notify();
    },
  };
});

vi.mock("next/navigation", async () => {
  const { useSyncExternalStore } = await import("react");

  return {
    useParams: () => ({ documentId: "10" }),
    usePathname: () => "/documents/10/workspace",
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
    useSearchParams: () =>
      new URLSearchParams(
        useSyncExternalStore(
          router.subscribe,
          router.query,
          router.query,
        ),
      ),
  };
});

const REPRESENTATION = {
  document_id: 10,
  content_checksum: "a".repeat(64),
  checksum_algorithm: "sha256",
  representation_version: "1.0",
  parser_name: "pymupdf",
  parser_version: "1.24.0",
  page_count: 3,
};

/** Every read the Workspace performs, answered as the backend would. */
function workspaceRoutes(overrides: Routes = {}): Routes {
  return {
    "GET /documents/10": { body: aDocumentDetail() },
    "GET /documents/10/canonical-representation": {
      body: REPRESENTATION,
    },
    "GET /documents/10/canonical-representation/pages/1": {
      body: aCanonicalPage(),
    },
    "GET /documents/10/canonical-representation/pages/2": {
      body: aCanonicalPage({ page_number: 2 }),
    },
    "GET /documents/10/canonical-representation/pages/3": {
      body: aCanonicalPage({ page_number: 3 }),
    },
    "GET /documents/10/engineering-evidence": { body: anEvidenceSet() },
    "GET /documents/10/engineering-entities": { body: anEntitySet() },
    "GET /documents/10/engineering-facts": { body: aFactSet() },
    "GET /documents/10/engineering-semantics": { body: aSemanticSet() },
    ...overrides,
  };
}

/** The statement row's accessible name, built from its entity labels. */
const STATEMENT_ROW = /TR1 ha potenza nominale/;

async function renderWorkspace(
  overrides: Routes = {},
  filename = "schema-funzionale.pdf",
) {
  const backend = stubBackend(workspaceRoutes(overrides));

  render(<DocumentWorkspacePage />);

  await screen.findByRole("heading", { name: filename });

  return backend;
}

/** Opens an explorer tab by its visible name. */
async function openTab(name: RegExp) {
  await userEvent.click(await screen.findByRole("tab", { name }));
}

beforeEach(() => {
  router.reset();

  // The page writes the selection with the native History API, which the
  // App Router supports and keeps `useSearchParams` in sync with. The
  // stub closes that loop so a click really does change what the page
  // reads back.
  vi.spyOn(window.history, "pushState").mockImplementation(
    (_state, _title, url) => {
      router.push(String(url).split("?")[1] ?? "");
    },
  );
});

// --- The page loads a real document --------------------------------------

describe("the workspace route", () => {
  it("loads one document and its artefacts through the public API", async () => {
    const backend = await renderWorkspace();

    const paths = backend.requests.map((request) =>
      request.url.replace("http://127.0.0.1:8000", ""),
    );

    expect(paths).toContain("/documents/10");
    expect(paths).toContain("/documents/10/engineering-semantics");
    expect(paths).toContain("/documents/10/engineering-evidence");
  });

  it("never sends or receives a storage location", async () => {
    const backend = await renderWorkspace();

    for (const request of backend.requests) {
      expect(request.url).not.toContain("file_path");
      expect(request.url).not.toContain("storage");
    }

    expect(document.body.innerHTML).not.toContain("file_path");
    expect(document.body.innerHTML).not.toContain("storage_reference");
  });
});

// --- The source viewer ---------------------------------------------------

describe("the source viewer", () => {
  it("reads only the page it is displaying", async () => {
    const backend = await renderWorkspace();

    await waitFor(() =>
      expect(
        backend.requestsFor(
          "GET",
          "/documents/10/canonical-representation/pages/1",
        ),
      ).toHaveLength(1),
    );

    // The whole-representation read is the summary the page count comes
    // from; no other page is fetched until it is shown.
    expect(
      backend.requestsFor(
        "GET",
        "/documents/10/canonical-representation/pages/2",
      ),
    ).toHaveLength(0);
  });

  it("navigates pages and reports the page count the backend gave", async () => {
    const backend = await renderWorkspace();

    expect(await screen.findByText("Pagina 1 di 3")).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Pagina successiva" }),
    );

    expect(await screen.findByText("Pagina 2 di 3")).toBeInTheDocument();

    await waitFor(() =>
      expect(
        backend.requestsFor(
          "GET",
          "/documents/10/canonical-representation/pages/2",
        ),
      ).toHaveLength(1),
    );
  });

  it("embeds the original through the governed content endpoint", async () => {
    await renderWorkspace();

    await userEvent.click(screen.getByRole("tab", { name: "Originale" }));

    const frame = await screen.findByTitle(
      "Documento originale: schema-funzionale.pdf",
    );

    expect(frame).toHaveAttribute(
      "src",
      "http://127.0.0.1:8000/documents/10/content#page=1",
    );
  });

  it("refuses to interpret a format that has no canonical form", async () => {
    await renderWorkspace(
      {
        "GET /documents/10": {
          body: aDocumentDetail({
            filename: "layout-quadri.dwg",
            file_format: "dwg",
          }),
        },
      },
      "layout-quadri.dwg",
    );

    await userEvent.click(screen.getByRole("tab", { name: "Originale" }));

    expect(
      await screen.findByText(/ispezione inline non disponibile/i),
    ).toBeInTheDocument();

    // A download, never an inline render of unknown bytes.
    expect(screen.queryByTitle(/Documento originale/)).toBeNull();
    expect(
      screen.getByRole("link", { name: /Scarica il documento/ }),
    ).toHaveAttribute("href", "http://127.0.0.1:8000/documents/10/content");
  });

  it("reports missing content instead of embedding nothing", async () => {
    await renderWorkspace({
      "GET /documents/10": {
        body: aDocumentDetail({ content_available: false }),
      },
    });

    await userEvent.click(screen.getByRole("tab", { name: "Originale" }));

    expect(
      await screen.findByText(/non è più disponibile nell'archivio/i),
    ).toBeInTheDocument();
  });
});

// --- Navigating the support chain ----------------------------------------

describe("navigating from meaning back to the source", () => {
  it("shows a rated power read from the quantity entity", async () => {
    await renderWorkspace();

    const statements = await screen.findByRole("list", {
      name: "Affermazioni semantiche",
    });

    expect(within(statements).getByText("630 kVA")).toBeInTheDocument();
    expect(
      within(statements).getByText("has_rated_power"),
    ).toBeInTheDocument();
  });

  it("says the value cannot be resolved rather than inventing one", async () => {
    await renderWorkspace({
      "GET /documents/10/engineering-entities": { status: 404 },
    });

    expect(
      await screen.findByText(/non è disponibile/i),
    ).toBeInTheDocument();
    expect(screen.queryByText("630 kVA")).toBeNull();
  });

  it("exposes a statement's supporting fact when it is selected", async () => {
    await renderWorkspace();

    await userEvent.click(
      await screen.findByRole("button", { name: STATEMENT_ROW }),
    );

    const inspector = screen.getByRole("region", { name: "Ispettore" });

    expect(
      within(inspector).getByText(/has_associated_quantity/),
    ).toBeInTheDocument();
    expect(
      within(inspector).getByText("statement-tr1-power"),
    ).toBeInTheDocument();
  });

  it("shows both entities a fact references", async () => {
    await renderWorkspace();

    await openTab(/Fatti/);
    await userEvent.click(
      await screen.findByRole("button", {
        name: /Fatto: TR1 grandezza associata 630 kVA/,
      }),
    );

    const inspector = screen.getByRole("region", { name: "Ispettore" });

    expect(
      within(inspector).getByText(/TR1 \(soggetto\)/),
    ).toBeInTheDocument();
    expect(
      within(inspector).getByText(/630 kVA \(oggetto\)/),
    ).toBeInTheDocument();
  });

  it("shows only the evidence an entity itself declares", async () => {
    await renderWorkspace();

    await openTab(/Entità/);
    await userEvent.click(
      await screen.findByRole("button", { name: /^Entità TR1/ }),
    );

    const inspector = screen.getByRole("region", { name: "Ispettore" });

    // The section that follows the "Evidenze di supporto" heading.
    const support = within(inspector)
      .getByText("Evidenze di supporto")
      .nextElementSibling!.querySelectorAll("button");

    // `entity-tr1` declares exactly one observation. The power
    // observation reads `630 kVA` on the same line, and a text- or
    // value-matching implementation would attribute it here too.
    expect(
      [...support].map((button) => button.textContent),
    ).toHaveLength(1);
    expect(support[0].textContent).toContain("TR1");
    expect(support[0].textContent).not.toContain("630 kVA");
  });

  it("navigates the source to the page of the selected evidence", async () => {
    const backend = await renderWorkspace({
      "GET /documents/10/engineering-evidence": {
        body: anEvidenceSet({
          evidence: [
            {
              ...anEvidenceSet().evidence[0],
              provenance: {
                ...anEvidenceSet().evidence[0].provenance,
                page_number: 3,
              },
            },
          ],
          evidence_count: 1,
        }),
      },
    });

    await openTab(/Evidenze/);
    await userEvent.click(
      await screen.findByRole("button", { name: /^Evidenza TR1/ }),
    );

    expect(await screen.findByText("Pagina 3 di 3")).toBeInTheDocument();

    await waitFor(() =>
      expect(
        backend.requestsFor(
          "GET",
          "/documents/10/canonical-representation/pages/3",
        ),
      ).toHaveLength(1),
    );
  });

  it("reports an incomplete chain instead of filling the gap", async () => {
    await renderWorkspace({
      "GET /documents/10/engineering-facts": { status: 404 },
    });

    await userEvent.click(
      await screen.findByRole("button", { name: STATEMENT_ROW }),
    );

    expect(
      await screen.findByText(/Catena di supporto incompleta/),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(/non corrisponde ad alcun artefatto caricato/),
    ).not.toHaveLength(0);
  });
});

// --- Diagnostics and the states that are not failures --------------------

describe("declined, empty, unrun and failed", () => {
  it("keeps diagnostics visible when no statement was produced", async () => {
    await renderWorkspace({
      "GET /documents/10/engineering-semantics": {
        body: aSemanticSet({
          statements: [],
          statement_count: 0,
          has_ambiguities: true,
          diagnostics: [
            {
              reason: "multiple_candidate_quantities",
              subject_entity_key: "entity-tr1",
              candidate_fact_keys: ["fact-tr1-630"],
            },
          ],
        }),
      },
    });

    await openTab(/Diagnostiche/);

    expect(
      await screen.findByText(/Interpretazione semantica declinata/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Più potenze associate alla stessa sigla/),
    ).toBeInTheDocument();
  });

  it("does not present a declined subject as though it had a meaning", async () => {
    await renderWorkspace({
      "GET /documents/10/engineering-semantics": {
        body: aSemanticSet({
          statements: [],
          statement_count: 0,
          has_ambiguities: true,
          diagnostics: [
            {
              reason: "multiple_candidate_quantities",
              subject_entity_key: "entity-tr1",
              candidate_fact_keys: [],
            },
          ],
        }),
      },
    });

    expect(
      await screen.findByText(/non ha trovato affermazioni semantiche/),
    ).toBeInTheDocument();
    expect(screen.queryByText("has_rated_power")).toBeNull();
  });

  it("tells an unrun stage apart from one that found nothing", async () => {
    await renderWorkspace({
      "GET /documents/10/engineering-semantics": { status: 404 },
    });

    expect(
      await screen.findAllByText(/non è ancora stato eseguito/),
    ).not.toHaveLength(0);
    expect(screen.queryByText(/non ha trovato/)).toBeNull();
  });

  it("calls an empty result an answer, not a failure", async () => {
    await renderWorkspace({
      "GET /documents/10/engineering-semantics": {
        body: aSemanticSet({ statements: [], statement_count: 0 }),
      },
    });

    expect(
      await screen.findByText(/non ha trovato affermazioni semantiche/),
    ).toBeInTheDocument();
  });

  it("shows an ambiguous artefact with the backend's own word", async () => {
    await renderWorkspace({
      "GET /documents/10/engineering-semantics": {
        body: aSemanticSet({
          statements: [
            {
              ...aSemanticSet().statements[0],
              status: "ambiguous",
            },
          ],
        }),
      },
    });

    expect(await screen.findByText("ambiguous")).toBeInTheDocument();
  });

  it("leaves the other stages inspectable when one read fails", async () => {
    await renderWorkspace({
      "GET /documents/10/engineering-semantics": { status: 500 },
    });

    // The semantic tab reports its own failure...
    expect(
      await screen.findAllByText(/ha risposto con un errore interno/i),
    ).not.toHaveLength(0);

    // ...and the evidence that loaded is still there to inspect.
    await openTab(/Evidenze/);

    expect(
      await screen.findByRole("button", { name: /^Evidenza TR1/ }),
    ).toBeInTheDocument();
  });
});

// --- Selection state -----------------------------------------------------

describe("selection in the URL", () => {
  it("writes the selected artefact to the query string", async () => {
    await renderWorkspace();

    await userEvent.click(
      await screen.findByRole("button", { name: STATEMENT_ROW }),
    );

    expect(router.query()).toContain("kind=semantic");
    expect(router.query()).toContain("key=statement-tr1-power");
  });

  it("never puts artefact contents in the URL", async () => {
    await renderWorkspace();

    await userEvent.click(
      await screen.findByRole("button", { name: STATEMENT_ROW }),
    );

    expect(router.query()).not.toContain("630");
    expect(router.query()).not.toContain("{");
  });

  it("restores the selection on a reload", async () => {
    router.reset("kind=semantic&key=statement-tr1-power");

    await renderWorkspace();

    const inspector = await screen.findByRole("region", {
      name: "Ispettore",
    });

    expect(
      within(inspector).getByText("statement-tr1-power"),
    ).toBeInTheDocument();
  });

  it("follows the browser's Back and Forward", async () => {
    await renderWorkspace();

    await userEvent.click(
      await screen.findByRole("button", { name: STATEMENT_ROW }),
    );
    expect(router.query()).toContain("statement-tr1-power");

    await openTab(/Evidenze/);
    await userEvent.click(
      await screen.findByRole("button", { name: /^Evidenza TR1/ }),
    );
    expect(router.query()).toContain("ev-designation");

    router.back();
    await waitFor(() =>
      expect(router.query()).toContain("statement-tr1-power"),
    );

    router.forward();
    await waitFor(() => expect(router.query()).toContain("ev-designation"));
  });

  it("reports a key that matches nothing as a not-found selection", async () => {
    router.reset("kind=evidence&key=ev-che-non-esiste");

    await renderWorkspace();

    expect(
      await screen.findByText(/Nessun artefatto corrisponde/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Nessuna corrispondenza approssimata viene tentata/),
    ).toBeInTheDocument();
  });

  it("ignores a kind outside the closed vocabulary", async () => {
    router.reset("kind=documento&key=../../etc/passwd");

    const backend = await renderWorkspace();

    // No request is composed from the query string.
    for (const request of backend.requests) {
      expect(request.url).not.toContain("passwd");
    }

    expect(screen.queryByText(/Nessun artefatto corrisponde/)).toBeNull();
  });
});

// --- Inspection only -----------------------------------------------------

describe("the human validation boundary", () => {
  it("offers no control that would imply a judgement", async () => {
    await renderWorkspace();

    await userEvent.click(
      await screen.findByRole("button", { name: STATEMENT_ROW }),
    );

    for (const forbidden of [
      /approva/i,
      /rifiuta/i,
      /conferma/i,
      /correggi/i,
      /modifica/i,
      /unisci/i,
      /valida/i,
    ]) {
      expect(screen.queryByRole("button", { name: forbidden })).toBeNull();
    }
  });

  it("states that interpreted does not mean approved", async () => {
    await renderWorkspace();

    expect(
      await screen.findByText(/Non significa verificato o approvato/i),
    ).toBeInTheDocument();
  });

  it("keeps a structural association from reading as a rated value", async () => {
    await renderWorkspace();

    await openTab(/Fatti/);

    expect(
      await screen.findAllByText(/Associazione strutturale/),
    ).not.toHaveLength(0);
    expect(
      screen.getByText(/Non dice che la grandezza sia la potenza/),
    ).toBeInTheDocument();
  });
});

// --- Accessibility -------------------------------------------------------

describe("accessibility", () => {
  it("makes every explorer item a keyboard-reachable control", async () => {
    await renderWorkspace();

    const list = await screen.findByRole("list", {
      name: "Affermazioni semantiche",
    });

    const buttons = within(list).getAllByRole("button");

    expect(buttons.length).toBeGreaterThan(0);

    buttons[0].focus();
    expect(buttons[0]).toHaveFocus();

    await userEvent.keyboard("{Enter}");
    expect(router.query()).toContain("kind=semantic");
  });

  it("marks the selected item beyond colour", async () => {
    await renderWorkspace();

    const statement = await screen.findByRole("button", {
      name: STATEMENT_ROW,
    });

    await userEvent.click(statement);

    expect(statement).toHaveAttribute("aria-current", "true");
  });

  it("names the three regions of the workspace", async () => {
    await renderWorkspace();

    expect(
      screen.getByRole("region", { name: "Documento sorgente" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Esploratore di ingegneria" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Ispettore" }),
    ).toBeInTheDocument();
  });

  it("keeps every engineering value textual", async () => {
    await renderWorkspace();

    // The figure is text, not a bar, a gauge or a colour.
    const statements = await screen.findByRole("list", {
      name: "Affermazioni semantiche",
    });

    expect(within(statements).getByText("630 kVA")).toBeInTheDocument();
  });

  it("labels the source viewer controls", async () => {
    await renderWorkspace();

    expect(
      screen.getByRole("button", { name: "Pagina successiva" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Aumenta zoom" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /Mappa canonica della pagina 1/ }),
    ).toBeInTheDocument();
  });
});
