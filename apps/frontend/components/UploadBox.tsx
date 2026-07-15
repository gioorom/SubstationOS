"use client";

import { useState } from "react";
import { UploadCloud } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";

interface UploadBoxProps {
  onUpload: (file: File) => Promise<unknown>;
  uploading?: boolean;
  title?: string;
  description?: string;
}

export default function UploadBox({
  onUpload,
  uploading = false,
  title = "Carica documento tecnico",
  description = "Seleziona un PDF, DWG o altro file tecnico.",
}: UploadBoxProps) {
  const [file, setFile] = useState<File | null>(null);

  async function handleUpload() {
    if (!file) {
      toast.warning("Seleziona prima un file.");
      return;
    }

    try {
      await onUpload(file);

      toast.success("Documento caricato correttamente", {
        description: file.name,
      });

      setFile(null);
    } catch {
      toast.error("Upload non riuscito", {
        description:
          "Controlla il backend e riprova.",
      });
    }
  }

  return (
    <section className="rounded-3xl border border-white/70 bg-white/72 p-6 shadow-[0_18px_45px_rgba(15,23,42,0.06)] backdrop-blur-2xl">
      <div className="flex items-start gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <UploadCloud className="h-6 w-6" />
        </div>

        <div>
          <h2 className="text-lg font-semibold text-foreground">
            {title}
          </h2>

          <p className="mt-1 text-sm text-muted-foreground">
            {description}
          </p>
        </div>
      </div>

      <div className="mt-6">
        <input
          type="file"
          disabled={uploading}
          onChange={(event) =>
            setFile(event.target.files?.[0] ?? null)
          }
          className="block w-full rounded-2xl border border-input bg-white/80 px-4 py-3 text-sm text-foreground file:mr-4 file:rounded-xl file:border-0 file:bg-secondary file:px-4 file:py-2 file:text-sm file:font-medium file:text-secondary-foreground hover:file:bg-secondary/80 disabled:cursor-not-allowed disabled:opacity-60"
        />
      </div>

      {file && (
        <p className="mt-3 text-sm text-muted-foreground">
          Selezionato: {file.name}
        </p>
      )}

      <Button
        type="button"
        onClick={() => void handleUpload()}
        disabled={uploading || !file}
        className="mt-5"
      >
        <UploadCloud className="h-4 w-4" />

        {uploading
          ? "Caricamento..."
          : "Carica documento"}
      </Button>
    </section>
  );
}