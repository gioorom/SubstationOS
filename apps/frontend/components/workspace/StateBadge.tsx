import {
  TONE_CLASSES,
  TONE_DESCRIPTIONS,
  TONE_LABELS,
  TONE_MARKS,
  type ArtefactTone,
} from "@/lib/workspace";

interface StateBadgeProps {
  tone: ArtefactTone;
  /**
   * The canonical value this badge stands for, when it differs from the
   * tone's own name - a fact's `constructed`, an entity's `resolved`.
   * Shown verbatim so the backend's word is never replaced by ours.
   */
  value?: string;
}

/**
 * One governed state, shown so it can be told apart without colour.
 *
 * Colour, a glyph and a word all carry the distinction, and the tooltip
 * carries the definition. `interpreted` is not green anywhere in this
 * application: green reads as approval, and no artefact in this
 * milestone has been approved by anyone.
 */
export default function StateBadge({ tone, value }: StateBadgeProps) {
  const label = value ?? TONE_LABELS[tone];

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]}`}
      title={TONE_DESCRIPTIONS[tone]}
    >
      <span aria-hidden="true">{TONE_MARKS[tone]}</span>
      {label}
      <span className="sr-only">
        {` (${TONE_LABELS[tone]}: ${TONE_DESCRIPTIONS[tone]})`}
      </span>
    </span>
  );
}
