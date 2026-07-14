"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  createProject,
  getProjects,
} from "@/lib/projects";

import {
  CreateProjectPayload,
  Project,
} from "@/types/project";

interface UseProjectsResult {
  projects: Project[];
  loading: boolean;
  creating: boolean;
  error: string;
  reload: () => Promise<void>;
  addProject: (
    payload: CreateProjectPayload
  ) => Promise<Project>;
}

export function useProjects(): UseProjectsResult {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const data = await getProjects();
      setProjects(data);
    } catch {
      setError(
        "Errore durante il caricamento dei progetti."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const addProject = useCallback(
    async (
      payload: CreateProjectPayload
    ): Promise<Project> => {
      setCreating(true);
      setError("");

      try {
        const project = await createProject(payload);

        setProjects((currentProjects) => [
          project,
          ...currentProjects,
        ]);

        return project;
      } catch (error) {
        setError(
          "Errore durante la creazione del progetto."
        );

        throw error;
      } finally {
        setCreating(false);
      }
    },
    []
  );

  useEffect(() => {
    void reload();
  }, [reload]);

  return {
    projects,
    loading,
    creating,
    error,
    reload,
    addProject,
  };
}