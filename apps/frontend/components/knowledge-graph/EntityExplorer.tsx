"use client";

import type { KnowledgeGraphNode } from "@/types/knowledge-graph";

interface Props {
  nodes: KnowledgeGraphNode[];
  selectedId?: number;
  onSelect(node: KnowledgeGraphNode): void;
}

export default function EntityExplorer({
  nodes,
  selectedId,
  onSelect,
}: Props) {
  if (nodes.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed p-8 text-center text-muted-foreground">
        Nessuna entità disponibile.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border overflow-hidden">
      {nodes.map((node) => (
        <button
          key={node.id}
          onClick={() => onSelect(node)}
          className={[
            "w-full border-b last:border-b-0 px-5 py-4",
            "text-left transition-colors",
            selectedId === node.id
              ? "bg-primary/10"
              : "hover:bg-muted/50",
          ].join(" ")}
        >
          <div className="flex justify-between items-center">
            <div>
              <div className="font-medium">
                {node.name}
              </div>

              <div className="text-sm text-muted-foreground">
                {node.source_document ?? "Manuale"}
              </div>
            </div>

            <span className="rounded-full bg-muted px-3 py-1 text-xs uppercase">
              {node.entity_type.replaceAll("_", " ")}
            </span>
          </div>
        </button>
      ))}
    </div>
  );
}