"use client";

import { useCallback, useEffect, useState } from "react";

import { getKnowledgeGraph } from "@/lib/knowledge-graph";
import type {
  EntityType,
  KnowledgeGraph,
} from "@/types/knowledge-graph";

interface UseKnowledgeGraphOptions {
  search?: string;
  entityType?: EntityType;
}

export function useKnowledgeGraph(
  projectId: number | undefined,
  options: UseKnowledgeGraphOptions = {}
) {
  const [graph, setGraph] = useState<KnowledgeGraph | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadGraph = useCallback(async () => {
    if (projectId === undefined) {
      setGraph(null);
      setLoading(false);
      setError("Identificativo progetto non valido.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const loadedGraph = await getKnowledgeGraph(
        projectId,
        options
      );

      setGraph(loadedGraph);
    } catch {
      setGraph(null);
      setError(
        "Impossibile caricare il Knowledge Graph."
      );
    } finally {
      setLoading(false);
    }
  }, [
    projectId,
    options.search,
    options.entityType,
  ]);

  useEffect(() => {
    void loadGraph();
  }, [loadGraph]);

  return {
    graph,
    loading,
    error,
    reload: loadGraph,
  };
}