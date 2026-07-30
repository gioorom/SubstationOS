"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { describeError, type ErrorCopy } from "@/lib/api";
import {
  PIPELINE_STAGE_DESCRIPTIONS,
  PIPELINE_STAGE_LABELS,
  PIPELINE_STAGES,
  type CanonicalRepresentationSummary,
  type CanonicalText,
  type EntitySet,
  type EvidenceSet,
  type FactSet,
  type IngestionJob,
  type PipelineStageId,
  type SemanticSet,
} from "@/lib/contracts";
import {
  buildCanonicalRepresentation,
  constructEngineeringFacts,
  extractEngineeringEvidence,
  interpretEngineeringSemantics,
  listIngestionJobs,
  readCanonicalRepresentation,
  readCanonicalText,
  readEntitySet,
  readEvidenceSet,
  readFactSet,
  readSemanticSet,
  resolveEngineeringEntities,
  segmentCanonicalText,
} from "@/lib/resources/pipeline";

import { useResource } from "./useResource";

/**
 * Everything the pipeline view knows about one document, read from the
 * seven stage endpoints in parallel.
 *
 * A `null` artefact means the stage has not run - the read returned 404,
 * which for a freshly uploaded document is the normal state and not a
 * failure.
 */
export interface PipelineSnapshot {
  ingestionJobs: IngestionJob[];
  representation: CanonicalRepresentationSummary | null;
  text: CanonicalText | null;
  evidence: EvidenceSet | null;
  entities: EntitySet | null;
  facts: FactSet | null;
  semantics: SemanticSet | null;
}

/**
 * - `blocked`   the stage before this one has not produced anything yet
 * - `ready`     runnable now, never run
 * - `running`   a run is in flight
 * - `produced`  ran and produced artefacts
 * - `empty`     ran successfully and found nothing - a valid answer
 * - `failed`    the last run reported a typed failure
 */
export type StageState =
  | "blocked"
  | "ready"
  | "running"
  | "produced"
  | "empty"
  | "failed";

export interface StageVersion {
  label: string;
  value: string;
}

export interface StageView {
  id: PipelineStageId;
  label: string;
  description: string;
  state: StageState;
  /** Artefacts produced, or `null` where the stage produces no count. */
  count: number | null;
  countLabel: string | null;
  /**
   * Only where the backend exposes one. The pipeline artefacts carry no
   * timestamp **by design** - excluding it is what lets two runs compare
   * equal and makes determinism assertable - so most stages report
   * `null` here and identify themselves by version and checksum instead.
   */
  timestamp: string | null;
  /** True when the last run re-used the artefact this source already had. */
  reused: boolean;
  /** Declined subjects or lines: an answer the rules refused to guess. */
  ambiguities: number | null;
  error: string | null;
  versions: StageVersion[];
  canRun: boolean;
  /** Whether an artefact exists to inspect. */
  inspectable: boolean;
}

interface RunOutcome {
  reused: boolean;
  error: string | null;
}

function label(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

async function loadSnapshot(
  documentId: number,
  signal: AbortSignal,
): Promise<PipelineSnapshot> {
  const [
    ingestionJobs,
    representation,
    text,
    evidence,
    entities,
    facts,
    semantics,
  ] = await Promise.all([
    listIngestionJobs(documentId, signal),
    readCanonicalRepresentation(documentId, signal),
    readCanonicalText(documentId, signal),
    readEvidenceSet(documentId, signal),
    readEntitySet(documentId, signal),
    readFactSet(documentId, signal),
    readSemanticSet(documentId, signal),
  ]);

  return {
    ingestionJobs,
    representation,
    text,
    evidence,
    entities,
    facts,
    semantics,
  };
}

/** The one place a stage is run. Each returns its own typed result. */
const RUNNERS: Record<
  Exclude<PipelineStageId, "uploaded">,
  (
    documentId: number,
    signal: AbortSignal,
  ) => Promise<{
    succeeded: boolean;
    reused: boolean;
    failure: { message: string } | null;
  }>
> = {
  canonical_representation: buildCanonicalRepresentation,
  canonical_text: segmentCanonicalText,
  engineering_evidence: extractEngineeringEvidence,
  engineering_entities: resolveEngineeringEntities,
  engineering_facts: constructEngineeringFacts,
  engineering_semantics: interpretEngineeringSemantics,
};

const PIPELINE_COPY: ErrorCopy = {
  network:
    "Impossibile leggere lo stato della pipeline: il backend non risponde.",
};

const RUN_COPY: ErrorCopy = {
  notFound: "Lo stage precedente non ha ancora prodotto artefatti.",
};

export function usePipeline(
  documentId: number | undefined,
  uploadedAt?: string,
) {
  const read = useCallback(
    (signal: AbortSignal) => loadSnapshot(documentId as number, signal),
    [documentId],
  );

  const resource = useResource<PipelineSnapshot>(read, {
    enabled: documentId !== undefined,
    copy: PIPELINE_COPY,
  });

  const [running, setRunning] = useState<PipelineStageId | null>(null);

  const [outcomes, setOutcomes] = useState<
    Partial<Record<PipelineStageId, RunOutcome>>
  >({});

  const { reload } = resource;
  const runController = useRef<AbortController | null>(null);

  useEffect(() => () => runController.current?.abort(), []);

  const runStage = useCallback(
    async (stage: Exclude<PipelineStageId, "uploaded">) => {
      if (documentId === undefined) {
        return;
      }

      runController.current?.abort();
      const controller = new AbortController();
      runController.current = controller;

      setRunning(stage);

      try {
        const result = await RUNNERS[stage](documentId, controller.signal);

        setOutcomes((current) => ({
          ...current,
          [stage]: {
            reused: result.reused,
            // A stage that ran and found nothing succeeded. Only a typed
            // failure is an error.
            error: result.succeeded
              ? null
              : (result.failure?.message ??
                "Lo stage ha riportato un errore non tipizzato."),
          },
        }));
      } catch (caught) {
        setOutcomes((current) => ({
          ...current,
          [stage]: {
            reused: false,
            error: describeError(caught, RUN_COPY),
          },
        }));
      } finally {
        if (!controller.signal.aborted) {
          setRunning(null);
          await reload();
        }
      }
    },
    [documentId, reload],
  );

  const stages = buildStages(
    resource.data,
    running,
    outcomes,
    uploadedAt,
  );

  return {
    snapshot: resource.data,
    stages,
    loading: resource.loading,
    refreshing: resource.refreshing,
    error: resource.error,
    reload: resource.reload,
    runStage,
    running,
  };
}

function buildStages(
  snapshot: PipelineSnapshot | null,
  running: PipelineStageId | null,
  outcomes: Partial<Record<PipelineStageId, RunOutcome>>,
  uploadedAt: string | undefined,
): StageView[] {
  const latestJob = snapshot?.ingestionJobs[0] ?? null;

  const produced: Record<PipelineStageId, number | null> = {
    uploaded: snapshot === null ? null : 1,
    canonical_representation:
      snapshot?.representation?.page_count ?? null,
    canonical_text: snapshot?.text?.token_count ?? null,
    engineering_evidence: snapshot?.evidence?.evidence_count ?? null,
    engineering_entities: snapshot?.entities?.entity_count ?? null,
    engineering_facts: snapshot?.facts?.fact_count ?? null,
    engineering_semantics: snapshot?.semantics?.statement_count ?? null,
  };

  const countLabels: Record<PipelineStageId, (n: number) => string> = {
    uploaded: () => "Archiviato",
    canonical_representation: (n) => label(n, "pagina", "pagine"),
    canonical_text: (n) => label(n, "token", "token"),
    engineering_evidence: (n) =>
      label(n, "osservazione", "osservazioni"),
    engineering_entities: (n) => label(n, "entità", "entità"),
    engineering_facts: (n) => label(n, "fatto", "fatti"),
    engineering_semantics: (n) =>
      label(n, "affermazione", "affermazioni"),
  };

  const versions: Record<PipelineStageId, StageVersion[]> = {
    uploaded: latestJob
      ? [
          { label: "Stato ingestione", value: latestJob.state },
          {
            label: "Versione pipeline",
            value: latestJob.pipeline_version,
          },
        ]
      : [],
    canonical_representation: snapshot?.representation
      ? [
          {
            label: "Rappresentazione",
            value: snapshot.representation.representation_version,
          },
          {
            label: "Parser",
            value: `${snapshot.representation.parser_name} ${snapshot.representation.parser_version}`,
          },
          {
            label: "Checksum",
            value: snapshot.representation.content_checksum,
          },
        ]
      : [],
    canonical_text: snapshot?.text
      ? [
          {
            label: "Segmentazione",
            value: snapshot.text.segmentation_version,
          },
          {
            label: "Rappresentazione",
            value: snapshot.text.representation_version,
          },
        ]
      : [],
    engineering_evidence: snapshot?.evidence
      ? [
          {
            label: "Policy di estrazione",
            value: snapshot.evidence.extraction_policy_version,
          },
          {
            label: "Segmentazione",
            value: snapshot.evidence.segmentation_version,
          },
        ]
      : [],
    engineering_entities: snapshot?.entities
      ? [
          {
            label: "Policy di risoluzione",
            value: snapshot.entities.resolution_policy_version,
          },
          {
            label: "Policy di estrazione",
            value: snapshot.entities.extraction_policy_version,
          },
        ]
      : [],
    engineering_facts: snapshot?.facts
      ? [
          {
            label: "Policy dei fatti",
            value: snapshot.facts.fact_policy_version,
          },
          {
            label: "Policy di risoluzione",
            value: snapshot.facts.resolution_policy_version,
          },
        ]
      : [],
    engineering_semantics: snapshot?.semantics
      ? [
          {
            label: "Policy semantica",
            value: snapshot.semantics.semantic_policy_version,
          },
          {
            label: "Policy dei fatti",
            value: snapshot.semantics.fact_policy_version,
          },
        ]
      : [],
  };

  const ambiguities: Record<PipelineStageId, number | null> = {
    uploaded: null,
    canonical_representation: null,
    canonical_text: null,
    engineering_evidence: null,
    engineering_entities: null,
    engineering_facts: snapshot?.facts?.diagnostics.length ?? null,
    engineering_semantics:
      snapshot?.semantics?.diagnostics.length ?? null,
  };

  // Only the two stages the backend timestamps report one. The rest
  // deliberately carry none; see StageView.timestamp.
  const timestamps: Record<PipelineStageId, string | null> = {
    uploaded: uploadedAt ?? latestJob?.created_at ?? null,
    canonical_representation: null,
    canonical_text: null,
    engineering_evidence: null,
    engineering_entities: null,
    engineering_facts: null,
    engineering_semantics: null,
  };

  let previousProduced = true;

  return PIPELINE_STAGES.map((id) => {
    const count = produced[id];
    const hasArtefact = count !== null;
    const outcome = outcomes[id];

    let state: StageState;

    if (running === id) {
      state = "running";
    } else if (outcome?.error) {
      state = "failed";
    } else if (hasArtefact) {
      state = count === 0 ? "empty" : "produced";
    } else if (previousProduced) {
      state = "ready";
    } else {
      state = "blocked";
    }

    const view: StageView = {
      id,
      label: PIPELINE_STAGE_LABELS[id],
      description: PIPELINE_STAGE_DESCRIPTIONS[id],
      state,
      count,
      countLabel: hasArtefact ? countLabels[id](count) : null,
      timestamp: timestamps[id],
      reused: outcome?.reused ?? false,
      ambiguities: ambiguities[id],
      error: outcome?.error ?? null,
      versions: versions[id],
      canRun:
        id !== "uploaded" &&
        running === null &&
        (previousProduced || hasArtefact),
      // Diagnostics are artefacts too. A stage that constructed nothing
      // because every candidate was ambiguous has the most to explain,
      // and hiding its inspector would hide exactly that.
      inspectable:
        hasArtefact && (count > 0 || (ambiguities[id] ?? 0) > 0),
    };

    // A stage unlocks the next one when it produced something. An empty
    // evidence set is a valid answer but leaves nothing to resolve, so
    // the stage below it stays blocked rather than being offered a run
    // that can only fail.
    previousProduced = hasArtefact && count > 0;

    return view;
  });
}
