interface ActivityItem {
  id: number;
  title: string;
  description: string;
  time: string;
  type: "upload" | "project" | "test" | "ai";
}

interface RecentActivityCardProps {
  activities: ActivityItem[];
}

const activityStyles: Record<
  ActivityItem["type"],
  {
    label: string;
    className: string;
  }
> = {
  upload: {
    label: "Upload",
    className:
      "bg-blue-50 text-blue-700 ring-1 ring-blue-100",
  },
  project: {
    label: "Project",
    className:
      "bg-violet-50 text-violet-700 ring-1 ring-violet-100",
  },
  test: {
    label: "Test",
    className:
      "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100",
  },
  ai: {
    label: "AI",
    className:
      "bg-amber-50 text-amber-700 ring-1 ring-amber-100",
  },
};

export default function RecentActivityCard({
  activities,
}: RecentActivityCardProps) {
  return (
    <section className="rounded-3xl border border-white/70 bg-white/72 p-6 shadow-[0_18px_45px_rgba(15,23,42,0.06)] backdrop-blur-2xl">
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-foreground">
          Recent Activity
        </h2>

        <p className="mt-1 text-sm text-muted-foreground">
          Ultime operazioni eseguite nel workspace
        </p>
      </div>

      {activities.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          Nessuna attività recente.
        </p>
      ) : (
        <div className="space-y-4">
          {activities.map((activity) => {
            const style = activityStyles[activity.type];

            return (
              <div
                key={activity.id}
                className="flex items-start gap-4 rounded-2xl border border-border bg-white/60 p-4 transition hover:bg-white"
              >
                <div
                  className={[
                    "mt-0.5 rounded-full px-2.5 py-1",
                    "text-[11px] font-semibold uppercase tracking-wide",
                    style.className,
                  ].join(" ")}
                >
                  {style.label}
                </div>

                <div className="min-w-0 flex-1">
                  <p className="font-medium text-foreground">
                    {activity.title}
                  </p>

                  <p className="mt-1 text-sm text-muted-foreground">
                    {activity.description}
                  </p>

                  <p className="mt-2 text-xs text-muted-foreground/80">
                    {activity.time}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}