"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  getDocuments,
  uploadDocument,
} from "@/lib/documents";
import { Document } from "@/types/document";

interface UseDocumentsResult {
  documents: Document[];
  loading: boolean;
  uploading: boolean;
  error: string;
  reload: () => Promise<void>;
  addDocument: (
    file: File,
    uploadProjectId?: number
  ) => Promise<Document>;
}

export function useDocuments(
  projectId?: number
): UseDocumentsResult {
  const [documents, setDocuments] = useState<Document[]>(
    []
  );

  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const data = await getDocuments(projectId);
      setDocuments(data);
    } catch {
      setError(
        "Errore durante il caricamento dei documenti."
      );
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const addDocument = useCallback(
    async (
      file: File,
      uploadProjectId?: number
    ): Promise<Document> => {
      const effectiveProjectId =
        uploadProjectId ?? projectId;

      if (effectiveProjectId === undefined) {
        throw new Error(
          "È necessario selezionare un progetto."
        );
      }

      setUploading(true);
      setError("");

      try {
        const document = await uploadDocument(
          file,
          effectiveProjectId
        );

        setDocuments((currentDocuments) => [
          document,
          ...currentDocuments,
        ]);

        return document;
      } catch (uploadError) {
        setError(
          "Errore durante il caricamento del documento."
        );

        throw uploadError;
      } finally {
        setUploading(false);
      }
    },
    [projectId]
  );

  useEffect(() => {
    void reload();
  }, [reload]);

  return {
    documents,
    loading,
    uploading,
    error,
    reload,
    addDocument,
  };
}