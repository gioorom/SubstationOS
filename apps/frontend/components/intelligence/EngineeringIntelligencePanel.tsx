import { ArrowRight, BrainCircuit, ShieldCheck } from "lucide-react";

import GlassPanel from "@/components/design-system/GlassPanel";
import {
  DOCUMENTATION_STATUS_LABELS,
  READINESS_LABELS,
  RISK_LEVEL_LABELS,
  type ProjectIntelligence,
  type ReadinessStatus,
} from "@/lib/contracts";

interface EngineeringIntelligencePanelProps {
  intelligence: ProjectIntelligence;
}

const readinessClasses: Record<ReadinessStatus, string> = {
  not_ready: "bg-red-50 text-red-700 ring-1 ring-red-100",
  partially_ready: "bg-amber-50 text-amber-700 ring-1 ring-amber-100",
  ready: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100",
};

/**
 * Presents only what the backend computes: documentation completeness,
 * the health score derived from it, readiness, risk and the next action.
 *
 * `commissioning`, `relay_testing` and `issues` are part of the contract
 * but are returned as constant zeros - modules that do not exist yet.
 * They are deliberately not rendered: a fabricated 0% beside a real
 * figure reads as a measurement, and it is not one.
 */
export default function EngineeringIntelligencePanel({
  intelligence,
}: EngineeringIntelligencePanelProps) {
  return (
    <GlassPanel padding="lg" className="overflow-hidden">
      <div className="flex flex-col gap-8 xl:flex-row xl:items-start xl:justify-between">
        <div className="max-w-3xl">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <BrainCircuit className="h-6 w-6" />
            </div>

            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
                Engineering Intelligence
              </p>

              <h2 className="mt-1 text-2xl font-semibold tracking-tight">
                Analisi della commessa
              </h2>
            </div>
          </div>

          <p className="mt-6 text-base leading-8 text-muted-foreground">
            {DOCUMENTATION_STATUS_LABELS[intelligence.documentation.status]}
            : {intelligence.documentation.document_count} documenti,
            completezza{" "}
            <strong>{intelligence.documentation.completion}%</strong>.
          </p>

          <div className="mt-8 rounded-2xl border border-primary/10 bg-primary/5 p-5">
            <div className="flex items-center gap-2 text-primary">
              <ArrowRight className="h-4 w-4" />

              <span className="text-xs font-semibold uppercase tracking-[0.16em]">
                Prossima azione consigliata
              </span>
            </div>

            <p className="mt-3 text-base font-medium leading-7 text-foreground">
              {intelligence.next_action}
            </p>
          </div>
        </div>

        <div className="shrink-0 rounded-3xl border border-white/70 bg-white/70 p-6 shadow-sm backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <ShieldCheck className="h-6 w-6 text-primary" />

            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                Readiness
              </p>

              <span
                className={[
                  "mt-2 inline-flex rounded-full px-3 py-1 text-xs font-semibold",
                  readinessClasses[intelligence.readiness],
                ].join(" ")}
              >
                {READINESS_LABELS[intelligence.readiness]}
              </span>
            </div>
          </div>

          <div className="mt-8">
            <p className="text-sm text-muted-foreground">Health Score</p>

            <p className="mt-2 text-5xl font-semibold tracking-tight">
              {intelligence.health_score}
            </p>

            <p className="mt-1 text-xs text-muted-foreground">
              {RISK_LEVEL_LABELS[intelligence.risk_level]}
            </p>
          </div>

          <div className="mt-8 h-2 overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-primary transition-all duration-700"
              style={{ width: `${intelligence.health_score}%` }}
            />
          </div>
        </div>
      </div>
    </GlassPanel>
  );
}
