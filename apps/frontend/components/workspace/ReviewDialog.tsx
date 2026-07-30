"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  REVIEW_DECISIONS,
  REVIEW_DECISION_DESCRIPTIONS,
  REVIEW_DECISION_LABELS,
  REVIEW_REASON_LABELS,
  type ReviewDecision,
  type ReviewReason,
  type ReviewVocabulary,
} from "@/lib/contracts";

interface ReviewDialogProps {
  /** Served by the backend, so the pairing can never disagree with it. */
  vocabulary: ReviewVocabulary | null;
  submitting: boolean;
  error: string | null;
  onSubmit: (input: {
    decision: ReviewDecision;
    reason: ReviewReason;
    comment: string | null;
  }) => Promise<void>;
  onCancel: () => void;
  /** True when a judgement already exists; the copy says what happens. */
  supersedes: boolean;
}

/**
 * Recording a judgement.
 *
 * Three things this form is careful about:
 *
 * - **The reasons offered depend on the decision**, and the list comes
 *   from the backend. A hard-coded pairing would eventually offer a
 *   combination the API refuses, and the reviewer would find out on
 *   submit.
 * - **The confirmation says what will actually happen.** Recording a
 *   second judgement does not overwrite the first; it appends, and the
 *   earlier one stays readable. Copy that said "replace" would describe a
 *   system this is not.
 * - **Nothing here claims the pipeline was wrong.** The decision labels
 *   are `Approvato` / `Respinto` / `Da approfondire`, never
 *   `Corretto` / `Errato`.
 */
export default function ReviewDialog({
  vocabulary,
  submitting,
  error,
  onSubmit,
  onCancel,
  supersedes,
}: ReviewDialogProps) {
  const [decision, setDecision] = useState<ReviewDecision>("approved");
  const [reason, setReason] = useState<ReviewReason | "">("");
  const [comment, setComment] = useState("");

  const reasons = useMemo(
    () => vocabulary?.reasons_by_decision[decision] ?? [],
    [vocabulary, decision],
  );

  const commentRequired =
    (vocabulary?.decisions_requiring_comment ?? []).includes(decision) ||
    reason === "other";

  const canSubmit =
    reason !== "" &&
    (!commentRequired || comment.trim() !== "") &&
    !submitting;

  return (
    <form
      aria-label="Registra una revisione"
      className="space-y-4 rounded-2xl border border-slate-300 bg-white p-4"
      onSubmit={(event) => {
        event.preventDefault();

        if (reason === "") {
          return;
        }

        void onSubmit({
          decision,
          reason,
          comment: comment.trim() === "" ? null : comment.trim(),
        }).catch(() => undefined);
      }}
    >
      <fieldset>
        <legend className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Giudizio
        </legend>

        <div className="mt-2 space-y-2">
          {REVIEW_DECISIONS.map((value) => (
            <label
              key={value}
              className="flex items-start gap-2 text-sm text-foreground"
            >
              <input
                type="radio"
                name="decision"
                value={value}
                checked={decision === value}
                onChange={() => {
                  setDecision(value);
                  // The reasons on offer change with the decision, so a
                  // selection made under the previous one is cleared
                  // rather than silently carried into a pairing the
                  // backend would refuse.
                  setReason("");
                }}
                className="mt-1"
              />

              <span>
                <span className="font-medium">
                  {REVIEW_DECISION_LABELS[value]}
                </span>

                <span className="mt-0.5 block text-xs leading-5 text-muted-foreground">
                  {REVIEW_DECISION_DESCRIPTIONS[value]}
                </span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <label className="block text-sm font-medium text-foreground">
        Motivo
        <select
          required
          value={reason}
          onChange={(event) =>
            setReason(event.target.value as ReviewReason | "")
          }
          className="mt-1 h-9 w-full rounded-xl border border-input bg-background px-3 text-sm"
        >
          <option value="">Seleziona un motivo…</option>
          {reasons.map((value) => (
            <option key={value} value={value}>
              {REVIEW_REASON_LABELS[value]}
            </option>
          ))}
        </select>
      </label>

      <label className="block text-sm font-medium text-foreground">
        {commentRequired ? "Commento (obbligatorio)" : "Commento"}
        <textarea
          rows={3}
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder="Cosa hai verificato, e cosa hai visto."
          className="mt-1 w-full rounded-xl border border-input bg-background px-3 py-2 text-sm"
        />
        <span className="mt-1 block text-xs font-normal text-muted-foreground">
          Testo semplice. Non viene interpretato come markup.
        </span>
      </label>

      {error !== null && (
        <p
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {error}
        </p>
      )}

      <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-700">
        {supersedes
          ? "Questo giudizio si aggiunge alla cronologia e diventa quello corrente. Il giudizio precedente non viene modificato né cancellato: resta leggibile nella cronologia."
          : "Il giudizio viene registrato in modo permanente e attribuito alla tua identità. Non modifica in alcun modo gli artefatti della pipeline."}
      </p>

      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={!canSubmit}>
          {submitting ? "Registrazione…" : "Registra revisione"}
        </Button>

        <Button
          type="button"
          variant="ghost"
          onClick={onCancel}
          disabled={submitting}
        >
          Annulla
        </Button>
      </div>
    </form>
  );
}
