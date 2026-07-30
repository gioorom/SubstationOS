/**
 * The identity contract, transcribed from `app/schemas/identity.py`.
 *
 * **Nothing here can carry a secret.** There is no session token type
 * and no field for one: the token lives in an `HttpOnly` cookie that
 * this application's script cannot read, and a type that could hold one
 * would be an invitation to put it somewhere script can.
 *
 * `LoginRequest` is the single exception in the other direction - a
 * password goes *out* once, over the wire, and is never stored, echoed
 * or logged.
 */

export const ROLES = ["engineer", "administrator"] as const;

export type Role = (typeof ROLES)[number];

export const ROLE_LABELS: Record<Role, string> = {
  engineer: "Ingegnere",
  administrator: "Amministratore",
};

export const USER_STATUSES = ["active", "disabled"] as const;

export type UserStatus = (typeof USER_STATUSES)[number];

export const USER_STATUS_LABELS: Record<UserStatus, string> = {
  active: "Attivo",
  disabled: "Disattivato",
};

/** `POST /auth/login`. */
export interface LoginRequest {
  email: string;
  password: string;
}

/** Who the caller is. Small on purpose - nothing worth stealing. */
export interface Identity {
  user_id: number;
  email: string;
  display_name: string;
  role: Role;
}

/**
 * `GET /auth/session`.
 *
 * `expires_at` is the session's **absolute** ceiling. The idle timeout is
 * deliberately not exposed: it moves with every request, so a client that
 * displayed it would be showing a number that was already wrong.
 */
export interface Session {
  identity: Identity;
  expires_at: string;
}

export interface User extends Identity {
  status: UserStatus;
  created_at: string;
}

export interface UserListResponse {
  items: User[];
}

// --- Audit ---------------------------------------------------------------

export const AUDIT_ACTIONS = [
  "login_succeeded",
  "login_failed",
  "logout",
  "password_changed",
  "user_created",
  "user_disabled",
  "project_created",
  "document_uploaded",
  "pipeline_executed",
  "workspace_accessed",
  "engineering_review_recorded",
  "engineering_review_superseded",
  "knowledge_promoted",
  "knowledge_graph_rebuilt",
  "access_denied",
] as const;

export type AuditAction = (typeof AUDIT_ACTIONS)[number];

export const AUDIT_ACTION_LABELS: Record<AuditAction, string> = {
  login_succeeded: "Accesso riuscito",
  login_failed: "Accesso rifiutato",
  logout: "Disconnessione",
  password_changed: "Password modificata",
  user_created: "Utente creato",
  user_disabled: "Utente disattivato",
  project_created: "Progetto creato",
  document_uploaded: "Documento caricato",
  pipeline_executed: "Pipeline eseguita",
  workspace_accessed: "Workspace consultato",
  engineering_review_recorded: "Revisione registrata",
  engineering_review_superseded: "Revisione superata",
  knowledge_promoted: "Conoscenza promossa nel grafo",
  knowledge_graph_rebuilt: "Grafo ricostruito",
  access_denied: "Accesso negato",
};

export const AUDIT_OUTCOMES = ["succeeded", "failed", "denied"] as const;

export type AuditOutcome = (typeof AUDIT_OUTCOMES)[number];

export const AUDIT_OUTCOME_LABELS: Record<AuditOutcome, string> = {
  succeeded: "Riuscito",
  failed: "Fallito",
  denied: "Negato",
};

/**
 * Who acted.
 *
 * `authenticated` is the field that matters: it says whether
 * `description` names a verified identity, or merely records what an
 * anonymous caller claimed at a login form.
 */
export interface AuditActor {
  authenticated: boolean;
  user_id: number | null;
  session_id: number | null;
  description: string;
}

export interface AuditEvent {
  event_id: number;
  occurred_at: string;
  action: AuditAction;
  outcome: AuditOutcome;
  actor: AuditActor;
  resource_type: string;
  resource_id: string | null;
  detail: string | null;
}

export interface AuditEventListResponse {
  items: AuditEvent[];
}
