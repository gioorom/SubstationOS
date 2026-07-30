"use client";

import { Network } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useSession } from "@/hooks/useSession";
import { useStatementPromotion } from "@/hooks/useStatementPromotion";
import {
  GRAPH_EDGE_KIND_LABELS,
  GRAPH_RETIREMENT_REASON_LABELS,
  PROMOTION_REFUSAL_LABELS,
} from "@/lib/contracts";

import InspectorField from "./InspectorField";

interface GraphPanelProps {
  documentId: number;
  statementKey: string;
}

/**
 * Whether this statement is in the governed Knowledge Graph.
 *
 * The Workspace remains the **inspection** interface; the graph is an
 * additional projection of the same knowledge, and this panel reports
 * it. It shows the graph identity, the promotion metadata and the
 * provenance the graph recorded - which is the same provenance the
 * panels above show, and that is the point: an answer in the graph and
 * the artefact it came from are traceable to each other in both
 * directions.
 *
 * The states it distinguishes are not interchangeable:
 *
 * | | |
 * |---|---|
 * | loading | The projection has not answered yet. |
 * | promoted | Governed knowledge, current, with a graph identity. |
 * | not promoted, with a reason | The reason is the content, not the absence. |
 * | historical | Was governed; retired, with the reason it was. |
 * | permission denied | Signed in, and not permitted to promote. |
 * | failed | The read failed; what the graph holds is unknown. |
 */
export default function GraphPanel({
  documentId,
  statementKey,
}: GraphPanelProps) {
  const { identity } = useSession();
  const promotion = useStatementPromotion(documentId, statementKey);

  // The backend is the authority and answers `403`; this only decides
  // whether to offer the control, which is presentation.
  const mayPromote =
    identity !== null &&
    (identity.role === "engineer" || identity.role === "administrator");

  const state = promotion.promotion;
  const edge = state?.edge ?? null;

  return (
    <section
      aria-label="Grafo della conoscenza governata"
      className="mt-4 rounded-2xl border border-slate-300 bg-white/70 p-4"
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Network className="h-4 w-4" aria-hidden="true" />
          Grafo della conoscenza
        </h3>

        {mayPromote && state !== null && !state.promoted && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={promotion.promoting}
            onClick={() => {
              void promotion.promote().catch(() => undefined);
            }}
          >
            {promotion.promoting ? "Riconciliazione…" : "Riconcilia"}
          </Button>
        )}
      </header>

      <p className="mt-1 text-xs leading-5 text-muted-foreground">
        Il grafo è una proiezione: contiene solo affermazioni approvate da
        un ingegnere e ancora attuali. Non sostituisce la pipeline né la
        revisione, e può sempre essere ricostruito da entrambe.
      </p>

      {promotion.loading ? (
        <Skeleton className="mt-4 h-12 rounded-xl" />
      ) : promotion.error !== null ? (
        <p
          role="alert"
          className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {promotion.error}
        </p>
      ) : state === null ? null : (
        <>
          <div className="mt-4">
            <PromotionBadge promoted={state.promoted} />
          </div>

          {!state.promoted && state.refusal !== null && (
            <p className="mt-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-700">
              {PROMOTION_REFUSAL_LABELS[state.refusal]}
            </p>
          )}

          {edge !== null && edge.state !== "active" && (
            <p
              role="status"
              className="mt-3 rounded-xl border border-violet-300 bg-violet-50 px-3 py-2 text-xs leading-5 text-violet-900"
            >
              {edge.retirement === null
                ? "Questa conoscenza non è più attuale."
                : `Ritirata dal grafo: ${
                    GRAPH_RETIREMENT_REASON_LABELS[edge.retirement.reason]
                  }. Il record resta leggibile con la sua provenienza.`}
            </p>
          )}

          {promotion.promoteError !== null && (
            <p
              role="alert"
              className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
            >
              {promotion.promoteError}
            </p>
          )}

          {edge !== null && (
            <dl className="mt-3">
              <InspectorField label="Relazione governata">
                {GRAPH_EDGE_KIND_LABELS[edge.kind]}{" "}
                <span className="font-mono text-xs text-muted-foreground">
                  ({edge.kind})
                </span>
              </InspectorField>

              <InspectorField
                label="Identità nel grafo"
                copyValue={edge.edge_id}
              >
                <span className="font-mono text-xs break-all">
                  {edge.edge_id}
                </span>
              </InspectorField>

              <InspectorField label="Autorizzata da">
                {edge.provenance.reviewer_display_name}
                {" · "}
                <span className="text-xs text-muted-foreground">
                  {`revisione ${edge.provenance.review_id}`}
                </span>
              </InspectorField>

              <InspectorField label="Regola al momento della promozione">
                <span className="font-mono text-xs">
                  {edge.provenance.semantic_rule_id}@
                  {edge.provenance.semantic_rule_version}
                </span>
              </InspectorField>

              <InspectorField label="Nel grafo dal">
                {new Date(edge.created_at).toLocaleString("it-IT")}
              </InspectorField>
            </dl>
          )}

          {!mayPromote && (
            <p className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs leading-5 text-slate-700">
              Il tuo ruolo consente di leggere il grafo ma non di
              promuovervi conoscenza.
            </p>
          )}
        </>
      )}
    </section>
  );
}

/**
 * "In the graph" or not.
 *
 * Deliberately **not** green for promoted: the badge says *governed*,
 * not *correct*. What makes knowledge governed is that an engineer
 * approved it, which the panel states directly rather than implying with
 * a colour.
 */
function PromotionBadge({ promoted }: { promoted: boolean }) {
  if (promoted) {
    return (
      <span
        className="inline-flex items-center gap-1.5 rounded-full border border-indigo-300 bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-900"
        title="Questa affermazione è conoscenza governata: approvata da un ingegnere e ancora attuale."
      >
        <span aria-hidden="true">◈</span>
        Nel grafo
      </span>
    );
  }

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-0.5 text-xs font-medium text-slate-500"
      title="Questa affermazione non è conoscenza governata."
    >
      <span aria-hidden="true">·</span>
      Non nel grafo
    </span>
  );
}
