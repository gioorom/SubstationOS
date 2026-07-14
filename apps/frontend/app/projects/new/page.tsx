"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Building2,
  FolderPlus,
  MapPin,
  Network,
  Save,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { useProjects } from "@/hooks/useProjects";
import {
  CreateProjectPayload,
  ProjectStatus,
} from "@/types/project";

const initialForm: CreateProjectPayload = {
  name: "",
  code: "",
  customer: "",
  epc: "",
  location: "",
  voltage_level: "",
  status: "planning",
  description: "",
};

export default function NewProjectPage() {
  const router = useRouter();

  const {
    addProject,
    creating,
    error,
  } = useProjects();

  const [form, setForm] =
    useState<CreateProjectPayload>(initialForm);

  function updateField<
    K extends keyof CreateProjectPayload
  >(
    field: K,
    value: CreateProjectPayload[K]
  ) {
    setForm((currentForm) => ({
      ...currentForm,
      [field]: value,
    }));
  }

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    const payload: CreateProjectPayload = {
      name: form.name.trim(),
      code: form.code.trim(),
      customer: form.customer?.trim() || undefined,
      epc: form.epc?.trim() || undefined,
      location: form.location?.trim() || undefined,
      voltage_level:
        form.voltage_level?.trim() || undefined,
      status: form.status,
      description:
        form.description?.trim() || undefined,
    };

    if (!payload.name || !payload.code) {
      return;
    }

    try {
      const project = await addProject(payload);
      router.push(`/projects/${project.id}`);
    } catch {
      // L'errore viene già gestito da useProjects.
    }
  }

  return (
    <main className="px-6 py-8 lg:px-10 lg:py-10">
      <section className="mx-auto max-w-5xl">
        <Button
          type="button"
          variant="ghost"
          onClick={() => router.push("/projects")}
        >
          <ArrowLeft className="h-4 w-4" />
          Torna ai progetti
        </Button>

        <div className="mt-6">
          <p className="text-sm font-medium text-primary">
            Project Workspace
          </p>

          <h2 className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
            Nuovo progetto
          </h2>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Crea una nuova commessa tecnica e configura le
            informazioni principali della cabina o sottostazione.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="mt-8 space-y-6"
        >
          <section className="rounded-[2rem] border border-white/70 bg-white/72 p-6 shadow-[0_18px_45px_rgba(15,23,42,0.06)] backdrop-blur-2xl lg:p-8">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                <FolderPlus className="h-5 w-5" />
              </div>

              <div>
                <h3 className="text-lg font-semibold text-foreground">
                  Informazioni principali
                </h3>

                <p className="mt-1 text-sm text-muted-foreground">
                  Identificazione e stato della commessa
                </p>
              </div>
            </div>

            <div className="mt-6 grid gap-5 md:grid-cols-2">
              <div>
                <label
                  htmlFor="project-code"
                  className="mb-2 block text-sm font-medium text-foreground"
                >
                  Codice progetto
                </label>

                <input
                  id="project-code"
                  type="text"
                  required
                  value={form.code}
                  onChange={(event) =>
                    updateField("code", event.target.value)
                  }
                  placeholder="es. CP-GAMMA-2026"
                  className="w-full rounded-2xl border border-input bg-white/80 px-4 py-3 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-4 focus:ring-primary/10"
                />
              </div>

              <div>
                <label
                  htmlFor="project-name"
                  className="mb-2 block text-sm font-medium text-foreground"
                >
                  Nome progetto
                </label>

                <input
                  id="project-name"
                  type="text"
                  required
                  value={form.name}
                  onChange={(event) =>
                    updateField("name", event.target.value)
                  }
                  placeholder="es. Cabina Primaria Gamma"
                  className="w-full rounded-2xl border border-input bg-white/80 px-4 py-3 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-4 focus:ring-primary/10"
                />
              </div>

              <div>
                <label
                  htmlFor="project-status"
                  className="mb-2 block text-sm font-medium text-foreground"
                >
                  Stato
                </label>

                <select
                  id="project-status"
                  value={form.status}
                  onChange={(event) =>
                    updateField(
                      "status",
                      event.target.value as ProjectStatus
                    )
                  }
                  className="w-full rounded-2xl border border-input bg-white/80 px-4 py-3 text-sm text-foreground outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10"
                >
                  <option value="planning">
                    Pianificazione
                  </option>
                  <option value="active">
                    Attivo
                  </option>
                  <option value="on_hold">
                    In sospeso
                  </option>
                  <option value="completed">
                    Completato
                  </option>
                  <option value="cancelled">
                    Annullato
                  </option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="voltage-level"
                  className="mb-2 block text-sm font-medium text-foreground"
                >
                  Livello di tensione
                </label>

                <div className="relative">
                  <Zap className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />

                  <input
                    id="voltage-level"
                    type="text"
                    value={form.voltage_level}
                    onChange={(event) =>
                      updateField(
                        "voltage_level",
                        event.target.value
                      )
                    }
                    placeholder="es. 150/20 kV"
                    className="w-full rounded-2xl border border-input bg-white/80 py-3 pr-4 pl-11 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-4 focus:ring-primary/10"
                  />
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-[2rem] border border-white/70 bg-white/72 p-6 shadow-[0_18px_45px_rgba(15,23,42,0.06)] backdrop-blur-2xl lg:p-8">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                <Building2 className="h-5 w-5" />
              </div>

              <div>
                <h3 className="text-lg font-semibold text-foreground">
                  Soggetti e localizzazione
                </h3>

                <p className="mt-1 text-sm text-muted-foreground">
                  Committente, EPC e sede dell’impianto
                </p>
              </div>
            </div>

            <div className="mt-6 grid gap-5 md:grid-cols-2">
              <div>
                <label
                  htmlFor="customer"
                  className="mb-2 block text-sm font-medium text-foreground"
                >
                  Committente
                </label>

                <input
                  id="customer"
                  type="text"
                  value={form.customer}
                  onChange={(event) =>
                    updateField(
                      "customer",
                      event.target.value
                    )
                  }
                  placeholder="es. Distributore Nazionale"
                  className="w-full rounded-2xl border border-input bg-white/80 px-4 py-3 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-4 focus:ring-primary/10"
                />
              </div>

              <div>
                <label
                  htmlFor="epc"
                  className="mb-2 block text-sm font-medium text-foreground"
                >
                  EPC
                </label>

                <div className="relative">
                  <Network className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />

                  <input
                    id="epc"
                    type="text"
                    value={form.epc}
                    onChange={(event) =>
                      updateField(
                        "epc",
                        event.target.value
                      )
                    }
                    placeholder="Società EPC"
                    className="w-full rounded-2xl border border-input bg-white/80 py-3 pr-4 pl-11 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-4 focus:ring-primary/10"
                  />
                </div>
              </div>

              <div className="md:col-span-2">
                <label
                  htmlFor="location"
                  className="mb-2 block text-sm font-medium text-foreground"
                >
                  Località
                </label>

                <div className="relative">
                  <MapPin className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />

                  <input
                    id="location"
                    type="text"
                    value={form.location}
                    onChange={(event) =>
                      updateField(
                        "location",
                        event.target.value
                      )
                    }
                    placeholder="Comune, provincia o area impianto"
                    className="w-full rounded-2xl border border-input bg-white/80 py-3 pr-4 pl-11 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-4 focus:ring-primary/10"
                  />
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-[2rem] border border-white/70 bg-white/72 p-6 shadow-[0_18px_45px_rgba(15,23,42,0.06)] backdrop-blur-2xl lg:p-8">
            <label
              htmlFor="description"
              className="block text-sm font-medium text-foreground"
            >
              Descrizione
            </label>

            <textarea
              id="description"
              rows={6}
              value={form.description}
              onChange={(event) =>
                updateField(
                  "description",
                  event.target.value
                )
              }
              placeholder="Descrivi lo scopo della commessa, le principali attività previste e le informazioni tecniche rilevanti."
              className="mt-2 w-full resize-y rounded-2xl border border-input bg-white/80 px-4 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-4 focus:ring-primary/10"
            />
          </section>

          {error && (
            <section className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
              {error}
            </section>
          )}

          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              onClick={() => router.push("/projects")}
              disabled={creating}
            >
              Annulla
            </Button>

            <Button
              type="submit"
              disabled={
                creating ||
                !form.name.trim() ||
                !form.code.trim()
              }
            >
              <Save className="h-4 w-4" />
              {creating
                ? "Creazione in corso..."
                : "Crea progetto"}
            </Button>
          </div>
        </form>
      </section>
    </main>
  );
}