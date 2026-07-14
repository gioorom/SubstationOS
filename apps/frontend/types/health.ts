export type ServiceStatus =
  | "online"
  | "warning"
  | "offline";

export interface HealthResponse {
  status: ServiceStatus;

  services: {
    api: ServiceStatus;
    database: ServiceStatus;
    storage: ServiceStatus;
    ai: ServiceStatus;
  };
}