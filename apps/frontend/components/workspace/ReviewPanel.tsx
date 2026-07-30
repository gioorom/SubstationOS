"use client";

import { useCallback, useState } from "react";
import { ClipboardCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useResource } from "@/hooks/useResource";
import { useSession } from "@/hooks/useSession";
import { useStatementReview } from "@/hooks/useStatementReview";
import {
  REVIEW_APPLICABILITY_DESCRIPTIONS,
  REVIEW_REASON_LABELS,
  type ReviewVocabulary,
} from "@/lib/contracts";
import { readReviewVocabulary } from "@/lib/resources/review";

import InspectorField from "./InspectorField";
import ReviewBadge from "./ReviewBadge";
import ReviewDialog from "./ReviewDialog";
import ReviewTimeline from "./ReviewTimeline";

interface ReviewPanelProps {
  documentId: number;
  statementKey: string;
}

/**
 * The one place in the Workspace where an engineer *acts*.
 *
 * Everything else in this screen is read-first inspection; the review
 * panel is the dedicated region where a judgement is recorded, and it
 * stays visually and structurally separate for that reason.
 *
 * The states it distinguishes are not interchangeable:
 *
 * | | |
 * |---|---|
 * | loading | The projection has not answered yet. |
 * | never reviewed | Nobody has judged this. Not an approval, not a rejection. |
 * | approved / rejected / needs investigation | The current decision. |
 * | requires revalidation | The pipeline moved on; the judgement is marked, not discarded. |
 * | orphaned | There is no interpretation to compare against. |
 * | permission denied | Signed in, and not a reviewer. Reading still works. |
 * | failed | The read failed; what exists is unknown. |
 *
 * **Nothing here modifies an engineering artefact**, and there is no
 * control that could: the panel appends a review and re-reads two
 * projections.
 */
export default function ReviewPanel({
  documentId,
  statementKey,
}: ReviewPanelProps) {
  const { identity } = useSession();
  const review = useStatementReview(documentId, statementKey);
  const [open, setOpen] = useState(false);

  const readVocabulary = useCallback(
    (signal: AbortSignal) => readReviewVocabulary(signal),
    [],
  );

  const vocabulary = useResource<ReviewVocabulary>(readVocabulary);

  // The backend is the authority: it answers `403` if the role may not
  // review, and the panel reports that. This only decides whether to
  // *offer* the control, which is presentation.
  const mayReview =
    identity !== null &&
    (identity.role === "engineer" || identity.role === "administrator");

  const current = review.current?.current ?? null;

  return (
    <section
      aria-label="Revisione ingegneristica"
      className="mt-6 rounded-2xl border border-slate-300 bg-slate-50/60 p-4"
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <ClipboardCheck className="h-4 w-4" aria-hidden="true" />
          Revisione ingegneristica
        </h3>

        {!open && mayReview && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setOpen(true)}
          >
            {current === null ? "Registra revisione" : "Aggiorna giudizio"}
          </Button>
        )}
      </header>

      <p className="mt-1 text-xs leading-5 text-muted-foreground">
        Il giudizio di un ingegnere sull&apos;interpretazione prodotta dalla
        pipeline. Non modifica in alcun modo l&apos;affermazione, i fatti,
        le entità o le evidenze.
      </p>

      {review.loading ? (
        <Skeleton className="mt-4 h-16 rounded-xl" />
      ) : review.error !== null ? (
        <p
          role="alert"
          className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {review.error}
        </p>
      ) : (
        <>
          <div className="mt-4">
            <ReviewBadge
              decision={current?.decision ?? null}
              applicability={
                current === null
                  ? undefined
                  : review.current?.applicability
              }
            />
          </div>

          {current !== null &&
            review.current !== null &&
            review.current.applicability !== "applies" && (
              <p
                role="status"
                className="mt-3 rounded-xl border border-violet-300 bg-violet-50 px-3 py-2 text-xs leading-5 text-violet-900"
              >
                {
                  REVIEW_APPLICABILITY_DESCRIPTIONS[
                    review.current.applicability
                  ]
                }
              </p>
            )}

          {review.current?.snapshot_intact === false && (
            <p
              role="alert"
              className="mt-3 rounded-xl border border-red-300 bg-red-50 px-3 py-2 text-xs leading-5 text-red-900"
            >
              L&apos;affermazione ha conservato la propria chiave ma il suo
              supporto è cambiato. Non dovrebbe essere possibile: vale la
              pena indagare prima di fidarsi di questo giudizio.
            </p>
          )}

          {current !== null && (
            <dl className="mt-3">
              <InspectorField label="Motivo">
                {REVIEW_REASON_LABELS[current.reason]}
              </InspectorField>

              <InspectorField label="Revisore">
                {current.reviewer.display_name}
              </InspectorField>

              <InspectorField label="Registrato">
                {new Date(current.recorded_at).toLocaleString("it-IT")}
              </InspectorField>

              <InspectorField label="Regola al momento della revisione">
                <span className="font-mono text-xs">
                  {current.snapshot.semantic_rule_id}@
                  {current.snapshot.semantic_rule_version}
                </span>
              </InspectorField>

              <InspectorField label="Policy semantica">
                <span className="font-mono text-xs">
                  {current.snapshot.semantic_policy_version}
                </span>
              </InspectorField>

              {current.comment !== null && (
                <InspectorField label="Commento">
                  <span className="whitespace-pre-wrap">
                    {current.comment}
                  </span>
                </InspectorField>
              )}
            </dl>
          )}

          {current === null && (
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              Nessun ingegnere ha ancora espresso un giudizio su questa
              affermazione. &ldquo;Interpretato&rdquo; significa prodotto da
              una regola versionata, non verificato da una persona.
            </p>
          )}

          {!mayReview && (
            <p className="mt-3 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs leading-5 text-slate-700">
              Il tuo ruolo consente di leggere le revisioni ma non di
              registrarne.
            </p>
          )}

          {open && (
            <div className="mt-4">
              <ReviewDialog
                vocabulary={vocabulary.data}
                submitting={review.submitting}
                error={review.submitError}
                supersedes={current !== null}
                onCancel={() => setOpen(false)}
                onSubmit={async (input) => {
                  await review.submit(input);
                  setOpen(false);
                }}
              />
            </div>
          )}

          <h4 className="mt-5 mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Cronologia
          </h4>

          <ReviewTimeline
            entries={review.history}
            total={review.historyTotal}
            hasMore={review.hasMoreHistory}
            error={review.historyError}
          />
        </>
      )}
    </section>
  );
}
