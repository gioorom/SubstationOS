"use client";

import { useState } from "react";

interface UploadBoxProps {
  onUploadSuccess?: () => void | Promise<void>;
}

export default function UploadBox({
  onUploadSuccess,
}: UploadBoxProps) {
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [uploading, setUploading] = useState(false);

  async function uploadFile() {
    if (!file) {
      setMessage("Seleziona prima un file.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setUploading(true);
    setMessage("");

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/documents/upload",
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        throw new Error("Upload non riuscito");
      }

      const data = await response.json();

      setMessage(`Caricato: ${data.filename}`);
      setFile(null);

      await onUploadSuccess?.();
    } catch {
      setMessage("Upload non riuscito.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold text-gray-900">
        Carica documento tecnico
      </h2>

      <p className="mt-2 text-sm text-gray-500">
        Seleziona un PDF, DWG o altro file tecnico.
      </p>

      <input
        type="file"
        className="mt-5 block w-full text-sm text-gray-600"
        onChange={(event) =>
          setFile(event.target.files?.[0] ?? null)
        }
      />

      {file && (
        <p className="mt-3 text-sm text-gray-600">
          Selezionato: {file.name}
        </p>
      )}

      <button
        type="button"
        onClick={() => void uploadFile()}
        disabled={uploading}
        className="mt-5 rounded-xl bg-black px-5 py-3 font-medium text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {uploading ? "Caricamento..." : "Upload"}
      </button>

      {message && (
        <p className="mt-4 text-sm text-gray-600">
          {message}
        </p>
      )}
    </div>
  );
}