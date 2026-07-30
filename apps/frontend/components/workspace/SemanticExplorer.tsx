"use client";

import type { EngineeringEntity, SemanticStatement } from "@/lib/contracts";
import { SEMANTIC_STATEMENT_LABELS } from "@/lib/contracts";
import {
  SEMANTIC_STATUS_TONES,
  entityLabel,
  type StageStatus,
} from "@/lib/workspace";

import ArtefactButton from "./ArtefactButton";
import ExplorerList from "./ExplorerList";
import StateBadge from "./StateBadge";

interface SemanticExplorerProps {
  statements: readonly SemanticStatement[];
  status: StageStatus;
  selectedKey: string | null;
  onSelect: (statementKey: string) => void;
  entityLabels: ReadonlyMap<string, string>;
  /** Resolves a statement's object entity - where the figure lives. */
  quantityOf: (statement: SemanticStatement) => EngineeringEntity | null;
}

/**
 * The interpreted engineering meaning.
 *
 * For `HAS_RATED_POWER` the value and unit are read **through** the
 * referenced quantity entity - `quantityOf` resolves the reference, and
 * the figure is displayed from `entity.quantity`. The statement itself
 * carries no value and the Workspace does not give it one: a copy would
 * be a second source of truth for a rated figure.
 *
 * The wording is careful about what "interpretato" means. A versioned
 * rule produced this statement; no engineer has confirmed it.
 */
export default function SemanticExplorer({
  statements,
  status,
  selectedKey,
  onSelect,
  entityLabels,
  quantityOf,
}: SemanticExplorerProps) {
  return (
    <div className="space-y-4">
      <p className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs leading-5 text-slate-700">
        &ldquo;Interpretato&rdquo; significa prodotto da una regola
        deterministica e versionata. Non significa verificato o approvato
        da un ingegnere: in questo milestone la validazione umana non
        esiste ancora.
      </p>

      <ExplorerList
        items={statements}
        keyOf={(statement) => statement.statement_key}
        status={status}
        noun="affermazioni semantiche"
        label="Affermazioni semantiche"
        render={(statement) => {
          const subject = entityLabel(
            entityLabels,
            statement.subject_entity_key,
          );
          const quantity = quantityOf(statement);

          return (
            <ArtefactButton
              selected={statement.statement_key === selectedKey}
              onSelect={() => onSelect(statement.statement_key)}
              label={`${subject} ${SEMANTIC_STATEMENT_LABELS[statement.statement_type]} ${quantity?.label ?? statement.object_entity_key}`}
            >
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-sm font-semibold text-foreground">
                  {subject}
                </span>

                <span className="font-mono text-xs uppercase tracking-wide text-sky-700">
                  {statement.statement_type}
                </span>

                <span className="text-sm font-semibold text-foreground">
                  {quantity === null ? (
                    <span className="font-mono text-amber-700">
                      {statement.object_entity_key}
                    </span>
                  ) : (
                    <QuantityValue entity={quantity} />
                  )}
                </span>

                <StateBadge
                  tone={SEMANTIC_STATUS_TONES[statement.status]}
                  value={statement.status}
                />
              </span>

              <span className="mt-1 block text-xs text-muted-foreground">
                {`${SEMANTIC_STATEMENT_LABELS[statement.statement_type]} · ${statement.supporting_fact_keys.length} fatto/i a supporto · `}
                <span className="font-mono">
                  {statement.semantic_rule_id}@
                  {statement.semantic_rule_version}
                </span>
              </span>

              {quantity === null && (
                <span className="mt-1 block text-xs text-amber-700">
                  L&apos;entità grandezza referenziata non è disponibile:
                  il valore non può essere risolto e non viene inventato.
                </span>
              )}
            </ArtefactButton>
          );
        }}
      />
    </div>
  );
}

/**
 * The figure, from the quantity entity that owns it.
 *
 * `value` arrives as a string because the backend serialises `Decimal`
 * as one. It is rendered as it arrived: parsing it into a JS number to
 * format it would be the one way a rated value could acquire a rounding
 * error on this screen.
 */
function QuantityValue({ entity }: { entity: EngineeringEntity }) {
  if (entity.quantity === null) {
    return <span className="font-mono">{entity.label}</span>;
  }

  return (
    <span className="font-mono tabular-nums">
      {entity.quantity.value} {entity.quantity.unit}
    </span>
  );
}
