/**
 * Contracts for the two platform-level endpoints the UI reads:
 * `GET /health` (`app/main.py`) and
 * `GET /projects/{id}/intelligence` (`app/schemas/project_intelligence.py`).
 */

export const SERVICE_STATUSES = ["online", "warning", "offline"] as const;

export type ServiceStatus = (typeof SERVICE_STATUSES)[number];

export interface HealthResponse {
  status: ServiceStatus;
  services: {
    api: ServiceStatus;
    database: ServiceStatus;
    storage: ServiceStatus;
    ai: ServiceStatus;
  };
}

export const DOCUMENTATION_STATUSES = [
  "empty",
  "incomplete",
  "available",
] as const;

export type DocumentationStatus =
  (typeof DOCUMENTATION_STATUSES)[number];

export const RISK_LEVELS = ["low", "medium", "high"] as const;

export type RiskLevel = (typeof RISK_LEVELS)[number];

export const READINESS_STATUSES = [
  "not_ready",
  "partially_ready",
  "ready",
] as const;

export type ReadinessStatus = (typeof READINESS_STATUSES)[number];

export const MODULE_STATUSES = [
  "not_started",
  "in_progress",
  "completed",
] as const;

export type ModuleStatus = (typeof MODULE_STATUSES)[number];

export interface DocumentationIntelligence {
  document_count: number;
  completion: number;
  status: DocumentationStatus;
}

export interface ProgressIntelligence {
  completed: number;
  total: number;
  completion: number;
  status: ModuleStatus;
}

export interface IssuesIntelligence {
  open: number;
  critical: number;
}

/**
 * Only `documentation`, `health_score`, `risk_level`, `readiness` and
 * `next_action` are computed by the backend today.
 *
 * `commissioning`, `relay_testing` and `issues` are returned as constant
 * zeros by `app/services/project_intelligence.py` - they are placeholders
 * for modules that do not exist yet. They are part of the contract and so
 * are typed here, but **the UI must not present them as measurements**;
 * rendering a fabricated 0% commissioning figure beside a real
 * documentation figure is exactly the mock this EPIC removes.
 */
export interface ProjectIntelligence {
  project_id: number;
  health_score: number;
  risk_level: RiskLevel;
  readiness: ReadinessStatus;
  next_action: string;
  documentation: DocumentationIntelligence;
  commissioning: ProgressIntelligence;
  relay_testing: ProgressIntelligence;
  issues: IssuesIntelligence;
}

export const DOCUMENTATION_STATUS_LABELS: Record<
  DocumentationStatus,
  string
> = {
  empty: "Nessun documento disponibile",
  incomplete: "Set documentale incompleto",
  available: "Documentazione disponibile",
};

export const READINESS_LABELS: Record<ReadinessStatus, string> = {
  not_ready: "Non pronto",
  partially_ready: "Parzialmente pronto",
  ready: "Pronto",
};

export const RISK_LEVEL_LABELS: Record<RiskLevel, string> = {
  low: "Rischio basso",
  medium: "Rischio medio",
  high: "Rischio alto",
};
