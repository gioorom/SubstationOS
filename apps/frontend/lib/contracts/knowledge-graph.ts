/**
 * The per-project Knowledge Graph contract, transcribed from
 * `app/schemas/knowledge_graph.py` and `app/models/knowledge_graph.py`.
 *
 * This is the pre-existing LLM-backed graph the upload endpoint feeds -
 * a different thing from the deterministic engineering pipeline in
 * `pipeline.ts`, and the audit says so explicitly. `busbar` and `line`
 * were missing from the previous frontend enum.
 */

export const GRAPH_ENTITY_TYPES = [
  "substation",
  "bay",
  "panel",
  "circuit_breaker",
  "disconnector",
  "transformer",
  "current_transformer",
  "voltage_transformer",
  "protection_relay",
  "cable",
  "signal",
  "document",
  "test",
  "other",
  "busbar",
  "line",
] as const;

export type GraphEntityType = (typeof GRAPH_ENTITY_TYPES)[number];

export const GRAPH_RELATION_TYPES = [
  "belongs_to",
  "connected_to",
  "protected_by",
  "documented_in",
  "tested_by",
  "part_of",
  "other",
] as const;

export type GraphRelationType = (typeof GRAPH_RELATION_TYPES)[number];

export interface KnowledgeGraphNode {
  id: number;
  project_id: number;
  entity_type: GraphEntityType;
  name: string;
  description?: string | null;
  source_document?: string | null;
  created_at: string;
}

export interface KnowledgeGraphEdge {
  id: number;
  source: number;
  target: number;
  relation_type: GraphRelationType;
}

export interface KnowledgeGraph {
  project_id: number;
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
}

export interface EntityDetail extends KnowledgeGraphNode {
  related_entities: KnowledgeGraphNode[];
}

export const GRAPH_ENTITY_TYPE_LABELS: Record<GraphEntityType, string> = {
  substation: "Sottostazione",
  bay: "Stallo",
  panel: "Quadro",
  circuit_breaker: "Interruttore",
  disconnector: "Sezionatore",
  transformer: "Trasformatore",
  current_transformer: "TA",
  voltage_transformer: "TV",
  protection_relay: "Relè di protezione",
  cable: "Cavo",
  signal: "Segnale",
  document: "Documento",
  test: "Prova",
  other: "Altro",
  busbar: "Sbarra",
  line: "Linea",
};

export const GRAPH_RELATION_TYPE_LABELS: Record<
  GraphRelationType,
  string
> = {
  belongs_to: "appartiene a",
  connected_to: "connesso a",
  protected_by: "protetto da",
  documented_in: "documentato in",
  tested_by: "provato da",
  part_of: "parte di",
  other: "altro",
};
