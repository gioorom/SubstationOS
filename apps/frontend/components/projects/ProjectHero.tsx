import {
  Activity,
  Building2,
  Globe2,
  MapPin,
  Network,
  Sparkles,
  Zap,
} from "lucide-react";

import GlassPanel from "@/components/design-system/GlassPanel";
import {
  PROJECT_LIFECYCLE_LABELS,
  PROJECT_STATUS_LABELS,
  type Project,
  type ProjectLifecycleState,
  type ProjectStatus,
} from "@/lib/contracts";

interface ProjectHeroProps {
  project: Project;
  documentCount: number;
  lastActivityLabel: string;
  /** From `GET /projects/{id}/intelligence`. Never a default. */
  healthScore: number;
}

/**
 * `status` is the delivery phase; `lifecycle_state` is whether the record
 * is editable. Both are shown because they answer different questions and
 * a project can be `energized` and `archived` at once.
 */
const statusStyles: Record<ProjectStatus, string> = {
  planning: "border-blue-200 bg-blue-50 text-blue-700",
  engineering: "border-indigo-200 bg-indigo-50 text-indigo-700",
  construction: "border-amber-200 bg-amber-50 text-amber-700",
  commissioning: "border-violet-200 bg-violet-50 text-violet-700",
  energized: "border-emerald-200 bg-emerald-50 text-emerald-700",
  closed: "border-slate-200 bg-slate-100 text-slate-700",
};

const lifecycleStyles: Record<ProjectLifecycleState, string> = {
  draft: "border-slate-200 bg-slate-100 text-slate-600",
  active: "border-emerald-200 bg-emerald-50 text-emerald-700",
  archived: "border-amber-200 bg-amber-50 text-amber-700",
  deleted: "border-red-200 bg-red-50 text-red-700",
};

function healthLabel(score: number): string {
  if (score >= 90) return "Eccellente";
  if (score >= 75) return "Buono";
  if (score >= 60) return "Da monitorare";
  return "Critico";
}

function healthClasses(score: number) {
  if (score >= 90) {
    return { text: "text-emerald-700", ring: "stroke-emerald-500" };
  }

  if (score >= 75) {
    return { text: "text-blue-700", ring: "stroke-blue-500" };
  }

  if (score >= 60) {
    return { text: "text-amber-700", ring: "stroke-amber-500" };
  }

  return { text: "text-red-700", ring: "stroke-red-500" };
}

function Fact({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | null;
}) {
  return (
    <div className="rounded-2xl border border-white/70 bg-white/58 p-4 shadow-sm backdrop-blur-xl">
      <div className="flex items-center gap-3 text-primary">
        {icon}

        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          {label}
        </p>
      </div>

      <p className="mt-3 truncate text-sm font-semibold text-foreground">
        {value || "Non specificato"}
      </p>
    </div>
  );
}

export default function ProjectHero({
  project,
  documentCount,
  lastActivityLabel,
  healthScore,
}: ProjectHeroProps) {
  const classes = healthClasses(healthScore);
  const circumference = 2 * Math.PI * 52;
  const dashOffset = circumference - (healthScore / 100) * circumference;

  return (
    <GlassPanel padding="lg" className="overflow-hidden">
      <div className="relative grid gap-8 xl:grid-cols-[1fr_auto] xl:items-center">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold tracking-wide text-primary">
              {project.code}
            </span>

            <span
              className={[
                "rounded-full border px-3 py-1 text-xs font-semibold",
                statusStyles[project.status],
              ].join(" ")}
            >
              {PROJECT_STATUS_LABELS[project.status]}
            </span>

            <span
              className={[
                "rounded-full border px-3 py-1 text-xs font-semibold",
                lifecycleStyles[project.lifecycle_state],
              ].join(" ")}
            >
              {PROJECT_LIFECYCLE_LABELS[project.lifecycle_state]}
            </span>
          </div>

          <h1 className="mt-5 text-3xl font-semibold tracking-tight text-foreground lg:text-5xl">
            {project.name}
          </h1>

          {project.description && (
            <p className="mt-4 max-w-3xl text-sm leading-6 text-muted-foreground lg:text-base">
              {project.description}
            </p>
          )}

          <div className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <Fact
              icon={<Building2 className="h-5 w-5" />}
              label="Committente"
              value={project.customer}
            />

            <Fact
              icon={<Network className="h-5 w-5" />}
              label="EPC"
              value={project.epc}
            />

            <Fact
              icon={<Zap className="h-5 w-5" />}
              label="Tensione"
              value={project.voltage_level}
            />

            <Fact
              icon={<MapPin className="h-5 w-5" />}
              label="Località"
              value={project.location}
            />

            <Fact
              icon={<Globe2 className="h-5 w-5" />}
              label="Paese"
              value={project.country}
            />
          </div>

          <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="inline-flex items-center gap-2 rounded-2xl border border-white/70 bg-white/58 px-4 py-3 text-sm text-muted-foreground shadow-sm backdrop-blur-xl">
              <Activity className="h-4 w-4 text-primary" />

              <span>
                Ultima attività:{" "}
                <strong className="font-semibold text-foreground">
                  {lastActivityLabel}
                </strong>
              </span>
            </div>

            <div className="inline-flex items-center gap-2 rounded-2xl border border-white/70 bg-white/58 px-4 py-3 text-sm text-muted-foreground shadow-sm backdrop-blur-xl">
              <Sparkles className="h-4 w-4 text-primary" />

              <span>{documentCount} documenti associati</span>
            </div>
          </div>
        </div>

        <div className="mx-auto flex w-full max-w-xs flex-col items-center justify-center rounded-[2rem] border border-white/70 bg-white/60 p-6 shadow-[0_24px_70px_rgba(15,23,42,0.08)] backdrop-blur-2xl xl:mx-0">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Project Health
          </p>

          <div className="relative mt-5 flex h-40 w-40 items-center justify-center rounded-full bg-white/80">
            <svg
              viewBox="0 0 120 120"
              className="absolute inset-0 h-full w-full -rotate-90"
              aria-hidden="true"
            >
              <circle
                cx="60"
                cy="60"
                r="52"
                fill="none"
                stroke="currentColor"
                strokeWidth="8"
                className="text-slate-200"
              />

              <circle
                cx="60"
                cy="60"
                r="52"
                fill="none"
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={circumference}
                strokeDashoffset={dashOffset}
                className={["transition-all duration-700", classes.ring].join(
                  " ",
                )}
              />
            </svg>

            <div className="relative text-center">
              <p className="text-4xl font-semibold tracking-tight text-foreground">
                {healthScore}
              </p>

              <p
                className={["mt-1 text-xs font-semibold", classes.text].join(
                  " ",
                )}
              >
                {healthLabel(healthScore)}
              </p>
            </div>
          </div>

          <p className="mt-5 text-center text-xs leading-5 text-muted-foreground">
            Calcolato dal backend sulla sola completezza documentale.
          </p>
        </div>
      </div>
    </GlassPanel>
  );
}
