"use client";

import { type ReactNode, useState } from "react";

import { Button } from "@/components/ui/button";
import type { StageStatus } from "@/lib/workspace";

import StageStatusNotice from "./StageStatusNotice";

/**
 * How many rows are rendered before the engineer asks for more.
 *
 * A realistic drawing set produces observations in the hundreds to low
 * thousands. Rendering all of them costs a visibly slow first paint and
 * an unusable tab order, and virtualising them would cost a dependency
 * and a scroll implementation. A bound plus an explicit "show more" is
 * the smaller answer, and it keeps every row a real, focusable element.
 */
const PAGE_SIZE = 60;

interface ExplorerListProps<T> {
  items: readonly T[];
  /** Stable identity of a row - the artefact's own key. */
  keyOf: (item: T) => string;
  render: (item: T) => ReactNode;
  /** The stage this list draws from, so unrun never looks like empty. */
  status: StageStatus;
  /** What the stage produces, for the empty and unrun wording. */
  noun: string;
  /** Accessible name of the list. */
  label: string;
  /** Filters applied above; used only to word "no match" honestly. */
  filtered?: boolean;
}

export default function ExplorerList<T>({
  items,
  keyOf,
  render,
  status,
  noun,
  label,
  filtered = false,
}: ExplorerListProps<T>) {
  const [limit, setLimit] = useState(PAGE_SIZE);

  if (status.availability !== "available") {
    return <StageStatusNotice status={status} noun={noun} />;
  }

  if (items.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-600">
        {filtered
          ? `Nessun risultato corrisponde ai filtri. Lo stage ha prodotto ${noun}, ma non di questo tipo.`
          : `Nessun artefatto da mostrare.`}
      </p>
    );
  }

  const visible = items.slice(0, limit);

  return (
    <>
      <ul aria-label={label} className="space-y-2">
        {visible.map((item) => (
          <li key={keyOf(item)}>{render(item)}</li>
        ))}
      </ul>

      {items.length > visible.length && (
        <div className="mt-3 flex items-center gap-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setLimit((current) => current + PAGE_SIZE)}
          >
            Mostra altri
          </Button>

          <p aria-live="polite" className="text-xs text-muted-foreground">
            {visible.length} di {items.length}
          </p>
        </div>
      )}
    </>
  );
}
