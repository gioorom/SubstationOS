"use client";

import Link from "next/link";
import { FileText, FolderKanban, HeartPulse, Server } from "lucide-react";

import DashboardSkeleton from "@/components/dashboard/DashboardSkeleton";
import DashboardStatCard from "@/components/dashboard/DashboardStatCard";
import RecentDocumentsCard from "@/components/dashboard/RecentDocumentsCard";
import SystemStatusCard from "@/components/dashboard/SystemStatusCard";
import { buttonVariants } from "@/components/ui/button";

import { useDocuments } from "@/hooks/useDocuments";
import { useHealth } from "@/hooks/usePlatform";
import { useProjects } from "@/hooks/useProjects";
import { isMutable } from "@/lib/contracts";

/**
 * Every figure on this page is read from the backend.
 *
 * The previous dashboard hardcoded "0" for projects and commissioning,
 * an "AI Assistant: Offline" tile and a "+12% questo mese" trend that no
 * endpoint produced. Counters that are not measurements are worse than
 * absent ones - they are read as measurements.
 */
export default function HomePage() {
  const {
    documents,
    loading: documentsLoading,
    error: documentsError,
  } = useDocuments();

  const {
    projects,
    loading: projectsLoading,
    error: projectsError,
  } = useProjects();

  const { health, loading: healthLoading, error: healthError } = useHealth();

  if (documentsLoading || projectsLoading || healthLoading) {
    return <DashboardSkeleton />;
  }

  const recentDocuments = documents
    .slice()
    .sort(
      (first, second) =>
        new Date(second.uploaded_at).getTime() -
        new Date(first.uploaded_at).getTime(),
    )
    .slice(0, 5);

  const activeProjects = projects.filter(isMutable);

  const systemStatusItems = [
    {
      id: "api",
      label: "Backend API",
      description: "FastAPI e servizi REST",
      status: health?.services.api ?? "offline",
    },
    {
      id: "database",
      label: "Database",
      description: "Registro progetti e documenti",
      status: health?.services.database ?? "offline",
    },
    {
      id: "storage",
      label: "Document Storage",
      description: "Archivio dei file tecnici",
      status: health?.services.storage ?? "offline",
    },
    {
      id: "ai",
      label: "AI Engine",
      description: "Non richiesto dalla pipeline deterministica",
      status: health?.services.ai ?? "offline",
    },
  ];

  return (
    <main className="px-6 py-8 lg:px-10 lg:py-10">
      <section className="rounded-[2rem] border border-white/70 bg-white/68 p-7 shadow-[0_28px_80px_rgba(15,23,42,0.08)] backdrop-blur-2xl lg:p-9">
        <div className="inline-flex items-center gap-2 rounded-full border border-blue-200/70 bg-blue-50/80 px-3 py-1.5 text-xs font-semibold text-blue-700">
          <span className="h-2 w-2 rounded-full bg-blue-500" />
          Engineering Command Center
        </div>

        <h1 className="mt-5 max-w-3xl text-4xl font-semibold tracking-tight text-foreground lg:text-5xl">
          SubstationOS
        </h1>

        <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">
          Carica documentazione tecnica ed eseguine la pipeline
          deterministica: rappresentazione canonica, testo, evidenze,
          entità, fatti e interpretazione semantica.
        </p>

        <div className="mt-7 flex flex-wrap gap-3">
          <Link href="/projects" className={buttonVariants()}>
            <FolderKanban className="h-4 w-4" />
            Apri i progetti
          </Link>

          <Link
            href="/documents"
            className={buttonVariants({ variant: "outline" })}
          >
            <FileText className="h-4 w-4" />
            Registro documenti
          </Link>
        </div>
      </section>

      <section className="mt-8 grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <DashboardStatCard
          title="Documents"
          value={documents.length}
          subtitle="Documenti registrati"
          icon={<FileText className="h-6 w-6" />}
        />

        <DashboardStatCard
          title="Projects"
          value={projects.length}
          subtitle={`${activeProjects.length} modificabili`}
          icon={<FolderKanban className="h-6 w-6" />}
        />

        <DashboardStatCard
          title="Servizi"
          value={
            health?.status === "online"
              ? "Operativi"
              : health?.status === "warning"
                ? "Degradati"
                : "Non verificati"
          }
          subtitle="Stato riportato da /health"
          icon={<HeartPulse className="h-6 w-6" />}
        />

        <DashboardStatCard
          title="Database"
          value={health?.services.database === "online" ? "Online" : "Offline"}
          subtitle="Connessione verificata dal backend"
          icon={<Server className="h-6 w-6" />}
        />
      </section>

      {(documentsError || projectsError || healthError) && (
        <section
          role="alert"
          className="mt-8 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700"
        >
          {documentsError ?? projectsError ?? healthError}
        </section>
      )}

      <section className="mt-8 grid gap-6 xl:grid-cols-2">
        <RecentDocumentsCard documents={recentDocuments} />

        <SystemStatusCard items={systemStatusItems} />
      </section>
    </main>
  );
}
