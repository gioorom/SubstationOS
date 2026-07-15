import {
  Activity,
  Building2,
  MapPin,
  Network,
  Sparkles,
  Zap,
} from "lucide-react";

import GlassPanel from "@/components/design-system/GlassPanel";
import { Project } from "@/types/project";

interface ProjectHeroProps {
  project: Project;
  documentCount: number;
  lastActivityLabel?: string;
  healthScore?: number;
}

const statusLabels: Record<Project["status"], string> = {
  planning: "Pianificazione",
  active: "Attivo",
  on_hold: "In sospeso",
  completed: "Completato",
  cancelled: "Annullato",
};

const statusStyles: Record<Project["status"], string> = {
  planning:
    "border-blue-200 bg-blue-50 text-blue-700",
  active:
    "border-emerald-200 bg-emerald-50 text-emerald-700",
  on_hold:
    "border-amber-200 bg-amber-50 text-amber-700",
  completed:
    "border-slate-200 bg-slate-100 text-slate-700",
  cancelled:
    "border-red-200 bg-red-50 text-red-700",
};

function getHealthLabel(score: number) {
  if (score >= 90) {
    return "Eccellente";
  }

  if (score >= 75) {
    return "Buono";
  }

  if (score >= 60) {
    return "Da monitorare";
  }

  return "Critico";
}

function getHealthClasses(score: number) {
  if (score >= 90) {
    return {
      text: "text-emerald-700",
      ring: "stroke-emerald-500",
      glow: "shadow-[0_0_35px_rgba(16,185,129,0.24)]",
    };
  }

  if (score >= 75) {
    return {
      text: "text-blue-700",
      ring: "stroke-blue-500",
      glow: "shadow-[0_0_35px_rgba(59,130,246,0.22)]",
    };
  }

  if (score >= 60) {
    return {
      text: "text-amber-700",
      ring: "stroke-amber-500",
      glow: "shadow-[0_0_35px_rgba(245,158,11,0.22)]",
    };
  }

  return {
    text: "text-red-700",
    ring: "stroke-red-500",
    glow: "shadow-[0_0_35px_rgba(239,68,68,0.22)]",
  };
}

export default function ProjectHero({
  project,
  documentCount,
  lastActivityLabel = "Nessuna attività recente",
  healthScore = 82,
}: ProjectHeroProps) {
  const healthClasses = getHealthClasses(healthScore);
  const healthLabel = getHealthLabel(healthScore);

  const circumference = 2 * Math.PI * 52;
  const dashOffset =
    circumference -
    (healthScore / 100) * circumference;

  return (
    <GlassPanel
      padding="lg"
      className="overflow-hidden"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-24 -top-28 h-80 w-80 rounded-full bg-blue-400/16 blur-3xl"
      />

      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-32 left-1/3 h-72 w-72 rounded-full bg-violet-400/12 blur-3xl"
      />

      <div className="relative grid gap-8 xl:grid-cols-[1fr_auto] xl:items-center">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold tracking-wide text-primary">
              {project.code}
            </span>

            <span
              className={[
                "rounded-full border px-3 py-1",
                "text-xs font-semibold",
                statusStyles[project.status],
              ].join(" ")}
            >
              {statusLabels[project.status]}
            </span>
          </div>

          <h1 className="mt-5 text-3xl font-semibold tracking-tight text-foreground lg:text-5xl">
            {project.name}
          </h1>

          <p className="mt-4 max-w-3xl text-sm leading-6 text-muted-foreground lg:text-base">
            {project.description ||
              "Workspace tecnico della commessa, con documenti, attività e dati operativi centralizzati."}
          </p>

          <div className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl border border-white/70 bg-white/58 p-4 shadow-sm backdrop-blur-xl">
              <div className="flex items-center gap-3">
                <Building2 className="h-5 w-5 text-primary" />

                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  Committente
                </p>
              </div>

              <p className="mt-3 truncate text-sm font-semibold text-foreground">
                {project.customer || "Non specificato"}
              </p>
            </div>

            <div className="rounded-2xl border border-white/70 bg-white/58 p-4 shadow-sm backdrop-blur-xl">
              <div className="flex items-center gap-3">
                <Network className="h-5 w-5 text-primary" />

                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  EPC
                </p>
              </div>

              <p className="mt-3 truncate text-sm font-semibold text-foreground">
                {project.epc || "Non specificato"}
              </p>
            </div>

            <div className="rounded-2xl border border-white/70 bg-white/58 p-4 shadow-sm backdrop-blur-xl">
              <div className="flex items-center gap-3">
                <Zap className="h-5 w-5 text-primary" />

                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  Tensione
                </p>
              </div>

              <p className="mt-3 truncate text-sm font-semibold text-foreground">
                {project.voltage_level || "Non specificata"}
              </p>
            </div>

            <div className="rounded-2xl border border-white/70 bg-white/58 p-4 shadow-sm backdrop-blur-xl">
              <div className="flex items-center gap-3">
                <MapPin className="h-5 w-5 text-primary" />

                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  Località
                </p>
              </div>

              <p className="mt-3 truncate text-sm font-semibold text-foreground">
                {project.location || "Non specificata"}
              </p>
            </div>
          </div>

          <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="inline-flex items-center gap-2 rounded-2xl border border-white/70 bg-white/58 px-4 py-3 text-sm text-muted-foreground shadow-sm backdrop-blur-xl">
              <Activity className="h-4 w-4 text-primary" />

              <span>
                Ultima attività:
                {" "}
                <strong className="font-semibold text-foreground">
                  {lastActivityLabel}
                </strong>
              </span>
            </div>

            <div className="inline-flex items-center gap-2 rounded-2xl border border-white/70 bg-white/58 px-4 py-3 text-sm text-muted-foreground shadow-sm backdrop-blur-xl">
              <Sparkles className="h-4 w-4 text-primary" />

              <span>
                {documentCount} documenti associati
              </span>
            </div>
          </div>
        </div>

        <div className="mx-auto flex w-full max-w-xs flex-col items-center justify-center rounded-[2rem] border border-white/70 bg-white/60 p-6 shadow-[0_24px_70px_rgba(15,23,42,0.08)] backdrop-blur-2xl xl:mx-0">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Project Health
          </p>

          <div
            className={[
              "relative mt-5 flex h-40 w-40 items-center justify-center rounded-full",
              "bg-white/80",
              healthClasses.glow,
            ].join(" ")}
          >
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
                className={[
                  "transition-all duration-700",
                  healthClasses.ring,
                ].join(" ")}
              />
            </svg>

            <div className="relative text-center">
              <p className="text-4xl font-semibold tracking-tight text-foreground">
                {healthScore}
              </p>

              <p
                className={[
                  "mt-1 text-xs font-semibold",
                  healthClasses.text,
                ].join(" ")}
              >
                {healthLabel}
              </p>
            </div>
          </div>

          <p className="mt-5 text-center text-sm leading-6 text-muted-foreground">
            Indicatore sintetico dello stato della commessa.
          </p>
        </div>
      </div>
    </GlassPanel>
  );
}