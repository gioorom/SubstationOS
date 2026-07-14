"use client";

import DashboardSkeleton from "@/components/dashboard/DashboardSkeleton";
import DashboardStatCard from "@/components/dashboard/DashboardStatCard";
import RecentActivityCard from "@/components/dashboard/RecentActivityCard";
import RecentDocumentsCard from "@/components/dashboard/RecentDocumentsCard";
import SystemStatusCard from "@/components/dashboard/SystemStatusCard";

import {
  normalizeServiceStatus,
  useHealth,
} from "@/hooks/useHealth";
import { useDocuments } from "@/hooks/useDocuments";

export default function HomePage() {
  const {
    documents,
    loading: documentsLoading,
    error: documentsError,
  } = useDocuments();

  const {
    health,
    loading: healthLoading,
    error: healthError,
  } = useHealth();

  if (documentsLoading || healthLoading) {
    return <DashboardSkeleton />;
  }

  const recentDocuments = documents
    .slice()
    .sort(
      (a, b) =>
        new Date(b.uploaded_at).getTime() -
        new Date(a.uploaded_at).getTime()
    )
    .slice(0, 5);

  const recentActivities = recentDocuments.map(
    (document, index) => ({
      id: index + 1,
      title: "Documento caricato",
      description: document.filename,
      time: new Date(
        document.uploaded_at
      ).toLocaleString("it-IT"),
      type: "upload" as const,
    })
  );

  const systemStatusItems = [
    {
      id: "api",
      label: "Backend API",
      description: "FastAPI e servizi REST",
      status: normalizeServiceStatus(
        health?.services.api
      ),
    },
    {
      id: "database",
      label: "Database",
      description: "SQLite e registro documenti",
      status: normalizeServiceStatus(
        health?.services.database
      ),
    },
    {
      id: "storage",
      label: "Document Storage",
      description: "Archivio locale dei file tecnici",
      status: normalizeServiceStatus(
        health?.services.storage
      ),
    },
    {
      id: "ai",
      label: "AI Engine",
      description: "Motore AI non ancora configurato",
      status: normalizeServiceStatus(
        health?.services.ai
      ),
    },
  ];

  const workspaceOnline =
    health?.status === "online";

  return (
    <main className="px-6 py-8 lg:px-10 lg:py-10">
      <section className="relative overflow-hidden rounded-[2rem] border border-white/70 bg-white/68 p-7 shadow-[0_28px_80px_rgba(15,23,42,0.08)] backdrop-blur-2xl lg:p-9">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-blue-400/18 blur-3xl"
        />

        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-24 left-1/3 h-64 w-64 rounded-full bg-violet-400/14 blur-3xl"
        />

        <div className="relative grid gap-8 xl:grid-cols-[1.5fr_0.9fr] xl:items-center">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-blue-200/70 bg-blue-50/80 px-3 py-1.5 text-xs font-semibold text-blue-700">
              <span className="h-2 w-2 rounded-full bg-blue-500 shadow-[0_0_16px_rgba(59,130,246,0.7)]" />

              Engineering Command Center
            </div>

            <h2 className="mt-5 max-w-3xl text-4xl font-semibold tracking-tight text-foreground lg:text-5xl">
              Buongiorno Pietro.
            </h2>

            <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">
              Gestisci documenti tecnici, attività di
              commissioning, prove relè e flussi di ingegneria
              da un unico workspace operativo.
            </p>

            <div className="mt-7 grid gap-3 sm:grid-cols-2 xl:max-w-2xl">
              <div className="rounded-2xl border border-white/70 bg-white/60 p-4 shadow-sm backdrop-blur-xl">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Oggi
                </p>

                <p className="mt-2 text-sm font-semibold text-foreground">
                  {documents.length} documenti disponibili
                </p>

                <p className="mt-1 text-sm text-muted-foreground">
                  Workspace documentale operativo
                </p>
              </div>

              <div className="rounded-2xl border border-white/70 bg-white/60 p-4 shadow-sm backdrop-blur-xl">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Stato workspace
                </p>

                <p className="mt-2 text-sm font-semibold text-foreground">
                  {workspaceOnline
                    ? "Servizi principali operativi"
                    : "Verifica servizi richiesta"}
                </p>

                <p className="mt-1 text-sm text-muted-foreground">
                  Stato recuperato dal backend
                </p>
              </div>
            </div>
          </div>

          <div className="relative mx-auto w-full max-w-md">
            <div className="relative aspect-square overflow-hidden rounded-[2rem] border border-white/70 bg-gradient-to-br from-slate-950 via-slate-900 to-blue-950 p-6 shadow-[0_35px_90px_rgba(15,23,42,0.28)]">
              <div
                aria-hidden="true"
                className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(96,165,250,0.28),transparent_30%),radial-gradient(circle_at_80%_75%,rgba(139,92,246,0.18),transparent_32%)]"
              />

              <div className="relative flex h-full flex-col justify-between">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-200/70">
                      Live workspace
                    </p>

                    <p className="mt-2 text-lg font-semibold text-white">
                      Substation Core
                    </p>
                  </div>

                  <span
                    className={[
                      "inline-flex items-center gap-2 rounded-full",
                      "border px-3 py-1 text-xs font-semibold",
                      workspaceOnline
                        ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-300"
                        : "border-amber-400/20 bg-amber-400/10 text-amber-300",
                    ].join(" ")}
                  >
                    <span
                      className={[
                        "h-2 w-2 rounded-full",
                        workspaceOnline
                          ? "bg-emerald-400"
                          : "bg-amber-400",
                      ].join(" ")}
                    />

                    {workspaceOnline
                      ? "Online"
                      : "Warning"}
                  </span>
                </div>

                <div className="relative flex flex-1 items-center justify-center">
                  <div className="relative h-44 w-44">
                    <div className="absolute inset-0 rounded-[2.4rem] border border-blue-300/20 bg-blue-400/10 shadow-[inset_0_0_50px_rgba(59,130,246,0.08)] backdrop-blur-xl [transform:rotateX(58deg)_rotateZ(-28deg)]" />

                    <div className="absolute left-1/2 top-1/2 h-28 w-28 -translate-x-1/2 -translate-y-1/2 rounded-[2rem] border border-violet-300/20 bg-violet-400/10 shadow-[0_20px_50px_rgba(59,130,246,0.15)] [transform:rotateX(58deg)_rotateZ(-28deg)_translateZ(30px)]" />

                    <div className="absolute left-1/2 top-1/2 h-16 w-16 -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-white/20 bg-white/10 shadow-[0_15px_40px_rgba(96,165,250,0.25)] [transform:rotateX(58deg)_rotateZ(-28deg)_translateZ(60px)]" />
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                    <p className="text-[11px] uppercase tracking-wide text-white/50">
                      Docs
                    </p>

                    <p className="mt-1 text-lg font-semibold text-white">
                      {documents.length}
                    </p>
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                    <p className="text-[11px] uppercase tracking-wide text-white/50">
                      DB
                    </p>

                    <p className="mt-1 text-lg font-semibold text-white">
                      {health?.services.database === "online"
                        ? "On"
                        : "Off"}
                    </p>
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                    <p className="text-[11px] uppercase tracking-wide text-white/50">
                      AI
                    </p>

                    <p className="mt-1 text-lg font-semibold text-amber-300">
                      Offline
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mt-8 grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <DashboardStatCard
          title="Documents"
          value={documents.length}
          subtitle="Documenti registrati"
          trend="+12% questo mese"
          icon={
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              className="h-6 w-6"
            >
              <path d="M6 3h8l4 4v14H6z" />
              <path d="M14 3v5h5" />
              <path d="M9 13h6" />
              <path d="M9 17h6" />
            </svg>
          }
        />

        <DashboardStatCard
          title="Projects"
          value="0"
          subtitle="Commesse attive"
          icon={
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              className="h-6 w-6"
            >
              <path d="M3 7h7l2 2h9v11H3z" />
              <path d="M3 7V4h7l2 3" />
            </svg>
          }
        />

        <DashboardStatCard
          title="Commissioning"
          value="0"
          subtitle="Attività in corso"
          icon={
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              className="h-6 w-6"
            >
              <path d="M12 3v7" />
              <path d="M8 7h8" />
              <path d="M5 13h14" />
              <path d="M7 13v8" />
              <path d="M17 13v8" />
            </svg>
          }
        />

        <DashboardStatCard
          title="AI Assistant"
          value="Offline"
          subtitle="Configurazione futura"
          icon={
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              className="h-6 w-6"
            >
              <rect
                x="4"
                y="5"
                width="16"
                height="14"
                rx="4"
              />
              <path d="M9 10h.01" />
              <path d="M15 10h.01" />
              <path d="M9 15h6" />
              <path d="M12 2v3" />
            </svg>
          }
        />
      </section>

      {(documentsError || healthError) && (
        <section className="mt-8 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          {documentsError || healthError}
        </section>
      )}

      <section className="mt-8 grid gap-6 xl:grid-cols-2">
        <RecentDocumentsCard
          documents={recentDocuments}
        />

        <RecentActivityCard
          activities={recentActivities}
        />
      </section>

      <section className="mt-8 grid gap-6 xl:grid-cols-[1fr_1.2fr]">
        <SystemStatusCard
          items={systemStatusItems}
        />

        <section className="overflow-hidden rounded-[2rem] border border-white/70 bg-gradient-to-br from-blue-600 via-blue-500 to-violet-500 p-7 text-white shadow-[0_28px_80px_rgba(37,99,235,0.25)] lg:p-9">
          <p className="text-sm font-semibold text-white/75">
            SubstationOS AI
          </p>

          <h2 className="mt-2 text-2xl font-semibold tracking-tight lg:text-3xl">
            Il workspace intelligente sarà disponibile qui.
          </h2>

          <p className="mt-3 max-w-2xl text-sm leading-6 text-white/78">
            Analisi documentale, ricerca tecnica e supporto
            alle attività di ingegneria verranno collegati
            quando il motore AI sarà configurato.
          </p>

          <button
            type="button"
            disabled
            className="mt-7 rounded-2xl border border-white/20 bg-white/10 px-5 py-3 text-sm font-semibold text-white/60"
          >
            AI non configurata
          </button>
        </section>
      </section>
    </main>
  );
}