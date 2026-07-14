import { apiRequest } from "@/lib/api";
import { HealthResponse } from "@/types/health";

export function getHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>("/health");
}