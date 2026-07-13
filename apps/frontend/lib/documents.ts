import { apiRequest } from "@/lib/api";
import { Document } from "@/types/document";

export function getDocuments(): Promise<Document[]> {
  return apiRequest<Document[]>("/documents/");
}