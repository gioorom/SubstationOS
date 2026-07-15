"use client";

import Link from "next/link";
import {
  FolderKanban,
  MapPin,
  Plus,
  RefreshCw,
} from "lucide-react";

import {
  Button,
  buttonVariants,
} from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useProjects } from "@/hooks/useProjects";

export default function ProjectsPage() {
  const {
    projects,
    loading,
    error,
    reload,
  } = useProjects();

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

      {!loading && !error && projects.length === 0 && (
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

                <span className="rounded-full bg-secondary px-3 py-1 text-xs font-semibold text-secondary-foreground">
                  {project.status}
                </span>
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
    </main>
  );
}