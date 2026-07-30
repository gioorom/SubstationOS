"use client";

import type { SelectionKind } from "@/lib/workspace";
import { SELECTION_KIND_LABELS } from "@/lib/workspace";

interface ChainStepProps {
  kind: SelectionKind;
  artefactKey: string;
  /** What to read - the entity's label, the observed text, the predicate. */
  title: string;
  detail?: string;
  /** `false` when the reference resolved to no loaded artefact. */
  resolved: boolean;
  onSelect: () => void;
}

/**
 * One link of a support chain, as a control.
 *
 * The chain is a **list of buttons with text**, not a diagram: every
 * step names its kind, its key and what it says, so the relationship
 * survives a screen reader and a monochrome print. No connector line
 * carries information that the text does not.
 *
 * An unresolved link is rendered, disabled, and says why. Dropping it
 * would hide the one thing an engineer most needs to see - that a claim
 * cites something which is not there.
 */
export default function ChainStep({
  kind,
  artefactKey,
  title,
  detail,
  resolved,
  onSelect,
}: ChainStepProps) {
  if (!resolved) {
    return (
      <div className="rounded-xl border border-dashed border-amber-300 bg-amber-50 px-3 py-2">
        <p className="text-xs font-medium uppercase tracking-wide text-amber-800">
          {SELECTION_KIND_LABELS[kind]} — non disponibile
        </p>

        <p className="mt-1 font-mono text-xs break-all text-amber-900">
          {artefactKey}
        </p>

        <p className="mt-1 text-xs leading-5 text-amber-800">
          La catena di supporto è incompleta: questo riferimento non
          corrisponde ad alcun artefatto caricato. Lo stage che lo
          produrrebbe potrebbe non essere stato eseguito.
        </p>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onSelect}
      className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-left hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <span className="block text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {SELECTION_KIND_LABELS[kind]}
      </span>

      <span className="mt-0.5 block text-sm font-medium text-foreground">
        {title}
      </span>

      {detail !== undefined && (
        <span className="mt-0.5 block text-xs text-muted-foreground">
          {detail}
        </span>
      )}
    </button>
  );
}
