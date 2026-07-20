"use client";

import type { KnowledgeGraphNode } from "@/types/knowledge-graph";

interface Props {
  entity?: KnowledgeGraphNode;
}

export default function EntityDetailsPanel({
  entity,
}: Props) {
  if (!entity) {
    return (
      <div className="rounded-2xl border p-8 text-muted-foreground">
        Seleziona un'entità.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border p-6 space-y-5">
      <div>
        <p className="text-xs uppercase text-muted-foreground">
          Tipo
        </p>

        <h2 className="text-2xl font-semibold mt-1">
          {entity.name}
        </h2>

        <p className="mt-2">
          {entity.entity_type.replaceAll("_", " ")}
        </p>
      </div>

      <div>
        <p className="text-xs uppercase text-muted-foreground">
          Descrizione
        </p>

        <p className="mt-2">
          {entity.description ?? "Non disponibile"}
        </p>
      </div>

      <div>
        <p className="text-xs uppercase text-muted-foreground">
          Documento sorgente
        </p>

        <p className="mt-2">
          {entity.source_document ?? "Manuale"}
        </p>
      </div>

      <div>
        <p className="text-xs uppercase text-muted-foreground">
          Creato il
        </p>

        <p className="mt-2">
          {new Date(entity.created_at).toLocaleString("it-IT")}
        </p>
      </div>
    </div>
  );
}