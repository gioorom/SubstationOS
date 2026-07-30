/**
 * The Workspace read model.
 *
 * These are the tests that make "the frontend infers nothing" an
 * assertion rather than a promise in a comment. Every one of them is
 * about a *join*: which artefact is related to which, and on the
 * strength of what. The answer is always a key the backend wrote, and
 * several tests below exist purely to prove that a resemblance - the
 * same text, the same value, the same line - relates nothing.
 */

import { describe, expect, it } from "vitest";

import {
  buildSupportChain,
  buildWorkspaceIndex,
  describeLocation,
  evidenceKeysForSelection,
  factDiagnosticKey,
  locationOfProvenance,
  locationsForSelection,
  reconcileDiagnosticStatus,
  resolveSpanBoxes,
  resolveStatementQuantity,
  selectionFromQuery,
  semanticDiagnosticKey,
} from "@/lib/workspace";

import {
  aCanonicalPage,
  aFactSet,
  aSemanticSet,
  anEntitySet,
  anEvidenceSet,
} from "./_backend";

const DOCUMENT_ID = 10;

function anIndex(
  overrides: Partial<{
    evidence: ReturnType<typeof anEvidenceSet> | null;
    entities: ReturnType<typeof anEntitySet> | null;
    facts: ReturnType<typeof aFactSet> | null;
    semantics: ReturnType<typeof aSemanticSet> | null;
  }> = {},
) {
  // `null` is a meaningful value here - it is how a test says "this
  // stage has not run" - so a missing key and an explicit `null` must
  // not collapse into the same thing.
  return buildWorkspaceIndex(DOCUMENT_ID, {
    evidence: "evidence" in overrides ? overrides.evidence! : anEvidenceSet(),
    entities: "entities" in overrides ? overrides.entities! : anEntitySet(),
    facts: "facts" in overrides ? overrides.facts! : aFactSet(),
    semantics:
      "semantics" in overrides ? overrides.semantics! : aSemanticSet(),
  });
}

// --- Indexing ------------------------------------------------------------

describe("the workspace index", () => {
  it("keys every artefact by its own backend key", () => {
    const index = anIndex();

    expect([...index.evidenceByKey.keys()]).toEqual([
      "ev-designation",
      "ev-power",
    ]);
    expect([...index.entitiesByKey.keys()]).toEqual([
      "entity-tr1",
      "entity-630kva",
    ]);
    expect([...index.factsByKey.keys()]).toEqual(["fact-tr1-630"]);
    expect([...index.semanticsByKey.keys()]).toEqual([
      "statement-tr1-power",
    ]);
  });

  it("links an entity to the evidence the entity itself declares", () => {
    const index = anIndex();

    expect(index.evidenceKeysByEntity.get("entity-tr1")).toEqual([
      "ev-designation",
    ]);
    expect(index.evidenceKeysByEntity.get("entity-630kva")).toEqual([
      "ev-power",
    ]);
  });

  it("does not group two observations because their text matches", () => {
    /**
     * The designation observation and the entity both read `TR1`, and
     * that resemblance must relate nothing. The entity that declares no
     * evidence gets none - a text-matching implementation would hand it
     * the observation anyway, which is the failure this test pins.
     */
    const index = anIndex({
      entities: anEntitySet({
        entities: [
          {
            entity_key: "entity-tr1",
            entity_type: "equipment_designation",
            status: "resolved",
            entity_version: "1.0",
            resolution_rule_id: "designation_grouping",
            resolution_rule_version: "1.0",
            label: "TR1",
            evidence_count: 0,
            designation: { normalized: "TR1" },
            quantity: null,
            evidence: [],
          },
        ],
      }),
    });

    expect(index.evidenceKeysByEntity.get("entity-tr1")).toBeUndefined();
    expect(index.evidenceByKey.get("ev-designation")?.observed_text).toBe(
      "TR1",
    );
  });

  it("reads an entity's evidence references the other way round", () => {
    const index = anIndex();

    expect(index.entityKeysByEvidence.get("ev-designation")).toEqual([
      "entity-tr1",
    ]);
  });

  it("links a fact to both entities it names, and to its support", () => {
    const index = anIndex();

    expect(index.factKeysByEntity.get("entity-tr1")).toEqual([
      "fact-tr1-630",
    ]);
    expect(index.factKeysByEntity.get("entity-630kva")).toEqual([
      "fact-tr1-630",
    ]);
    expect(index.factKeysByEvidence.get("ev-designation")).toEqual([
      "fact-tr1-630",
    ]);
  });

  it("links a statement to the facts it cites", () => {
    const index = anIndex();

    expect(index.semanticKeysByFact.get("fact-tr1-630")).toEqual([
      "statement-tr1-power",
    ]);
  });

  it("indexes observations by the page they declare", () => {
    const index = anIndex();

    expect(index.evidenceKeysByPage.get(1)).toEqual([
      "ev-designation",
      "ev-power",
    ]);
    expect(index.pages).toEqual([1]);
  });

  it("is empty, not broken, when a stage has produced nothing", () => {
    const index = buildWorkspaceIndex(DOCUMENT_ID, {
      evidence: null,
      entities: null,
      facts: null,
      semantics: null,
    });

    expect(index.evidenceByKey.size).toBe(0);
    expect(index.pages).toEqual([]);
  });
});

// --- Diagnostics ---------------------------------------------------------

describe("diagnostics", () => {
  it("addresses a declined fact by the line it happened on", () => {
    const index = anIndex({
      facts: aFactSet({
        facts: [],
        fact_count: 0,
        has_ambiguities: true,
        diagnostics: [
          {
            reason: "multiple_subjects",
            page_number: 2,
            paragraph_index: 4,
            line_index: 1,
            subject_entity_keys: ["entity-tr1", "entity-630kva"],
            object_entity_keys: [],
          },
        ],
      }),
    });

    const key = factDiagnosticKey({
      reason: "multiple_subjects",
      page_number: 2,
      paragraph_index: 4,
      line_index: 1,
    });

    const diagnostic = index.diagnosticsByKey.get(key);

    expect(diagnostic?.origin).toBe("fact");
    expect(diagnostic?.location?.page_number).toBe(2);
    expect(diagnostic?.entityKeys).toEqual([
      "entity-tr1",
      "entity-630kva",
    ]);
  });

  it("gives a declined interpretation no line, because it has none", () => {
    /**
     * A semantic diagnostic names a subject, not a line: which line
     * carried the meaning is exactly what could not be decided. Inventing
     * one would be the frontend answering a question the rules declined.
     */
    const index = anIndex({
      semantics: aSemanticSet({
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
    });

    const diagnostic = index.diagnosticsByKey.get(
      semanticDiagnosticKey({
        reason: "multiple_candidate_quantities",
        subject_entity_key: "entity-tr1",
      }),
    );

    expect(diagnostic?.location).toBeNull();
    expect(diagnostic?.factKeys).toEqual(["fact-tr1-630"]);
  });

  it("reports the worse of the two stages they come from", () => {
    const unrun = {
      availability: "unrun",
      error: null,
      count: null,
    } as const;
    const empty = {
      availability: "empty",
      error: null,
      count: 0,
    } as const;
    const failed = {
      availability: "failed",
      error: "Il backend ha risposto con un errore interno.",
      count: null,
    } as const;

    // A failed read must never be reported as "no diagnostics".
    expect(
      reconcileDiagnosticStatus(failed, empty, 0).availability,
    ).toBe("failed");

    // Two stages that never ran is not a document that declined nothing.
    expect(reconcileDiagnosticStatus(unrun, unrun, 0).availability).toBe(
      "unrun",
    );

    // One stage ran and declined nothing: an answer, not an absence.
    expect(reconcileDiagnosticStatus(empty, unrun, 0).availability).toBe(
      "empty",
    );

    expect(reconcileDiagnosticStatus(empty, empty, 3)).toEqual({
      availability: "available",
      error: null,
      count: 3,
    });
  });

  it("never turns a diagnostic into a statement", () => {
    const index = anIndex({
      semantics: aSemanticSet({
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
    });

    expect(index.semanticsByKey.size).toBe(0);
    expect(index.semanticKeysByEntity.get("entity-tr1")).toBeUndefined();
  });
});

// --- The support chain ---------------------------------------------------

describe("the support chain", () => {
  it("walks meaning back to the observations, by explicit key", () => {
    const chain = buildSupportChain(anIndex(), "statement-tr1-power");

    expect(chain.statement?.statement_key).toBe("statement-tr1-power");
    expect(chain.facts.map((link) => link.key)).toEqual(["fact-tr1-630"]);
    expect(chain.entities.map((link) => link.key)).toEqual([
      "entity-tr1",
      "entity-630kva",
    ]);
    expect(chain.evidence.map((link) => link.key)).toEqual([
      "ev-designation",
      "ev-power",
    ]);
    expect(chain.incomplete).toBe(false);
  });

  it("is deterministic: the same statement gives the same chain", () => {
    const index = anIndex();

    expect(buildSupportChain(index, "statement-tr1-power")).toEqual(
      buildSupportChain(index, "statement-tr1-power"),
    );
  });

  it("reports a cited fact that is not loaded instead of dropping it", () => {
    /**
     * The one thing an engineer most needs to see is a claim resting on
     * something that is not there. Silently omitting the link would turn
     * a broken chain into a short one.
     */
    const chain = buildSupportChain(anIndex({ facts: null }), "statement-tr1-power");

    expect(chain.facts).toEqual([
      { key: "fact-tr1-630", artefact: null },
    ]);
    expect(chain.missing).toContain("fact-tr1-630");
    expect(chain.incomplete).toBe(true);
  });

  it("still resolves what it can when one stage is missing", () => {
    const chain = buildSupportChain(anIndex({ facts: null }), "statement-tr1-power");

    expect(
      chain.entities.every((link) => link.artefact !== null),
    ).toBe(true);
  });

  it("reports a statement key that matches nothing as missing", () => {
    const chain = buildSupportChain(anIndex(), "statement-che-non-esiste");

    expect(chain.statement).toBeNull();
    expect(chain.missing).toEqual(["statement-che-non-esiste"]);
    expect(chain.incomplete).toBe(true);
  });

  it("resolves a rated power through the quantity entity, not a copy", () => {
    const index = anIndex();
    const statement = index.semanticsByKey.get("statement-tr1-power")!;

    const quantity = resolveStatementQuantity(index, statement);

    expect(quantity?.entity_key).toBe(statement.object_entity_key);
    expect(quantity?.quantity).toEqual({
      value: "630",
      unit: "kVA",
      base_value: "630000",
      base_unit: "VA",
    });
    // The statement itself carries no figure, and nothing here adds one.
    expect(statement).not.toHaveProperty("value");
    expect(statement).not.toHaveProperty("unit");
  });

  it("gives no quantity when the referenced entity is not loaded", () => {
    const index = anIndex({ entities: null });
    const statement = index.semanticsByKey.get("statement-tr1-power")!;

    expect(resolveStatementQuantity(index, statement)).toBeNull();
  });
});

// --- What a selection points at ------------------------------------------

describe("locating a selection in the source", () => {
  it("follows an entity's own evidence list", () => {
    expect(
      evidenceKeysForSelection(anIndex(), "entity", "entity-tr1"),
    ).toEqual(["ev-designation"]);
  });

  it("follows a fact's own support", () => {
    expect(
      evidenceKeysForSelection(anIndex(), "fact", "fact-tr1-630"),
    ).toEqual(["ev-designation"]);
  });

  it("locates evidence at the page, paragraph and line it declares", () => {
    const index = anIndex();
    const [location] = locationsForSelection(
      index,
      "evidence",
      "ev-power",
    );

    expect(location.page_number).toBe(1);
    expect(location.paragraph_index).toBe(0);
    expect(location.line_index).toBe(0);
    expect(location.excerpt).toBe("Trasformatore TR1 630 kVA");
    expect(describeLocation(location)).toBe("p. 1 · par. 0 · riga 0");
  });

  it("has no location for a key that matches nothing", () => {
    expect(
      locationsForSelection(anIndex(), "evidence", "ev-inesistente"),
    ).toEqual([]);
  });
});

// --- Geometry ------------------------------------------------------------

describe("resolving a highlight", () => {
  const index = anIndex();
  const location = locationOfProvenance(
    DOCUMENT_ID,
    index.evidenceByKey.get("ev-power")!.provenance,
  );

  it("returns the parser's own rectangle for the span cited", () => {
    expect(resolveSpanBoxes(aCanonicalPage(), location)).toEqual([
      { x0: 72, y0: 102, x1: 320, y1: 118 },
    ]);
  });

  it("returns nothing for a page other than the one cited", () => {
    expect(
      resolveSpanBoxes(aCanonicalPage({ page_number: 2 }), location),
    ).toEqual([]);
  });

  it("returns nothing when the page has not been read", () => {
    expect(resolveSpanBoxes(null, location)).toEqual([]);
  });

  it("returns nothing, rather than a nearby box, for an unknown span", () => {
    /**
     * The span the observation cites is not on this page. A viewer that
     * fell back to the block's rectangle would draw a plausible box in
     * the wrong place, and an engineer could not tell.
     */
    const page = aCanonicalPage({
      blocks: [
        {
          reading_order: 0,
          kind: "text",
          bounding_box: { x0: 70, y0: 100, x1: 400, y1: 120 },
          spans: [
            {
              reading_order: 7,
              line_index: 0,
              text: "altro",
              bounding_box: { x0: 1, y0: 2, x1: 3, y1: 4 },
              style: {
                font_family: "Helvetica",
                font_size: 11,
                bold: false,
                italic: false,
              },
            },
          ],
        },
      ],
    });

    expect(resolveSpanBoxes(page, location)).toEqual([]);
  });

  it("returns nothing for a location that cites no span at all", () => {
    expect(
      resolveSpanBoxes(aCanonicalPage(), {
        ...location,
        spans: [],
      }),
    ).toEqual([]);
  });
});

// --- Selection parsing ---------------------------------------------------

describe("reading a selection out of the query string", () => {
  it("accepts the five kinds the workspace knows", () => {
    expect(selectionFromQuery("semantic", "s-1")).toEqual({
      kind: "semantic",
      key: "s-1",
    });
  });

  it("discards a kind outside the closed vocabulary", () => {
    expect(selectionFromQuery("../../admin", "x")).toBeNull();
    expect(selectionFromQuery("document", "10")).toBeNull();
  });

  it("discards an incomplete selection", () => {
    expect(selectionFromQuery("evidence", null)).toBeNull();
    expect(selectionFromQuery("evidence", "")).toBeNull();
    expect(selectionFromQuery(null, "ev-1")).toBeNull();
  });

  it("keeps a valid kind whose key matches nothing", () => {
    // Not the same as a rejected selection: this one is shown as a
    // not-found selection, which is information.
    expect(selectionFromQuery("evidence", "ev-inesistente")).toEqual({
      kind: "evidence",
      key: "ev-inesistente",
    });
  });
});
