"use client";

import { useEffect, useState } from "react";

interface Document {
  id: number;
  filename: string;
  category: string;
  project: string;
  revision: string;
  uploaded_at: string;
}

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadDocuments() {
      try {
        const response = await fetch(
          "http://127.0.0.1:8000/documents/"
        );

        if (!response.ok) {
          throw new Error("Impossibile caricare i documenti");
        }

        const data: Document[] = await response.json();
        setDocuments(data);
      } catch {
        setError("Errore durante il caricamento dei documenti.");
      } finally {
        setLoading(false);
      }
    }

    loadDocuments();
  }, []);

  return (
    <main className="p-8">
      <h1 className="text-3xl font-bold">
        Document Registry
      </h1>

      <p className="mt-2 text-gray-600">
        Documenti tecnici registrati in SubstationOS.
      </p>

      {loading && (
        <p className="mt-8">
          Caricamento documenti...
        </p>
      )}

      {error && (
        <p className="mt-8 text-red-600">
          {error}
        </p>
      )}

      {!loading && !error && documents.length === 0 && (
        <p className="mt-8 text-gray-600">
          Nessun documento registrato.
        </p>
      )}

      {!loading && !error && documents.length > 0 && (
        <div className="mt-8 overflow-hidden rounded-xl border">
          <table className="w-full border-collapse">
            <thead className="bg-gray-100 text-black">
              <tr>
                <th className="p-4 text-left">
                  Filename
                </th>
                <th className="p-4 text-left">
                  Categoria
                </th>
                <th className="p-4 text-left">
                  Progetto
                </th>
                <th className="p-4 text-left">
                  Revisione
                </th>
                <th className="p-4 text-left">
                  Caricato il
                </th>
              </tr>
            </thead>

            <tbody>
              {documents.map((document) => (
                <tr
                  key={document.id}
                  className="border-t"
                >
                  <td className="p-4">
                    {document.filename}
                  </td>
                  <td className="p-4">
                    {document.category}
                  </td>
                  <td className="p-4">
                    {document.project}
                  </td>
                  <td className="p-4">
                    {document.revision}
                  </td>
                  <td className="p-4">
                    {new Date(
                      document.uploaded_at
                    ).toLocaleString("it-IT")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}