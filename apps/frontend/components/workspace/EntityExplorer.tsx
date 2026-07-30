"use client";

import { useMemo, useState } from "react";

import type {
  EngineeringEntity,
  EngineeringEntityType,
} from "@/lib/contracts";
import { ENTITY_TYPES, ENTITY_TYPE_LABELS } from "@/lib/contracts";
import { ENTITY_STATUS_TONES, type StageStatus } from "@/lib/workspace";

import ArtefactButton from "./ArtefactButton";
import ExplorerList from "./ExplorerList";
import StateBadge from "./StateBadge";

interface EntityExplorerProps {
  entities: readonly EngineeringEntity[];
  status: StageStatus;
  selectedKey: string | null;
  onSelect: (entityKey: string) => void;
}

/**
 * The entities, each with the count of observations **it declares**.
 *
 * `evidence_count` and the evidence list both come from the entity
 * record. The Workspace never counts how many observations look like an
 * entity, and never adds one to a group because its text matches.
 */
export default function EntityExplorer({
  entities,
  status,
  selectedKey,
  onSelect,
}: EntityExplorerProps) {
  const [type, setType] = useState<EngineeringEntityType | "">("");

  const filtered = useMemo(
    () =>
      type === ""
        ? entities
        : entities.filter((entity) => entity.entity_type === type),
    [entities, type],
  );

  return (
    <div className="space-y-4">
      <label className="flex w-fit flex-col gap-1 text-xs text-muted-foreground">
        Tipo di entità
        <select
          value={type}
          onChange={(event) =>
            setType(event.target.value as EngineeringEntityType | "")
          }
          className="h-9 rounded-xl border border-input bg-background px-3 text-sm text-foreground"
        >
          <option value="">Tutti</option>
          {ENTITY_TYPES.map((value) => (
            <option key={value} value={value}>
              {ENTITY_TYPE_LABELS[value]}
            </option>
          ))}
        </select>
      </label>

      <ExplorerList
        items={filtered}
        keyOf={(entity) => entity.entity_key}
        status={status}
        noun="entità"
        label="Entità di ingegneria"
        filtered={type !== ""}
        render={(entity) => (
          <ArtefactButton
            selected={entity.entity_key === selectedKey}
            onSelect={() => onSelect(entity.entity_key)}
            label={`Entità ${entity.label}, ${ENTITY_TYPE_LABELS[entity.entity_type]}, ${entity.evidence_count} osservazioni`}
          >
            <span className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm font-semibold text-foreground">
                {entity.label}
              </span>

              <StateBadge
                tone={ENTITY_STATUS_TONES[entity.status]}
                value={entity.status}
              />

              <span className="rounded-full border border-slate-200 px-2 py-0.5 text-xs text-slate-600">
                {ENTITY_TYPE_LABELS[entity.entity_type]}
              </span>
            </span>

            <span className="mt-1 block text-xs text-muted-foreground">
              {`${entity.evidence_count} ${entity.evidence_count === 1 ? "osservazione dichiarata" : "osservazioni dichiarate"}`}
              {" · "}
              <span className="font-mono">
                {entity.resolution_rule_id}@{entity.resolution_rule_version}
              </span>
            </span>
          </ArtefactButton>
        )}
      />
    </div>
  );
}
