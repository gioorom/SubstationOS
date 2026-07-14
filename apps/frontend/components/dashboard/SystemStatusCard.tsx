interface SystemStatusItem {
  id: string;
  label: string;
  description: string;
  status: "online" | "warning" | "offline";
}

interface SystemStatusCardProps {
  items: SystemStatusItem[];
}

const statusStyles: Record<
  SystemStatusItem["status"],
  {
    label: string;
    dotClassName: string;
    badgeClassName: string;
  }
> = {
  online: {
    label: "Online",
    dotClassName:
      "bg-emerald-500 shadow-[0_0_16px_rgba(16,185,129,0.55)]",
    badgeClassName:
      "bg-emerald-50 text-emerald-700 ring-emerald-100",
  },
  warning: {
    label: "Attenzione",
    dotClassName:
      "bg-amber-500 shadow-[0_0_16px_rgba(245,158,11,0.45)]",
    badgeClassName:
      "bg-amber-50 text-amber-700 ring-amber-100",
  },
  offline: {
    label: "Offline",
    dotClassName:
      "bg-red-500 shadow-[0_0_16px_rgba(239,68,68,0.45)]",
    badgeClassName:
      "bg-red-50 text-red-700 ring-red-100",
  },
};

export default function SystemStatusCard({
  items,
}: SystemStatusCardProps) {
  return (
    <section className="rounded-3xl border border-white/70 bg-white/72 p-6 shadow-[0_18px_45px_rgba(15,23,42,0.06)] backdrop-blur-2xl">
      <div>
        <h2 className="text-lg font-semibold text-foreground">
          System Status
        </h2>

        <p className="mt-1 text-sm text-muted-foreground">
          Stato dei servizi principali di SubstationOS
        </p>
      </div>

      <div className="mt-6 space-y-3">
        {items.map((item) => {
          const style = statusStyles[item.status];

          return (
            <div
              key={item.id}
              className="flex items-center justify-between gap-4 rounded-2xl border border-border bg-white/60 p-4 transition hover:bg-white"
            >
              <div className="flex min-w-0 items-center gap-3">
                <span
                  className={[
                    "h-2.5 w-2.5 shrink-0 rounded-full",
                    style.dotClassName,
                  ].join(" ")}
                />

                <div className="min-w-0">
                  <p className="font-medium text-foreground">
                    {item.label}
                  </p>

                  <p className="mt-1 truncate text-sm text-muted-foreground">
                    {item.description}
                  </p>
                </div>
              </div>

              <span
                className={[
                  "shrink-0 rounded-full px-3 py-1",
                  "text-xs font-semibold ring-1",
                  style.badgeClassName,
                ].join(" ")}
              >
                {style.label}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}