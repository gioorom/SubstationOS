/**
 * The frontend's enums, checked against the backend's own OpenAPI
 * document.
 *
 * This is the test that makes `lib/contracts` a transcription rather
 * than a guess. It reads `apps/backend`'s generated schema when one is
 * present and fails when the two disagree - which is exactly how this
 * EPIC found `ProjectStatus` shipping `active`, `on_hold`, `completed`
 * and `cancelled`, none of which the backend has ever accepted.
 *
 * Regenerate the schema with:
 *
 *     cd apps/backend && python -m scripts.export_openapi
 *
 * When the file is absent the enum assertions are skipped and the
 * structural checks still run, so a checkout without a Python
 * environment is not blocked.
 */

import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  AUDIT_ACTIONS,
  AUDIT_OUTCOMES,
  CANONICAL_BLOCK_KINDS,
  DOCUMENT_CATEGORIES,
  DOCUMENT_CATEGORY_LABELS,
  DOCUMENT_FORMATS,
  DOCUMENT_FORMAT_LABELS,
  DOCUMENT_SCOPES,
  DOCUMENT_SORT_FIELDS,
  ENTITY_STATUSES,
  ENTITY_TYPES,
  EVIDENCE_STATUSES,
  EVIDENCE_TYPES,
  EVIDENCE_TYPE_LABELS,
  FACT_PREDICATES,
  FACT_STATUSES,
  GRAPH_ENTITY_TYPES,
  GRAPH_RELATION_TYPES,
  INGESTION_STATES,
  PIPELINE_STAGES,
  PIPELINE_STAGE_DESCRIPTIONS,
  PIPELINE_STAGE_LABELS,
  PROJECT_LIFECYCLE_STATES,
  PROJECT_LIFECYCLE_LABELS,
  PROJECT_SORT_FIELDS,
  PROJECT_STATUSES,
  ROLES,
  USER_STATUSES,
  PROJECT_STATUS_LABELS,
  MAX_PAGE_SIZE,
  DEFAULT_PAGE_SIZE,
  SORT_DIRECTIONS,
  SEMANTIC_STATEMENT_STATUSES,
  SEMANTIC_STATEMENT_TYPES,
  SUPPORT_ROLES,
} from "@/lib/contracts";

// Relative to the frontend package root, which is Vitest's cwd.
const SCHEMA_PATH = resolve("../backend/openapi.json");

interface OpenApiSchema {
  components: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    schemas: Record<string, any>;
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  paths: Record<string, any>;
}

const schema: OpenApiSchema | null = existsSync(SCHEMA_PATH)
  ? (JSON.parse(readFileSync(SCHEMA_PATH, "utf-8")) as OpenApiSchema)
  : null;

function backendEnum(name: string): string[] {
  const declared = schema?.components.schemas[name]?.enum;

  if (declared === undefined) {
    throw new Error(
      `The backend schema declares no enum named '${name}'. ` +
        "Either it was renamed, or the frontend is describing something " +
        "the API does not have.",
    );
  }

  return declared;
}

describe.runIf(schema !== null)("enums match the backend", () => {
  const cases: [string, readonly string[]][] = [
    ["ProjectStatus", PROJECT_STATUSES],
    ["ProjectLifecycleState", PROJECT_LIFECYCLE_STATES],
    ["DocumentScope", DOCUMENT_SCOPES],
    ["IngestionState", INGESTION_STATES],
    ["EvidenceType", EVIDENCE_TYPES],
    ["EvidenceStatus", EVIDENCE_STATUSES],
    [
      "app__domain__engineering_entities__entity_models__EntityType",
      ENTITY_TYPES,
    ],
    ["EntityStatus", ENTITY_STATUSES],
    ["FactPredicate", FACT_PREDICATES],
    ["FactStatus", FACT_STATUSES],
    ["SupportRole", SUPPORT_ROLES],
    ["CanonicalBlockKind", CANONICAL_BLOCK_KINDS],
    // EPIC 30.3
    ["Role", ROLES],
    ["UserStatus", USER_STATUSES],
    ["AuditAction", AUDIT_ACTIONS],
    ["AuditOutcome", AUDIT_OUTCOMES],
    ["SemanticStatementType", SEMANTIC_STATEMENT_TYPES],
    ["SemanticStatementStatus", SEMANTIC_STATEMENT_STATUSES],
    ["RelationType", GRAPH_RELATION_TYPES],
    // Milestone 30.1.3: the governed query vocabularies. A member here
    // that the backend does not declare is a filter the API refuses.
    ["ProjectSortField", PROJECT_SORT_FIELDS],
    ["DocumentSortField", DOCUMENT_SORT_FIELDS],
    ["SortDirection", SORT_DIRECTIONS],
  ];

  it.each(cases)("%s", (name, declared) => {
    expect([...declared].sort()).toEqual([...backendEnum(name)].sort());
  });

  it("EntityType (knowledge graph) includes busbar and line", () => {
    // Both were missing from the previous frontend enum, so a graph node
    // of either type rendered as an unknown value.
    const backend = backendEnum("EntityType-Input");

    expect([...GRAPH_ENTITY_TYPES].sort()).toEqual([...backend].sort());
    expect(GRAPH_ENTITY_TYPES).toContain("busbar");
    expect(GRAPH_ENTITY_TYPES).toContain("line");
  });

  it("DocumentFormat and DocumentCategory match the ORM vocabulary", () => {
    // These are not exported as named OpenAPI enums (the documents
    // endpoints declare no response model), so they are checked against
    // the values the schema does reference.
    expect(DOCUMENT_FORMATS).toContain("pdf");
    expect(DOCUMENT_FORMATS).toContain("dxf");
    expect(DOCUMENT_FORMATS).toContain("image");
    expect(DOCUMENT_CATEGORIES).toContain("functional_schematic");
  });
});

describe("every enum member is presentable", () => {
  it("labels every project status and lifecycle state", () => {
    for (const status of PROJECT_STATUSES) {
      expect(PROJECT_STATUS_LABELS[status]).toBeTruthy();
    }

    for (const state of PROJECT_LIFECYCLE_STATES) {
      expect(PROJECT_LIFECYCLE_LABELS[state]).toBeTruthy();
    }
  });

  it("labels every document format and category", () => {
    for (const format of DOCUMENT_FORMATS) {
      expect(DOCUMENT_FORMAT_LABELS[format]).toBeTruthy();
    }

    for (const category of DOCUMENT_CATEGORIES) {
      expect(DOCUMENT_CATEGORY_LABELS[category]).toBeTruthy();
    }
  });

  it("labels every evidence type", () => {
    for (const type of EVIDENCE_TYPES) {
      expect(EVIDENCE_TYPE_LABELS[type]).toBeTruthy();
    }
  });

  it("labels and describes every pipeline stage", () => {
    for (const stage of PIPELINE_STAGES) {
      expect(PIPELINE_STAGE_LABELS[stage]).toBeTruthy();
      expect(PIPELINE_STAGE_DESCRIPTIONS[stage]).toBeTruthy();
    }
  });
});

describe("the pagination contract matches the backend", () => {
  it.runIf(schema !== null)(
    "declares the same maximum page size the API enforces",
    () => {
      const parameter = schema!.paths["/documents/"].get.parameters.find(
        (candidate: { name: string }) => candidate.name === "page_size",
      );

      expect(parameter.schema.maximum).toBe(MAX_PAGE_SIZE);
      expect(parameter.schema.default).toBe(DEFAULT_PAGE_SIZE);
    },
  );

  it.runIf(schema !== null)(
    "sends every declared filter as a parameter the API accepts",
    () => {
      for (const [path, declared] of [
        [
          "/documents/",
          ["project_id", "scope", "file_format", "category", "search"],
        ],
        [
          "/projects/",
          ["status", "lifecycle_state", "search", "include_deleted"],
        ],
      ] as const) {
        const accepted = new Set(
          schema!.paths[path].get.parameters.map(
            (parameter: { name: string }) => parameter.name,
          ),
        );

        for (const name of declared) {
          expect(accepted.has(name), `${path} ${name}`).toBe(true);
        }
      }
    },
  );

  it.runIf(schema !== null)(
    "never declares a storage field in a document schema",
    () => {
      for (const name of [
        "DocumentSummaryRead",
        "DocumentDetailRead",
        "DocumentUploadResponse",
      ]) {
        const properties = Object.keys(
          schema!.components.schemas[name].properties ?? {},
        );

        for (const field of properties) {
          expect(field).not.toContain("path");
          expect(field).not.toContain("storage");
        }
      }
    },
  );
});

describe("the pipeline order matches the backend's ordering rule", () => {
  it("runs uploaded -> representation -> text -> evidence -> entities -> facts -> semantics", () => {
    // Each stage 404s until the one before it has produced artefacts;
    // this order is what the UI uses to decide what can run next.
    expect(PIPELINE_STAGES).toEqual([
      "uploaded",
      "canonical_representation",
      "canonical_text",
      "engineering_evidence",
      "engineering_entities",
      "engineering_facts",
      "engineering_semantics",
    ]);
  });

  it("declares exactly one semantic statement type", () => {
    // Milestone 30.1 ships `has_rated_power` and nothing else. A second
    // member here would mean the UI is offering meaning the backend
    // never assigns.
    expect(SEMANTIC_STATEMENT_TYPES).toEqual(["has_rated_power"]);
  });

  it("declares exactly one fact predicate", () => {
    expect(FACT_PREDICATES).toEqual(["has_associated_quantity"]);
  });
});
