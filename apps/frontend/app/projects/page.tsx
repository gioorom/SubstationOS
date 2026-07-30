"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  FolderKanban,
  MapPin,
  Plus,
  RefreshCw,
  Search,
} from "lucide-react";

import Pagination from "@/components/common/Pagination";

import {
  Button,
  buttonVariants,
} from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useProjectQuery, useProjects } from "@/hooks/useProjects";
import {
  PROJECT_STATUSES,
  PROJECT_LIFECYCLE_LABELS,
  PROJECT_STATUS_LABELS,
  type ProjectStatus,
} from "@/lib/contracts";

/** Typing should not fire a request per keystroke. */
const SEARCH_DEBOUNCE_MS = 300;

/**
 * The project registry. Search, filtering and paging are executed by the
 * backend over the whole registry - never client-side over one page.
 */
export default function ProjectsPage() {
  const { query, setFilter, setPage } = useProjectQuery();

  const {
    projects,
    pagination,
    loading,
    refreshing,
    error,
    reload,
  } = useProjects(query);

  const [searchInput, setSearchInput] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => {
      setFilter({ search: searchInput || undefined });
    }, SEARCH_DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [searchInput, setFilter]);

  return (
    <main className="px-6 py-8 lg:px-10 lg:py-10">
      <section className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-primary">
            Project Workspace
          </p>

          <h2 className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
            Projects
          </h2>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Gestisci commesse, cabine primarie, documenti e attività
            operative da un unico spazio di lavoro.
          </p>
        </div>

        <Link
          href="/projects/new"
          className={buttonVariants()}
        >
          <Plus className="h-4 w-4" />
          Nuovo progetto
        </Link>
      </section>

      <section className="mt-6 flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:flex-row sm:items-end">
        <div className="flex-1">
          <label
            htmlFor="project-search"
            className="mb-2 block text-sm font-medium text-slate-700"
          >
            Ricerca
          </label>

          <div className="relative">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />

            <input
              id="project-search"
              type="search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Nome, codice, committente o località"
              className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-11 pr-4 text-slate-900 outline-none transition focus:border-slate-400 focus:ring-4 focus:ring-slate-200/70"
            />
          </div>
        </div>

        <div className="sm:w-64">
          <label
            htmlFor="project-status-filter"
            className="mb-2 block text-sm font-medium text-slate-700"
          >
            Fase
          </label>

          <select
            id="project-status-filter"
            value={query.status ?? ""}
            onChange={(event) =>
              setFilter({
                status:
                  (event.target.value || undefined) as
                    | ProjectStatus
                    | undefined,
              })
            }
            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-slate-400 focus:ring-4 focus:ring-slate-200/70"
          >
            <option value="">Tutte le fasi</option>

            {PROJECT_STATUSES.map((status) => (
              <option key={status} value={status}>
                {PROJECT_STATUS_LABELS[status]}
              </option>
            ))}
          </select>
        </div>
      </section>

      {loading && (
        <section className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div
              key={index}
              className="rounded-3xl border border-white/70 bg-white/72 p-6 shadow-sm backdrop-blur-2xl"
            >
              <Skeleton className="h-11 w-11 rounded-2xl" />
              <Skeleton className="mt-5 h-5 w-36" />
              <Skeleton className="mt-3 h-4 w-24" />
              <Skeleton className="mt-6 h-4 w-full" />
              <Skeleton className="mt-2 h-4 w-4/5" />
            </div>
          ))}
        </section>
      )}

      {!loading && error && (
        <section className="mt-8 rounded-3xl border border-red-200 bg-red-50 p-6 text-red-700">
          <p className="font-semibold">
            Impossibile caricare i progetti.
          </p>

          <p className="mt-2 text-sm">
            {error}
          </p>

          <Button
            type="button"
            variant="outline"
            className="mt-5"
            onClick={() => void reload()}
          >
            <RefreshCw className="h-4 w-4" />
            Riprova
          </Button>
        </section>
      )}

      {!loading && !error && projects.length === 0 && (query.search || query.status) && (
        <section className="mt-8 rounded-2xl border border-slate-200 bg-white/70 px-6 py-10 text-center text-sm text-muted-foreground">
          Nessun progetto corrisponde ai criteri selezionati.
        </section>
      )}

      {!loading && !error && projects.length === 0 && !query.search && !query.status && (
        <section className="mt-8 rounded-[2rem] border border-dashed border-border bg-white/60 px-6 py-16 text-center shadow-sm backdrop-blur-xl">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-primary/10 text-primary">
            <FolderKanban className="h-8 w-8" />
          </div>

          <h3 className="mt-6 text-xl font-semibold text-foreground">
            Nessun progetto disponibile
          </h3>

          <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-muted-foreground">
            Crea il primo progetto per organizzare documenti,
            attività di commissioning, revisioni e dati tecnici
            della cabina.
          </p>

          <Link
            href="/projects/new"
            className={[
              buttonVariants(),
              "mt-6",
            ].join(" ")}
          >
            <Plus className="h-4 w-4" />
            Crea il primo progetto
          </Link>
        </section>
      )}

      {!loading && !error && projects.length > 0 && (
        <section className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {projects.map((project) => (
            <Link
              key={project.id}
              href={`/projects/${project.id}`}
              className="group rounded-3xl border border-white/70 bg-white/72 p-6 shadow-[0_18px_45px_rgba(15,23,42,0.06)] backdrop-blur-2xl transition duration-300 hover:-translate-y-1 hover:bg-white/90 hover:shadow-[0_26px_65px_rgba(15,23,42,0.1)]"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <FolderKanban className="h-6 w-6" />
                </div>

                <div className="flex flex-wrap justify-end gap-2">
                  <span className="rounded-full bg-secondary px-3 py-1 text-xs font-semibold text-secondary-foreground">
                    {PROJECT_STATUS_LABELS[project.status]}
                  </span>

                  {project.lifecycle_state !== "active" && (
                    <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
                      {PROJECT_LIFECYCLE_LABELS[project.lifecycle_state]}
                    </span>
                  )}
                </div>
              </div>

              <p className="mt-5 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                {project.code}
              </p>

              <h3 className="mt-2 text-xl font-semibold tracking-tight text-foreground">
                {project.name}
              </h3>

              <p className="mt-3 line-clamp-2 text-sm leading-6 text-muted-foreground">
                {project.description ||
                  "Nessuna descrizione disponibile."}
              </p>

              <div className="mt-6 flex items-center gap-2 text-sm text-muted-foreground">
                <MapPin className="h-4 w-4" />

                <span>
                  {project.location ||
                    "Località non specificata"}
                </span>
              </div>

              <div className="mt-6 border-t border-border pt-4 text-sm font-medium text-primary">
                Apri progetto
              </div>
            </Link>
          ))}
        </section>
      )}

      {!loading && !error && projects.length > 0 && (
        <Pagination
          pagination={pagination}
          onPageChange={setPage}
          disabled={refreshing}
          itemLabel={{ singular: "progetto", plural: "progetti" }}
        />
      )}
    </main>
  );
}