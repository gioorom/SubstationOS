import { apiRequest } from "@/lib/api";
import { ProjectIntelligence } from "@/types/project-intelligence";

export async function getProjectIntelligence(
  projectId: number
): Promise<ProjectIntelligence> {
  return apiRequest<ProjectIntelligence>(
    `/projects/${projectId}/intelligence`
  );
}