"use client";

import type { EngineeringFact } from "@/lib/contracts";
import { FACT_PREDICATE_LABELS } from "@/lib/contracts";
import {
  FACT_STATUS_TONES,
  PREDICATE_DESCRIPTIONS,
  entityLabel,
  type StageStatus,
} from "@/lib/workspace";

import ArtefactButton from "./ArtefactButton";
import ExplorerList from "./ExplorerList";
import StateBadge from "./StateBadge";

interface FactExplorerProps {
  facts: readonly EngineeringFact[];
  status: StageStatus;
  selectedKey: string | null;
  onSelect: (factKey: string) => void;
  entityLabels: ReadonlyMap<string, string>;
}

/**
 * The structural associations.
 *
 * Each row shows the canonical predicate in mono type **and** what it
 * asserts. The two are never swapped: `HAS_ASSOCIATED_QUANTITY` says two
 * entities appeared together on a line, and a UI that rendered that as
 * "potenza nominale" would put an engineering claim on screen that no
 * rule in this system has made.
 */
export default function FactExplorer({
  facts,
  status,
  selectedKey,
  onSelect,
  entityLabels,
}: FactExplorerProps) {
  return (
    <div className="space-y-4">
      <p className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs leading-5 text-slate-700">
        {PREDICATE_DESCRIPTIONS.has_associated_quantity}
      </p>

      <ExplorerList
        items={facts}
        keyOf={(fact) => fact.fact_key}
        status={status}
        noun="fatti"
        label="Fatti di ingegneria"
        render={(fact) => {
          const subject = entityLabel(
            entityLabels,
            fact.subject_entity_key,
          );
          const object = entityLabel(entityLabels, fact.object_entity_key);

          return (
            <ArtefactButton
              selected={fact.fact_key === selectedKey}
              onSelect={() => onSelect(fact.fact_key)}
              label={`Fatto: ${subject} ${FACT_PREDICATE_LABELS[fact.predicate]} ${object}`}
            >
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-sm font-semibold text-foreground">
                  {subject}
                </span>

                <span className="font-mono text-xs uppercase tracking-wide text-sky-700">
                  {fact.predicate}
                </span>

                <span className="font-mono text-sm font-semibold text-foreground">
                  {object}
                </span>

                <StateBadge
                  tone={FACT_STATUS_TONES[fact.status]}
                  value={fact.status}
                />
              </span>

              <span className="mt-1 block text-xs text-muted-foreground">
                {`Associazione strutturale · ${fact.support.length} evidenze di supporto · `}
                <span className="font-mono">
                  {fact.construction_rule_id}@
                  {fact.construction_rule_version}
                </span>
              </span>
            </ArtefactButton>
          );
        }}
      />
    </div>
  );
}
