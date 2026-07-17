"use client";

import {
  AlertTriangle,
  Boxes,
  CheckCircle2,
  CircleDashed,
  Clock3,
  ShieldAlert,
} from "lucide-react";

import { AssetGrid } from "./AssetGrid";

import type {
  CommissioningAsset,
  CommissioningSummary,
} from "@/types/commissioning";

interface OverviewPanelProps {
  assets: CommissioningAsset[];
  summary: CommissioningSummary;
  onSelectAsset?: (asset: CommissioningAsset) => void;
}

interface SummaryMetricProps {
  label: string;
  value: number;
  description: string;
  icon: typeof Boxes;
  tone?: "default" | "blue" | "amber" | "red" | "emerald";
}

const toneConfiguration = {
  default: {
    iconContainer:
      "border-slate-200 bg-slate-50 text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-400",
    value: "text-slate-950 dark:text-white",
  },
  blue: {
    iconContainer:
      "border-blue-200 bg-blue-50 text-blue-600 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-300",
    value: "text-blue-700 dark:text-blue-300",
  },
  amber: {
    iconContainer:
      "border-amber-200 bg-amber-50 text-amber-600 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-300",
    value: "text-amber-700 dark:text-amber-300",
  },
  red: {
    iconContainer:
      "border-red-200 bg-red-50 text-red-600 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-300",
    value: "text-red-700 dark:text-red-300",
  },
  emerald: {
    iconContainer:
      "border-emerald-200 bg-emerald-50 text-emerald-600 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-300",
    value: "text-emerald-700 dark:text-emerald-300",
  },
} satisfies Record<
  NonNullable<SummaryMetricProps["tone"]>,
  {
    iconContainer: string;
    value: string;
  }
>;

function clampProgress(progress: number): number {
  return Math.min(100, Math.max(0, progress));
}

function SummaryMetric({
  label,
  value,
  description,
  icon: Icon,
  tone = "default",
}: SummaryMetricProps) {
  const configuration = toneConfiguration[tone];

  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white/70 p-5 shadow-sm backdrop-blur-xl dark:border-white/10 dark:bg-white/[0.035]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
            {label}
          </p>

          <p
            className={`mt-3 text-3xl font-semibold tracking-tight tabular-nums ${configuration.value}`}
          >
            {value}
          </p>
        </div>

        <div
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${configuration.iconContainer}`}
        >
          <Icon className="h-5 w-5" />
        </div>
      </div>

      <p className="mt-4 text-sm leading-5 text-slate-500 dark:text-slate-400">
        {description}
      </p>
    </div>
  );
}

export function OverviewPanel({
  assets,
  summary,
  onSelectAsset,
}: OverviewPanelProps) {
  const overallProgress = clampProgress(summary.overallProgress);
  const activeAssets =
    summary.inProgressAssets + summary.readyForReviewAssets;

  return (
    <section className="space-y-6">
      <div className="overflow-hidden rounded-3xl border border-slate-200/80 bg-white/80 shadow-sm backdrop-blur-xl dark:border-white/10 dark:bg-white/[0.04]">
        <div className="border-b border-slate-200/80 px-6 py-6 dark:border-white/10 md:px-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-2xl">
              <div className="flex items-center gap-2">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-blue-200 bg-blue-50 text-blue-600 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-300">
                  <Boxes className="h-4.5 w-4.5" />
                </span>

                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600 dark:text-blue-300">
                  Project domain
                </p>
              </div>

              <h2 className="mt-4 text-2xl font-semibold tracking-tight text-slate-950 dark:text-white">
                Commissioning
              </h2>

              <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
                Monitor asset readiness, field activities, blockers,
                documentation and outstanding issues across the entire
                substation.
              </p>
            </div>

            <div className="min-w-52 rounded-2xl border border-slate-200 bg-slate-50/80 px-5 py-4 dark:border-white/10 dark:bg-white/5">
              <div className="flex items-center justify-between gap-6">
                <span className="text-sm font-medium text-slate-600 dark:text-slate-300">
                  Overall progress
                </span>

                <span className="text-2xl font-semibold tracking-tight tabular-nums text-slate-950 dark:text-white">
                  {overallProgress}%
                </span>
              </div>

              <div
                className="mt-4 h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-white/10"
                role="progressbar"
                aria-label="Overall commissioning progress"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={overallProgress}
              >
                <div
                  className="h-full rounded-full bg-blue-500 transition-[width] duration-500"
                  style={{ width: `${overallProgress}%` }}
                />
              </div>

              <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                {summary.completedAssets} of {summary.totalAssets} assets
                completed
              </p>
            </div>
          </div>
        </div>

        <div className="grid gap-4 p-6 md:grid-cols-2 lg:grid-cols-4 md:p-8">
          <SummaryMetric
            label="Assets"
            value={summary.totalAssets}
            description={`${summary.completedAssets} completed and ${summary.notStartedAssets} not started`}
            icon={Boxes}
          />

          <SummaryMetric
            label="Active assets"
            value={activeAssets}
            description={`${summary.inProgressAssets} in progress and ${summary.readyForReviewAssets} ready for review`}
            icon={Clock3}
            tone="blue"
          />

          <SummaryMetric
            label="Blocked"
            value={summary.blockedAssets}
            description={
              summary.blockedAssets > 0
                ? "Assets requiring immediate operational attention"
                : "No assets are currently blocked"
            }
            icon={ShieldAlert}
            tone={summary.blockedAssets > 0 ? "red" : "emerald"}
          />

          <SummaryMetric
            label="Open issues"
            value={summary.openIssues}
            description={
              summary.openIssues > 0
                ? "Outstanding issues across commissioning assets"
                : "No open commissioning issues"
            }
            icon={AlertTriangle}
            tone={summary.openIssues > 0 ? "amber" : "emerald"}
          />
        </div>

        <div className="grid gap-px border-t border-slate-200/80 bg-slate-200/80 dark:border-white/10 dark:bg-white/10 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex items-center gap-3 bg-white/90 px-6 py-4 dark:bg-slate-950/90">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            <div>
              <p className="text-sm font-semibold tabular-nums text-slate-900 dark:text-white">
                {summary.completedAssets}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Completed
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 bg-white/90 px-6 py-4 dark:bg-slate-950/90">
            <Clock3 className="h-4 w-4 text-blue-500" />
            <div>
              <p className="text-sm font-semibold tabular-nums text-slate-900 dark:text-white">
                {summary.inProgressAssets}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                In progress
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 bg-white/90 px-6 py-4 dark:bg-slate-950/90">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            <div>
              <p className="text-sm font-semibold tabular-nums text-slate-900 dark:text-white">
                {summary.readyForReviewAssets}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Ready for review
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 bg-white/90 px-6 py-4 dark:bg-slate-950/90">
            <CircleDashed className="h-4 w-4 text-slate-400" />
            <div>
              <p className="text-sm font-semibold tabular-nums text-slate-900 dark:text-white">
                {summary.notStartedAssets}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Not started
              </p>
            </div>
          </div>
        </div>
      </div>

      <div>
        <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
              Asset workspaces
            </p>

            <h3 className="mt-2 text-xl font-semibold tracking-tight text-slate-950 dark:text-white">
              Commissioning assets
            </h3>
          </div>

          <p className="text-sm text-slate-500 dark:text-slate-400">
            {assets.length} operational workspaces
          </p>
        </div>

        <AssetGrid assets={assets} onSelect={onSelectAsset} />
      </div>
    </section>
  );
}