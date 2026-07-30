"use client";

import type { BoundingBox, CanonicalPdfPage } from "@/lib/contracts";

interface CanonicalPageMapProps {
  page: CanonicalPdfPage | null;
  loading: boolean;
  error: string | null;
  /** Rectangles to highlight, already resolved by explicit span identity. */
  highlights: readonly BoundingBox[];
  zoom: number;
}

/**
 * The page as the parser recorded it.
 *
 * Every rectangle drawn here is a `bounding_box` from the canonical
 * representation, in the parser's own PDF user-space points, placed by
 * an SVG viewBox of the page's own `width`/`height`. **No coordinate is
 * computed by this component.** Nothing is measured from rendered text,
 * nothing is scaled by a guessed ratio, and a span the representation
 * does not record is not drawn.
 *
 * This is the surface highlighting happens on, and it is why the
 * Workspace does not need a PDF engine: an observation cites a span by
 * `(page, block_reading_order, span_reading_order)`, that span carries a
 * rectangle, and the rectangle goes on the map. Over the browser's own
 * PDF viewer none of that would be addressable.
 *
 * It is a *map of what was extracted*, not a facsimile. The original
 * bytes remain authoritative and are one tab away.
 */
export default function CanonicalPageMap({
  page,
  loading,
  error,
  highlights,
  zoom,
}: CanonicalPageMapProps) {
  if (error !== null) {
    return (
      <p
        role="alert"
        className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
      >
        {error}
      </p>
    );
  }

  if (loading) {
    return (
      <p aria-live="polite" className="text-sm text-muted-foreground">
        Caricamento della pagina canonica…
      </p>
    );
  }

  if (page === null) {
    return (
      <p className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-600">
        La rappresentazione canonica non contiene questa pagina. Nessuna
        mappa può essere disegnata: il documento non è stato
        canonicalizzato, oppure il parser non ha registrato la pagina.
      </p>
    );
  }

  return (
    <figure className="m-0">
      <svg
        role="img"
        aria-label={`Mappa canonica della pagina ${page.page_number}`}
        viewBox={`0 0 ${page.width} ${page.height}`}
        style={{ width: `${zoom * 100}%` }}
        className="h-auto rounded-xl border border-slate-300 bg-white shadow-sm"
      >
        <title>{`Pagina ${page.page_number}: ${page.blocks.length} blocchi`}</title>

        {page.blocks.map((block) => (
          <g key={block.reading_order}>
            <rect
              x={block.bounding_box.x0}
              y={block.bounding_box.y0}
              width={block.bounding_box.x1 - block.bounding_box.x0}
              height={block.bounding_box.y1 - block.bounding_box.y0}
              fill="none"
              stroke="#cbd5e1"
              strokeWidth={0.5}
            />

            {block.spans.map((span) => (
              <text
                key={span.reading_order}
                x={span.bounding_box.x0}
                // The parser's box is the glyph box; its baseline sits
                // at the bottom edge. Anchoring there is transcription,
                // not layout: nothing is nudged to look better.
                y={span.bounding_box.y1}
                fontSize={span.style.font_size}
                fontFamily={span.style.font_family}
                fontWeight={span.style.bold ? "bold" : "normal"}
                fontStyle={span.style.italic ? "italic" : "normal"}
                fill="#0f172a"
                // `textLength` holds the drawn text inside the box the
                // parser measured, so the map cannot drift from the
                // coordinates the highlights use.
                textLength={
                  span.bounding_box.x1 - span.bounding_box.x0 || undefined
                }
                lengthAdjust="spacingAndGlyphs"
              >
                {span.text}
              </text>
            ))}
          </g>
        ))}

        {highlights.map((box, index) => (
          <rect
            key={`${box.x0}-${box.y0}-${index}`}
            x={box.x0}
            y={box.y0}
            width={box.x1 - box.x0}
            height={box.y1 - box.y0}
            fill="#0ea5e9"
            fillOpacity={0.18}
            stroke="#0284c7"
            strokeWidth={1}
          />
        ))}
      </svg>

      <figcaption className="mt-2 text-xs leading-5 text-muted-foreground">
        Mappa della rappresentazione canonica: mostra ciò che il parser ha
        estratto, alle coordinate che ha registrato. Non è un facsimile
        del PDF; il documento originale resta la fonte autorevole.
      </figcaption>
    </figure>
  );
}
