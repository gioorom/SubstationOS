import {
  ArrowRight,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Target,
} from "lucide-react";

import GlassPanel from "@/components/design-system/GlassPanel";

interface TodaysFocusItem {
  id: string;
  title: string;
  description: string;
  priority: "high" | "medium" | "low";
  estimatedMinutes?: number;
  completed?: boolean;
}

interface TodaysFocusPanelProps {
  items: TodaysFocusItem[];
}

const priorityLabels = {
  high: "Alta",
  medium: "Media",
  low: "Bassa",
};

const priorityClasses = {
  high: "bg-red-50 text-red-700 ring-1 ring-red-100",
  medium: "bg-amber-50 text-amber-700 ring-1 ring-amber-100",
  low: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100",
};

function formatEstimatedTime(totalMinutes: number) {
  if (totalMinutes <= 0) {
    return "Nessuna attività pianificata";
  }

  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours === 0) {
    return `${minutes} min`;
  }

  if (minutes === 0) {
    return `${hours} h`;
  }

  return `${hours} h ${minutes} min`;
}

export default function TodaysFocusPanel({
  items,
}: TodaysFocusPanelProps) {
  const activeItems = items.filter(
    (item) => !item.completed
  );

  const completedItems = items.filter(
    (item) => item.completed
  );

  const estimatedMinutes = activeItems.reduce(
    (total, item) =>
      total + (item.estimatedMinutes ?? 0),
    0
  );

  const highestPriority =
    activeItems.find(
      (item) => item.priority === "high"
    )?.priority ??
    activeItems.find(
      (item) => item.priority === "medium"
    )?.priority ??
    activeItems[0]?.priority ??
    "low";

  return (
    <GlassPanel padding="lg">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <Target className="h-6 w-6" />
            </div>

            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
                Today&apos;s Focus
              </p>

              <h2 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
                Priorità operative
              </h2>
            </div>
          </div>

          <p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground">
            Le attività più importanti da completare per far
            avanzare la commessa senza introdurre ritardi o
            criticità.
          </p>
        </div>

        <div className="grid shrink-0 grid-cols-2 gap-3">
          <div className="rounded-2xl border border-white/70 bg-white/70 px-4 py-3 shadow-sm">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Clock3 className="h-4 w-4" />

              <span className="text-xs font-semibold uppercase tracking-[0.14em]">
                Tempo stimato
              </span>
            </div>

            <p className="mt-2 text-sm font-semibold text-foreground">
              {formatEstimatedTime(
                estimatedMinutes
              )}
            </p>
          </div>

          <div className="rounded-2xl border border-white/70 bg-white/70 px-4 py-3 shadow-sm">
            <div className="flex items-center gap-2 text-muted-foreground">
              <CircleAlert className="h-4 w-4" />

              <span className="text-xs font-semibold uppercase tracking-[0.14em]">
                Priorità
              </span>
            </div>

            <span
              className={[
                "mt-2 inline-flex rounded-full px-3 py-1 text-xs font-semibold",
                priorityClasses[
                  highestPriority
                ],
              ].join(" ")}
            >
              {
                priorityLabels[
                  highestPriority
                ]
              }
            </span>
          </div>
        </div>
      </div>

      {activeItems.length === 0 ? (
        <div className="mt-8 rounded-3xl border border-dashed border-border bg-white/55 px-6 py-12 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600">
            <CheckCircle2 className="h-7 w-7" />
          </div>

          <h3 className="mt-5 text-lg font-semibold text-foreground">
            Nessuna priorità aperta
          </h3>

          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
            Tutte le attività operative risultano completate.
            Il progetto può procedere al prossimo controllo.
          </p>
        </div>
      ) : (
        <div className="mt-8 space-y-3">
          {activeItems.map((item, index) => (
            <article
              key={item.id}
              className="group flex items-start gap-4 rounded-2xl border border-border bg-white/60 p-4 transition duration-200 hover:-translate-y-0.5 hover:bg-white hover:shadow-md"
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-sm font-semibold text-primary">
                {index + 1}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h3 className="font-semibold text-foreground">
                      {item.title}
                    </h3>

                    <p className="mt-1 text-sm leading-6 text-muted-foreground">
                      {item.description}
                    </p>
                  </div>

                  <span
                    className={[
                      "shrink-0 rounded-full px-3 py-1 text-xs font-semibold",
                      priorityClasses[
                        item.priority
                      ],
                    ].join(" ")}
                  >
                    {
                      priorityLabels[
                        item.priority
                      ]
                    }
                  </span>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                  {item.estimatedMinutes !==
                    undefined && (
                    <span className="inline-flex items-center gap-1.5">
                      <Clock3 className="h-3.5 w-3.5" />
                      {formatEstimatedTime(
                        item.estimatedMinutes
                      )}
                    </span>
                  )}

                  <span className="inline-flex items-center gap-1.5 font-medium text-primary">
                    Apri attività
                    <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
                  </span>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {completedItems.length > 0 && (
        <div className="mt-6 border-t border-border pt-5">
          <p className="text-sm font-medium text-muted-foreground">
            {completedItems.length} attività completate oggi
          </p>
        </div>
      )}
    </GlassPanel>
  );
}