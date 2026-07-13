"use client";

import { useMemo, useState } from "react";

import DocumentTable from "@/components/documents/DocumentTable";
import FilterPanel from "@/components/documents/FilterPanel";
import SearchBar from "@/components/documents/SearchBar";
import UploadBox from "@/components/UploadBox";

import { useDocuments } from "@/hooks/useDocuments";

export default function DocumentsPage() {
  const {
    documents,
    loading,
    error,
    reload,
  } = useDocuments();

  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] =
    useState("");
  const [selectedProject, setSelectedProject] =
    useState("");
  const [selectedRevision, setSelectedRevision] =
    useState("");

  const categories = useMemo(() => {
    return [
      ...new Set(
        documents.map((document) => document.category)
      ),
    ]
      .filter(Boolean)
      .sort();
  }, [documents]);

  const projects = useMemo(() => {
    return [
      ...new Set(
        documents.map((document) => document.project)
      ),
    ]
      .filter(Boolean)
      .sort();
  }, [documents]);

  const revisions = useMemo(() => {
    return [
      ...new Set(
        documents.map((document) => document.revision)
      ),
    ]
      .filter(Boolean)
      .sort();
  }, [documents]);

  const filteredDocuments = useMemo(() => {
    const normalizedSearchTerm = searchTerm
      .trim()
      .toLowerCase();

    return documents.filter((document) => {
      const matchesSearch =
        normalizedSearchTerm === "" ||
        document.filename
          .toLowerCase()
          .includes(normalizedSearchTerm) ||
        document.category
          .toLowerCase()
          .includes(normalizedSearchTerm) ||
        document.project
          .toLowerCase()
          .includes(normalizedSearchTerm) ||
        document.revision
          .toLowerCase()
          .includes(normalizedSearchTerm);

      const matchesCategory =
        selectedCategory === "" ||
        document.category === selectedCategory;

      const matchesProject =
        selectedProject === "" ||
        document.project === selectedProject;

      const matchesRevision =
        selectedRevision === "" ||
        document.revision === selectedRevision;

      return (
        matchesSearch &&
        matchesCategory &&
        matchesProject &&
        matchesRevision
      );
    });
  }, [
    documents,
    searchTerm,
    selectedCategory,
    selectedProject,
    selectedRevision,
  ]);

  function resetFilters() {
    setSearchTerm("");
    setSelectedCategory("");
    setSelectedProject("");
    setSelectedRevision("");
  }

  return (
    <main className="p-8">
      <h1 className="text-3xl font-bold">
        Document Registry
      </h1>

      <p className="mt-2 text-gray-600">
        Carica, ricerca e gestisci i documenti tecnici di
        SubstationOS.
      </p>

      <div className="mt-8">
        <UploadBox
          onUploadSuccess={reload}
        />
      </div>

      <SearchBar
        value={searchTerm}
        onChange={setSearchTerm}
      />

      <FilterPanel
        categories={categories}
        projects={projects}
        revisions={revisions}
        selectedCategory={selectedCategory}
        selectedProject={selectedProject}
        selectedRevision={selectedRevision}
        onCategoryChange={setSelectedCategory}
        onProjectChange={setSelectedProject}
        onRevisionChange={setSelectedRevision}
        onReset={resetFilters}
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
            Nessun documento corrisponde ai criteri selezionati.
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