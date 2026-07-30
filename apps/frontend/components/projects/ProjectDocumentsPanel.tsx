"use client";

import Link from "next/link";
import { FileText, Upload } from "lucide-react";

import EmptyState from "@/components/common/EmptyState";
import GlassPanel from "@/components/design-system/GlassPanel";
import { Button } from "@/components/ui/button";
import { DOCUMENT_FORMAT_LABELS } from "@/lib/contracts";
import type { DocumentSummary } from "@/lib/contracts";

interface ProjectDocumentsPanelProps {
  documents: DocumentSummary[];
  loading: boolean;
  error: string | null;
}

/**
 * Renders documents the page already loaded rather than fetching its own
 * copy. The previous version called `useDocuments(projectId)` a second
 * time, so the same list was held twice and could disagree with itself
 * after an upload.
 */
export default function ProjectDocumentsPanel({
  documents,
  loading,
  error,
}: ProjectDocumentsPanelProps) {
  if (loading) {
    return (
      <GlassPanel padding="lg">
        <div className="space-y-4">
          <div className="h-8 w-52 animate-pulse rounded-xl bg-muted" />

          {Array.from({ length: 4 }).map((_, index) => (
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
          description="Carica il primo documento tecnico della commessa per avviare la pipeline di ingegneria."
        />
      </GlassPanel>
    );
  }

  return (
    <GlassPanel padding="lg">
      <div>
        <h2 className="text-xl font-semibold">Documentazione</h2>

        <p className="mt-1 text-sm text-muted-foreground">
          {documents.length} documenti associati alla commessa
        </p>
      </div>

      <div className="mt-6 space-y-3">
        {documents.map((item) => (
          <div
            key={item.id}
            className="flex items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
          >
            <div className="min-w-0">
              <p className="truncate font-medium">{item.filename}</p>

              <p className="mt-1 text-sm text-muted-foreground">
                Revisione {item.revision} ·{" "}
                {new Date(item.uploaded_at).toLocaleDateString("it-IT")}
              </p>
            </div>

            <div className="flex shrink-0 items-center gap-3">
              <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold uppercase text-primary">
                {DOCUMENT_FORMAT_LABELS[item.file_format] ??
                  item.file_format}
              </span>

              <Button asChild variant="outline" size="sm">
                <Link href={`/documents/${item.id}/workspace`}>
                  Workspace
                </Link>
              </Button>
            </div>
          </div>
        ))}
      </div>
    </GlassPanel>
  );
}
