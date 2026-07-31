"use client";

/**
 * The governed Knowledge Graph, for one project.
 *
 * Replaces `usePlatform.useKnowledgeGraph`, which read the legacy
 * `/projects/{id}/knowledge-graph` endpoint that EPIC 31.1 retired. That
 * endpoint served LLM-extracted entities written straight from upload
 * with no review gate; this one serves knowledge an engineer approved,
 * and every node and edge carries the provenance to prove it.
 *
 * Two reads, settled independently: a node list and, when one is
 * selected, its relationships. A failed detail read leaves the list
 * usable, which matters because the list is how the detail is reached.
 */

import { useCallback, useState } from "react";

import type { ErrorCopy } from "@/lib/api";
import type {
  GraphNodeDetail,
  GraphNodeKind,
  GraphNodeListResponse,
} from "@/lib/contracts";
import { listGraphNodes, readGraphNode } from "@/lib/resources/graph";

import { useResource } from "./useResource";

const PAGE_SIZE = 50;

const COPY: ErrorCopy = {
  network:
    "Impossibile leggere il grafo governato: il backend non risponde.",
};

export interface GovernedGraphState {
  nodes: GraphNodeListResponse | null;
  loading: boolean;
  error: string | null;

  selectedNodeId: string | null;
  select: (nodeId: string | null) => void;

  detail: GraphNodeDetail | null;
  detailLoading: boolean;
  detailError: string | null;

  search: string;
  setSearch: (value: string) => void;
  kind: GraphNodeKind | "all";
  setKind: (value: GraphNodeKind | "all") => void;

  reload: () => Promise<void>;
}

export function useGovernedGraph(
  projectId: number | undefined,
): GovernedGraphState {
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<GraphNodeKind | "all">("all");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const readNodes = useCallback(
    (signal: AbortSignal) =>
      listGraphNodes(
        {
          project_id: projectId,
          kind: kind === "all" ? undefined : kind,
          search: search.trim() || undefined,
          page_size: PAGE_SIZE,
        },
        signal,
      ),
    [projectId, kind, search],
  );

  const nodes = useResource<GraphNodeListResponse>(readNodes, {
    enabled: projectId !== undefined,
    copy: COPY,
  });

  const readDetail = useCallback(
    (signal: AbortSignal) =>
      readGraphNode(selectedNodeId as string, {}, signal),
    [selectedNodeId],
  );

  const detail = useResource<GraphNodeDetail>(readDetail, {
    enabled: selectedNodeId !== null,
    copy: COPY,
  });

  return {
    nodes: nodes.data,
    loading: nodes.loading,
    error: nodes.error,
    selectedNodeId,
    select: setSelectedNodeId,
    detail: detail.data,
    detailLoading: detail.loading,
    detailError: detail.error,
    search,
    setSearch,
    kind,
    setKind,
    reload: nodes.reload,
  };
}
