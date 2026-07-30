/**
 * A stand-in for the SubstationOS backend.
 *
 * Routes are declared per test with the **exact** status and body the
 * real API returns - taken from the routers, not invented - so a test
 * that passes here is a test against the documented contract. An
 * undeclared request fails the test rather than resolving to nothing.
 */

import { vi } from "vitest";

import type {
  CanonicalPdfPage,
  Session,
  DocumentDetail,
  DocumentSummary,
  EntitySet,
  EvidenceSet,
  FactSet,
  IngestionJob,
  Project,
  SemanticSet,
} from "@/lib/contracts";

export interface RouteResponse {
  status?: number;
  body?: unknown;
  /** Rejects the request at transport level (no response at all). */
  networkFailure?: boolean;
  /** Never settles - used to observe pending and cancelled states. */
  hang?: boolean;
}

export type Routes = Record<string, RouteResponse | RouteResponse[]>;

export interface RecordedRequest {
  method: string;
  url: string;
  body: unknown;
  /** Lower-cased, so a test never depends on header capitalisation. */
  headers: Record<string, string>;
  /** `"include"` is what makes the session cookie travel. */
  credentials: RequestCredentials | undefined;
}

export interface BackendStub {
  requests: RecordedRequest[];
  /** Requests whose method and path match, in order. */
  requestsFor: (method: string, path: string) => RecordedRequest[];
}

const BASE = "http://localhost:8000";

function keyFor(method: string, url: string): string {
  return `${method.toUpperCase()} ${url.replace(BASE, "").split("?")[0]}`;
}

/**
 * @param routes keyed `"<METHOD> <path>"`, e.g. `"GET /projects/"`. An
 * array of responses is consumed one per call, which is how a test
 * asserts that a second POST returns 200 (re-used) after a 201.
 */
export function stubBackend(routes: Routes): BackendStub {
  const requests: RecordedRequest[] = [];
  const queues = new Map<string, RouteResponse[]>();

  for (const [key, value] of Object.entries(routes)) {
    queues.set(key, Array.isArray(value) ? [...value] : [value]);
  }

  const fetchStub = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      const key = keyFor(method, url);

      let body: unknown = null;

      if (typeof init?.body === "string") {
        body = JSON.parse(init.body) as unknown;
      } else if (init?.body instanceof FormData) {
        body = Object.fromEntries(init.body.entries());
      }

      const headers: Record<string, string> = {};

      for (const [name, value] of Object.entries(
        (init?.headers ?? {}) as Record<string, string>,
      )) {
        headers[name.toLowerCase()] = value;
      }

      requests.push({
        method,
        url,
        body,
        headers,
        credentials: init?.credentials,
      });

      const queue = queues.get(key);

      if (queue === undefined || queue.length === 0) {
        throw new Error(
          `Unexpected request ${key}. Declared: ${[...queues.keys()].join(
            ", ",
          )}`,
        );
      }

      const route = queue.length === 1 ? queue[0] : queue.shift()!;

      if (route.hang === true) {
        return new Promise<Response>((_, reject) => {
          init?.signal?.addEventListener("abort", () => {
            const error = new Error("aborted");
            error.name = "AbortError";
            reject(error);
          });
        });
      }

      if (route.networkFailure === true) {
        throw new TypeError("Failed to fetch");
      }

      const status = route.status ?? 200;

      return new Response(
        route.body === undefined ? "" : JSON.stringify(route.body),
        {
          status,
          headers: { "Content-Type": "application/json" },
        },
      );
    },
  );

  vi.stubGlobal("fetch", fetchStub);

  return {
    requests,
    requestsFor: (method, path) =>
      requests.filter(
        (request) => keyFor(request.method, request.url) === keyFor(method, path),
      ),
  };
}

// --- Fixtures, shaped exactly as the backend serialises them ------------

export function aProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 1,
    name: "Cabina Primaria Gamma",
    code: "CP-GAMMA-2026",
    customer: "Distributore Nazionale",
    epc: null,
    country: "Italia",
    location: "Bari",
    voltage_level: "150/20 kV",
    status: "planning",
    description: null,
    lifecycle_state: "active",
    canonical_domain_version: "unversioned",
    created_by: null,
    created_at: "2026-07-01T09:00:00",
    updated_at: "2026-07-01T09:00:00",
    archived_at: null,
    deleted_at: null,
    ...overrides,
  };
}

export function aDocument(
  overrides: Partial<DocumentSummary> = {},
): DocumentSummary {
  return {
    id: 10,
    project_id: 1,
    filename: "schema-funzionale.pdf",
    file_format: "pdf",
    category: "functional_schematic",
    revision: "00",
    project_name: "Cabina Primaria Gamma",
    scope: "project",
    uploaded_at: "2026-07-02T10:30:00",
    ...overrides,
  };
}

/**
 * `PagedResponse<T>` as the backend serialises it. Milestone 30.1.3 made
 * every list endpoint return this envelope.
 */
export function aPage<T>(
  items: T[],
  overrides: Partial<{
    page: number;
    page_size: number;
    total: number;
  }> = {},
) {
  const page = overrides.page ?? 1;
  const pageSize = overrides.page_size ?? 25;
  const total = overrides.total ?? items.length;

  return {
    items,
    pagination: {
      page,
      page_size: pageSize,
      total,
      total_pages: Math.ceil(total / pageSize),
      has_next: page * pageSize < total,
      has_previous: page > 1,
    },
  };
}

export function aDocumentDetail(
  overrides: Partial<DocumentDetail> = {},
): DocumentDetail {
  return {
    ...aDocument(),
    content_checksum: "b".repeat(64),
    checksum_algorithm: "sha256",
    size_bytes: 2048,
    content_available: true,
    ingestion_state: "processed",
    ingestion_outcome: "ready_for_extraction",
    ...overrides,
  };
}

export function anUpload(
  document: DocumentDetail = aDocumentDetail(),
  overrides: {
    status?: string;
    entities_found?: number;
    warnings?: string[];
  } = {},
) {
  return {
    document,
    scope: document.scope,
    analysis: {
      status: overrides.status ?? "completed",
      entities_found: overrides.entities_found ?? 0,
      failure: null,
    },
    warnings: overrides.warnings ?? [],
  };
}

export function anIngestionJob(
  overrides: Partial<IngestionJob> = {},
): IngestionJob {
  return {
    id: 5,
    project_id: 1,
    document_id: 10,
    state: "processed",
    outcome: "ready_for_extraction",
    pipeline_version: "1.0",
    attempt_count: 1,
    created_at: "2026-07-02T10:30:05",
    updated_at: "2026-07-02T10:30:09",
    completed_at: "2026-07-02T10:30:09",
    failure: null,
    document: null,
    ready_for_extraction: true,
    ...overrides,
  };
}

export function anEvidenceSet(
  overrides: Partial<EvidenceSet> = {},
): EvidenceSet {
  return {
    document_id: 10,
    project_id: 1,
    content_checksum: "a".repeat(64),
    segmentation_version: "1.0",
    extraction_policy_version: "1.0",
    evidence_count: 2,
    evidence: [
      {
        evidence_key: "ev-designation",
        evidence_type: "designation",
        status: "observed",
        observed_text: "TR1",
        rule_id: "designation_pattern",
        rule_version: "1.0",
        quantity: null,
        designation: { normalized: "TR1" },
        provenance: {
          page_number: 1,
          section_index: 0,
          paragraph_index: 0,
          block_reading_order: 0,
          line_index: 0,
          token_start: 1,
          token_end: 2,
          spans: [
            {
              span_reading_order: 0,
              character_start: 14,
              character_end: 17,
            },
          ],
          source_text: "Trasformatore TR1 630 kVA",
        },
      },
      {
        evidence_key: "ev-power",
        evidence_type: "power_value",
        status: "observed",
        observed_text: "630 kVA",
        rule_id: "power_with_unit",
        rule_version: "1.0",
        quantity: {
          value: "630",
          unit: "kVA",
          base_value: "630000",
          base_unit: "VA",
        },
        designation: null,
        provenance: {
          page_number: 1,
          section_index: 0,
          paragraph_index: 0,
          block_reading_order: 0,
          line_index: 0,
          token_start: 2,
          token_end: 4,
          spans: [
            {
              span_reading_order: 0,
              character_start: 18,
              character_end: 25,
            },
          ],
          source_text: "Trasformatore TR1 630 kVA",
        },
      },
    ],
    ...overrides,
  };
}

export function anEntitySet(overrides: Partial<EntitySet> = {}): EntitySet {
  return {
    document_id: 10,
    project_id: 1,
    content_checksum: "a".repeat(64),
    extraction_policy_version: "1.0",
    resolution_policy_version: "1.0",
    entity_count: 2,
    entities: [
      {
        entity_key: "entity-tr1",
        entity_type: "equipment_designation",
        status: "resolved",
        entity_version: "1.0",
        resolution_rule_id: "designation_grouping",
        resolution_rule_version: "1.0",
        label: "TR1",
        evidence_count: 1,
        designation: { normalized: "TR1" },
        quantity: null,
        // The entity's own declaration of what created it. Every support
        // relationship in this application is an explicit reference like
        // this one - never a text or value comparison.
        evidence: [
          {
            evidence_key: "ev-designation",
            evidence_type: "designation",
            observed_text: "TR1",
            page_number: 1,
            paragraph_index: 0,
            line_index: 0,
            token_start: 1,
            token_end: 2,
          },
        ],
      },
      {
        entity_key: "entity-630kva",
        entity_type: "engineering_quantity",
        status: "resolved",
        entity_version: "1.0",
        resolution_rule_id: "quantity_observation",
        resolution_rule_version: "1.0",
        label: "630 kVA",
        evidence_count: 1,
        designation: null,
        quantity: {
          value: "630",
          unit: "kVA",
          base_value: "630000",
          base_unit: "VA",
        },
        evidence: [
          {
            evidence_key: "ev-power",
            evidence_type: "power_value",
            observed_text: "630 kVA",
            page_number: 1,
            paragraph_index: 0,
            line_index: 0,
            token_start: 2,
            token_end: 4,
          },
        ],
      },
    ],
    ...overrides,
  };
}

export function aFactSet(overrides: Partial<FactSet> = {}): FactSet {
  return {
    document_id: 10,
    project_id: 1,
    content_checksum: "a".repeat(64),
    resolution_policy_version: "1.0",
    fact_policy_version: "1.0",
    fact_count: 1,
    has_ambiguities: false,
    facts: [
      {
        fact_key: "fact-tr1-630",
        subject_entity_key: "entity-tr1",
        predicate: "has_associated_quantity",
        object_entity_key: "entity-630kva",
        status: "constructed",
        fact_version: "1.0",
        construction_rule_id: "same_line_association",
        construction_rule_version: "1.0",
        support: [
          {
            evidence_key: "ev-designation",
            role: "subject",
            evidence_type: "designation",
            observed_text: "TR1",
            page_number: 1,
            paragraph_index: 0,
            line_index: 0,
            token_start: 1,
            token_end: 2,
          },
        ],
      },
    ],
    diagnostics: [],
    ...overrides,
  };
}

export function aSemanticSet(
  overrides: Partial<SemanticSet> = {},
): SemanticSet {
  return {
    document_id: 10,
    project_id: 1,
    content_checksum: "a".repeat(64),
    resolution_policy_version: "1.0",
    fact_policy_version: "1.0",
    semantic_policy_version: "1.0",
    statement_count: 1,
    has_ambiguities: false,
    statements: [
      {
        statement_key: "statement-tr1-power",
        statement_type: "has_rated_power",
        subject_entity_key: "entity-tr1",
        object_entity_key: "entity-630kva",
        status: "interpreted",
        semantic_contract_version: "1.0",
        semantic_rule_id: "rated_power_from_associated_power_quantity",
        semantic_rule_version: "1.0",
        supporting_fact_keys: ["fact-tr1-630"],
      },
    ],
    diagnostics: [],
    ...overrides,
  };
}

/**
 * One page of the canonical representation, as
 * `GET /documents/{id}/canonical-representation/pages/{n}` serialises it.
 *
 * `reading_order` on the span is the number `anEvidenceSet`'s provenance
 * cites in `spans[].span_reading_order`. That, with the block's own
 * `reading_order` and the page number, is the whole join: it is how a
 * highlight finds its rectangle without any text ever being compared.
 */
export function aCanonicalPage(
  overrides: Partial<CanonicalPdfPage> = {},
): CanonicalPdfPage {
  return {
    page_number: 1,
    width: 595,
    height: 842,
    blocks: [
      {
        reading_order: 0,
        kind: "text",
        bounding_box: { x0: 70, y0: 100, x1: 400, y1: 120 },
        spans: [
          {
            reading_order: 0,
            line_index: 0,
            text: "Trasformatore TR1 630 kVA",
            bounding_box: { x0: 72, y0: 102, x1: 320, y1: 118 },
            style: {
              font_family: "Helvetica",
              font_size: 11,
              bold: false,
              italic: false,
            },
          },
        ],
      },
    ],
    ...overrides,
  };
}


/**
 * `GET /auth/session` / `POST /auth/login`, as the backend serialises it.
 *
 * There is no token here, and no fixture could add one: the session
 * token leaves the server only in a `Set-Cookie` header, and no response
 * model has a field for it.
 */
export function aSession(
  overrides: Partial<Session["identity"]> = {},
): Session {
  return {
    identity: {
      user_id: 1,
      email: "ada@substationos.test",
      display_name: "Ada Lovelace",
      role: "engineer",
      ...overrides,
    },
    expires_at: "2026-07-30T21:00:00",
  };
}
