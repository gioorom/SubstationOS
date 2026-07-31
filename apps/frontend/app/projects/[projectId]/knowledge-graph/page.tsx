"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Network, Search } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useGovernedGraph } from "@/hooks/useGovernedGraph";
import {
  GRAPH_EDGE_KIND_LABELS,
  GRAPH_NODE_KINDS,
  GRAPH_NODE_KIND_LABELS,
  type GraphNode,
  type GraphNodeKind,
} from "@/lib/contracts";

/**
 * The governed Knowledge Graph, for one project.
 *
 * **Rewritten by EPIC 31.1.** This route used to read
 * `/projects/{id}/knowledge-graph`, an endpoint serving LLM-extracted
 * entities written straight from document upload with no review gate -
 * the ADR-0004 violation that milestone ended. The route survives
 * because engineers have it bookmarked; what it shows does not.
 *
 * Everything here is **governed knowledge**: a statement the pipeline
 * interpreted deterministically, that an engineer approved, and whose
 * approval still applies. Every node and relationship carries the
 * provenance to prove it, and the page shows that rather than asking
 * anyone to take it on trust.
 */
export default function ProjectKnowledgeGraphPage() {
  const params = useParams<{ projectId: string }>();

  const projectId = useMemo(
    () => Number(params.projectId),
    [params.projectId],
  );

  const valid = Number.isInteger(projectId);
  const graph = useGovernedGraph(valid ? projectId : undefined);

  if (!valid) {
    return (
      <main className="px-6 py-8 lg:px-10">
        <p
          role="alert"
          className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700"
        >
          Identificativo progetto non valido.
        </p>
      </main>
    );
  }

  const nodes = graph.nodes?.items ?? [];

  return (
    <main className="px-6 py-8 lg:px-10">
      <Link
        href={`/projects/${projectId}`}
        className={buttonVariants({ variant: "ghost" })}
      >
        <ArrowLeft className="h-4 w-4" />
        Torna al progetto
      </Link>

      <section className="mt-4">
        <p className="text-sm font-medium text-primary">
          Conoscenza governata
        </p>

        <h1 className="mt-1 flex items-center gap-2 text-3xl font-semibold tracking-tight text-foreground">
          <Network className="h-7 w-7" aria-hidden="true" />
          Grafo della conoscenza
        </h1>

        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
          Contiene soltanto affermazioni interpretate dalla pipeline
          deterministica, approvate da un ingegnere e ancora attuali. È una
          proiezione: può sempre essere ricostruita dalla pipeline e dalle
          revisioni, e non è mai la fonte della verità.
        </p>
      </section>

      <section className="mt-6 flex flex-wrap items-end gap-3">
        <label className="flex flex-1 flex-col gap-1 text-xs text-muted-foreground">
          Cerca per sigla o valore
          <span className="relative">
            <Search
              className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <input
              type="search"
              value={graph.search}
              onChange={(event) => graph.setSearch(event.target.value)}
              placeholder="TR1, 630 kVA…"
              className="h-9 w-full rounded-xl border border-input bg-background pl-9 pr-3 text-sm text-foreground"
            />
          </span>
        </label>

        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Tipo
          <select
            value={graph.kind}
            onChange={(event) =>
              graph.setKind(event.target.value as GraphNodeKind | "all")
            }
            className="h-9 rounded-xl border border-input bg-background px-3 text-sm text-foreground"
          >
            <option value="all">Tutti</option>
            {GRAPH_NODE_KINDS.map((value) => (
              <option key={value} value={value}>
                {GRAPH_NODE_KIND_LABELS[value]}
              </option>
            ))}
          </select>
        </label>
      </section>

      {graph.error !== null && (
        <p
          role="alert"
          className="mt-6 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700"
        >
          {graph.error}
        </p>
      )}

      {graph.loading ? (
        <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <Skeleton className="h-96 rounded-3xl" />
          <Skeleton className="h-96 rounded-3xl" />
        </div>
      ) : (
        <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <section
            aria-label="Concetti governati"
            className="rounded-3xl border border-slate-200 bg-white/80 p-4"
          >
            {nodes.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center">
                <p className="text-sm font-medium text-foreground">
                  Nessuna conoscenza governata per questo progetto.
                </p>

                <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
                  Il grafo si popola quando un ingegnere approva
                  un&apos;affermazione semantica e la promuove. Non è un
                  errore: è la differenza fra ciò che la pipeline ha
                  interpretato e ciò che qualcuno ha sostenuto.
                </p>
              </div>
            ) : (
              <ul aria-label="Nodi del grafo" className="space-y-2">
                {nodes.map((node) => (
                  <li key={node.node_id}>
                    <NodeRow
                      node={node}
                      selected={node.node_id === graph.selectedNodeId}
                      onSelect={() => graph.select(node.node_id)}
                    />
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section
            aria-label="Dettaglio del nodo"
            className="rounded-3xl border border-slate-200 bg-white/80 p-4"
          >
            <NodeDetail graph={graph} />
          </section>
        </div>
      )}
    </main>
  );
}

function NodeRow({
  node,
  selected,
  onSelect,
}: {
  node: GraphNode;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected ? "true" : undefined}
      className={`w-full rounded-2xl border px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
        selected
          ? "border-l-4 border-slate-400 border-l-slate-900 bg-slate-100"
          : "border-slate-200 bg-white hover:bg-slate-50"
      }`}
    >
      <span className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm font-semibold text-foreground">
          {node.label}
        </span>

        <span className="rounded-full border border-slate-200 px-2 py-0.5 text-xs text-slate-600">
          {GRAPH_NODE_KIND_LABELS[node.kind]}
        </span>

        {node.unit !== null && (
          <span className="text-xs text-muted-foreground">{node.unit}</span>
        )}
      </span>

      <span className="mt-1 block text-xs text-muted-foreground">
        {`Approvato da ${node.provenance.reviewer_display_name} · `}
        <span className="font-mono">
          {node.provenance.semantic_rule_id}@
          {node.provenance.semantic_rule_version}
        </span>
      </span>
    </button>
  );
}

function NodeDetail({
  graph,
}: {
  graph: ReturnType<typeof useGovernedGraph>;
}) {
  if (graph.selectedNodeId === null) {
    return (
      <p className="text-sm leading-6 text-muted-foreground">
        Seleziona un concetto per vedere le relazioni governate che lo
        riguardano e la provenienza di ciascuna.
      </p>
    );
  }

  if (graph.detailError !== null) {
    return (
      <p
        role="alert"
        className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
      >
        {graph.detailError}
      </p>
    );
  }

  if (graph.detailLoading || graph.detail === null) {
    return <Skeleton className="h-40 rounded-2xl" />;
  }

  const { node, relationships } = graph.detail;

  return (
    <div>
      <p className="font-mono text-base font-semibold text-foreground">
        {node.label}
      </p>

      <p className="mt-1 text-xs text-muted-foreground">
        {GRAPH_NODE_KIND_LABELS[node.kind]}
      </p>

      <h2 className="mt-5 mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Relazioni governate
      </h2>

      {relationships.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nessuna relazione governata riguarda questo concetto.
        </p>
      ) : (
        <ul aria-label="Relazioni governate" className="space-y-2">
          {relationships.map((relationship) => (
            <li
              key={relationship.edge.edge_id}
              className="rounded-2xl border border-slate-200 bg-white px-3 py-2"
            >
              <p className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-mono text-xs uppercase tracking-wide text-sky-700">
                  {relationship.edge.kind}
                </span>

                <span className="font-medium text-foreground">
                  {GRAPH_EDGE_KIND_LABELS[relationship.edge.kind]}
                </span>

                <span className="font-mono font-semibold text-foreground">
                  {relationship.other_node?.label ?? "—"}
                </span>

                {relationship.other_node?.unit != null && (
                  <span className="text-xs text-muted-foreground">
                    {relationship.other_node.unit}
                  </span>
                )}
              </p>

              {/*
                Provenance beside every relationship, not behind a click.
                A governed graph whose value is that every answer is
                explainable should not make the explanation optional.
              */}
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                {`Approvata da ${relationship.edge.provenance.reviewer_display_name} · revisione ${relationship.edge.provenance.review_id} · `}
                <span className="font-mono">
                  {relationship.edge.provenance.semantic_rule_id}@
                  {relationship.edge.provenance.semantic_rule_version}
                </span>
              </p>

              <p className="mt-0.5 text-xs text-muted-foreground">
                <Link
                  href={`/documents/${relationship.edge.provenance.document_id}/workspace?kind=semantic&key=${encodeURIComponent(
                    relationship.edge.statement_key,
                  )}`}
                  className="text-primary hover:underline"
                >
                  Apri l&apos;affermazione nel Workspace
                </Link>
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
