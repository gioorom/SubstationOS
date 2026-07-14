"use client";

import { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";
import { toast } from "sonner";

import { env } from "@/config/env";

interface UploadBoxProps {
  onUploadSuccess?: () => void | Promise<void>;
}

export default function UploadBox({
  onUploadSuccess,
}: UploadBoxProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  async function uploadFile() {
    if (!file) {
      toast.warning("Nessun file selezionato", {
        description:
          "Seleziona un documento tecnico prima di avviare l’upload.",
      });

      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setUploading(true);

    const toastId = toast.loading(
      "Caricamento documento",
      {
        description: file.name,
      }
    );

    try {
      const response = await fetch(
        `${env.apiBaseUrl}/documents/upload`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        throw new Error(
          `Upload fallito con stato ${response.status}`
        );
      }

      const data: {
        filename?: string;
      } = await response.json();

      toast.success("Documento caricato", {
        id: toastId,
        description:
          data.filename ??
          "Il documento è stato registrato correttamente.",
      });

      setFile(null);

      if (inputRef.current) {
        inputRef.current.value = "";
      }

      await onUploadSuccess?.();
    } catch {
      toast.error("Upload non riuscito", {
        id: toastId,
        description:
          "Verifica che il backend sia attivo e riprova.",
      });
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="rounded-3xl border border-white/70 bg-white/72 p-6 shadow-[0_18px_45px_rgba(15,23,42,0.06)] backdrop-blur-2xl">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <UploadCloud
                className="h-5 w-5"
                strokeWidth={1.8}
              />
            </div>

            <div>
              <h2 className="text-lg font-semibold text-foreground">
                Carica documento tecnico
              </h2>

              <p className="mt-1 text-sm text-muted-foreground">
                PDF, DWG e altri file tecnici di progetto.
              </p>
            </div>
          </div>

          <input
            ref={inputRef}
            type="file"
            className="mt-5 block w-full max-w-xl rounded-2xl border border-border bg-white/70 px-4 py-3 text-sm text-muted-foreground file:mr-4 file:rounded-xl file:border-0 file:bg-primary/10 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-primary hover:file:bg-primary/15"
            onChange={(event) =>
              setFile(event.target.files?.[0] ?? null)
            }
          />

          {file && (
            <p className="mt-3 text-sm text-muted-foreground">
              Selezionato:{" "}
              <span className="font-medium text-foreground">
                {file.name}
              </span>
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={() => void uploadFile()}
          disabled={uploading}
          className="inline-flex min-h-12 items-center justify-center rounded-2xl bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground shadow-lg shadow-blue-500/20 transition hover:-translate-y-0.5 hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {uploading
            ? "Caricamento..."
            : "Avvia upload"}
        </button>
      </div>
    </section>
  );
}