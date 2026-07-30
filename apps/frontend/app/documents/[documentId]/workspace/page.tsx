"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { ArrowLeft, Download, RefreshCw, Workflow } from "lucide-react";

import DiagnosticsExplorer from "@/components/workspace/DiagnosticsExplorer";
import EngineeringExplorer, {
  type ExplorerTab,
} from "@/components/workspace/EngineeringExplorer";
import EntityExplorer from "@/components/workspace/EntityExplorer";
import EvidenceExplorer from "@/components/workspace/EvidenceExplorer";
import FactExplorer from "@/components/workspace/FactExplorer";
import InspectorPanel from "@/components/workspace/InspectorPanel";
import SemanticExplorer from "@/components/workspace/SemanticExplorer";
import SourceViewer from "@/components/workspace/SourceViewer";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

import { useCanonicalPage } from "@/hooks/useCanonicalPage";
import { useDocumentReviews } from "@/hooks/useDocumentReviews";
import { useDocument } from "@/hooks/useDocuments";
import { useWorkspace } from "@/hooks/useWorkspace";
import { useWorkspaceSelection } from "@/hooks/useWorkspaceSelection";
import {
  describeLocation,
  locationsForSelection,
  reconcileDiagnosticStatus,
  resolveSpanBoxes,
  resolveStatementQuantity,
  type SelectionKind,
  type StageStatus,
} from "@/lib/workspace";

/**
 * The Engineering Workspace.
 *
 * The Pipeline page answers *did the pipeline run*. This page answers
 * *what does the platform claim about this document, and why should an
 * engineer believe it* - which is a different question and gets its own
 * route rather than a tab on the operational one.
 *
 * Three regions: the source on the left, the engineering artefacts in
 * the middle, the selected artefact's identity and support chain on the
 * right. Selecting anywhere moves the other two, and every move follows
 * a reference the backend wrote down.
 *
 * **Inspection only.** There is no approve, reject, correct or annotate
 * here, and their absence is deliberate: a validation this system cannot
 * record is a validation it must not appear to offer.
 */
export default function DocumentWorkspacePage() {
  return (
    // `useSearchParams` requires a boundary; the selection lives in the
    // query string, so this page has one.
    <Suspense fallback={<WorkspaceSkeleton />}>
      <Workspace />
    </Suspense>
  );
}

function WorkspaceSkeleton() {
  return (
    <main className="px-6 py-8 lg:px-10">
      <Skeleton className="h-8 w-64 rounded-xl" />
      <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(0,0.9fr)]">
        <Skeleton className="h-[70vh] rounded-3xl" />
        <Skeleton className="h-[70vh] rounded-3xl" />
        <Skeleton className="h-[70vh] rounded-3xl" />
      </div>
    </main>
  );
}

function Workspace() {
  const params = useParams<{ documentId: string }>();
  const documentId = Number(params.documentId);
  const valid = Number.isInteger(documentId);

  const {
    document: detail,
    loading: documentLoading,
    error: documentError,
    download,
    downloading,
    downloadError,
  } = useDocument(valid ? documentId : undefined);

  const workspace = useWorkspace(valid ? documentId : undefined);

  // One request for every statement's current judgement. Settles
  // independently of the artefact reads, so a review summary that fails
  // leaves the whole Workspace inspectable - the badges simply do not
  // appear.
  const reviews = useDocumentReviews(valid ? documentId : undefined);

  const { selection, select } = useWorkspaceSelection();

  const [tab, setTab] = useState<ExplorerTab>("semantic");

  /**
   * Where the selection points in the source.
   *
   * Only explicit references are followed: an entity's own evidence, a
   * fact's own support, a statement's own chain. Nothing is located by
   * matching text.
   */
  const locations = useMemo(
    () =>
      selection === null
        ? []
        : locationsForSelection(
            workspace.index,
            selection.kind,
            selection.key,
          ),
    [workspace.index, selection],
  );

  const selectionId =
    selection === null ? null : `${selection.kind}:${selection.key}`;

  const selectionPage = locations[0]?.page_number ?? null;

  /**
   * Page navigation, without an effect that writes state during render.
   *
   * The selection proposes a page; a manual step overrides it until the
   * selection changes, at which point the new artefact's page wins
   * again. That is the synchronisation the EPIC asks for, expressed as a
   * derivation rather than as a `useEffect` that fights the user.
   */
  const [override, setOverride] = useState<{
    forSelection: string | null;
    page: number;
  } | null>(null);

  const pageNumber =
    override !== null && override.forSelection === selectionId
      ? override.page
      : (selectionPage ?? override?.page ?? 1);

  const pageCount =
    workspace.snapshot?.representation.data?.page_count ?? null;

  const canonicalPage = useCanonicalPage(
    valid ? documentId : undefined,
    pageNumber,
  );

  /**
   * Rectangles for the observations of this selection that are on this
   * page, resolved by explicit span identity. A location whose span the
   * page does not record contributes nothing - the highlight is short,
   * never approximate.
   */
  const highlights = useMemo(
    () =>
      locations.flatMap((location) =>
        resolveSpanBoxes(canonicalPage.page, location),
      ),
    [canonicalPage.page, locations],
  );

  const caption = useMemo(() => {
    if (selection === null) {
      return null;
    }

    if (locations.length === 0) {
      return "L'artefatto selezionato non dichiara una posizione nel sorgente.";
    }

    const onPage = locations.filter(
      (location) => location.page_number === pageNumber,
    );

    if (onPage.length === 0) {
      return `L'artefatto selezionato è a ${describeLocation(locations[0])}.`;
    }

    return `${describeLocation(onPage[0])}${
      highlights.length === 0
        ? " — nessuna coordinata registrata per questo riferimento: la posizione è indicata per riga, non evidenziata."
        : ` — ${highlights.length} riferimento/i evidenziato/i.`
    }`;
  }, [selection, locations, pageNumber, highlights.length]);

  if (!valid) {
    return (
      <main className="px-6 py-8 lg:px-10">
        <p
          role="alert"
          className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700"
        >
          Identificativo documento non valido.
        </p>
      </main>
    );
  }

  const snapshot = workspace.snapshot;

  const unrun: StageStatus = {
    availability: "unrun",
    error: null,
    count: null,
  };

  const statuses: Record<ExplorerTab, StageStatus> = {
    semantic: snapshot?.semantics.status ?? unrun,
    fact: snapshot?.facts.status ?? unrun,
    entity: snapshot?.entities.status ?? unrun,
    evidence: snapshot?.evidence.status ?? unrun,
    // Diagnostics have no stage of their own; they come from two. The
    // same reconciliation feeds the tab badge and the list beneath it,
    // so the two cannot disagree about what is being shown.
    diagnostic: reconcileDiagnosticStatus(
      snapshot?.facts.status ?? unrun,
      snapshot?.semantics.status ?? unrun,
      workspace.index.diagnosticsByKey.size,
    ),
  };

  const onSelect = (kind: SelectionKind, key: string) => {
    select(kind, key);

    // Following a chain step must move the explorer to where that
    // artefact lives, or the selection would be invisible.
    setTab(kind);
  };

  return (
    <main className="flex min-h-0 flex-col px-6 py-8 lg:px-10">
      <Link
        href="/documents"
        className={buttonVariants({ variant: "ghost" })}
      >
        <ArrowLeft className="h-4 w-4" />
        Torna ai documenti
      </Link>

      <section className="mt-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-primary">
            Engineering Workspace
          </p>

          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-foreground">
            {documentLoading
              ? "Caricamento documento…"
              : (detail?.filename ?? `Documento ${documentId}`)}
          </h1>

          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Ogni affermazione mostrata qui è risalibile fino alla riga del
            documento che la sostiene. Nulla in questa pagina è stato
            approvato da un ingegnere: la validazione umana non fa parte di
            questo milestone.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <Link
            href={`/documents/${documentId}/pipeline`}
            className={buttonVariants({ variant: "outline" })}
          >
            <Workflow className="h-4 w-4" />
            Pipeline operativa
          </Link>

          <Button
            type="button"
            variant="outline"
            onClick={() => void download().catch(() => undefined)}
            disabled={downloading || detail?.content_available !== true}
          >
            <Download className="h-4 w-4" />
            {downloading ? "Download…" : "Scarica originale"}
          </Button>

          <Button
            type="button"
            variant="outline"
            onClick={() => void workspace.reload()}
            disabled={workspace.refreshing}
          >
            <RefreshCw
              className={`h-4 w-4 ${workspace.refreshing ? "animate-spin" : ""}`}
            />
            Aggiorna
          </Button>
        </div>
      </section>

      {(documentError || downloadError || workspace.error) && (
        <p
          role="alert"
          className="mt-6 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700"
        >
          {documentError ?? downloadError ?? workspace.error}
        </p>
      )}

      {workspace.loading ? (
        <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(0,0.9fr)]">
          <Skeleton className="h-[70vh] rounded-3xl" />
          <Skeleton className="h-[70vh] rounded-3xl" />
          <Skeleton className="h-[70vh] rounded-3xl" />
        </div>
      ) : (
        <div className="mt-6 grid min-h-0 gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)_minmax(0,0.9fr)]">
          <div className="min-h-0 xl:max-h-[calc(100vh-16rem)]">
            <SourceViewer
              document={detail}
              page={canonicalPage.page}
              pageLoading={canonicalPage.loading}
              pageError={canonicalPage.error}
              pageNumber={pageNumber}
              pageCount={pageCount}
              onPageChange={(next) =>
                setOverride({ forSelection: selectionId, page: next })
              }
              highlights={highlights}
              caption={caption}
            />
          </div>

          <div className="min-h-0 xl:max-h-[calc(100vh-16rem)]">
            <EngineeringExplorer
              tab={tab}
              onTabChange={setTab}
              statuses={statuses}
            >
              {tab === "semantic" && (
                <SemanticExplorer
                  statements={snapshot?.semantics.data?.statements ?? []}
                  status={statuses.semantic}
                  selectedKey={
                    selection?.kind === "semantic" ? selection.key : null
                  }
                  onSelect={(key) => onSelect("semantic", key)}
                  entityLabels={workspace.entityLabels}
                  quantityOf={(statement) =>
                    resolveStatementQuantity(workspace.index, statement)
                  }
                  reviewByStatement={reviews.byStatement}
                />
              )}

              {tab === "fact" && (
                <FactExplorer
                  facts={snapshot?.facts.data?.facts ?? []}
                  status={statuses.fact}
                  selectedKey={
                    selection?.kind === "fact" ? selection.key : null
                  }
                  onSelect={(key) => onSelect("fact", key)}
                  entityLabels={workspace.entityLabels}
                />
              )}

              {tab === "entity" && (
                <EntityExplorer
                  entities={snapshot?.entities.data?.entities ?? []}
                  status={statuses.entity}
                  selectedKey={
                    selection?.kind === "entity" ? selection.key : null
                  }
                  onSelect={(key) => onSelect("entity", key)}
                />
              )}

              {tab === "evidence" && (
                <EvidenceExplorer
                  documentId={documentId}
                  evidence={snapshot?.evidence.data?.evidence ?? []}
                  status={statuses.evidence}
                  selectedKey={
                    selection?.kind === "evidence" ? selection.key : null
                  }
                  onSelect={(key) => onSelect("evidence", key)}
                  pages={workspace.index.pages}
                />
              )}

              {tab === "diagnostic" && (
                <DiagnosticsExplorer
                  diagnostics={[
                    ...workspace.index.diagnosticsByKey.values(),
                  ]}
                  factStatus={statuses.fact}
                  semanticStatus={statuses.semantic}
                  selectedKey={
                    selection?.kind === "diagnostic" ? selection.key : null
                  }
                  onSelect={(key) => onSelect("diagnostic", key)}
                  entityLabels={workspace.entityLabels}
                />
              )}
            </EngineeringExplorer>
          </div>

          <div className="min-h-0 xl:max-h-[calc(100vh-16rem)]">
            <InspectorPanel
              selection={selection}
              index={workspace.index}
              entityLabels={workspace.entityLabels}
              onSelect={onSelect}
            />
          </div>
        </div>
      )}
    </main>
  );
}
