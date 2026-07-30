"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

import Pagination from "@/components/common/Pagination";
import DocumentTable from "@/components/documents/DocumentTable";
import FilterPanel from "@/components/documents/FilterPanel";
import SearchBar from "@/components/documents/SearchBar";
import UploadBox from "@/components/UploadBox";
import { Button } from "@/components/ui/button";

import {
  useDocumentQuery,
  useDocuments,
} from "@/hooks/useDocuments";
import { useProjects } from "@/hooks/useProjects";
import {
  DOCUMENT_CATEGORIES,
  DOCUMENT_CATEGORY_LABELS,
  DOCUMENT_FORMATS,
  DOCUMENT_FORMAT_LABELS,
  DOCUMENT_SCOPES,
  isMutable,
  type DocumentCategory,
  type DocumentFormat,
  type DocumentScope,
} from "@/lib/contracts";

/** Typing should not fire a request per keystroke. */
const SEARCH_DEBOUNCE_MS = 300;

/**
 * The document registry.
 *
 * **Filtering, search, sorting and paging all happen on the server**
 * since Milestone 30.1.3. This page holds the query and renders the page
 * it gets back; it never filters the result, because the result is one
 * page and filtering it would hide matches on every other.
 */
export default function DocumentsPage() {
  const { query, setFilter, setPage, reset, hasFilters } =
    useDocumentQuery();

  const {
    documents,
    pagination,
    loading,
    refreshing,
    error,
    reload,
    upload,
    uploading,
    uploadError,
  } = useDocuments(query);

  const { projects, loading: projectsLoading, error: projectsError } =
    useProjects({ page_size: 100 });

  const [searchInput, setSearchInput] = useState("");
  const [uploadProjectId, setUploadProjectId] = useState<number>();

  useEffect(() => {
    const timer = setTimeout(() => {
      setFilter({ search: searchInput || undefined });
    }, SEARCH_DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [searchInput, setFilter]);

  const firstUploadable = projects.find(isMutable)?.id;
  const effectiveUploadProjectId = uploadProjectId ?? firstUploadable;

  function resetAll() {
    setSearchInput("");
    reset();
  }

  return (
    <main className="px-6 py-8 lg:px-10 lg:py-10">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-primary">
            Document Workspace
          </p>

          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
            Document Registry
          </h1>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Carica e consulta i documenti tecnici registrati. Ricerca e
            filtri sono eseguiti dal backend sull&apos;intero registro.
          </p>
        </div>

        <Button
          type="button"
          variant="outline"
          onClick={() => void reload()}
          disabled={refreshing}
        >
          <RefreshCw
            className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
          />
          Aggiorna
        </Button>
      </section>

      <div className="mt-8">
        <UploadBox
          onUpload={upload}
          uploading={uploading}
          uploadError={uploadError}
          projects={projects}
          projectsLoading={projectsLoading}
          selectedProjectId={effectiveUploadProjectId}
          onProjectChange={setUploadProjectId}
        />
      </div>

      {projectsError && (
        <p
          role="alert"
          className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700"
        >
          {projectsError}
        </p>
      )}

      <SearchBar value={searchInput} onChange={setSearchInput} />

      <FilterPanel
        categories={DOCUMENT_CATEGORIES.map((category) => ({
          value: category,
          label: DOCUMENT_CATEGORY_LABELS[category],
        }))}
        formats={DOCUMENT_FORMATS.map((format) => ({
          value: format,
          label: DOCUMENT_FORMAT_LABELS[format],
        }))}
        scopes={DOCUMENT_SCOPES.map((scope) => ({
          value: scope,
          label:
            scope === "project" ? "Progetto" : "Libreria canonica",
        }))}
        selectedCategory={query.category ?? ""}
        selectedFormat={query.file_format ?? ""}
        selectedScope={query.scope ?? ""}
        onCategoryChange={(value) =>
          setFilter({
            category: (value || undefined) as DocumentCategory | undefined,
          })
        }
        onFormatChange={(value) =>
          setFilter({
            file_format: (value || undefined) as
              | DocumentFormat
              | undefined,
          })
        }
        onScopeChange={(value) =>
          setFilter({
            scope: (value || undefined) as DocumentScope | undefined,
          })
        }
        onReset={resetAll}
        hasActiveFilters={hasFilters || searchInput !== ""}
      />

      {loading && (
        <p className="mt-8 text-sm text-muted-foreground">
          Caricamento documenti...
        </p>
      )}

      {error && (
        <section
          role="alert"
          className="mt-8 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700"
        >
          <p>{error}</p>

          <Button
            type="button"
            variant="outline"
            className="mt-4"
            onClick={() => void reload()}
          >
            <RefreshCw className="h-4 w-4" />
            Riprova
          </Button>
        </section>
      )}

      {!loading && !error && documents.length === 0 && (
        <p className="mt-8 text-sm text-muted-foreground">
          {hasFilters || searchInput
            ? "Nessun documento corrisponde ai criteri selezionati."
            : "Nessun documento registrato."}
        </p>
      )}

      {!loading && !error && documents.length > 0 && (
        <>
          <DocumentTable documents={documents} />

          <Pagination
            pagination={pagination}
            onPageChange={setPage}
            disabled={refreshing}
            itemLabel={{ singular: "documento", plural: "documenti" }}
          />
        </>
      )}
    </main>
  );
}
