import type { StageStatus } from "@/lib/workspace";
import { TONE_DESCRIPTIONS } from "@/lib/workspace";

import StateBadge from "./StateBadge";

interface StageStatusNoticeProps {
  status: StageStatus;
  /** What this stage produces, e.g. "osservazioni". */
  noun: string;
}

/**
 * Why a list has nothing in it.
 *
 * The three answers are kept apart on purpose, because collapsing them
 * is how a UI starts lying about a deterministic pipeline:
 *
 * - **non eseguito** - the stage has produced nothing yet
 * - **vuoto** - it ran and found nothing, which is a valid answer
 * - **fallito** - the read failed, and what exists is unknown
 */
export default function StageStatusNotice({
  status,
  noun,
}: StageStatusNoticeProps) {
  if (status.availability === "available") {
    return null;
  }

  const tone =
    status.availability === "failed"
      ? "failed"
      : status.availability === "empty"
        ? "empty"
        : "unrun";

  const headline =
    status.availability === "failed"
      ? `Impossibile leggere ${noun}.`
      : status.availability === "empty"
        ? `Lo stage è stato eseguito e non ha trovato ${noun}.`
        : `Lo stage non è ancora stato eseguito: non esistono ${noun}.`;

  return (
    <div
      role={status.availability === "failed" ? "alert" : undefined}
      className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-6"
    >
      <StateBadge tone={tone} />

      <p className="mt-3 text-sm font-medium text-foreground">
        {headline}
      </p>

      <p className="mt-1 text-sm leading-6 text-muted-foreground">
        {status.error ?? TONE_DESCRIPTIONS[tone]}
      </p>
    </div>
  );
}
