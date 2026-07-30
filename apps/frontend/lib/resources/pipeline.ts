/**
 * The deterministic engineering pipeline, stage by stage.
 *
 * Each stage has the same two operations - run it, and read what it
 * produced - and the backend answers them the same way everywhere:
 *
 * - `POST` returns **201** when the stage produced a new artefact and
 *   **200** when it re-used the one this source already had. The result
 *   body says which through `reused`, so the client never inspects the
 *   status code to find out.
 * - `POST` returns **404** when the *previous* stage has not run. That is
 *   an ordering rule, not a missing document.
 * - A stage that runs and finds nothing is a **success** with
 *   `found_* === false`. It is not an error and must never be shown as
 *   one.
 * - `GET` returns **404** until the stage has run at least once.
 *
 * `readOptional*` turns that last 404 into `null`, because "this stage
 * has not run yet" is the normal state of a freshly uploaded document
 * and rendering it as a failure would be wrong.
 */

import { apiClient, NotFoundError } from "@/lib/api";
import { PIPELINE_TIMEOUT_MS } from "@/lib/api/client";
import type {
  CanonicalizationResult,
  CanonicalPdfPage,
  CanonicalRepresentationSummary,
  CanonicalText,
  CanonicalTextSummary,
  EngineeringFact,
  EntityResolutionResult,
  EntitySet,
  EvidenceExtractionResult,
  EvidenceSet,
  FactConstructionResult,
  FactSet,
  IngestionJob,
  SegmentationResult,
  SemanticInterpretationResult,
  SemanticSet,
} from "@/lib/contracts";

async function optional<T>(read: Promise<T>): Promise<T | null> {
  try {
    return await read;
  } catch (error) {
    if (error instanceof NotFoundError) {
      return null;
    }

    throw error;
  }
}

const runOptions = (signal?: AbortSignal) => ({
  signal,
  timeoutMs: PIPELINE_TIMEOUT_MS,
});

const readOptions = (signal?: AbortSignal) => ({ signal, retries: 1 });

// --- Ingestion -----------------------------------------------------------

export function listIngestionJobs(
  documentId: number,
  signal?: AbortSignal,
): Promise<IngestionJob[]> {
  return apiClient.get<IngestionJob[]>(
    `/documents/${documentId}/ingestion/jobs`,
    readOptions(signal),
  );
}

export function ingestDocument(
  documentId: number,
  signal?: AbortSignal,
): Promise<IngestionJob> {
  return apiClient.post<IngestionJob>("/documents/ingestion/jobs", {
    json: { document_id: documentId },
    ...runOptions(signal),
  });
}

export function retryIngestionJob(
  jobId: number,
  signal?: AbortSignal,
): Promise<IngestionJob> {
  return apiClient.post<IngestionJob>(
    `/documents/ingestion/jobs/${jobId}/retry`,
    runOptions(signal),
  );
}

// --- Canonical PDF representation ----------------------------------------

export function buildCanonicalRepresentation(
  documentId: number,
  signal?: AbortSignal,
): Promise<CanonicalizationResult> {
  return apiClient.post<CanonicalizationResult>(
    `/documents/${documentId}/canonical-representation`,
    runOptions(signal),
  );
}

export function readCanonicalRepresentation(
  documentId: number,
  signal?: AbortSignal,
): Promise<CanonicalRepresentationSummary | null> {
  return optional(
    apiClient.get<CanonicalRepresentationSummary>(
      `/documents/${documentId}/canonical-representation`,
      readOptions(signal),
    ),
  );
}

/**
 * One page of the representation.
 *
 * The Workspace's canonical page map renders the page currently on
 * screen and no other. Reading the whole representation to display one
 * page of a drawing set would transfer every span of every page to use
 * the spans of one.
 */
export function readCanonicalPage(
  documentId: number,
  pageNumber: number,
  signal?: AbortSignal,
): Promise<CanonicalPdfPage | null> {
  return optional(
    apiClient.get<CanonicalPdfPage>(
      `/documents/${documentId}/canonical-representation/pages/${pageNumber}`,
      readOptions(signal),
    ),
  );
}

// --- Canonical text segmentation -----------------------------------------

export function segmentCanonicalText(
  documentId: number,
  signal?: AbortSignal,
): Promise<SegmentationResult> {
  return apiClient.post<SegmentationResult>(
    `/documents/${documentId}/canonical-text`,
    runOptions(signal),
  );
}

export function readCanonicalText(
  documentId: number,
  signal?: AbortSignal,
): Promise<CanonicalText | null> {
  return optional(
    apiClient.get<CanonicalText>(
      `/documents/${documentId}/canonical-text`,
      readOptions(signal),
    ),
  );
}

export function readCanonicalTextSummary(
  documentId: number,
  signal?: AbortSignal,
): Promise<CanonicalTextSummary | null> {
  return readCanonicalText(documentId, signal);
}

// --- Engineering evidence ------------------------------------------------

export function extractEngineeringEvidence(
  documentId: number,
  signal?: AbortSignal,
): Promise<EvidenceExtractionResult> {
  return apiClient.post<EvidenceExtractionResult>(
    `/documents/${documentId}/engineering-evidence`,
    runOptions(signal),
  );
}

export function readEvidenceSet(
  documentId: number,
  signal?: AbortSignal,
): Promise<EvidenceSet | null> {
  return optional(
    apiClient.get<EvidenceSet>(
      `/documents/${documentId}/engineering-evidence`,
      readOptions(signal),
    ),
  );
}

// --- Engineering entities ------------------------------------------------

export function resolveEngineeringEntities(
  documentId: number,
  signal?: AbortSignal,
): Promise<EntityResolutionResult> {
  return apiClient.post<EntityResolutionResult>(
    `/documents/${documentId}/engineering-entities`,
    runOptions(signal),
  );
}

export function readEntitySet(
  documentId: number,
  signal?: AbortSignal,
): Promise<EntitySet | null> {
  return optional(
    apiClient.get<EntitySet>(
      `/documents/${documentId}/engineering-entities`,
      readOptions(signal),
    ),
  );
}

// --- Engineering facts ---------------------------------------------------

export function constructEngineeringFacts(
  documentId: number,
  signal?: AbortSignal,
): Promise<FactConstructionResult> {
  return apiClient.post<FactConstructionResult>(
    `/documents/${documentId}/engineering-facts`,
    runOptions(signal),
  );
}

export function readFactSet(
  documentId: number,
  signal?: AbortSignal,
): Promise<FactSet | null> {
  return optional(
    apiClient.get<FactSet>(
      `/documents/${documentId}/engineering-facts`,
      readOptions(signal),
    ),
  );
}

/** The support chain: which evidence put a fact's two entities together. */
export function readFactSupport(
  documentId: number,
  factKey: string,
  signal?: AbortSignal,
): Promise<EngineeringFact["support"]> {
  return apiClient.get<EngineeringFact["support"]>(
    `/documents/${documentId}/engineering-facts/${encodeURIComponent(
      factKey,
    )}/support`,
    readOptions(signal),
  );
}

// --- Engineering semantics -----------------------------------------------

export function interpretEngineeringSemantics(
  documentId: number,
  signal?: AbortSignal,
): Promise<SemanticInterpretationResult> {
  return apiClient.post<SemanticInterpretationResult>(
    `/documents/${documentId}/engineering-semantics`,
    runOptions(signal),
  );
}

export function readSemanticSet(
  documentId: number,
  signal?: AbortSignal,
): Promise<SemanticSet | null> {
  return optional(
    apiClient.get<SemanticSet>(
      `/documents/${documentId}/engineering-semantics`,
      readOptions(signal),
    ),
  );
}

/** The facts a statement cites - meaning, traced back to observation. */
export function readStatementFacts(
  documentId: number,
  statementKey: string,
  signal?: AbortSignal,
): Promise<EngineeringFact[]> {
  return apiClient.get<EngineeringFact[]>(
    `/documents/${documentId}/engineering-semantics/${encodeURIComponent(
      statementKey,
    )}/facts`,
    readOptions(signal),
  );
}
