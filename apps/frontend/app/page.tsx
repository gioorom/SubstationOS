"use client";

import { useEffect, useMemo, useState } from "react";

import DocumentTable from "@/components/documents/DocumentTable";
import SearchBar from "@/components/documents/SearchBar";

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
  const [searchTerm, setSearchTerm] = useState("");
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

  const filteredDocuments = useMemo(() => {
    const normalizedSearchTerm = searchTerm
      .trim()
      .toLowerCase();

    if (!normalizedSearchTerm) {
      return documents;
    }

    return documents.filter((document) =>
      document.filename
        .toLowerCase()
        .includes(normalizedSearchTerm)
    );
  }, [documents, searchTerm]);

  return (
    <main className="p-8">
      <h1 className="text-3xl font-bold">
        Document Registry
      </h1>

      <p className="mt-2 text-gray-600">
        Documenti tecnici registrati in SubstationOS.
      </p>

      <SearchBar
        value={searchTerm}
        onChange={setSearchTerm}
      />

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

      {!loading &&
        !error &&
        documents.length === 0 && (
          <p className="mt-8 text-gray-600">
            Nessun documento registrato.
          </p>
        )}

      {!loading &&
        !error &&
        documents.length > 0 &&
        filteredDocuments.length === 0 && (
          <p className="mt-8 text-gray-600">
            Nessun documento corrisponde alla ricerca.
          </p>
        )}

      {!loading &&
        !error &&
        filteredDocuments.length > 0 && (
          <DocumentTable
            documents={filteredDocuments}
          />
        )}
    </main>
  );
}