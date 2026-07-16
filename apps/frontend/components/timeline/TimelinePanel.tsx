import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ClipboardCheck,
  FileClock,
  FileText,
  FolderPlus,
  Gauge,
  MessageSquareText,
  ShieldCheck,
  TestTube2,
  Upload,
  Wrench,
} from "lucide-react";

import EmptyState from "@/components/common/EmptyState";
import GlassPanel from "@/components/design-system/GlassPanel";
import {
  TimelineEvent,
  TimelineEventSeverity,
  TimelineEventType,
} from "@/types/timeline";

interface TimelinePanelProps {
  events: TimelineEvent[];
  loading?: boolean;
  error?: string;
}

const eventIcons: Record<
  TimelineEventType,
  React.ComponentType<{
    className?: string;
  }>
> = {
  project_created: FolderPlus,
  document_uploaded: Upload,
  document_updated: FileText,
  revision_changed: FileClock,
  commissioning_started: Wrench,
  commissioning_completed: ClipboardCheck,
  relay_test_started: TestTube2,
  relay_test_completed: ShieldCheck,
  issue_opened: AlertTriangle,
  issue_resolved: CheckCircle2,
  health_score_changed: Gauge,
  intelligence_generated: Bot,
  note_added: MessageSquareText,
};

const severityClasses: Record<
  TimelineEventSeverity,
  {
    icon: string;
    line: string;
    badge: string;
  }
> = {
  info: {
    icon: "bg-blue-50 text-blue-700 ring-blue-100",
    line: "bg-blue-200",
    badge: "bg-blue-50 text-blue-700 ring-blue-100",
  },
  success: {
    icon: "bg-emerald-50 text-emerald-700 ring-emerald-100",
    line: "bg-emerald-200",
    badge:
      "bg-emerald-50 text-emerald-700 ring-emerald-100",
  },
  warning: {
    icon: "bg-amber-50 text-amber-700 ring-amber-100",
    line: "bg-amber-200",
    badge: "bg-amber-50 text-amber-700 ring-amber-100",
  },
  critical: {
    icon: "bg-red-50 text-red-700 ring-red-100",
    line: "bg-red-200",
    badge: "bg-red-50 text-red-700 ring-red-100",
  },
};

const severityLabels: Record<
  TimelineEventSeverity,
  string
> = {
  info: "Informazione",
  success: "Completato",
  warning: "Attenzione",
  critical: "Critico",
};

function formatEventDate(value: string) {
  return new Intl.DateTimeFormat("it-IT", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function formatEventTime(value: string) {
  return new Intl.DateTimeFormat("it-IT", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function groupEventsByDate(events: TimelineEvent[]) {
  return events.reduce<Record<string, TimelineEvent[]>>(
    (groups, event) => {
      const dateKey = new Date(event.occurred_at)
        .toISOString()
        .slice(0, 10);

      groups[dateKey] ??= [];
      groups[dateKey].push(event);

      return groups;
    },
    {}
  );
}

export default function TimelinePanel({
  events,
  loading = false,
  error = "",
}: TimelinePanelProps) {
  if (loading) {
    return (
      <GlassPanel padding="lg">
        <div className="animate-pulse">
          <div className="h-7 w-52 rounded-xl bg-muted" />
          <div className="mt-3 h-4 w-80 max-w-full rounded-lg bg-muted" />

          <div className="mt-8 space-y-5">
            {Array.from({ length: 4 }).map((_, index) => (
              <div
                key={index}
                className="flex gap-4"
              >
                <div className="h-11 w-11 shrink-0 rounded-2xl bg-muted" />

                <div className="flex-1">
                  <div className="h-5 w-2/5 rounded-lg bg-muted" />
                  <div className="mt-3 h-4 w-full rounded-lg bg-muted" />
                  <div className="mt-2 h-4 w-3/4 rounded-lg bg-muted" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </GlassPanel>
    );
  }

  if (error) {
    return (
      <GlassPanel padding="lg">
        <EmptyState
          icon={<AlertTriangle className="h-8 w-8" />}
          title="Timeline non disponibile"
          description={error}
        />
      </GlassPanel>
    );
  }

  if (events.length === 0) {
    return (
      <GlassPanel padding="lg">
        <EmptyState
          icon={<FileClock className="h-8 w-8" />}
          title="Nessuna attività registrata"
          description="La cronologia tecnica si popolerà automaticamente con upload, revisioni, prove, anomalie e variazioni dello stato della commessa."
        />
      </GlassPanel>
    );
  }

  const orderedEvents = events
    .slice()
    .sort(
      (first, second) =>
        new Date(second.occurred_at).getTime() -
        new Date(first.occurred_at).getTime()
    );

  const groupedEvents =
    groupEventsByDate(orderedEvents);

  return (
    <GlassPanel padding="lg">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
            Project Activity
          </p>

          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
            Timeline tecnica
          </h2>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Cronologia verificabile delle operazioni e delle
            variazioni più importanti della commessa.
          </p>
        </div>

        <span className="w-fit rounded-full bg-secondary px-3 py-1.5 text-xs font-semibold text-secondary-foreground">
          {events.length} eventi
        </span>
      </header>

      <div className="mt-8 space-y-9">
        {Object.entries(groupedEvents).map(
          ([dateKey, dateEvents]) => (
            <section key={dateKey}>
              <div className="flex items-center gap-4">
                <p className="shrink-0 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  {formatEventDate(
                    dateEvents[0].occurred_at
                  )}
                </p>

                <div className="h-px flex-1 bg-border" />
              </div>

              <div className="mt-5">
                {dateEvents.map((event, index) => {
                  const Icon = eventIcons[event.type];
                  const styles =
                    severityClasses[event.severity];

                  const isLast =
                    index === dateEvents.length - 1;

                  return (
                    <article
                      key={event.id}
                      className="relative flex gap-4 pb-6 last:pb-0"
                    >
                      {!isLast && (
                        <div
                          aria-hidden="true"
                          className={[
                            "absolute left-[21px] top-11 h-[calc(100%-2.1rem)] w-px",
                            styles.line,
                          ].join(" ")}
                        />
                      )}

                      <div
                        className={[
                          "relative z-10 flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ring-1",
                          styles.icon,
                        ].join(" ")}
                      >
                        <Icon className="h-5 w-5" />
                      </div>

                      <div className="min-w-0 flex-1 rounded-2xl border border-border bg-white/60 p-4 transition duration-200 hover:-translate-y-0.5 hover:bg-white hover:shadow-md">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <h3 className="font-semibold text-foreground">
                              {event.title}
                            </h3>

                            {event.description && (
                              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                                {event.description}
                              </p>
                            )}
                          </div>

                          <div className="flex shrink-0 items-center gap-2">
                            <span
                              className={[
                                "rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1",
                                styles.badge,
                              ].join(" ")}
                            >
                              {
                                severityLabels[
                                  event.severity
                                ]
                              }
                            </span>

                            <time
                              dateTime={event.occurred_at}
                              className="text-xs font-medium text-muted-foreground"
                            >
                              {formatEventTime(
                                event.occurred_at
                              )}
                            </time>
                          </div>
                        </div>

                        {(event.actor ||
                          event.entity?.label) && (
                          <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-border pt-3 text-xs text-muted-foreground">
                            {event.actor && (
                              <span>
                                Operatore:{" "}
                                <strong className="font-semibold text-foreground">
                                  {event.actor.name}
                                </strong>
                              </span>
                            )}

                            {event.entity?.label && (
                              <span>
                                Risorsa:{" "}
                                <strong className="font-semibold text-foreground">
                                  {event.entity.label}
                                </strong>
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>
          )
        )}
      </div>
    </GlassPanel>
  );
}