import {
  REVIEW_APPLICABILITY_DESCRIPTIONS,
  REVIEW_APPLICABILITY_LABELS,
  REVIEW_DECISION_DESCRIPTIONS,
  REVIEW_DECISION_LABELS,
  type ReviewApplicability,
  type ReviewDecision,
} from "@/lib/contracts";

/**
 * Colour, glyph and word for each review state - the same three-channel
 * treatment the pipeline states use, for the same reason: none of these
 * distinctions may depend on colour alone.
 *
 * **`approved` is not green.** Green reads as "correct", and an approval
 * is an engineer's judgement about one interpretation, not a verdict that
 * the pipeline was right. The palette here says *decided*, not *passed*.
 */
const DECISION_STYLES: Record<
  ReviewDecision,
  { classes: string; mark: string }
> = {
  approved: {
    classes: "border-sky-300 bg-sky-50 text-sky-900",
    mark: "◆",
  },
  rejected: {
    classes: "border-rose-300 bg-rose-50 text-rose-900",
    mark: "⊗",
  },
  needs_investigation: {
    classes: "border-amber-300 bg-amber-50 text-amber-900",
    mark: "◐",
  },
};

const UNREVIEWED = {
  classes: "border-slate-200 bg-white text-slate-500",
  mark: "·",
};

interface ReviewBadgeProps {
  /** `null` means nobody has reviewed - a state, not a decision. */
  decision: ReviewDecision | null;
  /** Shown alongside when the judgement no longer describes the pipeline. */
  applicability?: ReviewApplicability;
}

export default function ReviewBadge({
  decision,
  applicability,
}: ReviewBadgeProps) {
  const style = decision === null ? UNREVIEWED : DECISION_STYLES[decision];

  const label =
    decision === null
      ? "Mai revisionato"
      : REVIEW_DECISION_LABELS[decision];

  const description =
    decision === null
      ? "Nessun ingegnere ha ancora espresso un giudizio su questa affermazione. Non è né un'approvazione né un rifiuto."
      : REVIEW_DECISION_DESCRIPTIONS[decision];

  const stale =
    applicability !== undefined && applicability !== "applies";

  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <span
        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${style.classes}`}
        title={description}
      >
        <span aria-hidden="true">{style.mark}</span>
        {label}
        <span className="sr-only">{` — ${description}`}</span>
      </span>

      {stale && applicability !== undefined && (
        <span
          className="inline-flex items-center gap-1.5 rounded-full border border-violet-300 bg-violet-50 px-2.5 py-0.5 text-xs font-medium text-violet-900"
          title={REVIEW_APPLICABILITY_DESCRIPTIONS[applicability]}
        >
          <span aria-hidden="true">⟳</span>
          {REVIEW_APPLICABILITY_LABELS[applicability]}
          <span className="sr-only">
            {` — ${REVIEW_APPLICABILITY_DESCRIPTIONS[applicability]}`}
          </span>
        </span>
      )}
    </span>
  );
}
