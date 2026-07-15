import { apiRequest } from "@/lib/api";
import { Document } from "@/types/document";

export function getDocuments(
  projectId?: number
): Promise<Document[]> {
  const query =
    projectId !== undefined
      ? `?project_id=${projectId}`
      : "";

  return apiRequest<Document[]>(
    `/documents/${query}`
  );
}

export async function uploadDocument(
  file: File,
  projectId?: number
): Promise<Document> {
  const formData = new FormData();

  formData.append("file", file);

  if (projectId !== undefined) {
    formData.append(
      "project_id",
      String(projectId)
    );
  }

  return apiRequest<Document>(
    "/documents/upload",
    {
      method: "POST",
      body: formData,
    }
  );
}