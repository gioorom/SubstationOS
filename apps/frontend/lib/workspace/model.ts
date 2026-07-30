/**
 * The Workspace read model.
 *
 * One normalised, memoised index over the artefacts five endpoints
 * already return in full, built so that every navigation the Workspace
 * offers is a map lookup rather than a request.
 *
 * **The one rule this module exists to enforce:** every index is keyed
 * on a reference the backend wrote down. `entity.evidence[].evidence_key`,
 * `fact.subject_entity_key`, `statement.supporting_fact_keys` - those are
 * the joins, and they are the only joins. Nothing here compares observed
 * text, matches a quantity to a quantity, or decides that two artefacts
 * are related because they share a line. A reference to an artefact that
 * is not loaded is reported as missing, never resolved by resemblance.
 */

import type {
  EngineeringEntity,
  EngineeringEvidence,
  EngineeringFact,
  EntitySet,
  EvidenceSet,
  FactSet,
  SemanticSet,
  SemanticStatement,
} from "@/lib/contracts";
import {
  FACT_AMBIGUITY_LABELS,
  SEMANTIC_AMBIGUITY_LABELS,
} from "@/lib/contracts";

import {
  factDiagnosticKey,
  semanticDiagnosticKey,
} from "./selection";
import {
  locationOfFactDiagnostic,
  locationOfProvenance,
  type SourceLocation,
} from "./source-location";

/**
 * What one stage endpoint answered.
 *
 * These four are not interchangeable and the UI never merges them:
 *
 * - `unrun`     the stage has produced nothing yet (the read was a 404)
 * - `empty`     it ran and found nothing - a valid engineering answer
 * - `available` it ran and produced artefacts
 * - `failed`    the read itself failed; what exists is unknown
 */
export type StageAvailability =
  | "unrun"
  | "empty"
  | "available"
  | "failed";

export interface StageStatus {
  availability: StageAvailability;
  /** A user-facing sentence when `failed`, otherwise `null`. */
  error: string | null;
  /** Artefacts in the set, or `null` when there is no set. */
  count: number | null;
}

/**
 * The state of the diagnostics view, from the two stages that emit them.
 *
 * Diagnostics have no stage of their own, so their availability has to be
 * reconciled: a failed read must not be reported as "no diagnostics", and
 * two stages that never ran must not be reported as a document that
 * declined nothing. The worse answer wins, in that order.
 *
 * Lives here rather than in a component so the tab's badge and the list
 * beneath it cannot disagree about what they are showing.
 */
export function reconcileDiagnosticStatus(
  factStatus: StageStatus,
  semanticStatus: StageStatus,
  count: number,
): StageStatus {
  if (factStatus.availability === "failed") {
    return factStatus;
  }

  if (semanticStatus.availability === "failed") {
    return semanticStatus;
  }

  if (count > 0) {
    return { availability: "available", error: null, count };
  }

  if (
    factStatus.availability === "unrun" &&
    semanticStatus.availability === "unrun"
  ) {
    return { availability: "unrun", error: null, count: null };
  }

  return { availability: "empty", error: null, count: 0 };
}

export type DiagnosticOrigin = "fact" | "semantic";

/**
 * A declined result, as first-class Workspace content.
 *
 * A diagnostic is not a statement and is never shaped like one: it names
 * no subject/object pair, because which was which is exactly what the
 * rules could not determine. It carries the artefacts it *does* name, so
 * an engineer can navigate to them.
 */
export interface WorkspaceDiagnostic {
  key: string;
  origin: DiagnosticOrigin;
  reason: string;
  /** The backend's own catalogued explanation of that reason. */
  explanation: string;
  /** `null` where the artefact records no line - a semantic decline. */
  location: SourceLocation | null;
  /** Entities the diagnostic explicitly names. */
  entityKeys: readonly string[];
  /** Facts the diagnostic explicitly names. */
  factKeys: readonly string[];
}

export interface WorkspaceSets {
  evidence: EvidenceSet | null;
  entities: EntitySet | null;
  facts: FactSet | null;
  semantics: SemanticSet | null;
}

export interface WorkspaceIndex {
  documentId: number;

  evidenceByKey: ReadonlyMap<string, EngineeringEvidence>;
  entitiesByKey: ReadonlyMap<string, EngineeringEntity>;
  factsByKey: ReadonlyMap<string, EngineeringFact>;
  semanticsByKey: ReadonlyMap<string, SemanticStatement>;
  diagnosticsByKey: ReadonlyMap<string, WorkspaceDiagnostic>;

  /** From `entity.evidence[].evidence_key`. */
  evidenceKeysByEntity: ReadonlyMap<string, readonly string[]>;
  /** The same references, read the other way: which entities cite one. */
  entityKeysByEvidence: ReadonlyMap<string, readonly string[]>;
  /** From `fact.support[].evidence_key`. */
  factKeysByEvidence: ReadonlyMap<string, readonly string[]>;
  /** From `fact.subject_entity_key` and `fact.object_entity_key`. */
  factKeysByEntity: ReadonlyMap<string, readonly string[]>;
  /** From `statement.subject_entity_key` / `object_entity_key`. */
  semanticKeysByEntity: ReadonlyMap<string, readonly string[]>;
  /** From `statement.supporting_fact_keys`. */
  semanticKeysByFact: ReadonlyMap<string, readonly string[]>;
  /** From `evidence.provenance.page_number`. */
  evidenceKeysByPage: ReadonlyMap<number, readonly string[]>;

  /** Every page any artefact cites, ascending. */
  pages: readonly number[];
}

function push<K>(index: Map<K, string[]>, key: K, value: string): void {
  const existing = index.get(key);

  if (existing === undefined) {
    index.set(key, [value]);
    return;
  }

  if (!existing.includes(value)) {
    existing.push(value);
  }
}

/**
 * Builds the index.
 *
 * Deterministic: it preserves the order the backend returned artefacts
 * in and never sorts by a value it derived. Two runs over the same
 * responses produce the same index, which is what makes a Workspace
 * screenshot worth attaching to an engineering query.
 */
export function buildWorkspaceIndex(
  documentId: number,
  sets: WorkspaceSets,
): WorkspaceIndex {
  const evidenceByKey = new Map<string, EngineeringEvidence>();
  const entitiesByKey = new Map<string, EngineeringEntity>();
  const factsByKey = new Map<string, EngineeringFact>();
  const semanticsByKey = new Map<string, SemanticStatement>();
  const diagnosticsByKey = new Map<string, WorkspaceDiagnostic>();

  const evidenceKeysByEntity = new Map<string, string[]>();
  const entityKeysByEvidence = new Map<string, string[]>();
  const factKeysByEvidence = new Map<string, string[]>();
  const factKeysByEntity = new Map<string, string[]>();
  const semanticKeysByEntity = new Map<string, string[]>();
  const semanticKeysByFact = new Map<string, string[]>();
  const evidenceKeysByPage = new Map<number, string[]>();

  for (const evidence of sets.evidence?.evidence ?? []) {
    evidenceByKey.set(evidence.evidence_key, evidence);
    push(
      evidenceKeysByPage,
      evidence.provenance.page_number,
      evidence.evidence_key,
    );
  }

  for (const entity of sets.entities?.entities ?? []) {
    entitiesByKey.set(entity.entity_key, entity);

    // The entity's own declaration of what created it. Not a search of
    // the evidence set for observations that look like this entity.
    for (const reference of entity.evidence) {
      push(
        evidenceKeysByEntity,
        entity.entity_key,
        reference.evidence_key,
      );
      push(
        entityKeysByEvidence,
        reference.evidence_key,
        entity.entity_key,
      );
    }
  }

  for (const fact of sets.facts?.facts ?? []) {
    factsByKey.set(fact.fact_key, fact);
    push(factKeysByEntity, fact.subject_entity_key, fact.fact_key);
    push(factKeysByEntity, fact.object_entity_key, fact.fact_key);

    for (const support of fact.support) {
      push(factKeysByEvidence, support.evidence_key, fact.fact_key);
    }
  }

  for (const diagnostic of sets.facts?.diagnostics ?? []) {
    const key = factDiagnosticKey(diagnostic);

    diagnosticsByKey.set(key, {
      key,
      origin: "fact",
      reason: diagnostic.reason,
      explanation: FACT_AMBIGUITY_LABELS[diagnostic.reason],
      location: locationOfFactDiagnostic(documentId, diagnostic),
      entityKeys: [
        ...diagnostic.subject_entity_keys,
        ...diagnostic.object_entity_keys,
      ],
      factKeys: [],
    });
  }

  for (const statement of sets.semantics?.statements ?? []) {
    semanticsByKey.set(statement.statement_key, statement);
    push(
      semanticKeysByEntity,
      statement.subject_entity_key,
      statement.statement_key,
    );
    push(
      semanticKeysByEntity,
      statement.object_entity_key,
      statement.statement_key,
    );

    for (const factKey of statement.supporting_fact_keys) {
      push(semanticKeysByFact, factKey, statement.statement_key);
    }
  }

  for (const diagnostic of sets.semantics?.diagnostics ?? []) {
    const key = semanticDiagnosticKey(diagnostic);

    diagnosticsByKey.set(key, {
      key,
      origin: "semantic",
      reason: diagnostic.reason,
      explanation: SEMANTIC_AMBIGUITY_LABELS[diagnostic.reason],
      // A declined interpretation names a subject, not a line: which
      // line carried the meaning is what could not be decided.
      location: null,
      entityKeys: [diagnostic.subject_entity_key],
      factKeys: diagnostic.candidate_fact_keys,
    });
  }

  const pages = [...evidenceKeysByPage.keys()].sort(
    (left, right) => left - right,
  );

  return {
    documentId,
    evidenceByKey,
    entitiesByKey,
    factsByKey,
    semanticsByKey,
    diagnosticsByKey,
    evidenceKeysByEntity,
    entityKeysByEvidence,
    factKeysByEvidence,
    factKeysByEntity,
    semanticKeysByEntity,
    semanticKeysByFact,
    evidenceKeysByPage,
    pages,
  };
}

export const EMPTY_INDEX: WorkspaceIndex = buildWorkspaceIndex(0, {
  evidence: null,
  entities: null,
  facts: null,
  semantics: null,
});

// --- The support chain ---------------------------------------------------

/**
 * One link of a support chain, resolved or not.
 *
 * `artefact` is `null` when the reference names something this Workspace
 * did not load - a stage that has not run, a set that failed to read, or
 * a genuinely broken reference. The link stays in the chain either way:
 * an engineer must be able to see that a claim cites a fact that is not
 * there, which is precisely what silently dropping it would hide.
 */
export interface ChainLink<T> {
  key: string;
  artefact: T | null;
}

export interface SupportChain {
  statement: SemanticStatement | null;
  facts: readonly ChainLink<EngineeringFact>[];
  entities: readonly ChainLink<EngineeringEntity>[];
  evidence: readonly ChainLink<EngineeringEvidence>[];
  locations: readonly SourceLocation[];
  /** Every referenced key that resolved to nothing. */
  missing: readonly string[];
  /** True when any link in the chain is unresolved. */
  incomplete: boolean;
}

function link<T>(
  index: ReadonlyMap<string, T>,
  key: string,
): ChainLink<T> {
  return { key, artefact: index.get(key) ?? null };
}

/**
 * The whole chain behind one semantic statement:
 *
 * ```
 * statement -> supporting facts -> subject & object entities
 *           -> the evidence those entities and facts cite
 *           -> the canonical lines that evidence was read from
 * ```
 *
 * Every step follows a key the backend wrote. The traversal order is
 * fixed, so the same statement always produces the same chain.
 */
export function buildSupportChain(
  index: WorkspaceIndex,
  statementKey: string,
): SupportChain {
  const statement = index.semanticsByKey.get(statementKey) ?? null;

  if (statement === null) {
    return {
      statement: null,
      facts: [],
      entities: [],
      evidence: [],
      locations: [],
      missing: [statementKey],
      incomplete: true,
    };
  }

  const facts = statement.supporting_fact_keys.map((key) =>
    link(index.factsByKey, key),
  );

  // The statement's own two entities first - they are what it is about -
  // then any further entity its facts name.
  const entityKeys: string[] = [
    statement.subject_entity_key,
    statement.object_entity_key,
  ];

  for (const factLink of facts) {
    for (const key of [
      factLink.artefact?.subject_entity_key,
      factLink.artefact?.object_entity_key,
    ]) {
      if (key !== undefined && !entityKeys.includes(key)) {
        entityKeys.push(key);
      }
    }
  }

  const entities = entityKeys.map((key) => link(index.entitiesByKey, key));

  const evidenceKeys: string[] = [];

  for (const key of entityKeys) {
    for (const evidenceKey of index.evidenceKeysByEntity.get(key) ?? []) {
      if (!evidenceKeys.includes(evidenceKey)) {
        evidenceKeys.push(evidenceKey);
      }
    }
  }

  for (const factLink of facts) {
    for (const support of factLink.artefact?.support ?? []) {
      if (!evidenceKeys.includes(support.evidence_key)) {
        evidenceKeys.push(support.evidence_key);
      }
    }
  }

  const evidence = evidenceKeys.map((key) =>
    link(index.evidenceByKey, key),
  );

  const locations = evidence
    .map((evidenceLink) => evidenceLink.artefact)
    .filter((artefact): artefact is EngineeringEvidence => artefact !== null)
    .map((artefact) =>
      locationOfProvenance(index.documentId, artefact.provenance),
    );

  const missing = [...facts, ...entities, ...evidence]
    .filter((chainLink) => chainLink.artefact === null)
    .map((chainLink) => chainLink.key);

  return {
    statement,
    facts,
    entities,
    evidence,
    locations,
    missing,
    incomplete: missing.length > 0,
  };
}

// --- What a selection points at in the source ----------------------------

/**
 * The observations a selected artefact rests on, by explicit reference.
 *
 * Every branch follows a key the backend wrote: the entity's own
 * evidence list, the fact's own support, the statement's own chain. A
 * diagnostic resolves through the entities it names, which it names
 * itself.
 *
 * Order is the traversal order, and it is stable - the first key is what
 * the source viewer navigates to.
 */
export function evidenceKeysForSelection(
  index: WorkspaceIndex,
  kind: string,
  key: string,
): readonly string[] {
  if (kind === "evidence") {
    return index.evidenceByKey.has(key) ? [key] : [];
  }

  if (kind === "entity") {
    return index.evidenceKeysByEntity.get(key) ?? [];
  }

  if (kind === "fact") {
    const fact = index.factsByKey.get(key);

    return fact === undefined
      ? []
      : fact.support.map((support) => support.evidence_key);
  }

  if (kind === "semantic") {
    return buildSupportChain(index, key).evidence.map(
      (chainLink) => chainLink.key,
    );
  }

  if (kind === "diagnostic") {
    const diagnostic = index.diagnosticsByKey.get(key);

    if (diagnostic === undefined) {
      return [];
    }

    const keys: string[] = [];

    for (const entityKey of diagnostic.entityKeys) {
      for (const evidenceKey of index.evidenceKeysByEntity.get(entityKey) ??
        []) {
        if (!keys.includes(evidenceKey)) {
          keys.push(evidenceKey);
        }
      }
    }

    return keys;
  }

  return [];
}

/**
 * Where a selection is in the source.
 *
 * Full locations - the ones carrying spans, and therefore the only ones
 * a highlight can be drawn from - come from evidence provenance. A
 * diagnostic's own line is appended when it has one, so a declined
 * construction can still be navigated to even though it names no span.
 */
export function locationsForSelection(
  index: WorkspaceIndex,
  kind: string,
  key: string,
): readonly SourceLocation[] {
  const locations: SourceLocation[] = [];

  if (kind === "diagnostic") {
    const diagnostic = index.diagnosticsByKey.get(key);

    if (diagnostic?.location != null) {
      locations.push(diagnostic.location);
    }
  }

  for (const evidenceKey of evidenceKeysForSelection(index, kind, key)) {
    const evidence = index.evidenceByKey.get(evidenceKey);

    if (evidence !== undefined) {
      locations.push(
        locationOfProvenance(index.documentId, evidence.provenance),
      );
    }
  }

  return locations;
}

/**
 * The quantity a `HAS_RATED_POWER` statement is about.
 *
 * The figure is **not** on the statement: it lives on the object
 * entity, and a copy would be a second source of truth for a rated
 * value. This resolves the reference; it does not transcribe the value
 * into a model of its own.
 */
export function resolveStatementQuantity(
  index: WorkspaceIndex,
  statement: SemanticStatement,
): EngineeringEntity | null {
  return index.entitiesByKey.get(statement.object_entity_key) ?? null;
}
