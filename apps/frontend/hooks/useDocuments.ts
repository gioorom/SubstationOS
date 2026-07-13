"use client";

import { useCallback, useEffect, useState } from "react";

import { getDocuments } from "@/lib/documents";
import { Document } from "@/types/document";

interface UseDocumentsResult {
  documents: Document[];
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
}

export function useDocuments(): UseDocumentsResult {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const data = await getDocuments();
      setDocuments(data);
    } catch {
      setError("Errore durante il caricamento dei documenti.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return {
    documents,
    loading,
    error,
    reload,
  };
}