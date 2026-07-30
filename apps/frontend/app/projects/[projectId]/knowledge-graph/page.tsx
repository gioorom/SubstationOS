"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Boxes,
  Network,
  Search,
} from "lucide-react";

import EntityDetailsPanel from "@/components/knowledge-graph/EntityDetailsPanel";
import EntityExplorer from "@/components/knowledge-graph/EntityExplorer";
import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useKnowledgeGraph } from "@/hooks/usePlatform";

import type {
  GraphEntityType,
  KnowledgeGraphNode,
} from "@/lib/contracts";

export default function KnowledgeGraphPage() {
  const params = useParams<{
    projectId: string;
  }>();

  const projectId = useMemo(
    () => Number(params.projectId),
    [params.projectId]
  );

  const validProjectId = Number.isInteger(projectId)
    ? projectId
    : undefined;

  const [search, setSearch] = useState("");
  const [entityType, setEntityType] =
    useState<GraphEntityType | "all">("all");
  const [selectedNode, setSelectedNode] =
    useState<KnowledgeGraphNode>();

  const {
    graph,
    loading,
    error,
  } = useKnowledgeGraph(validProjectId);

  const availableEntityTypes = useMemo(() => {
    if (!graph) {
      return [];
    }

    return Array.from(
      new Set(
        graph.nodes.map((node) => node.entity_type)
      )
    ).sort();
  }, [graph]);

  const filteredNodes = useMemo(() => {
    if (!graph) {
      return [];
    }

    const normalizedSearch = search
      .trim()
      .toLowerCase();

    return graph.nodes.filter((node) => {
      const matchesSearch =
        normalizedSearch.length === 0 ||
        node.name
          .toLowerCase()
          .includes(normalizedSearch) ||
        node.description
          ?.toLowerCase()
          .includes(normalizedSearch) ||
        node.source_document
          ?.toLowerCase()
          .includes(normalizedSearch);

      const matchesType =
        entityType === "all" ||
        node.entity_type === entityType;

      return Boolean(matchesSearch && matchesType);
    });
  }, [graph, search, entityType]);

  if (loading) {
    return (
      <main className="px-6 py-8 lg:px-10 lg:py-10">
        <Skeleton className="h-10 w-44" />

        <section className="mt-6">
          <Skeleton className="h-40 rounded-[2rem]" />
        </section>

        <section className="mt-8 grid gap-5 sm:grid-cols-2">
          <Skeleton className="h-40 rounded-[2rem]" />
          <Skeleton className="h-40 rounded-[2rem]" />
        </section>

        <section className="mt-8">
          <Skeleton className="h-[580px] rounded-[2rem]" />
        </section>
      </main>
    );
  }

  if (
    error ||
    !graph ||
    validProjectId === undefined
  ) {
    return (
      <main className="px-6 py-8 lg:px-10 lg:py-10">
        <section className="rounded-3xl border border-red-200 bg-red-50 p-6 text-red-700 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-300">
          <p className="font-semibold">
            Knowledge Graph non disponibile
          </p>

          <p className="mt-2 text-sm">
            {error ||
              "Impossibile caricare il grafo del progetto."}
          </p>

          <Link
            href={`/projects/${params.projectId}`}
            className={[
              buttonVariants({
                variant: "outline",
              }),
              "mt-5",
            ].join(" ")}
          >
            <ArrowLeft className="h-4 w-4" />
            Torna al progetto
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="px-6 py-8 lg:px-10 lg:py-10">
      <Link
        href={`/projects/${graph.project_id}`}
        className={buttonVariants({
          variant: "ghost",
        })}
      >
        <ArrowLeft className="h-4 w-4" />
        Torna al progetto
      </Link>

      <section className="mt-6 rounded-[2rem] border bg-card p-6 shadow-sm lg:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-3 text-sm font-medium text-muted-foreground">
              <Network className="h-5 w-5" />
              Project Intelligence
            </div>

            <h1 className="mt-3 text-3xl font-semibold tracking-tight">
              Knowledge Graph
            </h1>

            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
              Esplora componenti, documenti e relazioni
              individuati automaticamente nel progetto.
            </p>
          </div>

          <div className="rounded-2xl border bg-muted/40 px-5 py-4">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
              Project ID
            </p>

            <p className="mt-2 text-2xl font-semibold">
              {graph.project_id}
            </p>
          </div>
        </div>
      </section>

      <section className="mt-8 grid gap-5 sm:grid-cols-2">
        <article className="rounded-[2rem] border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                Entità individuate
              </p>

              <p className="mt-3 text-4xl font-semibold">
                {graph.nodes.length}
              </p>
            </div>

            <div className="rounded-2xl bg-muted p-4">
              <Boxes className="h-7 w-7" />
            </div>
          </div>
        </article>

        <article className="rounded-[2rem] border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                Relazioni
              </p>

              <p className="mt-3 text-4xl font-semibold">
                {graph.edges.length}
              </p>
            </div>

            <div className="rounded-2xl bg-muted p-4">
              <Network className="h-7 w-7" />
            </div>
          </div>
        </article>
      </section>

      <section className="mt-8 rounded-[2rem] border bg-card p-6 shadow-sm lg:p-8">
        <div className="flex flex-col gap-5">
          <div>
            <div className="flex items-center gap-3">
              <Network className="h-5 w-5" />

              <h2 className="text-xl font-semibold">
                Entity Explorer
              </h2>
            </div>

            <p className="mt-2 text-sm text-muted-foreground">
              Cerca e seleziona un’entità per visualizzarne
              i dettagli.
            </p>
          </div>

          <div className="flex flex-col gap-4 lg:flex-row">
            <label className="relative flex-1">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />

              <input
                type="search"
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value)
                }
                placeholder="Cerca per nome, descrizione o documento..."
                className="h-11 w-full rounded-xl border bg-background pl-11 pr-4 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
            </label>

            <select
              value={entityType}
              onChange={(event) =>
                setEntityType(
                  event.target.value as
                    | GraphEntityType
                    | "all"
                )
              }
              className="h-11 rounded-xl border bg-background px-4 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 lg:min-w-56"
            >
              <option value="all">
                Tutti i tipi
              </option>

              {availableEntityTypes.map((type) => (
                <option
                  key={type}
                  value={type}
                >
                  {type.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <p>
              {filteredNodes.length} entità visualizzate
            </p>

            {search || entityType !== "all" ? (
              <button
                type="button"
                onClick={() => {
                  setSearch("");
                  setEntityType("all");
                }}
                className="font-medium text-foreground underline-offset-4 hover:underline"
              >
                Reimposta filtri
              </button>
            ) : null}
          </div>

          {graph.nodes.length === 0 ? (
            <div className="rounded-2xl border border-dashed p-8 text-center">
              <p className="font-medium">
                Nessuna entità trovata
              </p>

              <p className="mt-2 text-sm text-muted-foreground">
                Carica un documento tecnico per alimentare
                il Knowledge Graph.
              </p>
            </div>
          ) : filteredNodes.length === 0 ? (
            <div className="rounded-2xl border border-dashed p-8 text-center">
              <p className="font-medium">
                Nessun risultato
              </p>

              <p className="mt-2 text-sm text-muted-foreground">
                Modifica la ricerca o reimposta i filtri.
              </p>
            </div>
          ) : (
            <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
              <EntityExplorer
                nodes={filteredNodes}
                selectedId={selectedNode?.id}
                onSelect={setSelectedNode}
              />

              <EntityDetailsPanel
                entity={selectedNode}
              />
            </div>
          )}
        </div>
      </section>
    </main>
  );
}