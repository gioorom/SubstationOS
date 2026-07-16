import { TimelineEvent } from "@/types/timeline";

export const demoTimelineEvents: TimelineEvent[] = [
  {
    id: "timeline-001",
    project_id: 1,
    type: "document_uploaded",
    severity: "success",
    title: "Schema funzionale caricato",
    description:
      "Caricata la revisione più recente dello schema funzionale della linea AT.",
    occurred_at: "2026-07-16T08:42:00",
    actor: {
      id: 1,
      name: "Pietro Romano",
      role: "Commissioning Engineer",
    },
    entity: {
      type: "document",
      id: 12,
      label: "Schema Funzionale Linea AT - Rev. 03",
      href: null,
    },
    metadata: {
      filename: "Schema_Funzionale_Linea_AT_R03.pdf",
      revision: "03",
    },
  },
  {
    id: "timeline-002",
    project_id: 1,
    type: "health_score_changed",
    severity: "info",
    title: "Project Health aggiornato",
    description:
      "Il punteggio della commessa è aumentato dopo l’aggiornamento della documentazione tecnica.",
    occurred_at: "2026-07-16T08:45:00",
    actor: null,
    entity: {
      type: "intelligence",
      id: null,
      label: "Project Intelligence",
      href: null,
    },
    metadata: {
      health_score_before: 52,
      health_score_after: 64,
    },
  },
  {
    id: "timeline-003",
    project_id: 1,
    type: "intelligence_generated",
    severity: "warning",
    title: "Nuova azione consigliata",
    description:
      "Completare il set documentale minimo prima di pianificare le attività SAT.",
    occurred_at: "2026-07-16T08:46:00",
    actor: null,
    entity: {
      type: "intelligence",
      id: null,
      label: "Engineering Intelligence",
      href: null,
    },
    metadata: {},
  },
  {
    id: "timeline-004",
    project_id: 1,
    type: "revision_changed",
    severity: "info",
    title: "Revisione documento aggiornata",
    description:
      "La lista cavi è stata aggiornata dalla revisione 02 alla revisione 03.",
    occurred_at: "2026-07-15T16:18:00",
    actor: {
      id: 1,
      name: "Pietro Romano",
      role: "Project Engineer",
    },
    entity: {
      type: "document",
      id: 8,
      label: "Lista Cavi Cabina Primaria",
      href: null,
    },
    metadata: {
      previous_value: "02",
      current_value: "03",
      revision: "03",
    },
  },
];