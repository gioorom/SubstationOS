"use client";

import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Lock,
  Loader2,
  Play,
  RefreshCw,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import type { StageState, StageView } from "@/hooks/usePipeline";

interface PipelineStageCardProps {
  stage: StageView;
  index: number;
  onRun: () => void;
  onInspect?: () => void;
  inspectLabel?: string;
}

const STATE_LABELS: Record<StageState, string> = {
  blocked: "In attesa dello stage precedente",
  ready: "Pronto per l'esecuzione",
  running: "Esecuzione in corso",
  produced: "Completato",
  empty: "Completato — nessun artefatto prodotto",
  failed: "Non riuscito",
};

const STATE_STYLES: Record<StageState, string> = {
  blocked: "border-slate-200 bg-slate-50 text-slate-500",
  ready: "border-blue-200 bg-blue-50 text-blue-700",
  running: "border-blue-300 bg-blue-100 text-blue-800",
  produced: "border-emerald-200 bg-emerald-50 text-emerald-700",
  empty: "border-amber-200 bg-amber-50 text-amber-700",
  failed: "border-red-200 bg-red-50 text-red-700",
};

function StateIcon({ state }: { state: StageState }) {
  const className = "h-4 w-4";

  if (state === "running") {
    return <Loader2 className={`${className} animate-spin`} />;
  }

  if (state === "produced") {
    return <CheckCircle2 className={className} />;
  }

  if (state === "empty") {
    return <AlertTriangle className={className} />;
  }

  if (state === "failed") {
    return <XCircle className={className} />;
  }

  if (state === "blocked") {
    return <Lock className={className} />;
  }

  return <CircleDashed className={className} />;
}

export default function PipelineStageCard({
  stage,
  index,
  onRun,
  onInspect,
  inspectLabel = "Ispeziona",
}: PipelineStageCardProps) {
  const runnable = stage.id !== "uploaded" && stage.canRun;
  const alreadyRun = stage.count !== null;

  return (
    <article
      data-stage={stage.id}
      data-state={stage.state}
      className="rounded-3xl border border-white/70 bg-white/72 p-6 shadow-[0_18px_45px_rgba(15,23,42,0.05)] backdrop-blur-2xl"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Stage {index + 1}
          </p>

          <h3 className="mt-1 text-lg font-semibold text-foreground">
            {stage.label}
          </h3>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            {stage.description}
          </p>
        </div>

        <span
          className={[
            "inline-flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold",
            STATE_STYLES[stage.state],
          ].join(" ")}
        >
          <StateIcon state={stage.state} />
          {STATE_LABELS[stage.state]}
        </span>
      </div>

      <dl className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            Artefatti
          </dt>

          <dd className="mt-1 text-sm font-semibold text-foreground">
            {stage.countLabel ?? "—"}
          </dd>
        </div>

        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            Timestamp
          </dt>

          {/*
            Most pipeline artefacts carry no timestamp on purpose:
            excluding it is what makes two runs compare equal and
            determinism assertable. Saying so beats showing a plausible
            date the API never sent.
          */}
          <dd className="mt-1 text-sm text-foreground">
            {stage.timestamp
              ? new Date(stage.timestamp).toLocaleString("it-IT")
              : "Non esposto (artefatto deterministico)"}
          </dd>
        </div>

        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            Riuso
          </dt>

          <dd className="mt-1 text-sm text-foreground">
            {stage.reused
              ? "Artefatto esistente riutilizzato"
              : alreadyRun
                ? "Prodotto da questa sorgente"
                : "—"}
          </dd>
        </div>

        <div>
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            Ambiguità
          </dt>

          <dd className="mt-1 text-sm text-foreground">
            {stage.ambiguities === null
              ? "—"
              : stage.ambiguities === 0
                ? "Nessuna"
                : `${stage.ambiguities} dichiarate`}
          </dd>
        </div>
      </dl>

      {stage.versions.length > 0 && (
        <ul className="mt-5 flex flex-wrap gap-2">
          {stage.versions.map((version) => (
            <li
              key={version.label}
              className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600"
            >
              <span className="font-semibold">{version.label}:</span>{" "}
              <span className="font-mono">
                {version.value.length > 24
                  ? `${version.value.slice(0, 12)}…${version.value.slice(-6)}`
                  : version.value}
              </span>
            </li>
          ))}
        </ul>
      )}

      {stage.state === "empty" && (
        <p className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Lo stage è stato eseguito e non ha prodotto artefatti. È una
          risposta valida delle regole, non un errore.
        </p>
      )}

      {stage.error && (
        <p
          role="alert"
          className="mt-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {stage.error}
        </p>
      )}

      {(runnable || (stage.inspectable && onInspect)) && (
        <div className="mt-6 flex flex-wrap gap-3">
          {runnable && (
            <Button
              type="button"
              onClick={onRun}
              disabled={stage.state === "running"}
              variant={alreadyRun ? "outline" : "default"}
            >
              {alreadyRun ? (
                <RefreshCw className="h-4 w-4" />
              ) : (
                <Play className="h-4 w-4" />
              )}

              {stage.state === "running"
                ? "Esecuzione..."
                : alreadyRun
                  ? "Riesegui"
                  : "Esegui stage"}
            </Button>
          )}

          {stage.inspectable && onInspect && (
            <Button type="button" variant="ghost" onClick={onInspect}>
              {inspectLabel}
            </Button>
          )}
        </div>
      )}
    </article>
  );
}
