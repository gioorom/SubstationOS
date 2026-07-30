"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Building2, FolderPlus, Save } from "lucide-react";

import {
  SelectField,
  TextAreaField,
  TextField,
} from "@/components/projects/ProjectFormFields";
import { Button } from "@/components/ui/button";
import { useProjects } from "@/hooks/useProjects";
import { fieldMessages } from "@/lib/api";
import {
  PROJECT_FIELD_LIMITS,
  PROJECT_STATUSES,
  PROJECT_STATUS_LABELS,
} from "@/lib/contracts";
import {
  EMPTY_PROJECT_FORM,
  type FormErrors,
  type ProjectFormValues,
  toCreateRequest,
  validateProjectForm,
} from "@/lib/validation/project";

export default function NewProjectPage() {
  const router = useRouter();

  const { create, creating, createError, createFailure, resetCreateError } =
    useProjects();

  const [form, setForm] = useState<ProjectFormValues>(EMPTY_PROJECT_FORM);
  const [localErrors, setLocalErrors] = useState<FormErrors>({});

  // The backend's own 422, bound field by field. Client rules restate the
  // backend's; when they nonetheless disagree, the backend wins visibly.
  const serverErrors = fieldMessages(createFailure) as FormErrors;

  const errors: FormErrors = { ...serverErrors, ...localErrors };

  function update<K extends keyof ProjectFormValues>(
    field: K,
    value: ProjectFormValues[K],
  ) {
    setForm((current) => ({ ...current, [field]: value }));

    setLocalErrors((current) => {
      if (current[field] === undefined) {
        return current;
      }

      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    resetCreateError();

    const validation = validateProjectForm(form);

    if (Object.keys(validation).length > 0) {
      setLocalErrors(validation);
      return;
    }

    setLocalErrors({});

    try {
      const project = await create(toCreateRequest(form));
      router.push(`/projects/${project.id}`);
    } catch {
      // Rendered by `createError` and `serverErrors`; the form stays
      // open with the user's input intact.
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

          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
            Nuovo progetto
          </h1>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            I campi contrassegnati sono richiesti dal backend. Il codice
            progetto è un contratto: una volta creato non viene più
            rinominato.
          </p>
        </div>

        <form onSubmit={handleSubmit} noValidate className="mt-8 space-y-6">
          <section className="rounded-[2rem] border border-white/70 bg-white/72 p-6 shadow-[0_18px_45px_rgba(15,23,42,0.06)] backdrop-blur-2xl lg:p-8">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                <FolderPlus className="h-5 w-5" />
              </div>

              <div>
                <h2 className="text-lg font-semibold text-foreground">
                  Informazioni principali
                </h2>

                <p className="mt-1 text-sm text-muted-foreground">
                  Identificazione e fase di realizzazione della commessa
                </p>
              </div>
            </div>

            <div className="mt-6 grid gap-5 md:grid-cols-2">
              <TextField
                id="code"
                label="Codice progetto"
                required
                maxLength={PROJECT_FIELD_LIMITS.code.max}
                value={form.code}
                error={errors.code}
                onChange={(value) => update("code", value)}
                placeholder="es. CP-GAMMA-2026"
              />

              <TextField
                id="name"
                label="Nome progetto"
                required
                maxLength={PROJECT_FIELD_LIMITS.name.max}
                value={form.name}
                error={errors.name}
                onChange={(value) => update("name", value)}
                placeholder="es. Cabina Primaria Gamma"
              />

              <SelectField
                id="status"
                label="Fase"
                value={form.status}
                options={PROJECT_STATUSES}
                labels={PROJECT_STATUS_LABELS}
                error={errors.status}
                onChange={(value) => update("status", value)}
              />

              <TextField
                id="voltage_level"
                label="Livello di tensione"
                maxLength={PROJECT_FIELD_LIMITS.voltage_level.max}
                value={form.voltage_level}
                error={errors.voltage_level}
                onChange={(value) => update("voltage_level", value)}
                placeholder="es. 150/20 kV"
              />
            </div>
          </section>

          <section className="rounded-[2rem] border border-white/70 bg-white/72 p-6 shadow-[0_18px_45px_rgba(15,23,42,0.06)] backdrop-blur-2xl lg:p-8">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                <Building2 className="h-5 w-5" />
              </div>

              <div>
                <h2 className="text-lg font-semibold text-foreground">
                  Soggetti e localizzazione
                </h2>

                <p className="mt-1 text-sm text-muted-foreground">
                  Committente, EPC e sede dell&apos;impianto
                </p>
              </div>
            </div>

            <div className="mt-6 grid gap-5 md:grid-cols-2">
              <TextField
                id="customer"
                label="Committente"
                required
                maxLength={PROJECT_FIELD_LIMITS.customer.max}
                value={form.customer}
                error={errors.customer}
                onChange={(value) => update("customer", value)}
                placeholder="es. Distributore Nazionale"
              />

              <TextField
                id="epc"
                label="EPC"
                maxLength={PROJECT_FIELD_LIMITS.epc.max}
                value={form.epc}
                error={errors.epc}
                onChange={(value) => update("epc", value)}
                placeholder="Società EPC"
              />

              <TextField
                id="location"
                label="Località"
                maxLength={PROJECT_FIELD_LIMITS.location.max}
                value={form.location}
                error={errors.location}
                onChange={(value) => update("location", value)}
                placeholder="Comune, provincia o area impianto"
              />

              <TextField
                id="country"
                label="Paese"
                maxLength={PROJECT_FIELD_LIMITS.country.max}
                value={form.country}
                error={errors.country}
                onChange={(value) => update("country", value)}
                placeholder="es. Italia"
              />
            </div>
          </section>

          <section className="rounded-[2rem] border border-white/70 bg-white/72 p-6 shadow-[0_18px_45px_rgba(15,23,42,0.06)] backdrop-blur-2xl lg:p-8">
            <TextAreaField
              id="description"
              label="Descrizione"
              value={form.description}
              error={errors.description}
              onChange={(value) => update("description", value)}
              placeholder="Scopo della commessa, attività previste e informazioni tecniche rilevanti."
            />
          </section>

          {createError && (
            <p
              role="alert"
              className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700"
            >
              {createError}
            </p>
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

            <Button type="submit" disabled={creating}>
              <Save className="h-4 w-4" />
              {creating ? "Creazione in corso..." : "Crea progetto"}
            </Button>
          </div>
        </form>
      </section>
    </main>
  );
}
