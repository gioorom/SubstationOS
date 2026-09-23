"use client";

import Link from "next/link";
import { FileSpreadsheet, FileText, Search } from "lucide-react";

import GlassPanel from "@/components/design-system/GlassPanel";
import { Button } from "@/components/ui/button";
import Input from "@/components/ui/Input";
import type {
  SearchDocumentResult,
  SearchLocation,
  SearchMatch,
  SearchSnippet,
  SearchTermSuggestion,
} from "@/lib/contracts";

interface ProjectSearchPanelProps {
  query: string;
  onQueryChange: (value: string) => void;
  results: {
    terms: string[];
    total_matches: number;
    total_documents: number;
    documents: SearchDocumentResult[];
    suggestions: SearchTermSuggestion[];
  };
  submitted: string;
  searching: boolean;
  error: string | null;
  /** How many matches are on screen, of `results.total_matches`. */
  shown?: number;
  hasMore?: boolean;
  loadingMore?: boolean;
  onLoadMore?: () => void;
}

/**
 * Searching a project's documents.
 *
 * Every result says three things and in this order: which document,
 * where inside it, and what it says there. Where the position is not
 * known the panel says so in words - it never leaves a blank that could
 * be read as "page 1".
 *
 * The snippet is rendered from the source text with the matched terms
 * marked, so an engineer reading `-Q1` sees `-Q1` highlighted and not
 * the `Q1` inside it. The two are different designations and the
 * interface must not blur them.
 */
export default function ProjectSearchPanel({
  query,
  onQueryChange,
  results,
  submitted,
  searching,
  error,
  shown,
  hasMore = false,
  loadingMore = false,
  onLoadMore,
}: ProjectSearchPanelProps) {
  const asked = submitted !== "";

  return (
    <GlassPanel padding="lg">
      <div className="flex items-center gap-3">
        <Search
          aria-hidden="true"
          className="h-5 w-5 shrink-0 text-muted-foreground"
        />

        <div className="flex-1">
          <label htmlFor="project-search" className="sr-only">
            Cerca nei documenti del progetto
          </label>

          <Input
            id="project-search"
            type="search"
            role="searchbox"
            autoComplete="off"
            placeholder="Cerca: TR1, -Q1, +189L, quadro MT, 150 kV…"
            value={query}
            onChange={(event: React.ChangeEvent<HTMLInputElement>) =>
              onQueryChange(event.target.value)
            }
          />
        </div>
      </div>

      <p className="mt-3 text-xs text-muted-foreground">
        I termini sono cercati per intero e devono comparire tutti nello
        stesso punto. Le sigle mantengono il loro prefisso:{" "}
        <code className="font-mono">-Q1</code> e{" "}
        <code className="font-mono">Q1</code> sono sigle diverse.
      </p>

      {error && (
        <p
          role="alert"
          className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700"
        >
          {error}
        </p>
      )}

      {!error && asked && (
        <ResultSummary
          searching={searching}
          totalMatches={results.total_matches}
          totalDocuments={results.total_documents}
          shown={shown}
          terms={results.terms}
        />
      )}

      {!error && asked && results.total_matches === 0 && !searching && (
        <NoResults query={submitted} suggestions={results.suggestions} />
      )}

      {!error && results.documents.length > 0 && (
        <ul className="mt-5 space-y-4">
          {results.documents.map((document) => (
            <DocumentResult
              key={document.document_id}
              document={document}
            />
          ))}
        </ul>
      )}

      {/*
        Without this the panel announces a total it will not show. On a
        real corpus a common term matches thousands of times, nearly all
        of them inside whichever document sorts first, so the remaining
        documents are only reachable by asking for more.
      */}
      {!error && hasMore && onLoadMore && (
        <div className="mt-5 flex justify-center">
          <Button
            type="button"
            variant="outline"
            disabled={loadingMore}
            onClick={onLoadMore}
          >
            {loadingMore ? "Caricamento…" : "Mostra altri risultati"}
          </Button>
        </div>
      )}
    </GlassPanel>
  );
}

function ResultSummary({
  searching,
  totalMatches,
  totalDocuments,
  shown,
  terms,
}: {
  searching: boolean;
  totalMatches: number;
  totalDocuments: number;
  shown?: number;
  terms: string[];
}) {
  const partial = shown !== undefined && shown > 0 && shown < totalMatches;
  return (
    <p
      role="status"
      className="mt-4 text-sm text-muted-foreground"
    >
      {searching ? (
        "Ricerca in corso…"
      ) : (
        <>
          {partial && (
            <>
              <strong className="text-foreground">{shown}</strong> di{" "}
            </>
          )}
          <strong className="text-foreground">{totalMatches}</strong>{" "}
          {totalMatches === 1 ? "risultato" : "risultati"} in{" "}
          <strong className="text-foreground">{totalDocuments}</strong>{" "}
          {totalDocuments === 1 ? "documento" : "documenti"}
          {terms.length > 0 && (
            <>
              {" "}
              — cercato:{" "}
              <span className="font-mono">{terms.join(" ")}</span>
            </>
          )}
        </>
      )}
    </p>
  );
}

/**
 * What to say when nothing matched.
 *
 * A near miss is *offered*, never applied. If the project writes `-Q1`
 * and the engineer searched `Q1`, saying so is useful; searching `-Q1`
 * on their behalf would be the platform deciding which piece of
 * equipment they meant.
 */
function NoResults({
  query,
  suggestions,
}: {
  query: string;
  suggestions: SearchTermSuggestion[];
}) {
  const offered = suggestions.filter(
    (suggestion) => suggestion.present_variants.length > 0,
  );

  return (
    <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-900">
      <p>
        Nessun risultato per{" "}
        <span className="font-mono font-semibold">{query}</span> in questo
        progetto.
      </p>

      {offered.length > 0 && (
        <ul className="mt-3 space-y-1">
          {offered.map((suggestion) => (
            <li key={suggestion.term}>
              Il progetto contiene{" "}
              {suggestion.present_variants.map((variant, index) => (
                <span key={variant}>
                  {index > 0 && ", "}
                  <span className="font-mono font-semibold">{variant}</span>
                </span>
              ))}
              , che è una sigla diversa da{" "}
              <span className="font-mono">{suggestion.term}</span>.
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function DocumentResult({
  document,
}: {
  document: SearchDocumentResult;
}) {
  const Icon =
    document.source_type === "spreadsheet" ? FileSpreadsheet : FileText;

  return (
    <li className="rounded-2xl border border-border bg-background/60 p-4">
      <div className="flex items-center gap-2">
        <Icon
          aria-hidden="true"
          className="h-4 w-4 shrink-0 text-muted-foreground"
        />

        {/*
          The workspace, not `/documents/{id}` - that path has no page
          and a result that led nowhere would break the one thing a
          search result is for. This is the same destination the
          documentation panel uses, and it is where the source viewer
          and the download live.
        */}
        <Link
          href={`/documents/${document.document_id}/workspace`}
          className="font-medium underline-offset-4 hover:underline"
        >
          {document.filename}
        </Link>

        <span className="text-xs text-muted-foreground">
          {document.matches.length}{" "}
          {document.matches.length === 1 ? "occorrenza" : "occorrenze"}
        </span>
      </div>

      <ul className="mt-3 space-y-3">
        {document.matches.map((match, index) => (
          <MatchRow key={index} match={match} />
        ))}
      </ul>
    </li>
  );
}

function MatchRow({ match }: { match: SearchMatch }) {
  return (
    <li className="border-l-2 border-border pl-3">
      <p className="text-xs font-medium text-muted-foreground">
        {describeLocation(match.location)}
      </p>

      <p className="mt-1 text-sm leading-relaxed">
        <Snippet snippet={match.snippet} />
      </p>
    </li>
  );
}

/**
 * The position of a match, in words.
 *
 * When the source recorded no position this says so outright. A blank
 * here would be read as "somewhere obvious", and sending an engineer to
 * the wrong page of a drawing is worse than admitting the page is
 * unknown.
 */
export function describeLocation(location: SearchLocation): string {
  if (!location.determined) {
    return "Posizione nel documento non disponibile";
  }

  if (location.page_number !== null) {
    return `Pagina ${location.page_number}`;
  }

  const parts: string[] = [];

  if (location.worksheet_name !== null) {
    parts.push(`Foglio "${location.worksheet_name}"`);
  }

  if (location.cell_reference !== null) {
    parts.push(`cella ${location.cell_reference}`);
  } else if (location.row_number !== null) {
    parts.push(`riga ${location.row_number}`);
  }

  return parts.length > 0
    ? parts.join(" · ")
    : "Posizione nel documento non disponibile";
}

/**
 * The matched text with the searched terms marked.
 *
 * Built by walking the highlight offsets the backend computed against
 * the source string, so what is emphasised is exactly what was searched
 * for - prefix included.
 */
function Snippet({ snippet }: { snippet: SearchSnippet }) {
  const pieces: React.ReactNode[] = [];
  let cursor = 0;

  snippet.highlights.forEach((highlight, index) => {
    if (highlight.start > cursor) {
      pieces.push(snippet.text.slice(cursor, highlight.start));
    }

    pieces.push(
      <mark
        key={index}
        className="rounded bg-amber-200 px-0.5 font-semibold text-amber-950"
      >
        {snippet.text.slice(highlight.start, highlight.end)}
      </mark>,
    );

    cursor = highlight.end;
  });

  pieces.push(snippet.text.slice(cursor));

  return (
    <>
      {snippet.truncated_before && "… "}
      {pieces}
      {snippet.truncated_after && " …"}
    </>
  );
}
