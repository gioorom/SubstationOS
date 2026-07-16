export type TimelineEventType =
  | "project_created"
  | "document_uploaded"
  | "document_updated"
  | "revision_changed"
  | "commissioning_started"
  | "commissioning_completed"
  | "relay_test_started"
  | "relay_test_completed"
  | "issue_opened"
  | "issue_resolved"
  | "health_score_changed"
  | "intelligence_generated"
  | "note_added";

export type TimelineEventSeverity =
  | "info"
  | "success"
  | "warning"
  | "critical";

export type TimelineEntityType =
  | "project"
  | "document"
  | "commissioning"
  | "relay_test"
  | "issue"
  | "intelligence";

export interface TimelineActor {
  id: number | null;
  name: string;
  role: string | null;
}

export interface TimelineEntityReference {
  type: TimelineEntityType;
  id: number | null;
  label: string | null;
  href: string | null;
}

export interface TimelineEventMetadata {
  previous_value?: string | number | null;
  current_value?: string | number | null;
  revision?: string | null;
  filename?: string | null;
  health_score_before?: number | null;
  health_score_after?: number | null;
  [key: string]: string | number | boolean | null | undefined;
}

export interface TimelineEvent {
  id: string;
  project_id: number;
  type: TimelineEventType;
  severity: TimelineEventSeverity;
  title: string;
  description: string | null;
  occurred_at: string;
  actor: TimelineActor | null;
  entity: TimelineEntityReference | null;
  metadata: TimelineEventMetadata;
}

export interface ProjectTimeline {
  project_id: number;
  events: TimelineEvent[];
  total: number;
}