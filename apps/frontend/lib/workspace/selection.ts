/**
 * What the Workspace has selected, and how that survives a refresh.
 *
 * The selection lives in the URL as `?kind=...&key=...` and nowhere
 * else. Two consequences are deliberate: Back and Forward move through
 * inspections, and a link to a semantic statement is a link an engineer
 * can send to a colleague.
 *
 * The URL carries **two short strings**. It never carries artefact JSON,
 * and `kind` is checked against a closed vocabulary before it is used -
 * a selection is a lookup in an index the Workspace has already loaded,
 * so no value in the query string can reach an endpoint.
 */

export const SELECTION_KINDS = [
  "semantic",
  "fact",
  "entity",
  "evidence",
  "diagnostic",
] as const;

export type SelectionKind = (typeof SELECTION_KINDS)[number];

export const SELECTION_KIND_LABELS: Record<SelectionKind, string> = {
  semantic: "Affermazione semantica",
  fact: "Fatto",
  entity: "Entità",
  evidence: "Evidenza",
  diagnostic: "Diagnostica",
};

export interface Selection {
  kind: SelectionKind;
  key: string;
}

export function isSelectionKind(value: unknown): value is SelectionKind {
  return (
    typeof value === "string" &&
    (SELECTION_KINDS as readonly string[]).includes(value)
  );
}

/**
 * Reads a selection out of the query string.
 *
 * `null` for absent, incomplete or unrecognised input. An unknown `kind`
 * is discarded here rather than carried inward, so the rest of the
 * Workspace only ever handles the five it knows. A *valid* kind with a
 * key that matches no artefact is **not** discarded: that is a
 * not-found selection, and the Workspace says so.
 */
export function selectionFromQuery(
  kind: string | null,
  key: string | null,
): Selection | null {
  if (!isSelectionKind(kind) || key === null || key === "") {
    return null;
  }

  return { kind, key };
}

export function selectionsEqual(
  left: Selection | null,
  right: Selection | null,
): boolean {
  if (left === null || right === null) {
    return left === right;
  }

  return left.kind === right.kind && left.key === right.key;
}

/**
 * The address of a diagnostic.
 *
 * Diagnostics are the one artefact the backend does not key, because
 * they are not records: a declined construction is the *absence* of one.
 * The Workspace still has to be able to select, link to and restore one,
 * so it addresses each by the backend fields that identify it - a fact
 * diagnostic by the line it happened on, a semantic one by the subject
 * it declined.
 *
 * This is an address, not an identity: it is derived from governed
 * fields only, it is never sent to the backend, and it carries no claim
 * that the backend would recognise it.
 */
export function factDiagnosticKey(diagnostic: {
  reason: string;
  page_number: number;
  paragraph_index: number;
  line_index: number;
}): string {
  return [
    "fact",
    diagnostic.reason,
    diagnostic.page_number,
    diagnostic.paragraph_index,
    diagnostic.line_index,
  ].join(":");
}

export function semanticDiagnosticKey(diagnostic: {
  reason: string;
  subject_entity_key: string;
}): string {
  return ["semantic", diagnostic.reason, diagnostic.subject_entity_key].join(
    ":",
  );
}
