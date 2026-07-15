import type { ReactNode } from "react";

import GlassPanel from "@/components/design-system/GlassPanel";

interface MetricCardProps {
  label: string;
  value: string | number;
  description?: string;
  icon?: ReactNode;
  trend?: string;
  status?: "neutral" | "positive" | "warning" | "critical";
}

const statusClasses = {
  neutral:
    "bg-secondary text-secondary-foreground",
  positive:
    "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100",
  warning:
    "bg-amber-50 text-amber-700 ring-1 ring-amber-100",
  critical:
    "bg-red-50 text-red-700 ring-1 ring-red-100",
};

export default function MetricCard({
  label,
  value,
  description,
  icon,
  trend,
  status = "neutral",
}: MetricCardProps) {
  return (
    <GlassPanel
      as="article"
      interactive
      padding="md"
      className="group"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-medium text-muted-foreground">
            {label}
          </p>

          <p className="mt-3 text-3xl font-semibold tracking-tight text-foreground">
            {value}
          </p>

          {description && (
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {description}
            </p>
          )}
        </div>

        {icon && (
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary transition duration-300 group-hover:scale-105 group-hover:bg-primary/15">
            {icon}
          </div>
        )}
      </div>

      {trend && (
        <div
          className={[
            "mt-5 inline-flex rounded-full px-3 py-1",
            "text-xs font-semibold",
            statusClasses[status],
          ].join(" ")}
        >
          {trend}
        </div>
      )}
    </GlassPanel>
  );
}