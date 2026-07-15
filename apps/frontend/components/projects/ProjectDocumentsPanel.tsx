"use client";

import Link from "next/link";
import { FileText, Upload } from "lucide-react";

import EmptyState from "@/components/common/EmptyState";
import GlassPanel from "@/components/design-system/GlassPanel";
import { Button } from "@/components/ui/button";

import { useDocuments } from "@/hooks/useDocuments";

interface ProjectDocumentsPanelProps {
  projectId: number;
}

export default function ProjectDocumentsPanel({
  projectId,
}: ProjectDocumentsPanelProps) {
  const {
    documents,
    loading,
    error,
  } = useDocuments(projectId);

  if (loading) {
    return (
      <GlassPanel padding="lg">
        <div className="space-y-4">
          <div className="h-8 w-52 animate-pulse rounded-xl bg-muted" />

          {Array.from({ length: 5 }).map((_, index) => (
            <div
              key={index}
              className="h-16 animate-pulse rounded-2xl bg-muted"
            />
          ))}
        </div>
      </GlassPanel>
    );
  }

  if (error) {
    return (
      <GlassPanel padding="lg">
        <EmptyState
          icon={<FileText className="h-8 w-8" />}
          title="Impossibile caricare i documenti"
          description={error}
        />
      </GlassPanel>
    );
  }

  if (documents.length === 0) {
    return (
      <GlassPanel padding="lg">
        <EmptyState
          icon={<Upload className="h-8 w-8" />}
          title="La documentazione è ancora vuota"
          description="Carica il primo schema funzionale, lista cavi, report di commissioning o qualsiasi documento tecnico per iniziare a costruire la documentazione della commessa."
          actionLabel="Carica documento"
          onAction={() => {
            const element =
              document.getElementById(
                "project-upload-box"
              );

            element?.scrollIntoView({
              behavior: "smooth",
              block: "center",
            });
          }}
        />
      </GlassPanel>
    );
  }

  return (
    <GlassPanel padding="lg">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">
            Documentazione
          </h2>

          <p className="mt-1 text-sm text-muted-foreground">
            {documents.length} documenti associati
            alla commessa
          </p>
        </div>

        <Button asChild variant="outline">
          <Link href={`/projects/${projectId}`}>
            Apri Workspace
          </Link>
        </Button>
      </div>

      <div className="mt-6 space-y-3">
        {documents.map((document) => (
          <div
            key={document.id}
            className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
          >
            <div className="min-w-0">
              <p className="truncate font-medium">
                {document.filename}
              </p>

              <p className="mt-1 text-sm text-muted-foreground">
                Revisione {document.revision}
              </p>
            </div>

            <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold uppercase text-primary">
              {document.file_format}
            </span>
          </div>
        ))}
      </div>
    </GlassPanel>
  );
}