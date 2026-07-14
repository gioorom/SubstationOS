"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import { getHealth } from "@/lib/health";
import {
  HealthResponse,
  ServiceStatus,
} from "@/types/health";

interface UseHealthResult {
  health: HealthResponse | null;
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
}

export function useHealth(): UseHealthResult {
  const [health, setHealth] =
    useState<HealthResponse | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const data = await getHealth();
      setHealth(data);
    } catch {
      setHealth({
        status: "offline",
        services: {
          api: "offline",
          database: "offline",
          storage: "offline",
          ai: "offline",
        },
      });

      setError(
        "Impossibile verificare lo stato dei servizi."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return {
    health,
    loading,
    error,
    reload,
  };
}

export function normalizeServiceStatus(
  status?: ServiceStatus
): ServiceStatus {
  return status ?? "offline";
}