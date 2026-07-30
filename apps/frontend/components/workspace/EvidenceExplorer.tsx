"use client";

import { useMemo, useState } from "react";

import type { EngineeringEvidence, EvidenceType } from "@/lib/contracts";
import { EVIDENCE_TYPE_LABELS, EVIDENCE_TYPES } from "@/lib/contracts";
import {
  EVIDENCE_STATUS_TONES,
  describeLocation,
  locationOfProvenance,
  type StageStatus,
} from "@/lib/workspace";

import ArtefactButton from "./ArtefactButton";
import ExplorerList from "./ExplorerList";
import StateBadge from "./StateBadge";

interface EvidenceExplorerProps {
  documentId: number;
  evidence: readonly EngineeringEvidence[];
  status: StageStatus;
  selectedKey: string | null;
  onSelect: (evidenceKey: string) => void;
  /** Pages any observation cites, for the page filter. */
  pages: readonly number[];
}

/**
 * The observations, filtered by closed contract vocabularies.
 *
 * The type and status filters are the backend's own enums - the
 * frontend offers no category the extraction rules do not produce, and
 * classifies nothing itself. The text box searches the **loaded set**
 * only, over `observed_text` and the canonical line the backend already
 * supplied; it produces no new grouping and is never used to decide that
 * two observations belong together.
 */
export default function EvidenceExplorer({
  documentId,
  evidence,
  status,
  selectedKey,
  onSelect,
  pages,
}: EvidenceExplorerProps) {
  const [type, setType] = useState<EvidenceType | "">("");
  const [page, setPage] = useState<number | "">("");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();

    return evidence.filter((item) => {
      if (type !== "" && item.evidence_type !== type) {
        return false;
      }

      if (page !== "" && item.provenance.page_number !== page) {
        return false;
      }

      if (needle === "") {
        return true;
      }

      return (
        item.observed_text.toLowerCase().includes(needle) ||
        item.provenance.source_text.toLowerCase().includes(needle)
      );
    });
  }, [evidence, type, page, search]);

  const filtersApplied = type !== "" || page !== "" || search.trim() !== "";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Tipo di evidenza
          <select
            value={type}
            onChange={(event) =>
              setType(event.target.value as EvidenceType | "")
            }
            className="h-9 rounded-xl border border-input bg-background px-3 text-sm text-foreground"
          >
            <option value="">Tutti</option>
            {EVIDENCE_TYPES.map((value) => (
              <option key={value} value={value}>
                {EVIDENCE_TYPE_LABELS[value]}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Pagina
          <select
            value={page}
            onChange={(event) =>
              setPage(
                event.target.value === ""
                  ? ""
                  : Number(event.target.value),
              )
            }
            className="h-9 rounded-xl border border-input bg-background px-3 text-sm text-foreground"
          >
            <option value="">Tutte</option>
            {pages.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-1 flex-col gap-1 text-xs text-muted-foreground">
          Cerca nel testo osservato
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="TR1, 630 kVA…"
            className="h-9 rounded-xl border border-input bg-background px-3 text-sm text-foreground"
          />
        </label>
      </div>

      <p className="text-xs text-muted-foreground">
        La ricerca opera sugli artefatti già caricati e non crea
        classificazioni: tipo e stato restano quelli dichiarati dalle
        regole di estrazione.
      </p>

      <ExplorerList
        items={filtered}
        keyOf={(item) => item.evidence_key}
        status={status}
        noun="osservazioni"
        label="Evidenze di ingegneria"
        filtered={filtersApplied}
        render={(item) => {
          const location = locationOfProvenance(
            documentId,
            item.provenance,
          );

          return (
            <ArtefactButton
              selected={item.evidence_key === selectedKey}
              onSelect={() => onSelect(item.evidence_key)}
              label={`Evidenza ${item.observed_text}, ${EVIDENCE_TYPE_LABELS[item.evidence_type]}, ${describeLocation(location)}`}
            >
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-sm font-semibold text-foreground">
                  {item.observed_text}
                </span>

                <StateBadge
                  tone={EVIDENCE_STATUS_TONES[item.status]}
                  value={item.status}
                />

                <span className="rounded-full border border-slate-200 px-2 py-0.5 text-xs text-slate-600">
                  {EVIDENCE_TYPE_LABELS[item.evidence_type]}
                </span>
              </span>

              <span className="mt-1 block text-xs text-muted-foreground">
                {describeLocation(location)}
                {" · "}
                <span className="font-mono">
                  {item.rule_id}@{item.rule_version}
                </span>
              </span>

              <span className="mt-1 block truncate text-xs italic text-slate-500">
                {item.provenance.source_text}
              </span>
            </ArtefactButton>
          );
        }}
      />
    </div>
  );
}
