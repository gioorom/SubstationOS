/**
 * The Governed Knowledge Graph in the Workspace.
 *
 * The behaviours asserted here are the ones that would destroy the
 * distinction between a governed projection and a property graph: a UI
 * that shows knowledge without provenance, that says "not in the graph"
 * without saying why, that hides retired knowledge instead of marking it,
 * or that decides for itself what is promotable.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import GraphPanel from "@/components/workspace/GraphPanel";
import { SessionProvider } from "@/hooks/useSession";

import {
  aGraphEdge,
  aPromotedStatement,
  anUnpromotedStatement,
  aSession,
  stubBackend,
  type Routes,
} from "./_backend";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => ({ documentId: "10" }),
  usePathname: () => "/documents/10/workspace",
  useSearchParams: () => new URLSearchParams(),
}));

const KEY = "statement-tr1-power";

const PROMOTION = `GET /documents/10/engineering-semantics/${KEY}/promotion`;
const PROMOTE = "POST /knowledge-graph/promotions";

function panel(overrides: Routes = {}, session = aSession()) {
  const backend = stubBackend({
    "GET /auth/session": { body: session },
    [PROMOTION]: { body: anUnpromotedStatement() },
    ...overrides,
  });

  render(
    <SessionProvider>
      <GraphPanel documentId={10} statementKey={KEY} />
    </SessionProvider>,
  );

  return backend;
}

// --- Promotion state -----------------------------------------------------

describe("promotion state", () => {
  it("says when a statement is governed knowledge", async () => {
    panel({ [PROMOTION]: { body: aPromotedStatement() } });

    expect(await screen.findByText("Nel grafo")).toBeInTheDocument();
  });

  it("says when it is not, and why", async () => {
    /**
     * "Not promoted" and "not promoted because nobody has approved it"
     * are different things to an engineer looking at the screen.
     */
    panel();

    expect(await screen.findByText("Non nel grafo")).toBeInTheDocument();
    expect(
      screen.getByText(/Nessun ingegnere ha ancora espresso un giudizio/),
    ).toBeInTheDocument();
  });

  it("explains a rejection differently from an absent review", async () => {
    panel({
      [PROMOTION]: {
        body: anUnpromotedStatement({ refusal: "review_rejected" }),
      },
    });

    expect(
      await screen.findByText(/Un ingegnere ha respinto/),
    ).toBeInTheDocument();
  });

  it("explains a stale judgement as awaiting revalidation", async () => {
    panel({
      [PROMOTION]: {
        body: anUnpromotedStatement({ refusal: "review_stale" }),
      },
    });

    expect(
      await screen.findByText(/regole o byte diversi/),
    ).toBeInTheDocument();
  });

  it("marks retired knowledge rather than hiding it", async () => {
    panel({
      [PROMOTION]: {
        body: anUnpromotedStatement({
          refusal: "review_rejected",
          edge: aGraphEdge({
            state: "historical",
            retirement: {
              reason: "review_reversed",
              retired_at: "2026-07-30T10:00:00",
            },
          }),
        }),
      },
    });

    expect(
      await screen.findByText(/Ritirata dal grafo/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/resta leggibile con la sua provenienza/),
    ).toBeInTheDocument();
  });

  it("shows a loading state before the projection answers", () => {
    panel({ [PROMOTION]: { hang: true } });

    expect(screen.queryByText("Nel grafo")).toBeNull();
    expect(screen.queryByText("Non nel grafo")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("reports a failed read rather than an empty graph", async () => {
    panel({ [PROMOTION]: { status: 500, body: { detail: "boom" } } });

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText("Non nel grafo")).toBeNull();
  });
});

// --- Provenance ----------------------------------------------------------

describe("provenance", () => {
  it("shows who authorised the knowledge and under which rule", async () => {
    /**
     * Explainability is mandatory. A graph answer that could not say
     * where it came from would not have been storable.
     */
    panel({ [PROMOTION]: { body: aPromotedStatement() } });

    // The name sits beside the review id in one field, so the text node
    // is split across siblings.
    expect(
      await screen.findByText(/Ada Lovelace/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/rated_power_from_associated_power_quantity@1\.0/),
    ).toBeInTheDocument();
    expect(screen.getByText(/revisione 1/)).toBeInTheDocument();
  });

  it("shows the graph identity, and offers it for copying", async () => {
    panel({ [PROMOTION]: { body: aPromotedStatement() } });

    expect(
      await screen.findByText(aGraphEdge().edge_id),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Copia Identità nel grafo/ }),
    ).toBeInTheDocument();
  });

  it("names the governed relationship without renaming it", async () => {
    /**
     * The readable label accompanies the canonical kind; it never
     * replaces it.
     */
    panel({ [PROMOTION]: { body: aPromotedStatement() } });

    expect(
      await screen.findByText("ha potenza nominale"),
    ).toBeInTheDocument();
    expect(screen.getByText("(has_rated_power)")).toBeInTheDocument();
  });
});

// --- The graph is a projection ------------------------------------------

describe("what the panel says the graph is", () => {
  it("states that the graph is a projection that can be rebuilt", async () => {
    panel();

    expect(
      await screen.findByText(/può sempre essere ricostruito/),
    ).toBeInTheDocument();
  });

  it("states that only approved, current statements are in it", async () => {
    panel();

    expect(
      await screen.findByText(
        /solo affermazioni approvate da un ingegnere e ancora attuali/,
      ),
    ).toBeInTheDocument();
  });
});

// --- Reconciling ---------------------------------------------------------

describe("reconciling", () => {
  it("asks the backend to reconcile, and re-reads the projection", async () => {
    const backend = panel({
      [PROMOTE]: {
        status: 201,
        body: {
          promoted: 1,
          retired: 0,
          revalidated: 0,
          failed: 0,
          events: [],
        },
      },
    });

    await userEvent.click(
      await screen.findByRole("button", { name: "Riconcilia" }),
    );

    await waitFor(() =>
      expect(
        backend.requestsFor("POST", "/knowledge-graph/promotions"),
      ).toHaveLength(1),
    );

    // The projection is what changed; the panel re-reads it rather than
    // inferring the outcome from the run's counters.
    await waitFor(() =>
      expect(
        backend.requestsFor(
          "GET",
          `/documents/10/engineering-semantics/${KEY}/promotion`,
        ).length,
      ).toBeGreaterThan(1),
    );
  });

  it("names the statement it is reconciling", async () => {
    const backend = panel({
      [PROMOTE]: {
        status: 201,
        body: {
          promoted: 0,
          retired: 0,
          revalidated: 0,
          failed: 0,
          events: [],
        },
      },
    });

    await userEvent.click(
      await screen.findByRole("button", { name: "Riconcilia" }),
    );

    await waitFor(() =>
      expect(
        backend.requestsFor("POST", "/knowledge-graph/promotions"),
      ).toHaveLength(1),
    );

    const url = backend.requestsFor(
      "POST",
      "/knowledge-graph/promotions",
    )[0].url;

    expect(url).toContain("document_id=10");
    expect(url).toContain(`statement_key=${KEY}`);
  });

  it("offers no control once the statement is already promoted", async () => {
    panel({ [PROMOTION]: { body: aPromotedStatement() } });

    await screen.findByText("Nel grafo");

    expect(
      screen.queryByRole("button", { name: "Riconcilia" }),
    ).toBeNull();
  });

  it("reports a refusal without signing the user out", async () => {
    panel({
      [PROMOTE]: {
        status: 403,
        body: {
          detail: "This action requires a permission your role does not carry.",
        },
      },
    });

    await userEvent.click(
      await screen.findByRole("button", { name: "Riconcilia" }),
    );

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Riconcilia" }),
    ).toBeInTheDocument();
  });
});

// --- Permission ----------------------------------------------------------

describe("permission", () => {
  it("offers reconciliation to an engineer", async () => {
    panel();

    expect(
      await screen.findByRole("button", { name: "Riconcilia" }),
    ).toBeInTheDocument();
  });

  it("still shows the graph state to a role that may not promote", async () => {
    panel({}, aSession({ role: "auditor" as never }));

    expect(await screen.findByText("Non nel grafo")).toBeInTheDocument();
    expect(
      screen.getByText(/leggere il grafo ma non di promuovervi/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Riconcilia" }),
    ).toBeNull();
  });
});

// --- The frontend decides nothing ---------------------------------------

describe("the frontend decides nothing about promotability", () => {
  it("renders whatever the backend says, even an unlikely pairing", async () => {
    /**
     * The fixture reports a statement as **promoted** while carrying a
     * refusal - a combination the backend would not produce. The panel
     * renders what it was told rather than re-deriving the state, which
     * is what a client that had re-implemented the promotion rule would
     * fail to do.
     */
    panel({
      [PROMOTION]: {
        body: {
          ...aPromotedStatement(),
          refusal: "review_rejected" as const,
        },
      },
    });

    expect(await screen.findByText("Nel grafo")).toBeInTheDocument();
    expect(
      screen.queryByText(/Un ingegnere ha respinto/),
    ).toBeNull();
  });
});
