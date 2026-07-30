/**
 * The deterministic engineering pipeline contract, transcribed from the
 * backend.
 *
 * Source of truth, stage by stage:
 * - `app/schemas/document_ingestion.py` (Milestone 25.1 / 25.2)
 * - `app/schemas/canonical_pdf.py`      (Milestone 26.1)
 * - `app/schemas/canonical_text.py`     (Milestone 27.1)
 * - `app/schemas/engineering_evidence.py`  (Milestone 28.1)
 * - `app/schemas/engineering_entities.py`  (Milestone 29.1)
 * - `app/schemas/engineering_facts.py`     (Milestone 29.2)
 * - `app/schemas/engineering_semantics.py` (Milestone 30.1)
 *
 * The frontend knows these payloads and nothing beneath them: no
 * repository, no parser, no rule implementation. Every stage answers the
 * same four questions - did it run, was an existing artefact re-used, did
 * it produce anything, and if it failed, which typed code says why.
 */

// --- Ingestion -----------------------------------------------------------

export const INGESTION_STATES = [
  "uploaded",
  "queued",
  "processing",
  "processed",
  "failed",
] as const;

export type IngestionState = (typeof INGESTION_STATES)[number];

export const INGESTION_OUTCOMES = [
  "ready_for_extraction",
  "failed",
] as const;

export type IngestionOutcome = (typeof INGESTION_OUTCOMES)[number];

export const INGESTION_FAILURE_CODES = [
  "document_not_found",
  "unsupported_format",
  "invalid_lifecycle_transition",
  "duplicate_ingestion_request",
  "pipeline_execution_failure",
  "content_not_found",
  "content_inaccessible",
  "empty_content",
  "checksum_failure",
  "unknown_format",
  "conflicting_format_evidence",
  "invalid_stored_metadata",
] as const;

export type IngestionFailureCode =
  (typeof INGESTION_FAILURE_CODES)[number];

export interface StageFailure<Code extends string> {
  code: Code;
  message: string;
  detail: string | null;
}

export interface DocumentContentIdentity {
  storage_reference: string;
  checksum_algorithm: string;
  checksum: string;
  size_bytes: number;
}

export interface DocumentFormatVerdict {
  detected_format: string;
  decided_by: string;
  stored_format: string;
  disagreeing_evidence: string[];
  matches_stored_format: boolean;
}

export interface IngestedDocumentSnapshot {
  document_id: number;
  project_id: number | null;
  title: string;
  document_format: string;
  document_category: string;
  revision: string;
  scope: string | null;
  content?: DocumentContentIdentity | null;
  format?: DocumentFormatVerdict | null;
}

export interface IngestionJob {
  id: number | null;
  project_id: number | null;
  document_id: number;
  state: IngestionState;
  outcome: IngestionOutcome | null;
  pipeline_version: string;
  attempt_count: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  failure: StageFailure<IngestionFailureCode> | null;
  document: IngestedDocumentSnapshot | null;
  ready_for_extraction: boolean;
}

// --- Canonical PDF representation (26.1) ---------------------------------

export const CANONICALIZATION_FAILURE_CODES = [
  "document_not_found",
  "unsupported_format",
  "content_not_found",
  "content_inaccessible",
  "empty_content",
  "not_ready_for_extraction",
  "encrypted_document",
  "corrupted_document",
  "parser_failure",
  "empty_document",
  "no_extractable_text",
  "representation_persistence_failure",
] as const;

export type CanonicalizationFailureCode =
  (typeof CANONICALIZATION_FAILURE_CODES)[number];

export interface CanonicalRepresentationSummary {
  document_id: number;
  content_checksum: string;
  checksum_algorithm: string;
  representation_version: string;
  parser_name: string;
  parser_version: string;
  page_count: number;
}

export interface CanonicalizationResult {
  succeeded: boolean;
  reused: boolean;
  representation: CanonicalRepresentationSummary | null;
  failure: StageFailure<CanonicalizationFailureCode> | null;
}

/**
 * PDF user-space points, origin top-left - the parser's own convention,
 * unconverted. These are the **only** coordinates in this application:
 * nothing here is measured, estimated or laid out by the frontend.
 */
export interface BoundingBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface TextStyle {
  font_family: string;
  font_size: number;
  bold: boolean;
  italic: boolean;
}

/**
 * One span of a canonical page.
 *
 * `reading_order` is the key an evidence observation cites: a
 * `SpanReference` names a span by this number, within the block named by
 * `EvidenceProvenance.block_reading_order`, on the page named by
 * `EvidenceProvenance.page_number`. That triple is an explicit backend
 * identity, which is why an observation can be located on the page
 * without comparing any text.
 */
export interface CanonicalPdfSpan {
  reading_order: number;
  line_index: number;
  text: string;
  bounding_box: BoundingBox;
  style: TextStyle;
}

export const CANONICAL_BLOCK_KINDS = ["text", "image"] as const;

export type CanonicalBlockKind = (typeof CANONICAL_BLOCK_KINDS)[number];

export interface CanonicalPdfBlock {
  reading_order: number;
  kind: CanonicalBlockKind;
  bounding_box: BoundingBox;
  spans: CanonicalPdfSpan[];
}

/** `GET /documents/{id}/canonical-representation/pages/{page_number}`. */
export interface CanonicalPdfPage {
  page_number: number;
  width: number;
  height: number;
  blocks: CanonicalPdfBlock[];
}

// --- Canonical text segmentation (27.1) ----------------------------------

export const SEGMENTATION_FAILURE_CODES = [
  "canonical_representation_missing",
  "invalid_canonical_representation",
  "unsupported_representation_version",
  "segmentation_failure",
  "representation_persistence_failure",
] as const;

export type SegmentationFailureCode =
  (typeof SEGMENTATION_FAILURE_CODES)[number];

export interface CanonicalTextSummary {
  document_id: number;
  content_checksum: string;
  representation_version: string;
  segmentation_version: string;
  section_count: number;
  token_count: number;
}

export interface SegmentationResult {
  succeeded: boolean;
  reused: boolean;
  segmentation: CanonicalTextSummary | null;
  failure: StageFailure<SegmentationFailureCode> | null;
}

export interface SpanProvenance {
  page_number: number;
  block_reading_order: number;
  span_reading_order: number;
  line_index: number;
  character_start: number;
  character_end: number;
}

export interface CanonicalTextToken {
  position: number;
  text: string;
  normalized_text: string;
  provenance: SpanProvenance;
}

export interface CanonicalTextLine {
  line_index: number;
  tokens: CanonicalTextToken[];
}

export interface CanonicalTextParagraph {
  paragraph_index: number;
  page_number: number;
  block_reading_order: number;
  lines: CanonicalTextLine[];
}

export interface CanonicalTextSection {
  section_index: number;
  page_number: number;
  paragraphs: CanonicalTextParagraph[];
}

export interface CanonicalText extends CanonicalTextSummary {
  sections: CanonicalTextSection[];
}

// --- Engineering evidence (28.1) -----------------------------------------

export const EVIDENCE_TYPES = [
  "designation",
  "voltage_value",
  "current_value",
  "power_value",
  "cable_section_value",
] as const;

export type EvidenceType = (typeof EVIDENCE_TYPES)[number];

export const EVIDENCE_TYPE_LABELS: Record<EvidenceType, string> = {
  designation: "Sigla",
  voltage_value: "Tensione",
  current_value: "Corrente",
  power_value: "Potenza",
  cable_section_value: "Sezione cavo",
};

export const EVIDENCE_STATUSES = [
  "observed",
  "ambiguous",
  "rejected",
] as const;

export type EvidenceStatus = (typeof EVIDENCE_STATUSES)[number];

export const EVIDENCE_FAILURE_CODES = [
  "canonical_text_missing",
  "unsupported_canonical_text_version",
  "invalid_provenance",
  "invalid_extraction_rule",
  "rule_execution_failure",
  "invalid_engineering_quantity",
  "unsupported_unit",
  "evidence_validation_failure",
  "evidence_persistence_failure",
  "inconsistent_source_identity",
] as const;

export type EvidenceFailureCode = (typeof EVIDENCE_FAILURE_CODES)[number];

/**
 * `value` and `base_value` are **strings** on the wire, not numbers: the
 * backend serialises `Decimal` as JSON strings so a rated voltage cannot
 * acquire a rounding error on its way here. They are never parsed into a
 * JS number for display.
 */
export interface EngineeringQuantity {
  value: string;
  unit: string;
  base_value: string | null;
  base_unit: string | null;
}

export interface DesignationValue {
  normalized: string;
}

export interface SpanReference {
  span_reading_order: number;
  character_start: number;
  character_end: number;
}

export interface EvidenceProvenance {
  page_number: number;
  section_index: number;
  paragraph_index: number;
  block_reading_order: number;
  line_index: number;
  token_start: number;
  token_end: number;
  spans: SpanReference[];
  source_text: string;
}

export interface EngineeringEvidence {
  evidence_key: string;
  evidence_type: EvidenceType;
  status: EvidenceStatus;
  observed_text: string;
  rule_id: string;
  rule_version: string;
  quantity: EngineeringQuantity | null;
  designation: DesignationValue | null;
  provenance: EvidenceProvenance;
}

export interface EvidenceSetSummary {
  document_id: number;
  project_id: number | null;
  content_checksum: string;
  segmentation_version: string;
  extraction_policy_version: string;
  evidence_count: number;
}

export interface EvidenceSet extends EvidenceSetSummary {
  evidence: EngineeringEvidence[];
}

export interface EvidenceExtractionResult {
  succeeded: boolean;
  reused: boolean;
  found_evidence: boolean;
  rejected_count: number;
  evidence_set: EvidenceSetSummary | null;
  failure: StageFailure<EvidenceFailureCode> | null;
}

// --- Engineering entities (29.1) -----------------------------------------

export const ENTITY_TYPES = [
  "equipment_designation",
  "engineering_quantity",
] as const;

export type EngineeringEntityType = (typeof ENTITY_TYPES)[number];

export const ENTITY_TYPE_LABELS: Record<EngineeringEntityType, string> = {
  equipment_designation: "Sigla apparecchiatura",
  engineering_quantity: "Grandezza",
};

export const ENTITY_STATUSES = ["resolved", "ambiguous"] as const;

export type EntityStatus = (typeof ENTITY_STATUSES)[number];

export const ENTITY_RESOLUTION_FAILURE_CODES = [
  "evidence_set_missing",
  "unsupported_extraction_policy_version",
  "invalid_resolution_rule",
  "resolution_failure",
  "entity_validation_failure",
  "entity_persistence_failure",
  "inconsistent_source_identity",
] as const;

export type EntityResolutionFailureCode =
  (typeof ENTITY_RESOLUTION_FAILURE_CODES)[number];

export interface EvidenceReference {
  evidence_key: string;
  evidence_type: EvidenceType;
  observed_text: string;
  page_number: number;
  paragraph_index: number;
  line_index: number;
  token_start: number;
  token_end: number;
}

export interface EngineeringEntity {
  entity_key: string;
  entity_type: EngineeringEntityType;
  status: EntityStatus;
  entity_version: string;
  resolution_rule_id: string;
  resolution_rule_version: string;
  label: string;
  evidence_count: number;
  designation: DesignationValue | null;
  quantity: EngineeringQuantity | null;
  evidence: EvidenceReference[];
}

export interface EntitySetSummary {
  document_id: number;
  project_id: number | null;
  content_checksum: string;
  extraction_policy_version: string;
  resolution_policy_version: string;
  entity_count: number;
}

export interface EntitySet extends EntitySetSummary {
  entities: EngineeringEntity[];
}

export interface EntityResolutionResult {
  succeeded: boolean;
  reused: boolean;
  found_entities: boolean;
  entity_set: EntitySetSummary | null;
  failure: StageFailure<EntityResolutionFailureCode> | null;
}

// --- Engineering facts (29.2) --------------------------------------------

/**
 * One member, and it means what it says: two entities appeared together
 * under a declared structural rule. It is **not** a rated property.
 */
export const FACT_PREDICATES = ["has_associated_quantity"] as const;

export type FactPredicate = (typeof FACT_PREDICATES)[number];

export const FACT_PREDICATE_LABELS: Record<FactPredicate, string> = {
  has_associated_quantity: "grandezza associata",
};

export const FACT_STATUSES = ["constructed", "ambiguous"] as const;

export type FactStatus = (typeof FACT_STATUSES)[number];

export const SUPPORT_ROLES = ["subject", "object"] as const;

export type SupportRole = (typeof SUPPORT_ROLES)[number];

export const FACT_AMBIGUITY_REASONS = ["multiple_subjects"] as const;

export type FactAmbiguityReason =
  (typeof FACT_AMBIGUITY_REASONS)[number];

export const FACT_AMBIGUITY_LABELS: Record<FactAmbiguityReason, string> = {
  multiple_subjects:
    "La riga contiene più sigle: non dice a quale apparecchiatura appartiene la grandezza.",
};

export const FACT_CONSTRUCTION_FAILURE_CODES = [
  "entity_set_missing",
  "entity_evidence_missing",
  "inconsistent_source_identity",
  "unsupported_entity_set_version",
  "invalid_construction_rule",
  "rule_execution_failure",
  "invalid_fact_support",
  "fact_validation_failure",
  "fact_persistence_failure",
  "inconsistent_pipeline_state",
] as const;

export type FactConstructionFailureCode =
  (typeof FACT_CONSTRUCTION_FAILURE_CODES)[number];

export interface FactSupport {
  evidence_key: string;
  role: SupportRole;
  evidence_type: EvidenceType;
  observed_text: string;
  page_number: number;
  paragraph_index: number;
  line_index: number;
  token_start: number;
  token_end: number;
}

export interface EngineeringFact {
  fact_key: string;
  subject_entity_key: string;
  predicate: FactPredicate;
  object_entity_key: string;
  status: FactStatus;
  fact_version: string;
  construction_rule_id: string;
  construction_rule_version: string;
  support: FactSupport[];
}

export interface FactDiagnostic {
  reason: FactAmbiguityReason;
  page_number: number;
  paragraph_index: number;
  line_index: number;
  subject_entity_keys: string[];
  object_entity_keys: string[];
}

export interface FactSetSummary {
  document_id: number;
  project_id: number | null;
  content_checksum: string;
  resolution_policy_version: string;
  fact_policy_version: string;
  fact_count: number;
  has_ambiguities: boolean;
}

export interface FactSet extends FactSetSummary {
  facts: EngineeringFact[];
  diagnostics: FactDiagnostic[];
}

export interface FactConstructionResult {
  succeeded: boolean;
  reused: boolean;
  found_facts: boolean;
  has_ambiguities: boolean;
  fact_set: FactSetSummary | null;
  failure: StageFailure<FactConstructionFailureCode> | null;
}

// --- Engineering semantics (30.1) ----------------------------------------

/**
 * One statement type, from one catalogued rule. Voltage, current and
 * cable section are deliberately uninterpreted - an associated voltage
 * may be rated, test, insulation or busbar voltage, and the association
 * does not say which.
 */
export const SEMANTIC_STATEMENT_TYPES = ["has_rated_power"] as const;

export type SemanticStatementType =
  (typeof SEMANTIC_STATEMENT_TYPES)[number];

export const SEMANTIC_STATEMENT_LABELS: Record<
  SemanticStatementType,
  string
> = {
  has_rated_power: "ha potenza nominale",
};

export const SEMANTIC_STATEMENT_STATUSES = [
  "interpreted",
  "ambiguous",
] as const;

export type SemanticStatementStatus =
  (typeof SEMANTIC_STATEMENT_STATUSES)[number];

export const SEMANTIC_AMBIGUITY_REASONS = [
  "multiple_candidate_quantities",
] as const;

export type SemanticAmbiguityReason =
  (typeof SEMANTIC_AMBIGUITY_REASONS)[number];

export const SEMANTIC_AMBIGUITY_LABELS: Record<
  SemanticAmbiguityReason,
  string
> = {
  multiple_candidate_quantities:
    "Più potenze associate alla stessa sigla: quale sia la nominale non è deducibile.",
};

export const SEMANTIC_FAILURE_CODES = [
  "fact_set_missing",
  "unsupported_semantic_rule",
  "unsupported_fact_version",
  "invalid_support",
  "ambiguous_semantic_mapping",
  "semantic_validation_failure",
  "semantic_persistence_failure",
  "inconsistent_source_identity",
] as const;

export type SemanticFailureCode = (typeof SEMANTIC_FAILURE_CODES)[number];

/** Carries no value and no unit: the figure lives on the quantity entity. */
export interface SemanticStatement {
  statement_key: string;
  statement_type: SemanticStatementType;
  subject_entity_key: string;
  object_entity_key: string;
  status: SemanticStatementStatus;
  semantic_contract_version: string;
  semantic_rule_id: string;
  semantic_rule_version: string;
  supporting_fact_keys: string[];
}

export interface SemanticDiagnostic {
  reason: SemanticAmbiguityReason;
  subject_entity_key: string;
  candidate_fact_keys: string[];
}

export interface SemanticSetSummary {
  document_id: number;
  project_id: number | null;
  content_checksum: string;
  resolution_policy_version: string;
  fact_policy_version: string;
  semantic_policy_version: string;
  statement_count: number;
  has_ambiguities: boolean;
}

export interface SemanticSet extends SemanticSetSummary {
  statements: SemanticStatement[];
  diagnostics: SemanticDiagnostic[];
}

export interface SemanticInterpretationResult {
  succeeded: boolean;
  reused: boolean;
  found_semantics: boolean;
  has_ambiguities: boolean;
  semantic_set: SemanticSetSummary | null;
  failure: StageFailure<SemanticFailureCode> | null;
}

// --- The stages, as the UI presents them ---------------------------------

/**
 * The pipeline in execution order. A stage cannot run before the one
 * above it, and the backend enforces that with a 404 - this list is the
 * frontend's account of the same order, used to render the pipeline and
 * to decide which action is available next.
 */
export const PIPELINE_STAGES = [
  "uploaded",
  "canonical_representation",
  "canonical_text",
  "engineering_evidence",
  "engineering_entities",
  "engineering_facts",
  "engineering_semantics",
] as const;

export type PipelineStageId = (typeof PIPELINE_STAGES)[number];

export const PIPELINE_STAGE_LABELS: Record<PipelineStageId, string> = {
  uploaded: "Documento caricato",
  canonical_representation: "Rappresentazione canonica",
  canonical_text: "Testo canonico",
  engineering_evidence: "Evidenze di ingegneria",
  engineering_entities: "Entità di ingegneria",
  engineering_facts: "Fatti di ingegneria",
  engineering_semantics: "Interpretazione semantica",
};

export const PIPELINE_STAGE_DESCRIPTIONS: Record<
  PipelineStageId,
  string
> = {
  uploaded:
    "Il file originale, archiviato e identificato dal suo checksum. Resta sempre la fonte autorevole.",
  canonical_representation:
    "Ciò che il parser ha osservato nel PDF: pagine, blocchi e span con posizione e stile. Nessuna interpretazione.",
  canonical_text:
    "La struttura testuale neutra: sezione = pagina, paragrafo = blocco, riga = riga, token con provenienza completa.",
  engineering_evidence:
    "Osservazioni deterministiche: sigle, tensioni, correnti, potenze e sezioni cavo, ciascuna con la regola che l'ha prodotta.",
  engineering_entities:
    "Raggruppamento delle osservazioni compatibili in entità. Un'entità è un'ipotesi, non ancora un nodo del grafo.",
  engineering_facts:
    "Associazioni strutturali fra entità sulla stessa riga. Un fatto non è una proprietà classificata.",
  engineering_semantics:
    "Il significato ingegneristico, assegnato solo dove una regola versionata lo dichiara.",
};
