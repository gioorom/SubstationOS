"use client";

/**
 * Everything the Engineering Workspace reads about one document.
 *
 * Five stage endpoints, read in parallel and settled **independently**.
 * That is the difference between this hook and `usePipeline`: the
 * pipeline view asks whether the pipeline ran, so an all-or-nothing read
 * is honest there. The Workspace asks what an engineer can inspect, and
 * a semantic endpoint that fails is no reason to stop showing evidence
 * that loaded perfectly well.
 *
 * Each stage therefore carries its own `StageStatus`, distinguishing the
 * four answers a stage can give - not run, ran and found nothing, ran
 * and produced artefacts, could not be read - which the UI never merges.
 *
 * The canonical text segmentation is deliberately **not** read here.
 * Every observation already carries its own canonical line in
 * `provenance.source_text`, so the excerpt an engineer needs is in the
 * evidence set; pulling every token of every page to re-derive the same
 * string would be a large transfer for no additional fact.
 */

import { useCallback, useMemo } from "react";

import { describeError, type ErrorCopy } from "@/lib/api";
import type {
  CanonicalRepresentationSummary,
  EntitySet,
  EvidenceSet,
  FactSet,
  SemanticSet,
} from "@/lib/contracts";
import {
  readCanonicalRepresentation,
  readEntitySet,
  readEvidenceSet,
  readFactSet,
  readSemanticSet,
} from "@/lib/resources/pipeline";
import {
  buildWorkspaceIndex,
  EMPTY_INDEX,
  type StageStatus,
  type WorkspaceIndex,
} from "@/lib/workspace";

import { useResource } from "./useResource";

export interface WorkspaceStage<T> {
  data: T | null;
  status: StageStatus;
}

export interface WorkspaceSnapshot {
  representation: WorkspaceStage<CanonicalRepresentationSummary>;
  evidence: WorkspaceStage<EvidenceSet>;
  entities: WorkspaceStage<EntitySet>;
  facts: WorkspaceStage<FactSet>;
  semantics: WorkspaceStage<SemanticSet>;
}

const WORKSPACE_COPY: ErrorCopy = {
  network:
    "Impossibile leggere gli artefatti del documento: il backend non risponde.",
};

/**
 * Turns one settled read into a stage.
 *
 * `null` from a fulfilled read means the stage has not run - the
 * resource layer already translated that 404. A rejection means the read
 * itself failed, and what the stage holds stays unknown.
 */
function stageOf<T>(
  settled: PromiseSettledResult<T | null>,
  count: (value: T) => number,
): WorkspaceStage<T> {
  if (settled.status === "rejected") {
    return {
      data: null,
      status: {
        availability: "failed",
        error:
          describeError(settled.reason, WORKSPACE_COPY) ??
          "Lettura non riuscita.",
        count: null,
      },
    };
  }

  const value = settled.value;

  if (value === null) {
    return {
      data: null,
      status: { availability: "unrun", error: null, count: null },
    };
  }

  const total = count(value);

  return {
    data: value,
    status: {
      availability: total === 0 ? "empty" : "available",
      error: null,
      count: total,
    },
  };
}

async function loadWorkspace(
  documentId: number,
  signal: AbortSignal,
): Promise<WorkspaceSnapshot> {
  const [representation, evidence, entities, facts, semantics] =
    await Promise.allSettled([
      readCanonicalRepresentation(documentId, signal),
      readEvidenceSet(documentId, signal),
      readEntitySet(documentId, signal),
      readFactSet(documentId, signal),
      readSemanticSet(documentId, signal),
    ]);

  return {
    representation: stageOf(representation, (value) => value.page_count),
    evidence: stageOf(evidence, (value) => value.evidence.length),
    entities: stageOf(entities, (value) => value.entities.length),
    // Facts and statements are counted, diagnostics are not. A set that
    // declined everything it saw *is* empty of facts, and saying so is
    // the honest reading - the declines are not hidden, they are the
    // Diagnostiche tab's own content and carry their own count.
    facts: stageOf(facts, (value) => value.facts.length),
    semantics: stageOf(semantics, (value) => value.statements.length),
  };
}

export interface WorkspaceState {
  snapshot: WorkspaceSnapshot | null;
  index: WorkspaceIndex;
  /** Entity key -> the label the backend resolved for it. */
  entityLabels: ReadonlyMap<string, string>;
  loading: boolean;
  refreshing: boolean;
  /** Only a failure of the read as a whole - never one stage's. */
  error: string | null;
  reload: () => Promise<void>;
}

export function useWorkspace(
  documentId: number | undefined,
): WorkspaceState {
  const read = useCallback(
    (signal: AbortSignal) => loadWorkspace(documentId as number, signal),
    [documentId],
  );

  const resource = useResource<WorkspaceSnapshot>(read, {
    enabled: documentId !== undefined,
    copy: WORKSPACE_COPY,
  });

  const snapshot = resource.data;

  const index = useMemo(() => {
    if (documentId === undefined || snapshot === null) {
      return EMPTY_INDEX;
    }

    return buildWorkspaceIndex(documentId, {
      evidence: snapshot.evidence.data,
      entities: snapshot.entities.data,
      facts: snapshot.facts.data,
      semantics: snapshot.semantics.data,
    });
  }, [documentId, snapshot]);

  const entityLabels = useMemo(() => {
    const labels = new Map<string, string>();

    for (const entity of index.entitiesByKey.values()) {
      labels.set(entity.entity_key, entity.label);
    }

    return labels;
  }, [index]);

  return {
    snapshot,
    index,
    entityLabels,
    loading: resource.loading,
    refreshing: resource.refreshing,
    error: resource.error,
    reload: resource.reload,
  };
}
