/**
 * Human Review in the Workspace.
 *
 * The behaviours asserted here are the ones that would quietly destroy
 * the distinction this milestone exists to draw: a UI that renders "never
 * reviewed" as an approval, that computes which judgement is current, that
 * says the pipeline was wrong, that claims a new review replaces an old
 * one, or that hides a judgement the pipeline has since moved past.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ReviewPanel from "@/components/workspace/ReviewPanel";
import { SessionProvider } from "@/hooks/useSession";

import {
  aReview,
  aReviewHistory,
  aReviewVocabulary,
  aReviewedStatement,
  aSession,
  anUnreviewedStatement,
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

const CURRENT = `GET /documents/10/engineering-semantics/${KEY}/current-review`;
const HISTORY = `GET /documents/10/engineering-semantics/${KEY}/reviews`;
const RECORD = `POST /documents/10/engineering-semantics/${KEY}/reviews`;

function panel(overrides: Routes = {}, session = aSession()) {
  const backend = stubBackend({
    "GET /auth/session": { body: session },
    "GET /engineering-reviews/vocabulary": { body: aReviewVocabulary() },
    [CURRENT]: { body: anUnreviewedStatement() },
    [HISTORY]: { body: aReviewHistory([]) },
    ...overrides,
  });

  render(
    <SessionProvider>
      <ReviewPanel documentId={10} statementKey={KEY} />
    </SessionProvider>,
  );

  return backend;
}

// --- The states are not interchangeable ----------------------------------

describe("review states", () => {
  it("shows never-reviewed as a state, not as a decision", async () => {
    panel();

    expect(await screen.findByText("Mai revisionato")).toBeInTheDocument();

    for (const decision of ["Approvato", "Respinto", "Da approfondire"]) {
      expect(screen.queryByText(decision)).toBeNull();
    }
  });

  it("says plainly that interpreted is not reviewed", async () => {
    panel();

    expect(
      await screen.findByText(
        /significa prodotto da una regola versionata, non verificato da una persona/,
      ),
    ).toBeInTheDocument();
  });

  it("shows the current decision when there is one", async () => {
    panel({ [CURRENT]: { body: aReviewedStatement() } });

    expect(await screen.findByText("Approvato")).toBeInTheDocument();
    expect(screen.getByText("Confermato dal documento")).toBeInTheDocument();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
  });

  it("shows the rule version the judgement was passed under", async () => {
    panel({ [CURRENT]: { body: aReviewedStatement() } });

    expect(
      await screen.findByText(
        /rated_power_from_associated_power_quantity@1\.0/,
      ),
    ).toBeInTheDocument();
  });

  it("marks a judgement the pipeline has moved past", async () => {
    panel({
      [CURRENT]: {
        body: aReviewedStatement(aReview(), {
          applicability: "requires_revalidation",
        }),
      },
    });

    expect(await screen.findByText("Da riconvalidare")).toBeInTheDocument();

    // Marked, never discarded: the judgement is still on screen.
    expect(screen.getByText("Approvato")).toBeInTheDocument();
    // Twice on purpose: once as the badge's accessible description, once
    // as the explanation beneath it.
    expect(
      screen.getAllByText(/Il documento è stato reinterpretato/),
    ).not.toHaveLength(0);
  });

  it("distinguishes orphaned from requiring revalidation", async () => {
    panel({
      [CURRENT]: {
        body: aReviewedStatement(aReview(), {
          applicability: "orphaned",
        }),
      },
    });

    expect(
      await screen.findByText("Senza interpretazione"),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(/lo stage semantico non è stato eseguito/),
    ).not.toHaveLength(0);
  });

  it("raises a broken snapshot rather than trusting it", async () => {
    panel({
      [CURRENT]: {
        body: aReviewedStatement(aReview(), { snapshot_intact: false }),
      },
    });

    expect(
      await screen.findByText(/ha conservato la propria chiave/),
    ).toBeInTheDocument();
  });

  it("shows a loading state before the projection answers", () => {
    panel({ [CURRENT]: { hang: true } });

    expect(screen.queryByText("Mai revisionato")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("reports a failed read rather than showing no judgement", async () => {
    panel({ [CURRENT]: { status: 500, body: { detail: "boom" } } });

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText("Mai revisionato")).toBeNull();
  });
});

// --- The language --------------------------------------------------------

describe("the language of a review", () => {
  it("never calls the pipeline right or wrong", async () => {
    panel({ [CURRENT]: { body: aReviewedStatement() } });

    await screen.findByText("Approvato");

    const rendered = document.body.textContent ?? "";

    for (const forbidden of [
      "Corretto",
      "Errato",
      "Sbagliato",
      "✓",
      "✗",
    ]) {
      expect(rendered).not.toContain(forbidden);
    }
  });

  it("says a review changes no engineering artefact", async () => {
    panel();

    expect(
      await screen.findByText(/Non modifica in alcun modo/),
    ).toBeInTheDocument();
  });
});

// --- Recording a judgement -----------------------------------------------

describe("recording a judgement", () => {
  it("submits the decision, the reason and the comment", async () => {
    const backend = panel({ [RECORD]: { status: 201, body: aReview() } });

    await userEvent.click(
      await screen.findByRole("button", { name: /Registra revisione/ }),
    );

    await userEvent.click(screen.getByRole("radio", { name: /Respinto/ }));

    await userEvent.selectOptions(
      screen.getByLabelText("Motivo"),
      "incorrect_interpretation",
    );

    await userEvent.type(
      screen.getByLabelText(/Commento \(obbligatorio\)/),
      "la potenza non è quella nominale",
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Registra revisione" }),
    );

    await waitFor(() =>
      expect(backend.requestsFor("POST", `/documents/10/engineering-semantics/${KEY}/reviews`)).toHaveLength(1),
    );

    expect(
      backend.requestsFor(
        "POST",
        `/documents/10/engineering-semantics/${KEY}/reviews`,
      )[0].body,
    ).toEqual({
      decision: "rejected",
      reason: "incorrect_interpretation",
      comment: "la potenza non è quella nominale",
    });
  });

  it("never sends a reviewer", async () => {
    /**
     * The actor is the authenticated identity. A body that could name a
     * reviewer would be a body in which a caller could claim to be
     * somebody else.
     */
    const backend = panel({ [RECORD]: { status: 201, body: aReview() } });

    await userEvent.click(
      await screen.findByRole("button", { name: /Registra revisione/ }),
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Motivo"),
      "confirmed_by_source",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Registra revisione" }),
    );

    await waitFor(() =>
      expect(
        backend.requestsFor(
          "POST",
          `/documents/10/engineering-semantics/${KEY}/reviews`,
        ),
      ).toHaveLength(1),
    );

    const sent = backend.requestsFor(
      "POST",
      `/documents/10/engineering-semantics/${KEY}/reviews`,
    )[0].body as Record<string, unknown>;

    expect(sent).not.toHaveProperty("reviewer");
    expect(sent).not.toHaveProperty("reviewer_user_id");
  });

  it("offers only the reasons the backend admits for a decision", async () => {
    panel();

    await userEvent.click(
      await screen.findByRole("button", { name: /Registra revisione/ }),
    );

    const reasons = screen.getByLabelText("Motivo");

    expect(
      within(reasons).queryByRole("option", {
        name: "Interpretazione errata",
      }),
    ).toBeNull();

    await userEvent.click(screen.getByRole("radio", { name: /Respinto/ }));

    expect(
      within(screen.getByLabelText("Motivo")).getByRole("option", {
        name: "Interpretazione errata",
      }),
    ).toBeInTheDocument();
  });

  it("will not submit a rejection with no explanation", async () => {
    panel();

    await userEvent.click(
      await screen.findByRole("button", { name: /Registra revisione/ }),
    );
    await userEvent.click(screen.getByRole("radio", { name: /Respinto/ }));
    await userEvent.selectOptions(
      screen.getByLabelText("Motivo"),
      "incorrect_interpretation",
    );

    expect(
      screen.getByRole("button", { name: "Registra revisione" }),
    ).toBeDisabled();
  });

  it("says the earlier judgement is kept, not replaced", async () => {
    panel({ [CURRENT]: { body: aReviewedStatement() } });

    await userEvent.click(
      await screen.findByRole("button", { name: /Aggiorna giudizio/ }),
    );

    expect(
      screen.getByText(/non viene modificato né cancellato/),
    ).toBeInTheDocument();
  });

  it("re-reads both projections after recording", async () => {
    const backend = panel({ [RECORD]: { status: 201, body: aReview() } });

    await userEvent.click(
      await screen.findByRole("button", { name: /Registra revisione/ }),
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Motivo"),
      "confirmed_by_source",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Registra revisione" }),
    );

    await waitFor(() =>
      expect(
        backend.requestsFor(
          "GET",
          `/documents/10/engineering-semantics/${KEY}/current-review`,
        ).length,
      ).toBeGreaterThan(1),
    );
  });

  it("reports a refused submission without signing the user out", async () => {
    panel({
      [RECORD]: {
        status: 403,
        body: { detail: "This action requires a permission your role does not carry." },
      },
    });

    await userEvent.click(
      await screen.findByRole("button", { name: /Registra revisione/ }),
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Motivo"),
      "confirmed_by_source",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Registra revisione" }),
    );

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Registra revisione" }),
    ).toBeInTheDocument();
  });

  it("reports a policy refusal in the backend's own words", async () => {
    panel({
      [RECORD]: {
        status: 422,
        body: {
          detail:
            "A 'rejected' decision with reason 'other' requires a comment explaining it.",
        },
      },
    });

    await userEvent.click(
      await screen.findByRole("button", { name: /Registra revisione/ }),
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Motivo"),
      "confirmed_by_source",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Registra revisione" }),
    );

    expect(
      await screen.findByText(/requires a comment explaining it/),
    ).toBeInTheDocument();
  });
});

// --- Permission ----------------------------------------------------------

describe("permission", () => {
  it("offers the action to an engineer", async () => {
    panel();

    expect(
      await screen.findByRole("button", { name: /Registra revisione/ }),
    ).toBeInTheDocument();
  });

  it("still shows the judgement to a role that may not review", async () => {
    /**
     * Reading and recording are different permissions. A reader sees
     * everything and is told why the control is absent.
     */
    panel(
      { [CURRENT]: { body: aReviewedStatement() } },
      aSession({ role: "auditor" as never }),
    );

    expect(await screen.findByText("Approvato")).toBeInTheDocument();
    expect(
      screen.getByText(/consente di leggere le revisioni ma non di registrarne/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Registra revisione/ }),
    ).toBeNull();
  });
});

// --- The history ---------------------------------------------------------

describe("the history", () => {
  it("renders every judgement, newest first", async () => {
    panel({
      [HISTORY]: {
        body: aReviewHistory([
          {
            review: aReview({
              review_id: 2,
              decision: "rejected",
              reason: "incorrect_interpretation",
              comment: "rivisto",
            }),
            superseded: false,
            applicability: "applies",
          },
          {
            review: aReview({ review_id: 1 }),
            superseded: true,
            applicability: "applies",
          },
        ]),
      },
    });

    const timeline = await screen.findByRole("list", {
      name: "Cronologia delle revisioni",
    });

    const entries = within(timeline).getAllByRole("listitem");

    expect(entries).toHaveLength(2);
    expect(within(entries[0]).getByText("Respinto")).toBeInTheDocument();
    expect(within(entries[1]).getByText("Superato")).toBeInTheDocument();
  });

  it("does not decide for itself which judgement is current", async () => {
    /**
     * `superseded` comes from the backend, which derives it from the
     * ordered history. Here the fixture marks the *first* entry
     * superseded - an ordering no client would infer - and the UI renders
     * exactly what it was told.
     */
    panel({
      [HISTORY]: {
        body: aReviewHistory([
          {
            review: aReview({ review_id: 9 }),
            superseded: true,
            applicability: "applies",
          },
        ]),
      },
    });

    const timeline = await screen.findByRole("list", {
      name: "Cronologia delle revisioni",
    });

    expect(within(timeline).getByText("Superato")).toBeInTheDocument();
  });

  it("shows a comment as text, never as markup", async () => {
    panel({
      [HISTORY]: {
        body: aReviewHistory([
          {
            review: aReview({
              comment: "<b>non</b> interpretare questo",
            }),
            superseded: false,
            applicability: "applies",
          },
        ]),
      },
    });

    expect(
      await screen.findByText("<b>non</b> interpretare questo"),
    ).toBeInTheDocument();
    expect(document.querySelector("li b")).toBeNull();
  });

  it("keeps the current decision visible when the history fails", async () => {
    /**
     * Partial failure. An engineer looking at a rejected statement needs
     * to see the rejection even if the timeline beneath it is
     * unavailable.
     */
    panel({
      [CURRENT]: { body: aReviewedStatement() },
      [HISTORY]: { status: 500, body: { detail: "boom" } },
    });

    expect(await screen.findByText("Approvato")).toBeInTheDocument();
    expect(
      screen.getByText(/Cronologia non disponibile/),
    ).toBeInTheDocument();
  });

  it("says nothing has been judged rather than showing an empty list", async () => {
    panel();

    expect(
      await screen.findByText(/Nessun giudizio registrato/),
    ).toBeInTheDocument();
  });
});
