"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Building2,
  FileText,
  MapPin,
  Network,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getProject } from "@/lib/projects";
import { Project } from "@/types/project";

const statusLabels: Record<Project["status"], string> = {
  planning: "Pianificazione",
  active: "Attivo",
  on_hold: "In sospeso",
  completed: "Completato",
  cancelled: "Annullato",
};

export default function ProjectDetailPage() {
  const params = useParams<{ projectId: string }>();

  const [project, setProject] =
    useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadProject() {
      const projectId = Number(params.projectId);

      if (!Number.isInteger(projectId)) {
        setError("Identificativo progetto non valido.");
        setLoading(false);
        return;
      }

      try {
        const data = await getProject(projectId);
        setProject(data);
      } catch {
        setError("Impossibile caricare il progetto.");
      } finally {
        setLoading(false);
      }
    }

    void loadProject();
  }, [params.projectId]);

  if (loading) {
    return (
      <main className="px-6 py-8 lg:px-10 lg:py-10">
        <Skeleton className="h-10 w-40" />

        <section className="mt-6 rounded-[2rem] border border-white/70 bg-white/72 p-8 shadow-sm backdrop-blur-2xl">
          <Skeleton className="h-7 w-32" />
          <Skeleton className="mt-4 h-11 w-3/5" />
          <Skeleton className="mt-4 h-5 w-full max-w-2xl" />

          <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton
                key={index}
                className="h-28 rounded-2xl"
              />
            ))}
          </div>
        </section>
      </main>
    );
  }

  if (error || !project) {
    return (
      <main className="px-6 py-8 lg:px-10 lg:py-10">
        <section className="rounded-3xl border border-red-200 bg-red-50 p-6 text-red-700">
          <p className="font-semibold">
            Progetto non disponibile
          </p>

          <p className="mt-2 text-sm">
            {error || "Il progetto richiesto non esiste."}
          </p>

          <Button asChild variant="outline" className="mt-5">
            <Link href="/projects">
              <ArrowLeft className="h-4 w-4" />
              Torna ai progetti
            </Link>
          </Button>
        </section>
      </main>
    );
  }

  return (
    <main className="px-6 py-8 lg:px-10 lg:py-10">
      <Button asChild variant="ghost">
        <Link href="/projects">
          <ArrowLeft className="h-4 w-4" />
          Torna ai progetti
        </Link>
      </Button>

      <section className="relative mt-6 overflow-hidden rounded-[2rem] border border-white/70 bg-white/72 p-7 shadow-[0_24px_70px_rgba(15,23,42,0.08)] backdrop-blur-2xl lg:p-9">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 rounded-full bg-blue-400/14 blur-3xl"
        />

        <div className="relative">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
                  {project.code}
                </span>

                <span className="rounded-full bg-secondary px-3 py-1 text-xs font-semibold text-secondary-foreground">
                  {statusLabels[project.status]}
                </span>
              </div>

              <h2 className="mt-5 text-3xl font-semibold tracking-tight text-foreground lg:text-4xl">
                {project.name}
              </h2>

              <p className="mt-4 max-w-3xl text-sm leading-6 text-muted-foreground">
                {project.description ||
                  "Nessuna descrizione disponibile."}
              </p>
            </div>
          </div>

          <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl border border-white/70 bg-white/60 p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <Building2 className="h-5 w-5 text-primary" />

                <p className="text-sm font-medium text-muted-foreground">
                  Committente
                </p>
              </div>

              <p className="mt-3 font-semibold text-foreground">
                {project.customer || "Non specificato"}
              </p>
            </div>

            <div className="rounded-2xl border border-white/70 bg-white/60 p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <Network className="h-5 w-5 text-primary" />

                <p className="text-sm font-medium text-muted-foreground">
                  EPC
                </p>
              </div>

              <p className="mt-3 font-semibold text-foreground">
                {project.epc || "Non specificato"}
              </p>
            </div>

            <div className="rounded-2xl border border-white/70 bg-white/60 p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <MapPin className="h-5 w-5 text-primary" />

                <p className="text-sm font-medium text-muted-foreground">
                  Località
                </p>
              </div>

              <p className="mt-3 font-semibold text-foreground">
                {project.location || "Non specificata"}
              </p>
            </div>

            <div className="rounded-2xl border border-white/70 bg-white/60 p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <Zap className="h-5 w-5 text-primary" />

                <p className="text-sm font-medium text-muted-foreground">
                  Tensione
                </p>
              </div>

              <p className="mt-3 font-semibold text-foreground">
                {project.voltage_level || "Non specificata"}
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        <article className="rounded-3xl border border-white/70 bg-white/72 p-6 shadow-sm backdrop-blur-2xl">
          <FileText className="h-7 w-7 text-primary" />

          <h3 className="mt-5 text-lg font-semibold text-foreground">
            Documents
          </h3>

          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Documenti tecnici associati alla commessa.
          </p>

          <p className="mt-6 text-sm font-medium text-muted-foreground">
            Collegamento in arrivo
          </p>
        </article>

        <article className="rounded-3xl border border-white/70 bg-white/72 p-6 shadow-sm backdrop-blur-2xl">
          <Zap className="h-7 w-7 text-primary" />

          <h3 className="mt-5 text-lg font-semibold text-foreground">
            Commissioning
          </h3>

          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Attività, prove e avanzamento della messa in servizio.
          </p>

          <p className="mt-6 text-sm font-medium text-muted-foreground">
            Modulo in arrivo
          </p>
        </article>

        <article className="rounded-3xl border border-white/70 bg-white/72 p-6 shadow-sm backdrop-blur-2xl">
          <Network className="h-7 w-7 text-primary" />

          <h3 className="mt-5 text-lg font-semibold text-foreground">
            Engineering
          </h3>

          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Schemi funzionali, cablaggi, revisioni e as-built.
          </p>

          <p className="mt-6 text-sm font-medium text-muted-foreground">
            Workspace in arrivo
          </p>
        </article>
      </section>
    </main>
  );
}