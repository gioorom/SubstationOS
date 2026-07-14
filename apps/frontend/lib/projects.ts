import { apiRequest } from "@/lib/api";
import {
  CreateProjectPayload,
  Project,
} from "@/types/project";

export function getProjects(): Promise<Project[]> {
  return apiRequest<Project[]>("/projects/");
}

export function getProject(
  projectId: number
): Promise<Project> {
  return apiRequest<Project>(
    `/projects/${projectId}`
  );
}

export function createProject(
  payload: CreateProjectPayload
): Promise<Project> {
  return apiRequest<Project>(
    "/projects/",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    }
  );
}