"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  FileText,
  Network,
  TriangleAlert,
  Zap,
} from "lucide-react";

import MetricCard from "@/components/design-system/MetricCard";
import EngineeringIntelligencePanel from "@/components/intelligence/EngineeringIntelligencePanel";
import TodaysFocusPanel from "@/components/intelligence/TodaysFocusPanel";
import ProjectDocumentsPanel from "@/components/projects/ProjectDocumentsPanel";
import ProjectHero from "@/components/projects/ProjectHero";
import TimelinePanel from "@/components/timeline/TimelinePanel";
import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

import { useDocuments } from "@/hooks/useDocuments";
import { useProjectIntelligence } from "@/hooks/useProjectIntelligence";
import { demoTimelineEvents } from "@/lib/demo-timeline";
import { getProject } from "@/lib/projects";
import { Project } from "@/types/project";

const documentationStatusLabels = {
  empty: "Nessun documento disponibile",
  incomplete: "Set documentale incompleto",
  available: "Documentazione disponibile",
} as const;

const moduleStatusLabels = {
  not_started: "Modulo non avviato",
  in_progress: "Attività in corso",
  completed: "Attività completate",
} as const;

export default function ProjectDetailPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = useMemo(() => Number(params.projectId), [params.projectId]);
  const validProjectId = Number.isInteger(projectId) ? projectId : undefined;

  const [project, setProject] = useState<Project | null>(null);
  const [loadingProject, setLoadingProject] = useState(true);
  const [projectError, setProjectError] = useState("");

  const { documents, loading: documentsLoading } = useDocuments(validProjectId);
  const {
    intelligence,
    loading: intelligenceLoading,
    error: intelligenceError,
  } = useProjectIntelligence(validProjectId);

  useEffect(() => {
    async function loadProject() {
      if (validProjectId === undefined) {
        setProjectError("Identificativo progetto non valido.");
        setLoadingProject(false);
        return;
      }

      setLoadingProject(true);
      setProjectError("");

      try {
        setProject(await getProject(validProjectId));
      } catch {
        setProject(null);
        setProjectError("Impossibile caricare il progetto.");
      } finally {
        setLoadingProject(false);
      }
    }

    void loadProject();
  }, [validProjectId]);

  if (loadingProject || intelligenceLoading) {
    return (
      <main className="px-6 py-8 lg:px-10 lg:py-10">
        <Skeleton className="h-10 w-40" />
        <section className="mt-6"><Skeleton className="h-[440px] rounded-[2rem]" /></section>
        <section className="mt-8"><Skeleton className="h-80 rounded-[2rem]" /></section>
        <section className="mt-8 grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-44 rounded-[2rem]" />
          ))}
        </section>
        <section className="mt-8 grid gap-6 xl:grid-cols-2">
          <Skeleton className="h-[420px] rounded-[2rem]" />
          <Skeleton className="h-[420px] rounded-[2rem]" />
        </section>
        <section className="mt-8"><Skeleton className="h-[520px] rounded-[2rem]" /></section>
      </main>
    );
  }

  if (
    projectError ||
    intelligenceError ||
    !project ||
    !intelligence ||
    validProjectId === undefined
  ) {
    return (
      <main className="px-6 py-8 lg:px-10 lg:py-10">
        <section className="rounded-3xl border border-red-200 bg-red-50 p-6 text-red-700">
          <p className="font-semibold">Progetto non disponibile</p>
          <p className="mt-2 text-sm">
            {projectError || intelligenceError || "Il progetto richiesto non esiste."}
          </p>
          <Link
            href="/projects"
            className={[buttonVariants({ variant: "outline" }), "mt-5"].join(" ")}
          >
            <ArrowLeft className="h-4 w-4" />
            Torna ai progetti
          </Link>
        </section>
      </main>
    );
  }

  const lastDocument = documents
    .slice()
    .sort(
      (first, second) =>
        new Date(second.uploaded_at).getTime() -
        new Date(first.uploaded_at).getTime()
    )[0];

  const lastActivityLabel = documentsLoading
    ? "Caricamento..."
    : lastDocument
      ? new Date(lastDocument.uploaded_at).toLocaleString("it-IT")
      : "Nessuna attività recente";

  const documentationStatus = documentationStatusLabels[intelligence.documentation.status];
  const commissioningStatus = moduleStatusLabels[intelligence.commissioning.status];
  const relayTestingStatus = moduleStatusLabels[intelligence.relay_testing.status];

  const focusItems = [
    {
      id: "documentation",
      title:
        intelligence.documentation.status === "available"
          ? "Verifica revisioni documentali"
          : "Completa il set documentale minimo",
      description:
        intelligence.documentation.status === "available"
          ? "Controlla che schemi, liste cavi e report siano aggiornati all’ultima revisione disponibile."
          : intelligence.next_action,
      priority:
        intelligence.documentation.status === "empty"
          ? ("high" as const)
          : intelligence.documentation.status === "incomplete"
            ? ("medium" as const)
            : ("low" as const),
      estimatedMinutes: intelligence.documentation.status === "available" ? 30 : 45,
      completed: false,
    },
    {
      id: "commissioning",
      title: "Prepara il piano di commissioning",
      description:
        "Definisci attività, responsabilità e prerequisiti per la prossima fase operativa.",
      priority:
        intelligence.commissioning.status === "not_started"
          ? ("medium" as const)
          : ("low" as const),
      estimatedMinutes: 40,
      completed: intelligence.commissioning.status === "completed",
    },
    {
      id: "relay-testing",
      title: "Verifica il perimetro delle prove relè",
      description:
        "Conferma relè installati, configurazioni disponibili e prove ancora da pianificare.",
      priority:
        intelligence.relay_testing.status === "not_started"
          ? ("medium" as const)
          : ("low" as const),
      estimatedMinutes: 35,
      completed: intelligence.relay_testing.status === "completed",
    },
  ];

  const projectTimelineEvents = demoTimelineEvents.map((event) => ({
    ...event,
    project_id: project.id,
  }));

  return (
    <main className="px-6 py-8 lg:px-10 lg:py-10">
      <Link href="/projects" className={buttonVariants({ variant: "ghost" })}>
        <ArrowLeft className="h-4 w-4" />
        Torna ai progetti
      </Link>

      <section className="mt-6">
        <ProjectHero
          project={project}
          documentCount={intelligence.documentation.document_count}
          lastActivityLabel={lastActivityLabel}
          healthScore={intelligence.health_score}
        />
      </section>

      <section className="mt-8">
        <EngineeringIntelligencePanel intelligence={intelligence} />
      </section>

      <section className="mt-8 grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Documentazione"
          value={`${intelligence.documentation.completion}%`}
          description={`${intelligence.documentation.document_count} documenti associati`}
          trend={documentationStatus}
          status={
            intelligence.documentation.status === "available"
              ? "positive"
              : intelligence.documentation.status === "incomplete"
                ? "warning"
                : "critical"
          }
          icon={<FileText className="h-6 w-6" />}
        />
        <MetricCard
          label="Commissioning"
          value={`${intelligence.commissioning.completion}%`}
          description={`${intelligence.commissioning.completed} attività completate su ${intelligence.commissioning.total}`}
          trend={commissioningStatus}
          status={
            intelligence.commissioning.status === "completed"
              ? "positive"
              : intelligence.commissioning.status === "in_progress"
                ? "warning"
                : "neutral"
          }
          icon={<Zap className="h-6 w-6" />}
        />
        <MetricCard
          label="Relay Testing"
          value={`${intelligence.relay_testing.completed} / ${intelligence.relay_testing.total}`}
          description={`${intelligence.relay_testing.completion}% delle prove completate`}
          trend={relayTestingStatus}
          status={
            intelligence.relay_testing.status === "completed"
              ? "positive"
              : intelligence.relay_testing.status === "in_progress"
                ? "warning"
                : "neutral"
          }
          icon={<Network className="h-6 w-6" />}
        />
        <MetricCard
          label="Open Issues"
          value={intelligence.issues.open}
          description={`${intelligence.issues.critical} criticità ad alta priorità`}
          trend={
            intelligence.issues.open === 0
              ? "Nessuna criticità aperta"
              : "Intervento richiesto"
          }
          status={
            intelligence.issues.critical > 0
              ? "critical"
              : intelligence.issues.open > 0
                ? "warning"
                : "positive"
          }
          icon={<TriangleAlert className="h-6 w-6" />}
        />
      </section>

      <section className="mt-8 grid gap-6 xl:grid-cols-2">
        <TodaysFocusPanel items={focusItems} />
        <ProjectDocumentsPanel projectId={project.id} />
      </section>

      <section className="mt-8">
        <TimelinePanel events={projectTimelineEvents} />
      </section>
    </main>
  );
}