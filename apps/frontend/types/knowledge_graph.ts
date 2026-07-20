export type EntityType =
  | "substation"
  | "bay"
  | "panel"
  | "circuit_breaker"
  | "disconnector"
  | "transformer"
  | "current_transformer"
  | "voltage_transformer"
  | "protection_relay"
  | "cable"
  | "signal"
  | "document"
  | "test"
  | "other";

export type RelationType =
  | "belongs_to"
  | "connected_to"
  | "protected_by"
  | "documented_in"
  | "tested_by"
  | "part_of"
  | "other";

export interface KnowledgeGraphNode {
  id: number;
  project_id: number;
  entity_type: EntityType;
  name: string;
  description: string | null;
  source_document: string | null;
  created_at: string;
}

export interface KnowledgeGraphEdge {
  id: number;
  source: number;
  target: number;
  relation_type: RelationType;
}

export interface KnowledgeGraph {
  project_id: number;
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
}