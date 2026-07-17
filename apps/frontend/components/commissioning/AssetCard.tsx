"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Clock3,
  FileText,
  ShieldAlert,
} from "lucide-react";

import type {
  CommissioningAsset,
  CommissioningAssetStatus,
} from "@/types/commissioning";

interface AssetCardProps {
  asset: CommissioningAsset;
  onSelect?: (asset: CommissioningAsset) => void;
}

interface StatusConfiguration {
  label: string;
  icon: typeof Circle;
  badgeClassName: string;
  iconClassName: string;
  progressClassName: string;
}

const statusConfiguration: Record<
  CommissioningAssetStatus,
  StatusConfiguration
> = {
  "not-started": {
    label: "Not started",
    icon: Circle,
    badgeClassName:
      "border-slate-200 bg-slate-50 text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300",
    iconClassName: "text-slate-400",
    progressClassName: "bg-slate-400",
  },
  "in-progress": {
    label: "In progress",
    icon: Clock3,
    badgeClassName:
      "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-300",
    iconClassName: "text-blue-500",
    progressClassName: "bg-blue-500",
  },
  blocked: {
    label: "Blocked",
    icon: ShieldAlert,
    badgeClassName:
      "border-red-200 bg-red-50 text-red-700 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-300",
    iconClassName: "text-red-500",
    progressClassName: "bg-red-500",
  },
  "ready-for-review": {
    label: "Ready for review",
    icon: AlertTriangle,
    badgeClassName:
      "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-300",
    iconClassName: "text-amber-500",
    progressClassName: "bg-amber-500",
  },
  completed: {
    label: "Completed",
    icon: CheckCircle2,
    badgeClassName:
      "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-300",
    iconClassName: "text-emerald-500",
    progressClassName: "bg-emerald-500",
  },
};

function clampProgress(progress: number): number {
  return Math.min(100, Math.max(0, progress));
}

export function AssetCard({ asset, onSelect }: AssetCardProps) {
  const configuration = statusConfiguration[asset.status];
  const StatusIcon = configuration.icon;
  const progress = clampProgress(asset.metrics.progress);

  const cardContent = (
    <>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-400">
              {asset.code}
            </span>

            {asset.priority === "critical" && (
              <span className="flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.1em] text-red-600 dark:text-red-400">
                <AlertTriangle className="h-3.5 w-3.5" />
                Critical
              </span>
            )}
          </div>

          <h3 className="mt-4 truncate text-lg font-semibold tracking-tight text-slate-950 dark:text-white">
            {asset.name}
          </h3>

          <p className="mt-1 line-clamp-2 min-h-10 text-sm leading-5 text-slate-500 dark:text-slate-400">
            {asset.description}
          </p>
        </div>

        <div
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-white shadow-sm dark:border-white/10 dark:bg-white/5 ${configuration.iconClassName}`}
        >
          <StatusIcon className="h-5 w-5" />
        </div>
      </div>

      <div className="mt-6">
        <div className="flex items-center justify-between gap-4">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${configuration.badgeClassName}`}
          >
            <StatusIcon className="h-3.5 w-3.5" />
            {configuration.label}
          </span>

          <span className="text-sm font-semibold tabular-nums text-slate-900 dark:text-white">
            {progress}%
          </span>
        </div>

        <div
          className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-white/10"
          role="progressbar"
          aria-label={`${asset.name} commissioning progress`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
        >
          <div
            className={`h-full rounded-full transition-[width] duration-500 ${configuration.progressClassName}`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="mt-6 grid grid-cols-3 divide-x divide-slate-200 border-t border-slate-200 pt-5 dark:divide-white/10 dark:border-white/10">
        <div className="pr-3">
          <p className="text-lg font-semibold tabular-nums text-slate-950 dark:text-white">
            {asset.metrics.completedActivities}
            <span className="text-sm font-normal text-slate-400">
              /{asset.metrics.totalActivities}
            </span>
          </p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Activities
          </p>
        </div>

        <div className="px-3">
          <p
            className={`text-lg font-semibold tabular-nums ${
              asset.metrics.openIssues > 0
                ? "text-amber-600 dark:text-amber-400"
                : "text-slate-950 dark:text-white"
            }`}
          >
            {asset.metrics.openIssues}
          </p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Open issues
          </p>
        </div>

        <div className="pl-3">
          <p className="flex items-center gap-1.5 text-lg font-semibold tabular-nums text-slate-950 dark:text-white">
            <FileText className="h-4 w-4 text-slate-400" />
            {asset.metrics.documents}
          </p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Documents
          </p>
        </div>
      </div>

      {asset.metrics.blockedActivities > 0 && (
        <div className="mt-5 flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-xs font-medium text-red-700 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-300">
          <ShieldAlert className="h-4 w-4 shrink-0" />
          {asset.metrics.blockedActivities} blocked{" "}
          {asset.metrics.blockedActivities === 1 ? "activity" : "activities"}
        </div>
      )}
    </>
  );

  const sharedClassName =
    "group relative w-full overflow-hidden rounded-2xl border border-slate-200/80 bg-white/80 p-5 text-left shadow-sm backdrop-blur-xl transition duration-200 dark:border-white/10 dark:bg-white/[0.04]";

  if (onSelect) {
    return (
      <button
        type="button"
        onClick={() => onSelect(asset)}
        className={`${sharedClassName} cursor-pointer hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:hover:border-white/20 dark:focus-visible:ring-offset-slate-950`}
        aria-label={`Open ${asset.name}`}
      >
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-slate-300 to-transparent opacity-0 transition-opacity group-hover:opacity-100 dark:via-white/30" />
        {cardContent}
      </button>
    );
  }

  return (
    <article className={sharedClassName}>
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-slate-300 to-transparent dark:via-white/30" />
      {cardContent}
    </article>
  );
}