export type ProjectStatus =
  | "planning"
  | "active"
  | "on_hold"
  | "completed"
  | "cancelled";

export interface Project {
  id: number;
  name: string;
  code: string;
  customer: string | null;
  epc: string | null;
  location: string | null;
  voltage_level: string | null;
  status: ProjectStatus;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateProjectPayload {
  name: string;
  code: string;
  customer?: string;
  epc?: string;
  location?: string;
  voltage_level?: string;
  status?: ProjectStatus;
  description?: string;
}