/**
 * The Governed Knowledge Graph contract, transcribed from
 * `app/schemas/governed_knowledge_graph.py`.
 *
 * **Every node and every edge carries provenance**, and the types say so:
 * there is no `GraphNode` without a `GraphProvenance`, so a client cannot
 * receive a graph answer it is unable to trace back to the statement, the
 * review, the rules and the document it came from.
 *
 * Nothing here carries a semantic statement, a fact, an entity or a piece
 * of evidence. The graph names governed artefacts by key; what they
 * *said* comes from the engineering contracts, which stay their single
 * account.
 */

import type { PageMetadata } from "./pagination";

/**
 * Two node kinds, because governed semantics produces two entity types.
 *
 * No `voltage`, `protection`, `connection` or `function`: each would be
 * inventing engineering ontology, and the semantics context refuses to
 * interpret voltage upstream for exactly that reason.
 * See `knowledge_graph.md` for what each would need first.
 *
 * `structural_location` (EPIC 32.P1) is a place equipment is written
 * *inside* - the `+E01` of `+E01-QA1` - and not a classification of
 * that place.
 */
export const GRAPH_NODE_KINDS = [
  "engineering_asset",
  "engineering_quantity",
  "structural_location",
] as const;

export type GraphNodeKind = (typeof GRAPH_NODE_KINDS)[number];

export const GRAPH_NODE_KIND_LABELS: Record<GraphNodeKind, string> = {
  engineering_asset: "Apparecchiatura",
  engineering_quantity: "Grandezza",
  // "Ubicazione" and not "Scomparto": IEC 81346 assegna "+" all'aspetto
  // di ubicazione senza dire di che tipo di luogo si tratti.
  structural_location: "Ubicazione",
};

export const GRAPH_EDGE_KINDS = [
  "has_rated_power",
  "is_located_in",
] as const;

export type GraphEdgeKind = (typeof GRAPH_EDGE_KINDS)[number];

export const GRAPH_EDGE_KIND_LABELS: Record<GraphEdgeKind, string> = {
  has_rated_power: "ha potenza nominale",
  is_located_in: "si trova in",
};

/**
 * Where a graph object stands.
 *
 * `historical` is not deletion: the knowledge *was* governed, is no
 * longer current, and stays readable with its provenance and the reason
 * it was retired.
 */
export const GRAPH_OBJECT_STATES = [
  "active",
  "historical",
  "removed",
] as const;

export type GraphObjectState = (typeof GRAPH_OBJECT_STATES)[number];

export const GRAPH_OBJECT_STATE_LABELS: Record<GraphObjectState, string> = {
  active: "Nel grafo",
  historical: "Storico",
  removed: "Rimosso",
};

export const GRAPH_RETIREMENT_REASONS = [
  "review_reversed",
  "requires_revalidation",
  "orphaned",
  "rebuild_reconciliation",
  "no_remaining_relationships",
] as const;

export type GraphRetirementReason =
  (typeof GRAPH_RETIREMENT_REASONS)[number];

export const GRAPH_RETIREMENT_REASON_LABELS: Record<
  GraphRetirementReason,
  string
> = {
  review_reversed: "Giudizio successivo non favorevole",
  requires_revalidation: "In attesa di riconvalida",
  orphaned: "Nessuna interpretazione di riferimento",
  rebuild_reconciliation: "Riconciliato durante una ricostruzione",
  no_remaining_relationships: "Nessuna relazione governata residua",
};

/**
 * Why a statement is not in the graph.
 *
 * A closed catalogue, so the panel can say *why* rather than only that
 * the statement is absent - "not promoted" and "not promoted because
 * nobody has approved it" are different things to an engineer.
 */
export const PROMOTION_REFUSALS = [
  "not_reviewed",
  "review_rejected",
  "review_inconclusive",
  "review_stale",
  "review_orphaned",
  "ungoverned_statement_type",
  "ungoverned_entity_type",
  "invalid_endpoints",
] as const;

export type PromotionRefusal = (typeof PROMOTION_REFUSALS)[number];

export const PROMOTION_REFUSAL_LABELS: Record<PromotionRefusal, string> = {
  not_reviewed:
    "Nessun ingegnere ha ancora espresso un giudizio su questa affermazione.",
  review_rejected:
    "Un ingegnere ha respinto questa interpretazione: non entra nel grafo.",
  review_inconclusive:
    "Un ingegnere ha chiesto ulteriori approfondimenti. Non è un'approvazione parziale.",
  review_stale:
    "Il giudizio è stato espresso su un'affermazione derivata con regole o byte diversi, e va riconvalidato prima di poter autorizzare conoscenza.",
  review_orphaned:
    "Non esiste un'interpretazione attuale con cui confrontare il giudizio.",
  ungoverned_statement_type:
    "Il grafo non governa ancora questo tipo di affermazione.",
  ungoverned_entity_type:
    "Il grafo non governa ancora questo tipo di entità.",
  invalid_endpoints:
    "Gli estremi della relazione non hanno i tipi che questa relazione richiede.",
};

// --- Provenance ----------------------------------------------------------

/** Where one piece of governed knowledge came from. Never optional. */
export interface GraphProvenance {
  statement_key: string;
  document_id: number;
  project_id: number | null;
  content_checksum: string;

  review_id: number;
  reviewer_user_id: number;
  reviewer_display_name: string;
  reviewed_at: string;

  semantic_rule_id: string;
  semantic_rule_version: string;
  semantic_contract_version: string;
  resolution_policy_version: string;
  fact_policy_version: string;
  semantic_policy_version: string;
  support_fingerprint: string;
}

export interface GraphRetirement {
  reason: GraphRetirementReason;
  retired_at: string;
}

// --- Nodes and edges -----------------------------------------------------

export interface GraphNode {
  node_id: string;
  kind: GraphNodeKind;
  entity_key: string;
  /** Readable, and never identity. Two nodes may share a label. */
  label: string;
  normalized_value: string;
  unit: string | null;
  state: GraphObjectState;
  created_at: string;
  retirement: GraphRetirement | null;
  provenance: GraphProvenance;
}

export interface GraphEdge {
  edge_id: string;
  kind: GraphEdgeKind;
  statement_key: string;
  subject_node_id: string;
  object_node_id: string;
  state: GraphObjectState;
  created_at: string;
  retirement: GraphRetirement | null;
  provenance: GraphProvenance;
}

export interface RelatedNode {
  edge: GraphEdge;
  /** `outgoing` when this node is the subject of the relationship. */
  direction: "outgoing" | "incoming";
  other_node: GraphNode | null;
}

export interface GraphNodeDetail {
  node: GraphNode;
  relationships: RelatedNode[];
}

export interface GraphNodeListResponse {
  items: GraphNode[];
  pagination: PageMetadata;
}

export interface GraphEdgeListResponse {
  items: GraphEdge[];
  pagination: PageMetadata;
}

// --- Promotion -----------------------------------------------------------

/** Whether one statement is in the graph, and why or why not. */
export interface StatementPromotion {
  statement_key: string;
  promoted: boolean;
  refusal: PromotionRefusal | null;
  edge: GraphEdge | null;
}

export interface PromotionEvent {
  event_type: string;
  statement_key: string | null;
  edge_id: string | null;
  reason: string | null;
  refusal: PromotionRefusal | null;
}

export interface PromotionResult {
  promoted: number;
  retired: number;
  revalidated: number;
  failed: number;
  events: PromotionEvent[];
}

/**
 * One recomputation of the whole projection.
 *
 * Carries only the versions that are **global**. The semantic rule and
 * policy versions are deliberately absent: they differ per object and
 * live on each edge's provenance, because one graph can legitimately
 * span several rule versions.
 */
export interface GraphGeneration {
  generation_number: number;
  trigger: string;
  promotion_contract_version: string;
  created_at: string;
  node_count: number;
  edge_count: number;
  actor_user_id: number | null;
}

export interface GraphStatus {
  active_nodes: number;
  active_edges: number;
  latest_generation: GraphGeneration | null;
  promotion_contract_version: string;
}
