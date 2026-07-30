"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Archive, ArrowLeft, Network, RotateCcw } from "lucide-react";

import EngineeringIntelligencePanel from "@/components/intelligence/EngineeringIntelligencePanel";
import ProjectDocumentsPanel from "@/components/projects/ProjectDocumentsPanel";
import ProjectHero from "@/components/projects/ProjectHero";
import UploadBox from "@/components/UploadBox";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

import { useDocuments } from "@/hooks/useDocuments";
import {
  useProject,
  type ProjectTransition,
} from "@/hooks/useProjects";
import { useProjectIntelligence } from "@/hooks/usePlatform";
import { isMutable } from "@/lib/contracts";

export default function ProjectDetailPage() {
  const params = useParams<{ projectId: string }>();
  const parsed = Number(params.projectId);
  const projectId = Number.isInteger(parsed) ? parsed : undefined;

  const {
    project,
    loading: projectLoading,
    error: projectError,
    transition,
    transitioning,
    transitionError,
  } = useProject(projectId);

  const {
    intelligence,
    loading: intelligenceLoading,
    error: intelligenceError,
  } = useProjectIntelligence(projectId);

  const {
    documents,
    loading: documentsLoading,
    error: documentsError,
    upload,
    uploading,
    uploadError,
    // Server-side filter: this project's documents only.
  } = useDocuments({ project_id: projectId, page_size: 100 });

  const [uploadProjectId, setUploadProjectId] = useState<number | undefined>(
    projectId,
  );

  if (projectId === undefined) {
    return (
      <main className="px-6 py-8 lg:px-10 lg:py-10">
        <p className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          Identificativo progetto non valido.
        </p>
      </main>
    );
  }

  if (projectLoading || intelligenceLoading) {
    return (
      <main className="px-6 py-8 lg:px-10 lg:py-10">
        <Skeleton className="h-10 w-40" />

        <div className="mt-6 space-y-8">
          <Skeleton className="h-[420px] rounded-[2rem]" />
          <Skeleton className="h-72 rounded-[2rem]" />

          <div className="grid gap-6 xl:grid-cols-2">
            <Skeleton className="h-96 rounded-[2rem]" />
            <Skeleton className="h-96 rounded-[2rem]" />
          </div>
        </div>
      </main>
    );
  }

  if (projectError || !project) {
    return (
      <main className="px-6 py-8 lg:px-10 lg:py-10">
        <section className="rounded-3xl border border-red-200 bg-red-50 p-6 text-red-700">
          <p className="font-semibold">Progetto non disponibile</p>

          <p className="mt-2 text-sm">
            {projectError ?? "Il progetto richiesto non esiste."}
          </p>

          <Link
            href="/projects"
            className={[buttonVariants({ variant: "outline" }), "mt-5"].join(
              " ",
            )}
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
        new Date(first.uploaded_at).getTime(),
    )[0];

  const lastActivityLabel = documentsLoading
    ? "Caricamento..."
    : lastDocument
      ? new Date(lastDocument.uploaded_at).toLocaleString("it-IT")
      : "Nessuna attività registrata";

  const editable = isMutable(project);

  async function runTransition(action: ProjectTransition) {
    try {
      await transition(action);
    } catch {
      // Rendered below by `transitionError`.
    }
  }

  return (
    <main className="px-6 py-8 lg:px-10 lg:py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/projects"
          className={buttonVariants({ variant: "ghost" })}
        >
          <ArrowLeft className="h-4 w-4" />
          Torna ai progetti
        </Link>

        <div className="flex flex-wrap gap-3">
          <Link
            href={`/projects/${project.id}/knowledge-graph`}
            className={buttonVariants({ variant: "outline" })}
          >
            <Network className="h-4 w-4" />
            Knowledge Graph
          </Link>

          {/* Only transitions the project's lifecycle state allows. */}
          {editable && (
            <Button
              type="button"
              variant="outline"
              disabled={transitioning}
              onClick={() => void runTransition("archive")}
            >
              <Archive className="h-4 w-4" />
              Archivia
            </Button>
          )}

          {project.lifecycle_state === "archived" && (
            <Button
              type="button"
              variant="outline"
              disabled={transitioning}
              onClick={() => void runTransition("restore")}
            >
              <RotateCcw className="h-4 w-4" />
              Ripristina
            </Button>
          )}
        </div>
      </div>

      {transitionError && (
        <p
          role="alert"
          className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700"
        >
          {transitionError}
        </p>
      )}

      <section className="mt-6">
        <ProjectHero
          project={project}
          documentCount={
            intelligence?.documentation.document_count ?? documents.length
          }
          lastActivityLabel={lastActivityLabel}
          healthScore={intelligence?.health_score ?? 0}
        />
      </section>

      {intelligenceError && (
        <p className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-800">
          {intelligenceError}
        </p>
      )}

      {intelligence && (
        <section className="mt-8">
          <EngineeringIntelligencePanel intelligence={intelligence} />
        </section>
      )}

      <section className="mt-8 grid gap-6 xl:grid-cols-2">
        <div id="project-upload-box">
          {editable ? (
            <UploadBox
              onUpload={upload}
              uploading={uploading}
              uploadError={uploadError}
              projects={[project]}
              selectedProjectId={uploadProjectId ?? project.id}
              onProjectChange={setUploadProjectId}
              description="Il documento viene archiviato e classificato dal backend, poi può essere elaborato dalla pipeline di ingegneria."
            />
          ) : (
            <section className="rounded-3xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-800">
              Il progetto è{" "}
              <strong>{project.lifecycle_state}</strong> e non accetta
              nuovi documenti.
            </section>
          )}
        </div>

        <ProjectDocumentsPanel
          documents={documents}
          loading={documentsLoading}
          error={documentsError}
        />
      </section>
    </main>
  );
}
