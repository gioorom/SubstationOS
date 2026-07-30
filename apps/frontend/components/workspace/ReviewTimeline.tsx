import {
  REVIEW_APPLICABILITY_LABELS,
  REVIEW_REASON_LABELS,
  type ReviewHistoryEntry,
} from "@/lib/contracts";

import ReviewBadge from "./ReviewBadge";

interface ReviewTimelineProps {
  entries: readonly ReviewHistoryEntry[];
  total: number;
  hasMore: boolean;
  error: string | null;
}

/**
 * Every judgement ever passed, newest first.
 *
 * `superseded` comes from the backend, which derives it from position in
 * the ordered history. Nothing here computes it: a frontend that decided
 * which review was current would be a second account of the record.
 *
 * An ordered list rather than a diagram - each entry names its decision,
 * its reason, its reviewer and its date in text, so the history survives
 * a screen reader and a monochrome print.
 */
export default function ReviewTimeline({
  entries,
  total,
  hasMore,
  error,
}: ReviewTimelineProps) {
  if (error !== null) {
    return (
      <p
        role="alert"
        className="rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900"
      >
        {`Cronologia non disponibile: ${error} Il giudizio corrente resta visibile qui sopra.`}
      </p>
    );
  }

  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nessun giudizio registrato per questa affermazione.
      </p>
    );
  }

  return (
    <>
      <ol aria-label="Cronologia delle revisioni" className="space-y-2">
        {entries.map((entry) => (
          <li
            key={entry.review.review_id}
            className={`rounded-xl border px-3 py-2 ${
              entry.superseded
                ? "border-slate-200 bg-slate-50"
                : "border-slate-300 bg-white"
            }`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <ReviewBadge decision={entry.review.decision} />

              {entry.superseded && (
                <span className="rounded-full border border-slate-300 px-2 py-0.5 text-xs text-slate-600">
                  Superato
                </span>
              )}

              {entry.applicability !== "applies" && (
                <span className="rounded-full border border-violet-300 bg-violet-50 px-2 py-0.5 text-xs text-violet-900">
                  {REVIEW_APPLICABILITY_LABELS[entry.applicability]}
                </span>
              )}
            </div>

            <p className="mt-1 text-sm text-foreground">
              {REVIEW_REASON_LABELS[entry.review.reason]}
            </p>

            {entry.review.comment !== null && (
              // Rendered as a text node. The backend stores plain text
              // and nothing here interprets it as markup.
              <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                {entry.review.comment}
              </p>
            )}

            <p className="mt-1 text-xs text-muted-foreground">
              {entry.review.reviewer.display_name}
              {" · "}
              {new Date(entry.review.recorded_at).toLocaleString("it-IT")}
              {" · "}
              <span className="font-mono">
                {entry.review.snapshot.semantic_rule_id}@
                {entry.review.snapshot.semantic_rule_version}
              </span>
            </p>
          </li>
        ))}
      </ol>

      {hasMore && (
        <p className="mt-2 text-xs text-muted-foreground">
          {`Mostrati ${entries.length} di ${total} giudizi.`}
        </p>
      )}
    </>
  );
}
