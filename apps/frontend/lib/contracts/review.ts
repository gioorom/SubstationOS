/**
 * The Human Review contract, transcribed from `app/schemas/human_review.py`.
 *
 * **Every response here is a projection.** There is no field a client
 * could write to say which decision is current, and no `superseded` flag
 * on a stored record - both are computed by the backend from the review
 * history on every read. A frontend that derived either would be a second
 * account of the same fact.
 *
 * Nothing in this file carries a semantic statement, a fact, an entity or
 * a piece of evidence. A review names what it is about by key; what the
 * artefact *said* comes from the engineering contracts, which stay its
 * single account.
 */

export const REVIEW_DECISIONS = [
  "approved",
  "rejected",
  "needs_investigation",
] as const;

export type ReviewDecision = (typeof REVIEW_DECISIONS)[number];

/**
 * The engineer reviews the pipeline; the pipeline is not "right" or
 * "wrong". Nothing here reads `Corretto` or `Errato`, and a frontend test
 * asserts it.
 */
export const REVIEW_DECISION_LABELS: Record<ReviewDecision, string> = {
  approved: "Approvato",
  rejected: "Respinto",
  needs_investigation: "Da approfondire",
};

export const REVIEW_DECISION_DESCRIPTIONS: Record<ReviewDecision, string> =
  {
    approved:
      "Un ingegnere ha verificato questa interpretazione e la sostiene.",
    rejected:
      "Un ingegnere ha verificato questa interpretazione e non la sostiene.",
    needs_investigation:
      "Un ingegnere ha guardato e non ha ancora potuto decidere. Non è né un'approvazione parziale né un rifiuto.",
  };

export const REVIEW_REASONS = [
  "confirmed_by_source",
  "consistent_with_design",
  "incorrect_interpretation",
  "ambiguous_evidence",
  "insufficient_evidence",
  "pipeline_limitation",
  "engineering_exception",
  "documentation_issue",
  "other",
] as const;

export type ReviewReason = (typeof REVIEW_REASONS)[number];

export const REVIEW_REASON_LABELS: Record<ReviewReason, string> = {
  confirmed_by_source: "Confermato dal documento",
  consistent_with_design: "Coerente con il progetto",
  incorrect_interpretation: "Interpretazione errata",
  ambiguous_evidence: "Evidenza ambigua",
  insufficient_evidence: "Evidenza insufficiente",
  pipeline_limitation: "Limite della pipeline",
  engineering_exception: "Eccezione ingegneristica",
  documentation_issue: "Problema nella documentazione",
  other: "Altro",
};

/**
 * Whether a recorded judgement still describes today's pipeline.
 *
 * Computed by the backend from the review's snapshot and the document's
 * current interpretation. **A review is never discarded in any of these
 * states** - `requires_revalidation` marks it, and the record stays
 * readable with the identity it was passed under.
 */
export const REVIEW_APPLICABILITIES = [
  "applies",
  "requires_revalidation",
  "orphaned",
] as const;

export type ReviewApplicability =
  (typeof REVIEW_APPLICABILITIES)[number];

export const REVIEW_APPLICABILITY_LABELS: Record<
  ReviewApplicability,
  string
> = {
  applies: "Attuale",
  requires_revalidation: "Da riconvalidare",
  orphaned: "Senza interpretazione",
};

export const REVIEW_APPLICABILITY_DESCRIPTIONS: Record<
  ReviewApplicability,
  string
> = {
  applies:
    "L'affermazione recensita è nell'interpretazione attuale del documento, con la stessa identità che aveva al momento della revisione.",
  requires_revalidation:
    "Il documento è stato reinterpretato con byte o regole diverse. Il giudizio potrebbe valere ancora, e solo un ingegnere può dirlo: non viene mai riportato automaticamente su un'affermazione derivata in modo diverso.",
  orphaned:
    "Non esiste un'interpretazione con cui confrontare il giudizio: lo stage semantico non è stato eseguito da allora, oppure il suo insieme non c'è più.",
};

export const REVIEW_TARGET_TYPES = ["semantic_statement"] as const;

export type ReviewTargetType = (typeof REVIEW_TARGET_TYPES)[number];

// --- Requests ------------------------------------------------------------

/**
 * There is deliberately no reviewer field. The actor is the
 * authenticated identity, and there is no way for a client to name
 * somebody else.
 */
export interface RecordReviewRequest {
  decision: ReviewDecision;
  reason: ReviewReason;
  comment: string | null;
}

// --- Responses -----------------------------------------------------------

/** Who reviewed, as they were at the moment of reviewing. */
export interface Reviewer {
  user_id: number;
  display_name: string;
  email: string;
  role: string;
}

/**
 * The identity the reviewed artefact had, at review time.
 *
 * Identity only - which bytes, which rules, which policies. Not the
 * artefact.
 */
export interface ReviewSnapshot {
  content_checksum: string;
  semantic_rule_id: string;
  semantic_rule_version: string;
  semantic_contract_version: string;
  resolution_policy_version: string;
  fact_policy_version: string;
  semantic_policy_version: string;
  support_fingerprint: string;
  support_count: number;
}

export interface Review {
  review_id: number;
  target_type: ReviewTargetType;
  target_key: string;
  document_id: number;
  decision: ReviewDecision;
  reason: ReviewReason;
  comment: string | null;
  reviewer: Reviewer;
  snapshot: ReviewSnapshot;
  recorded_at: string;
  record_version: string;
}

/**
 * The effective decision for one statement.
 *
 * `current` is `null` for a statement nobody has reviewed - a distinct
 * state from every decision, and never rendered as one.
 */
export interface CurrentReview {
  target_type: ReviewTargetType;
  target_key: string;
  document_id: number;
  current: Review | null;
  review_count: number;
  applicability: ReviewApplicability;
  /** False only if a statement kept its key and changed its support. */
  snapshot_intact: boolean;
}

export interface ReviewHistoryEntry {
  review: Review;
  /** Derived from position in the newest-first history, never stored. */
  superseded: boolean;
  applicability: ReviewApplicability;
}

export interface ReviewHistoryResponse {
  items: ReviewHistoryEntry[];
  pagination: import("./pagination").PageMetadata;
}

export interface DocumentReviewSummaryResponse {
  document_id: number;
  /** Statements nobody reviewed are absent, not present with a null. */
  items: CurrentReview[];
}

export interface ReviewVocabulary {
  decisions: ReviewDecision[];
  reasons_by_decision: Record<ReviewDecision, ReviewReason[]>;
  decisions_requiring_comment: ReviewDecision[];
}
