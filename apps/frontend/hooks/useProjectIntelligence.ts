"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import { getProjectIntelligence } from "@/lib/project-intelligence";
import { ProjectIntelligence } from "@/types/project-intelligence";

interface UseProjectIntelligenceResult {
  intelligence: ProjectIntelligence | null;
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
}

export function useProjectIntelligence(
  projectId?: number
): UseProjectIntelligenceResult {
  const [intelligence, setIntelligence] =
    useState<ProjectIntelligence | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    if (
      projectId === undefined ||
      !Number.isInteger(projectId)
    ) {
      setIntelligence(null);
      setError("Identificativo progetto non valido.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError("");

    try {
      const data = await getProjectIntelligence(
        projectId
      );

      setIntelligence(data);
    } catch {
      setIntelligence(null);
      setError(
        "Impossibile caricare l'intelligence del progetto."
      );
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return {
    intelligence,
    loading,
    error,
    reload,
  };
}