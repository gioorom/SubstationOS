"use client";

import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Download, ZoomIn, ZoomOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { documentContentUrl } from "@/lib/resources/documents";
import type {
  BoundingBox,
  CanonicalPdfPage,
  DocumentDetail,
} from "@/lib/contracts";
import { DOCUMENT_FORMAT_LABELS } from "@/lib/contracts";

import CanonicalPageMap from "./CanonicalPageMap";

const ZOOM_STEPS = [0.5, 0.75, 1, 1.5, 2, 3] as const;

type ViewerTab = "canonical" | "original";

interface SourceViewerProps {
  document: DocumentDetail | null;
  page: CanonicalPdfPage | null;
  pageLoading: boolean;
  pageError: string | null;
  pageNumber: number;
  pageCount: number | null;
  onPageChange: (page: number) => void;
  highlights: readonly BoundingBox[];
  /** Why the current page is shown - the selected artefact's location. */
  caption: string | null;
}

/**
 * The source region of the Workspace.
 *
 * Two views of the same document, and the distinction between them is
 * the point:
 *
 * - **Mappa canonica** - what the parser extracted, at the coordinates
 *   it recorded. Highlights live here, because here every rectangle is a
 *   governed `bounding_box` rather than a guess about where rendered
 *   text sits.
 * - **Originale** - the document's own bytes, served by
 *   `GET /documents/{id}/content` and rendered by the browser's built-in
 *   viewer. Authoritative, and deliberately not annotated: nothing is
 *   drawn over a document this application did not lay out.
 *
 * The viewer is addressed **only** by document identity. It never sees a
 * storage reference, and the URL it embeds is composed from the API base
 * and the document id.
 */
export default function SourceViewer({
  document,
  page,
  pageLoading,
  pageError,
  pageNumber,
  pageCount,
  onPageChange,
  highlights,
  caption,
}: SourceViewerProps) {
  const [tab, setTab] = useState<ViewerTab>("canonical");
  const [zoomIndex, setZoomIndex] = useState(2);

  const isPdf = document?.file_format === "pdf";

  /**
   * The embedded original. The `#page=` fragment is the PDF Open
   * Parameters convention every built-in viewer honours.
   *
   * Only computed for the original tab, so an engineer paging through
   * the canonical map does not re-request the document's bytes on every
   * step.
   */
  const originalUrl = useMemo(() => {
    if (document === null || tab !== "original") {
      return null;
    }

    return `${documentContentUrl(document.id)}#page=${pageNumber}`;
  }, [document, pageNumber, tab]);

  const zoom = ZOOM_STEPS[zoomIndex];

  return (
    <section
      aria-label="Documento sorgente"
      className="flex min-h-0 flex-col rounded-3xl border border-slate-200 bg-white/80"
    >
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div
          role="tablist"
          aria-label="Vista del documento"
          className="flex gap-1 rounded-xl bg-slate-100 p-1"
        >
          {(["canonical", "original"] as const).map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              onClick={() => setTab(value)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                tab === value
                  ? "bg-white text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {value === "canonical" ? "Mappa canonica" : "Originale"}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="Pagina precedente"
            disabled={pageNumber <= 1}
            onClick={() => onPageChange(pageNumber - 1)}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>

          <span
            aria-live="polite"
            className="min-w-24 text-center text-sm tabular-nums text-foreground"
          >
            {pageCount === null
              ? `Pagina ${pageNumber}`
              : `Pagina ${pageNumber} di ${pageCount}`}
          </span>

          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="Pagina successiva"
            disabled={pageCount !== null && pageNumber >= pageCount}
            onClick={() => onPageChange(pageNumber + 1)}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>

          {tab === "canonical" && (
            <>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="Riduci zoom"
                disabled={zoomIndex === 0}
                onClick={() => setZoomIndex((index) => index - 1)}
              >
                <ZoomOut className="h-4 w-4" />
              </Button>

              <span className="min-w-12 text-center text-sm tabular-nums text-muted-foreground">
                {`${Math.round(zoom * 100)}%`}
              </span>

              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="Aumenta zoom"
                disabled={zoomIndex === ZOOM_STEPS.length - 1}
                onClick={() => setZoomIndex((index) => index + 1)}
              >
                <ZoomIn className="h-4 w-4" />
              </Button>
            </>
          )}
        </div>
      </header>

      {caption !== null && (
        <p className="border-b border-slate-200 bg-slate-50 px-4 py-2 text-xs text-slate-700">
          {caption}
        </p>
      )}

      <div className="min-h-0 flex-1 overflow-auto p-4">
        {tab === "canonical" ? (
          <CanonicalPageMap
            page={page}
            loading={pageLoading}
            error={pageError}
            highlights={highlights}
            zoom={zoom}
          />
        ) : (
          <OriginalDocument document={document} url={originalUrl} isPdf={isPdf} />
        )}
      </div>
    </section>
  );
}

interface OriginalDocumentProps {
  document: DocumentDetail | null;
  url: string | null;
  isPdf: boolean;
}

/**
 * The document's own bytes.
 *
 * A PDF is handed to the browser's built-in viewer. Any other format is
 * **not** interpreted: it is offered as a download and nothing more.
 * Rendering an unknown format inline would mean letting the browser
 * decide what it is, and a document that arrives claiming to be one
 * thing and renders as HTML is exactly the case that must not be
 * possible here.
 */
function OriginalDocument({ document, url, isPdf }: OriginalDocumentProps) {
  if (document === null) {
    return (
      <p className="text-sm text-muted-foreground">
        Documento non ancora caricato.
      </p>
    );
  }

  if (document.content_available === false) {
    return (
      <p
        role="alert"
        className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
      >
        Il contenuto originale non è più disponibile nell&apos;archivio.
        La scheda del documento esiste, i byte no.
      </p>
    );
  }

  if (!isPdf) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-5 py-8 text-center">
        <p className="text-sm font-medium text-foreground">
          {`Formato ${DOCUMENT_FORMAT_LABELS[document.file_format]}: ispezione inline non disponibile.`}
        </p>

        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
          Solo il PDF ha una rappresentazione canonica in questo
          milestone. Il file può essere scaricato e aperto con lo
          strumento adatto; SubstationOS non tenta di interpretarlo nel
          browser.
        </p>

        <Button asChild variant="outline" className="mt-6">
          <a href={documentContentUrl(document.id)} download>
            <Download className="h-4 w-4" />
            Scarica il documento
          </a>
        </Button>
      </div>
    );
  }

  return (
    <iframe
      key={url ?? "original"}
      src={url ?? undefined}
      title={`Documento originale: ${document.filename}`}
      className="h-[70vh] w-full rounded-xl border border-slate-300 bg-white"
    />
  );
}
