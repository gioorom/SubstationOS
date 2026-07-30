"use client";

import { useId } from "react";

import type { StageStatus } from "@/lib/workspace";

import StateBadge from "./StateBadge";

export const EXPLORER_TABS = [
  "semantic",
  "fact",
  "entity",
  "evidence",
  "diagnostic",
] as const;

export type ExplorerTab = (typeof EXPLORER_TABS)[number];

export const EXPLORER_TAB_LABELS: Record<ExplorerTab, string> = {
  semantic: "Significato",
  fact: "Fatti",
  entity: "Entità",
  evidence: "Evidenze",
  diagnostic: "Diagnostiche",
};

interface EngineeringExplorerProps {
  tab: ExplorerTab;
  onTabChange: (tab: ExplorerTab) => void;
  /** Per-tab availability, so a tab never claims a count it does not have. */
  statuses: Record<ExplorerTab, StageStatus>;
  children: React.ReactNode;
}

/**
 * The engineering region of the Workspace.
 *
 * Ordered from meaning back towards observation - `Significato` first,
 * `Evidenze` last - because that is the direction an engineer validates
 * in: read the claim, then ask what it rests on.
 *
 * Each tab carries its own count and its own state. A tab whose stage
 * has not run shows `non eseguito` rather than a zero, because those are
 * different documents.
 */
export default function EngineeringExplorer({
  tab,
  onTabChange,
  statuses,
  children,
}: EngineeringExplorerProps) {
  const panelId = useId();

  return (
    <section
      aria-label="Esploratore di ingegneria"
      className="flex min-h-0 flex-col rounded-3xl border border-slate-200 bg-white/80"
    >
      <div
        role="tablist"
        aria-label="Artefatti di ingegneria"
        className="flex flex-wrap gap-1 border-b border-slate-200 px-3 py-2"
      >
        {EXPLORER_TABS.map((value) => {
          const status = statuses[value];

          return (
            <button
              key={value}
              type="button"
              role="tab"
              id={`${panelId}-tab-${value}`}
              aria-selected={tab === value}
              aria-controls={panelId}
              onClick={() => onTabChange(value)}
              className={`flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                tab === value
                  ? "bg-slate-900 text-white"
                  : "text-muted-foreground hover:bg-slate-100 hover:text-foreground"
              }`}
            >
              {EXPLORER_TAB_LABELS[value]}

              <span className="tabular-nums opacity-80">
                {status.availability === "unrun"
                  ? "—"
                  : status.availability === "failed"
                    ? "!"
                    : (status.count ?? 0)}
              </span>
            </button>
          );
        })}
      </div>

      <div className="border-b border-slate-200 px-4 py-2">
        <StageSummary status={statuses[tab]} />
      </div>

      <div
        role="tabpanel"
        id={panelId}
        aria-labelledby={`${panelId}-tab-${tab}`}
        className="min-h-0 flex-1 overflow-auto px-4 py-4"
      >
        {children}
      </div>
    </section>
  );
}

function StageSummary({ status }: { status: StageStatus }) {
  const tone =
    status.availability === "failed"
      ? "failed"
      : status.availability === "unrun"
        ? "unrun"
        : status.availability === "empty"
          ? "empty"
          : "interpreted";

  return (
    <p className="flex items-center gap-2 text-xs text-muted-foreground">
      <StateBadge tone={tone} />

      {status.availability === "available" &&
        `${status.count} artefatti prodotti da regole deterministiche.`}
      {status.availability === "empty" &&
        "Lo stage è stato eseguito e non ha prodotto artefatti."}
      {status.availability === "unrun" &&
        "Lo stage non è ancora stato eseguito."}
      {status.availability === "failed" && status.error}
    </p>
  );
}
