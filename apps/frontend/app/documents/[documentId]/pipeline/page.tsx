"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { ArrowLeft, Download, Microscope, RefreshCw } from "lucide-react";

import {
  CanonicalTextInspector,
  EntityInspector,
  EvidenceInspector,
  FactInspector,
  SemanticInspector,
} from "@/components/pipeline/ArtifactInspector";
import PipelineStageCard from "@/components/pipeline/PipelineStageCard";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

import { useDocument } from "@/hooks/useDocuments";
import { usePipeline } from "@/hooks/usePipeline";
import type { PipelineStageId } from "@/lib/contracts";

/**
 * The deterministic pipeline of one document, stage by stage.
 *
 * Every number on this page comes from a stage endpoint. Nothing is
 * counted client-side, nothing is estimated, and a stage that has not run
 * says so rather than showing a zero.
 */
export default function DocumentPipelinePage() {
  const params = useParams<{ documentId: string }>();
  const documentId = Number(params.documentId);
  const valid = Number.isInteger(documentId);

  // `GET /documents/{id}` since Milestone 30.1.3. Before that this page
  // had to find its document inside the whole list, because no
  // per-document read existed.
  const {
    document: detail,
    loading: documentLoading,
    error: documentError,
    download,
    downloading,
    downloadError,
  } = useDocument(valid ? documentId : undefined);

  const pipeline = usePipeline(
    valid ? documentId : undefined,
    detail?.uploaded_at,
  );

  const [openStage, setOpenStage] = useState<PipelineStageId | null>(null);

  /**
   * Facts and statements reference entities by key. Resolving those keys
   * to labels here is presentation, not inference: the mapping comes from
   * the entity set the backend returned.
   */
  const entityLabels = useMemo(() => {
    const labels = new Map<string, string>();

    for (const entity of pipeline.snapshot?.entities?.entities ?? []) {
      labels.set(entity.entity_key, entity.label);
    }

    return labels;
  }, [pipeline.snapshot]);

  if (!valid) {
    return (
      <main className="px-6 py-8 lg:px-10 lg:py-10">
        <p className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          Identificativo documento non valido.
        </p>
      </main>
    );
  }

  return (
    <main className="px-6 py-8 lg:px-10 lg:py-10">
      <Link
        href="/documents"
        className={buttonVariants({ variant: "ghost" })}
      >
        <ArrowLeft className="h-4 w-4" />
        Torna ai documenti
      </Link>

      <section className="mt-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-primary">
            Engineering Pipeline
          </p>

          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
            {documentLoading
              ? "Caricamento documento..."
              : (detail?.filename ?? `Documento ${documentId}`)}
          </h1>

          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Ogni stage è deterministico e versionato. Il PDF originale
            resta sempre la fonte autorevole; ciò che vedi qui sono gli
            artefatti che il backend ne ha derivato.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          {/*
            This page is operational: which stages ran, and with what
            result. What the artefacts *say*, and what supports each
            claim, is the Workspace's question and lives on its own route.
          */}
          <Link
            href={`/documents/${documentId}/workspace`}
            className={buttonVariants({ variant: "default" })}
          >
            <Microscope className="h-4 w-4" />
            Apri Engineering Workspace
          </Link>

          {/*
            The download goes through the governed endpoint. The frontend
            never knows where the file is stored, and the filename is the
            one the backend sanitised.
          */}
          <Button
            type="button"
            variant="outline"
            onClick={() => void download().catch(() => undefined)}
            disabled={downloading || detail?.content_available !== true}
            title={
              detail?.content_available === false
                ? "Il file archiviato non è più disponibile"
                : undefined
            }
          >
            <Download className="h-4 w-4" />
            {downloading ? "Download..." : "Scarica originale"}
          </Button>

          <Button
            type="button"
            variant="outline"
            onClick={() => void pipeline.reload()}
            disabled={pipeline.refreshing}
          >
            <RefreshCw
              className={`h-4 w-4 ${pipeline.refreshing ? "animate-spin" : ""}`}
            />
            Aggiorna
          </Button>
        </div>
      </section>

      {detail && (
        <dl className="mt-6 grid gap-4 rounded-2xl border border-slate-200 bg-white/70 p-5 sm:grid-cols-2 xl:grid-cols-4">
          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">
              Progetto
            </dt>
            <dd className="mt-1 text-sm font-medium text-foreground">
              {detail.project_name}
            </dd>
          </div>

          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">
              Checksum del contenuto
            </dt>
            <dd className="mt-1 font-mono text-xs text-foreground">
              {detail.content_checksum
                ? `${detail.checksum_algorithm}:${detail.content_checksum.slice(0, 16)}…`
                : "Non ancora calcolato"}
            </dd>
          </div>

          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">
              Dimensione
            </dt>
            <dd className="mt-1 text-sm text-foreground">
              {detail.size_bytes === null
                ? "—"
                : `${(detail.size_bytes / 1024).toFixed(1)} KB`}
            </dd>
          </div>

          <div>
            <dt className="text-xs uppercase tracking-wide text-muted-foreground">
              Contenuto originale
            </dt>
            <dd className="mt-1 text-sm text-foreground">
              {detail.content_available
                ? "Disponibile"
                : "Non disponibile"}
            </dd>
          </div>
        </dl>
      )}

      {(documentError || downloadError) && (
        <p
          role="alert"
          className="mt-6 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700"
        >
          {documentError ?? downloadError}
        </p>
      )}

      {pipeline.error && (
        <p
          role="alert"
          className="mt-6 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700"
        >
          {pipeline.error}
        </p>
      )}

      {pipeline.loading && (
        <div className="mt-8 space-y-4">
          {Array.from({ length: 7 }).map((_, index) => (
            <Skeleton key={index} className="h-52 rounded-3xl" />
          ))}
        </div>
      )}

      {!pipeline.loading && !pipeline.error && (
        <div className="mt-8 space-y-4">
          {pipeline.stages.map((stage, index) => (
            <div key={stage.id}>
              <PipelineStageCard
                stage={stage}
                index={index}
                onRun={() => {
                  if (stage.id !== "uploaded") {
                    void pipeline.runStage(stage.id);
                  }
                }}
                onInspect={
                  hasInspector(stage.id)
                    ? () =>
                        setOpenStage((current) =>
                          current === stage.id ? null : stage.id,
                        )
                    : undefined
                }
                inspectLabel={
                  openStage === stage.id
                    ? "Chiudi artefatti"
                    : "Ispeziona artefatti"
                }
              />

              {openStage === stage.id && (
                <section className="mt-3 rounded-3xl border border-slate-200 bg-white/80 p-5">
                  {stage.id === "canonical_text" &&
                    pipeline.snapshot?.text && (
                      <CanonicalTextInspector
                        text={pipeline.snapshot.text}
                      />
                    )}

                  {stage.id === "engineering_evidence" &&
                    pipeline.snapshot?.evidence && (
                      <EvidenceInspector
                        set={pipeline.snapshot.evidence}
                      />
                    )}

                  {stage.id === "engineering_entities" &&
                    pipeline.snapshot?.entities && (
                      <EntityInspector
                        set={pipeline.snapshot.entities}
                      />
                    )}

                  {stage.id === "engineering_facts" &&
                    pipeline.snapshot?.facts && (
                      <FactInspector
                        set={pipeline.snapshot.facts}
                        entityLabels={entityLabels}
                      />
                    )}

                  {stage.id === "engineering_semantics" &&
                    pipeline.snapshot?.semantics && (
                      <SemanticInspector
                        set={pipeline.snapshot.semantics}
                        entityLabels={entityLabels}
                      />
                    )}
                </section>
              )}
            </div>
          ))}
        </div>
      )}
    </main>
  );
}

function hasInspector(stage: PipelineStageId): boolean {
  return (
    stage === "canonical_text" ||
    stage === "engineering_evidence" ||
    stage === "engineering_entities" ||
    stage === "engineering_facts" ||
    stage === "engineering_semantics"
  );
}
