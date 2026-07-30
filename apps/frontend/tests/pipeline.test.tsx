/**
 * The Engineering Pipeline view.
 *
 * The behaviours asserted here are the ones the deterministic pipeline
 * makes possible and a careless UI would destroy: an unrun stage is not
 * a failure, an empty result is not an error, a re-used artefact is
 * reported as re-used, a declined ambiguity is shown as the rules
 * working, and every artefact can be inspected down to the line it came
 * from.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import DocumentPipelinePage from "@/app/documents/[documentId]/pipeline/page";

import {
  aDocumentDetail,
  aFactSet,
  aSemanticSet,
  anEntitySet,
  anEvidenceSet,
  anIngestionJob,
  stubBackend,
  type Routes,
} from "./_backend";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => ({ documentId: "10" }),
  usePathname: () => "/documents/10/pipeline",
}));

const REPRESENTATION = {
  document_id: 10,
  content_checksum: "a".repeat(64),
  checksum_algorithm: "sha256",
  representation_version: "1.0",
  parser_name: "pymupdf",
  parser_version: "1.24.0",
  page_count: 3,
};

const TEXT = {
  document_id: 10,
  content_checksum: "a".repeat(64),
  representation_version: "1.0",
  segmentation_version: "1.0",
  section_count: 3,
  token_count: 128,
  sections: [
    {
      section_index: 0,
      page_number: 1,
      paragraphs: [
        {
          paragraph_index: 0,
          page_number: 1,
          block_reading_order: 0,
          lines: [
            {
              line_index: 0,
              tokens: [
                {
                  position: 0,
                  text: "Trasformatore",
                  normalized_text: "trasformatore",
                  provenance: {
                    page_number: 1,
                    block_reading_order: 0,
                    span_reading_order: 0,
                    line_index: 0,
                    character_start: 0,
                    character_end: 13,
                  },
                },
                {
                  position: 1,
                  text: "TR1",
                  normalized_text: "tr1",
                  provenance: {
                    page_number: 1,
                    block_reading_order: 0,
                    span_reading_order: 0,
                    line_index: 0,
                    character_start: 14,
                    character_end: 17,
                  },
                },
              ],
            },
          ],
        },
      ],
    },
  ],
};

/** A document whose every stage has run. */
function fullPipeline(overrides: Routes = {}): Routes {
  return {
    "GET /documents/10": { body: aDocumentDetail({ id: 10 }) },
    "GET /documents/10/ingestion/jobs": { body: [anIngestionJob()] },
    "GET /documents/10/canonical-representation": { body: REPRESENTATION },
    "GET /documents/10/canonical-text": { body: TEXT },
    "GET /documents/10/engineering-evidence": { body: anEvidenceSet() },
    "GET /documents/10/engineering-entities": { body: anEntitySet() },
    "GET /documents/10/engineering-facts": { body: aFactSet() },
    "GET /documents/10/engineering-semantics": { body: aSemanticSet() },
    ...overrides,
  };
}

/** A document that has only been uploaded and ingested. */
function freshDocument(overrides: Routes = {}): Routes {
  const notRun = { status: 404, body: { detail: "not run" } };

  return {
    "GET /documents/10": { body: aDocumentDetail({ id: 10 }) },
    "GET /documents/10/ingestion/jobs": { body: [anIngestionJob()] },
    "GET /documents/10/canonical-representation": notRun,
    "GET /documents/10/canonical-text": notRun,
    "GET /documents/10/engineering-evidence": notRun,
    "GET /documents/10/engineering-entities": notRun,
    "GET /documents/10/engineering-facts": notRun,
    "GET /documents/10/engineering-semantics": notRun,
    ...overrides,
  };
}

function stage(id: string): HTMLElement {
  return document.querySelector(`[data-stage="${id}"]`) as HTMLElement;
}

describe("stage states", () => {
  it("shows all seven stages of the deterministic pipeline", async () => {
    stubBackend(fullPipeline());

    render(<DocumentPipelinePage />);

    expect(
      await screen.findByText("Rappresentazione canonica"),
    ).toBeVisible();

    for (const label of [
      "Documento caricato",
      "Rappresentazione canonica",
      "Testo canonico",
      "Evidenze di ingegneria",
      "Entità di ingegneria",
      "Fatti di ingegneria",
      "Interpretazione semantica",
    ]) {
      expect(screen.getByText(label)).toBeVisible();
    }
  });

  it("treats a stage that has never run as ready, not failed", async () => {
    stubBackend(freshDocument());

    render(<DocumentPipelinePage />);

    await screen.findByText("Rappresentazione canonica");

    expect(stage("canonical_representation")).toHaveAttribute(
      "data-state",
      "ready",
    );

    // A 404 from a stage read means "not run yet". It is the normal
    // state of a fresh document and must not be shown as an error.
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("blocks a stage whose predecessor produced nothing", async () => {
    stubBackend(freshDocument());

    render(<DocumentPipelinePage />);

    await screen.findByText("Testo canonico");

    expect(stage("canonical_text")).toHaveAttribute("data-state", "blocked");
    expect(stage("engineering_semantics")).toHaveAttribute(
      "data-state",
      "blocked",
    );
  });

  it("reports counts read from each stage's own artefact", async () => {
    stubBackend(fullPipeline());

    render(<DocumentPipelinePage />);

    await screen.findByText("Rappresentazione canonica");

    expect(within(stage("canonical_representation")).getByText("3 pagine"))
      .toBeVisible();
    expect(within(stage("canonical_text")).getByText("128 token"))
      .toBeVisible();
    expect(
      within(stage("engineering_evidence")).getByText("2 osservazioni"),
    ).toBeVisible();
    expect(within(stage("engineering_entities")).getByText("2 entità"))
      .toBeVisible();
    expect(within(stage("engineering_facts")).getByText("1 fatto"))
      .toBeVisible();
    expect(
      within(stage("engineering_semantics")).getByText("1 affermazione"),
    ).toBeVisible();
  });

  it("says a stage exposes no timestamp rather than inventing one", async () => {
    stubBackend(fullPipeline());

    render(<DocumentPipelinePage />);

    await screen.findByText("Rappresentazione canonica");

    // Pipeline artefacts carry no timestamp by design: excluding it is
    // what makes two runs compare equal.
    expect(
      within(stage("engineering_evidence")).getByText(
        /Non esposto \(artefatto deterministico\)/,
      ),
    ).toBeVisible();
  });

  it("shows the version triad each stage ran under", async () => {
    stubBackend(fullPipeline());

    render(<DocumentPipelinePage />);

    await screen.findByText("Interpretazione semantica");

    expect(
      within(stage("engineering_semantics")).getByText(/Policy semantica/),
    ).toBeVisible();
    expect(
      within(stage("engineering_facts")).getByText(/Policy dei fatti/),
    ).toBeVisible();
  });

  it("marks an empty result as completed, not as a failure", async () => {
    stubBackend(
      fullPipeline({
        "GET /documents/10/engineering-evidence": {
          body: anEvidenceSet({ evidence_count: 0, evidence: [] }),
        },
      }),
    );

    render(<DocumentPipelinePage />);

    await screen.findByText("Evidenze di ingegneria");

    expect(stage("engineering_evidence")).toHaveAttribute(
      "data-state",
      "empty",
    );

    expect(
      within(stage("engineering_evidence")).getByText(
        /È una risposta valida delle regole, non un errore/,
      ),
    ).toBeVisible();
  });
});

describe("running a stage", () => {
  it("posts to the stage endpoint and refreshes the pipeline", async () => {
    const backend = stubBackend(
      freshDocument({
        "POST /documents/10/canonical-representation": {
          status: 201,
          body: {
            succeeded: true,
            reused: false,
            representation: REPRESENTATION,
            failure: null,
          },
        },
        "GET /documents/10/canonical-representation": [
          { status: 404, body: { detail: "not run" } },
          { body: REPRESENTATION },
        ],
      }),
    );

    const user = userEvent.setup();
    render(<DocumentPipelinePage />);

    await screen.findByText("Rappresentazione canonica");

    await user.click(
      within(stage("canonical_representation")).getByRole("button", {
        name: /Esegui stage/,
      }),
    );

    await waitFor(() => {
      expect(
        backend.requestsFor("POST", "/documents/10/canonical-representation"),
      ).toHaveLength(1);
    });

    expect(
      await within(stage("canonical_representation")).findByText("3 pagine"),
    ).toBeVisible();
  });

  it("reports a re-used artefact as re-used", async () => {
    stubBackend(
      fullPipeline({
        "POST /documents/10/engineering-evidence": {
          status: 200,
          body: {
            succeeded: true,
            reused: true,
            found_evidence: true,
            rejected_count: 0,
            evidence_set: anEvidenceSet(),
            failure: null,
          },
        },
      }),
    );

    const user = userEvent.setup();
    render(<DocumentPipelinePage />);

    await screen.findByText("Evidenze di ingegneria");

    await user.click(
      within(stage("engineering_evidence")).getByRole("button", {
        name: /Riesegui/,
      }),
    );

    expect(
      await within(stage("engineering_evidence")).findByText(
        "Artefatto esistente riutilizzato",
      ),
    ).toBeVisible();
  });

  it("shows a stage's typed failure code message", async () => {
    stubBackend(
      freshDocument({
        "POST /documents/10/canonical-representation": {
          status: 200,
          body: {
            succeeded: false,
            reused: false,
            representation: null,
            failure: {
              code: "encrypted_document",
              message: "The document is encrypted and cannot be parsed.",
              detail: null,
            },
          },
        },
      }),
    );

    const user = userEvent.setup();
    render(<DocumentPipelinePage />);

    await screen.findByText("Rappresentazione canonica");

    await user.click(
      within(stage("canonical_representation")).getByRole("button", {
        name: /Esegui stage/,
      }),
    );

    expect(
      await screen.findByText(
        "The document is encrypted and cannot be parsed.",
      ),
    ).toBeVisible();

    expect(stage("canonical_representation")).toHaveAttribute(
      "data-state",
      "failed",
    );
  });

  it("explains a 404 as the previous stage not having run", async () => {
    stubBackend(
      freshDocument({
        "POST /documents/10/canonical-representation": {
          status: 404,
          body: { detail: "Document has no canonical text" },
        },
      }),
    );

    const user = userEvent.setup();
    render(<DocumentPipelinePage />);

    await screen.findByText("Rappresentazione canonica");

    await user.click(
      within(stage("canonical_representation")).getByRole("button", {
        name: /Esegui stage/,
      }),
    );

    expect(
      await screen.findByText(
        "Lo stage precedente non ha ancora prodotto artefatti.",
      ),
    ).toBeVisible();
  });
});

describe("inspecting artefacts", () => {
  it("shows each observation with the rule and the line that produced it", async () => {
    const user = userEvent.setup();
    stubBackend(fullPipeline());

    render(<DocumentPipelinePage />);

    await screen.findByText("Evidenze di ingegneria");

    await user.click(
      within(stage("engineering_evidence")).getByRole("button", {
        name: /Ispeziona artefatti/,
      }),
    );

    // "630 kVA" appears as both the observed text and the exact value.
    expect((await screen.findAllByText("630 kVA")).length).toBeGreaterThan(1);
    expect(screen.getByText(/power_with_unit/)).toBeVisible();
    expect(screen.getAllByText(/p\.1 · par\.0 · riga 0/).length)
      .toBeGreaterThan(0);
  });

  it("prints quantities as the exact decimal strings the backend sent", async () => {
    const user = userEvent.setup();

    stubBackend(
      fullPipeline({
        "GET /documents/10/engineering-entities": {
          body: anEntitySet({
            entities: [
              {
                entity_key: "entity-precise",
                entity_type: "engineering_quantity",
                status: "resolved",
                entity_version: "1.0",
                resolution_rule_id: "quantity_observation",
                resolution_rule_version: "1.0",
                label: "20.500 kV",
                evidence_count: 1,
                designation: null,
                quantity: {
                  // A float round-trip would render 20.5.
                  value: "20.500",
                  unit: "kV",
                  base_value: "20500.000",
                  base_unit: "V",
                },
                evidence: [],
              },
            ],
            entity_count: 1,
          }),
        },
      }),
    );

    render(<DocumentPipelinePage />);

    await screen.findByText("Entità di ingegneria");

    await user.click(
      within(stage("engineering_entities")).getByRole("button", {
        name: /Ispeziona artefatti/,
      }),
    );

    // A float round-trip would render 20.5 in both the label and the
    // value column.
    const rendered = await screen.findAllByText("20.500 kV");
    expect(rendered.length).toBeGreaterThan(1);
  });

  it("resolves fact entity keys to their labels", async () => {
    const user = userEvent.setup();
    stubBackend(fullPipeline());

    render(<DocumentPipelinePage />);

    await screen.findByText("Fatti di ingegneria");

    await user.click(
      within(stage("engineering_facts")).getByRole("button", {
        name: /Ispeziona artefatti/,
      }),
    );

    expect(await screen.findByText("grandezza associata")).toBeVisible();

    // The keys are resolved through the entity set the backend returned,
    // not guessed.
    const table = screen.getByText("grandezza associata").closest("tr")!;
    expect(within(table).getByText("TR1")).toBeVisible();
    expect(within(table).getByText("630 kVA")).toBeVisible();
  });

  it("shows a declined fact line as the rules working", async () => {
    const user = userEvent.setup();

    stubBackend(
      fullPipeline({
        "GET /documents/10/engineering-facts": {
          body: aFactSet({
            fact_count: 0,
            facts: [],
            has_ambiguities: true,
            diagnostics: [
              {
                reason: "multiple_subjects",
                page_number: 2,
                paragraph_index: 1,
                line_index: 3,
                subject_entity_keys: ["entity-tr1", "entity-tr2"],
                object_entity_keys: ["entity-630kva"],
              },
            ],
          }),
        },
      }),
    );

    render(<DocumentPipelinePage />);

    await screen.findByText("Fatti di ingegneria");

    expect(
      within(stage("engineering_facts")).getByText("1 dichiarate"),
    ).toBeVisible();

    await user.click(
      within(stage("engineering_facts")).getByRole("button", {
        name: /Ispeziona artefatti/,
      }),
    );

    expect(
      await screen.findByText(
        /La riga contiene più sigle: non dice a quale apparecchiatura/,
      ),
    ).toBeVisible();
  });

  it("shows a semantic statement with its rule, and no value of its own", async () => {
    const user = userEvent.setup();
    stubBackend(fullPipeline());

    render(<DocumentPipelinePage />);

    await screen.findByText("Interpretazione semantica");

    await user.click(
      within(stage("engineering_semantics")).getByRole("button", {
        name: /Ispeziona artefatti/,
      }),
    );

    expect(await screen.findByText("ha potenza nominale")).toBeVisible();

    expect(
      screen.getByText(/rated_power_from_associated_power_quantity/),
    ).toBeVisible();

    const row = screen.getByText("ha potenza nominale").closest("tr")!;

    // A statement carries no value and no unit: the figure lives on the
    // quantity entity, where a rated value has one source of truth.
    expect(within(row).getByText("630 kVA")).toBeVisible();
    expect(within(row).queryByText("630 kVA kVA")).toBeNull();
  });

  it("shows an uninterpreted subject with the reason it was declined", async () => {
    const user = userEvent.setup();

    stubBackend(
      fullPipeline({
        "GET /documents/10/engineering-semantics": {
          body: aSemanticSet({
            statement_count: 0,
            statements: [],
            has_ambiguities: true,
            diagnostics: [
              {
                reason: "multiple_candidate_quantities",
                subject_entity_key: "entity-tr1",
                candidate_fact_keys: ["fact-a", "fact-b"],
              },
            ],
          }),
        },
      }),
    );

    render(<DocumentPipelinePage />);

    await screen.findByText("Interpretazione semantica");

    await user.click(
      within(stage("engineering_semantics")).getByRole("button", {
        name: /Ispeziona artefatti/,
      }),
    );

    expect(
      await screen.findByText(/Più potenze associate alla stessa sigla/),
    ).toBeVisible();
  });

  it("shows canonical text with page and paragraph provenance", async () => {
    const user = userEvent.setup();
    stubBackend(fullPipeline());

    render(<DocumentPipelinePage />);

    await screen.findByText("Testo canonico");

    await user.click(
      within(stage("canonical_text")).getByRole("button", {
        name: /Ispeziona artefatti/,
      }),
    );

    expect(await screen.findByText("Trasformatore TR1")).toBeVisible();
  });
});

describe("failures loading the pipeline", () => {
  it("reports a backend that cannot be reached", async () => {
    stubBackend({
      "GET /documents/10": { body: aDocumentDetail({ id: 10 }) },
      "GET /documents/10/ingestion/jobs": { networkFailure: true },
      "GET /documents/10/canonical-representation": { networkFailure: true },
      "GET /documents/10/canonical-text": { networkFailure: true },
      "GET /documents/10/engineering-evidence": { networkFailure: true },
      "GET /documents/10/engineering-entities": { networkFailure: true },
      "GET /documents/10/engineering-facts": { networkFailure: true },
      "GET /documents/10/engineering-semantics": { networkFailure: true },
    });

    render(<DocumentPipelinePage />);

    expect(
      await screen.findByText(/il backend non risponde/i),
    ).toBeVisible();
  });

  it("reports a 500 from a stage read", async () => {
    stubBackend(
      fullPipeline({
        "GET /documents/10/engineering-facts": {
          status: 500,
          body: { detail: "boom" },
        },
      }),
    );

    render(<DocumentPipelinePage />);

    expect(
      await screen.findByText(/il backend ha risposto con un errore interno/i),
    ).toBeVisible();
  });
});
