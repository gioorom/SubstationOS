"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import DocumentTable from "@/components/documents/DocumentTable";
import FilterPanel from "@/components/documents/FilterPanel";
import SearchBar from "@/components/documents/SearchBar";
import UploadBox from "@/components/UploadBox";

import { useDocuments } from "@/hooks/useDocuments";
import { getProjects } from "@/lib/projects";
import { Project } from "@/types/project";

export default function DocumentsPage() {
  const {
    documents,
    loading,
    uploading,
    error,
    addDocument,
  } = useDocuments();

  const [searchTerm, setSearchTerm] = useState("");

  const [selectedCategory, setSelectedCategory] =
    useState("");

  const [selectedProject, setSelectedProject] =
    useState("");

  const [selectedRevision, setSelectedRevision] =
    useState("");

  const [availableProjects, setAvailableProjects] =
    useState<Project[]>([]);

  const [uploadProjectId, setUploadProjectId] =
    useState<number>();

  const [projectsLoading, setProjectsLoading] =
    useState(true);

  const [projectsError, setProjectsError] =
    useState("");

  useEffect(() => {
    async function loadProjects() {
      setProjectsLoading(true);
      setProjectsError("");

      try {
        const projectList = await getProjects();

        setAvailableProjects(projectList);

        if (projectList.length > 0) {
          setUploadProjectId((currentProjectId) => {
            return (
              currentProjectId ??
              projectList[0].id
            );
          });
        }
      } catch {
        setProjectsError(
          "Errore durante il caricamento dei progetti."
        );
      } finally {
        setProjectsLoading(false);
      }
    }

    void loadProjects();
  }, []);

  const categories = useMemo(() => {
    return [
      ...new Set(
        documents.map(
          (document) => document.category
        )
      ),
    ]
      .filter(Boolean)
      .sort();
  }, [documents]);

  const documentProjects = useMemo(() => {
    return [
      ...new Set(
        documents.map(
          (document) => document.project_name
        )
      ),
    ]
      .filter(Boolean)
      .sort();
  }, [documents]);

  const revisions = useMemo(() => {
    return [
      ...new Set(
        documents.map(
          (document) => document.revision
        )
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
      const filename =
        document.filename?.toLowerCase() ?? "";

      const category =
        document.category?.toLowerCase() ?? "";

      const projectName =
        document.project_name?.toLowerCase() ?? "";

      const revision =
        document.revision?.toLowerCase() ?? "";

      const matchesSearch =
        normalizedSearchTerm === "" ||
        filename.includes(normalizedSearchTerm) ||
        category.includes(normalizedSearchTerm) ||
        projectName.includes(
          normalizedSearchTerm
        ) ||
        revision.includes(normalizedSearchTerm);

      const matchesCategory =
        selectedCategory === "" ||
        document.category === selectedCategory;

      const matchesProject =
        selectedProject === "" ||
        document.project_name === selectedProject;

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
    <main className="px-6 py-8 lg:px-10 lg:py-10">
      <section>
        <p className="text-sm font-medium text-primary">
          Document Workspace
        </p>

        <h2 className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
          Document Registry
        </h2>

        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          Carica, ricerca e gestisci i documenti
          tecnici registrati in SubstationOS.
        </p>
      </section>

      <div className="mt-8">
        <UploadBox
          onUpload={addDocument}
          uploading={uploading}
          projects={availableProjects}
          projectsLoading={projectsLoading}
          selectedProjectId={uploadProjectId}
          onProjectChange={setUploadProjectId}
        />
      </div>

      {projectsError && (
        <section className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          {projectsError}
        </section>
      )}

      <SearchBar
        value={searchTerm}
        onChange={setSearchTerm}
      />

      <FilterPanel
        categories={categories}
        projects={documentProjects}
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
        <p className="mt-8 text-sm text-muted-foreground">
          Caricamento documenti...
        </p>
      )}

      {error && (
        <section className="mt-8 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          {error}
        </section>
      )}

      {!loading &&
        !error &&
        documents.length === 0 && (
          <p className="mt-8 text-sm text-muted-foreground">
            Nessun documento registrato.
          </p>
        )}

      {!loading &&
        !error &&
        documents.length > 0 &&
        filteredDocuments.length === 0 && (
          <p className="mt-8 text-sm text-muted-foreground">
            Nessun documento corrisponde ai criteri
            selezionati.
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