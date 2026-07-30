/**
 * Architecture tests for the Engineering Workspace.
 *
 * Every assertion here is structural - on the source text of the files
 * that make up the Workspace, never on prose. A comment promising that
 * the frontend infers no engineering knowledge is worth nothing; a test
 * that reads the files and fails when a fuzzy match appears is worth
 * something, and will still be worth something in three years when
 * nobody remembers why the rule existed.
 *
 * The scope is stated explicitly and narrowly: the Workspace route, its
 * components, its read model and its hooks. It does not speak for the
 * rest of the application.
 */

import { readdirSync, readFileSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = resolve(__dirname, "..");

const WORKSPACE_COMPONENTS = join(ROOT, "components", "workspace");
const WORKSPACE_MODEL = join(ROOT, "lib", "workspace");
const WORKSPACE_ROUTE = join(
  ROOT,
  "app",
  "documents",
  "[documentId]",
  "workspace",
  "page.tsx",
);
const WORKSPACE_HOOKS = [
  join(ROOT, "hooks", "useWorkspace.ts"),
  join(ROOT, "hooks", "useWorkspaceSelection.ts"),
  join(ROOT, "hooks", "useCanonicalPage.ts"),
];

function filesIn(directory: string): string[] {
  return readdirSync(directory)
    .filter((name) => name.endsWith(".ts") || name.endsWith(".tsx"))
    .map((name) => join(directory, name));
}

/** Every file the Workspace is made of. */
const WORKSPACE_FILES = [
  ...filesIn(WORKSPACE_COMPONENTS),
  ...filesIn(WORKSPACE_MODEL),
  ...WORKSPACE_HOOKS,
  WORKSPACE_ROUTE,
];

function read(path: string): string {
  return readFileSync(path, "utf-8");
}

/** Source with comments stripped - a rule may be *named* in a comment. */
function code(path: string): string {
  return read(path)
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

describe("the workspace source tree", () => {
  it("exists and is not empty", () => {
    expect(existsSync(WORKSPACE_ROUTE)).toBe(true);
    expect(WORKSPACE_FILES.length).toBeGreaterThan(10);
  });
});

// --- The dependency direction --------------------------------------------

describe("what the workspace may import", () => {
  it("never reaches into the backend", () => {
    for (const path of WORKSPACE_FILES) {
      const source = code(path);

      expect(source, path).not.toMatch(/from ["'].*apps\/backend/);
      expect(source, path).not.toMatch(/from ["'].*\bapp\/(domain|services|routers|models|infrastructure)\b/);
    }
  });

  it("calls the backend only through the one API client", () => {
    for (const path of WORKSPACE_FILES) {
      const source = code(path);

      // `fetch`, `XMLHttpRequest` and `axios` are all ways of getting a
      // second, ungoverned HTTP path into the application.
      expect(source, path).not.toMatch(/\bfetch\s*\(/);
      expect(source, path).not.toMatch(/XMLHttpRequest/);
      expect(source, path).not.toMatch(/from ["']axios["']/);
    }
  });

  it("composes no API path of its own", () => {
    /**
     * `lib/resources` owns every backend path. A `href` to another page
     * is navigation and is fine; an endpoint spelled out in a component
     * is a second, ungoverned route to the API.
     */
    for (const path of WORKSPACE_FILES) {
      const source = code(path);

      expect(source, path).not.toMatch(/https?:\/\//);
      expect(source, path).not.toContain("canonical-representation");
      expect(source, path).not.toContain("engineering-evidence");
      expect(source, path).not.toContain("engineering-entities");
      expect(source, path).not.toContain("engineering-facts");
      expect(source, path).not.toContain("engineering-semantics");
      expect(source, path).not.toMatch(/\/documents\/\$\{\w+\}\/content/);
    }
  });

  it("imports no fuzzy-matching or similarity library", () => {
    const forbidden = [
      "fuse.js",
      "fuzzysort",
      "levenshtein",
      "string-similarity",
      "match-sorter",
      "didyoumean",
    ];

    for (const path of WORKSPACE_FILES) {
      const source = read(path).toLowerCase();

      for (const library of forbidden) {
        expect(source, `${path} imports ${library}`).not.toContain(
          `"${library}`,
        );
      }
    }
  });
});

// --- No storage reference ever reaches the viewer ------------------------

describe("the viewer's inputs", () => {
  it("never consumes a file path or a storage reference", () => {
    for (const path of WORKSPACE_FILES) {
      const source = code(path);

      expect(source, path).not.toContain("file_path");
      expect(source, path).not.toContain("storage_reference");
      expect(source, path).not.toContain("content_storage_reference");
    }
  });

  it("addresses document content by document identity alone", () => {
    const viewer = code(join(WORKSPACE_COMPONENTS, "SourceViewer.tsx"));

    // The one governed way to reach the bytes.
    expect(viewer).toContain("documentContentUrl");
    expect(viewer).toMatch(/documentContentUrl\(document\.id\)/);
  });
});

// --- No engineering rule lives in the frontend ---------------------------

describe("engineering knowledge stays in the backend", () => {
  it("declares no rule, policy or version of its own", () => {
    for (const path of WORKSPACE_FILES) {
      const source = code(path);

      // Every rule identifier and version on screen is read from an
      // artefact. None is written here.
      expect(source, path).not.toMatch(/rule_id\s*[:=]\s*["'`]/);
      expect(source, path).not.toMatch(/rule_version\s*[:=]\s*["'`]/);
      expect(source, path).not.toMatch(/policy_version\s*[:=]\s*["'`]/);
    }
  });

  it("performs no arithmetic on an engineering quantity", () => {
    for (const path of WORKSPACE_FILES) {
      const source = code(path);

      // `Decimal` arrives as a string precisely so it cannot acquire a
      // rounding error here. Parsing one would undo that.
      expect(source, path).not.toMatch(/parseFloat\s*\(/);
      expect(source, path).not.toMatch(/Number\s*\(\s*\w*[Qq]uantity/);
      expect(source, path).not.toMatch(/\.value\s*[*/+-]/);
    }
  });

  it("keeps the canonical predicate visible wherever it is described", () => {
    /**
     * A friendly description may accompany a predicate; it may never
     * replace it. Both files that describe one also render it.
     */
    for (const name of ["FactExplorer.tsx", "InspectorPanel.tsx"]) {
      const source = code(join(WORKSPACE_COMPONENTS, name));

      expect(source, name).toContain("fact.predicate");
    }
  });

  it("describes an association as structural, never as a rated value", () => {
    const presentation = read(join(WORKSPACE_MODEL, "presentation.ts"));

    expect(presentation).toContain("has_associated_quantity");
    expect(presentation).toMatch(/Associazione strutturale/);
    // The description does not merely omit a rated meaning - it denies
    // one, because an engineer reading `TR1 / 630 kVA` will supply the
    // conclusion themselves unless told the rules did not.
    expect(presentation).toMatch(/Non dice che la grandezza sia/);
  });
});

// --- Relationships are explicit ------------------------------------------

describe("how the workspace decides two artefacts are related", () => {
  const model = code(join(WORKSPACE_MODEL, "model.ts"));

  it("builds every index from a declared key", () => {
    for (const reference of [
      "reference.evidence_key",
      "fact.subject_entity_key",
      "fact.object_entity_key",
      "support.evidence_key",
      "statement.supporting_fact_keys",
    ]) {
      expect(model, reference).toContain(reference);
    }
  });

  it("never joins on observed text or on a value", () => {
    for (const path of WORKSPACE_FILES) {
      const source = code(path);

      // Comparing two artefacts' text or quantities would be the
      // frontend deciding they are the same thing.
      expect(source, path).not.toMatch(/observed_text\s*===/);
      expect(source, path).not.toMatch(/===\s*\w+\.observed_text/);
      expect(source, path).not.toMatch(/\.normalized\s*===/);
      expect(source, path).not.toMatch(/quantity\.value\s*===/);
      expect(source, path).not.toMatch(/\.toLowerCase\(\)\s*===/);
    }
  });

  it("keeps its only text search inside one explorer's filter", () => {
    /**
     * `includes` over text is legitimate for one thing - filtering the
     * rows already on screen - and illegitimate for everything else.
     * Confining it to the evidence explorer is what keeps that true.
     */
    const searching = WORKSPACE_FILES.filter((path) =>
      /toLowerCase\(\)\.includes|includes\(needle\)/.test(code(path)),
    ).map((path) => path.split(/[\\/]/).pop());

    expect(searching).toEqual(["EvidenceExplorer.tsx"]);
  });
});

// --- Coordinates are transcribed, never computed -------------------------

describe("source coordinates", () => {
  const sourceLocation = code(join(WORKSPACE_MODEL, "source-location.ts"));

  it("resolves a rectangle by span identity, not by geometry", () => {
    expect(sourceLocation).toContain("span_reading_order");
    expect(sourceLocation).toContain("block_reading_order");

    // No box is ever assembled from parts here; it is taken whole.
    expect(sourceLocation).toContain("span.bounding_box");
    expect(sourceLocation).not.toMatch(/x0:\s*[\d(]/);
  });

  it("declares no bounding box on the location contract itself", () => {
    /**
     * Evidence carries no geometry. A `bounding_box` field on
     * `SourceLocation` would be a field with nothing true to put in it,
     * and something plausible would eventually be put there.
     */
    expect(sourceLocation).not.toMatch(
      /^\s*bounding_box[?]?:/m,
    );
  });
});

// --- The human validation boundary ---------------------------------------

describe("inspection only", () => {
  it("performs no write of any kind", () => {
    for (const path of WORKSPACE_FILES) {
      const source = code(path);

      expect(source, path).not.toMatch(/apiClient\.(post|patch|put|delete)/);
      expect(source, path).not.toMatch(/useMutation/);
    }
  });

  it("offers no control that would imply a judgement", () => {
    const forbidden = [
      /\bapprova\b/i,
      /\brifiuta\b/i,
      /\bvalida\b/i,
      /\bcorreggi\b/i,
      /onApprove/,
      /onReject/,
      /onMerge/,
    ];

    for (const path of WORKSPACE_FILES) {
      const source = code(path);

      for (const pattern of forbidden) {
        expect(source, `${path} matches ${pattern}`).not.toMatch(pattern);
      }
    }
  });

  it("says in the model itself that interpreted is not approved", () => {
    const presentation = read(join(WORKSPACE_MODEL, "presentation.ts"));

    expect(presentation).toMatch(/Non significa approvato/);
  });
});

// --- The selection vocabulary is closed ----------------------------------

describe("selection", () => {
  it("validates the kind against a closed list before using it", () => {
    const selection = code(join(WORKSPACE_MODEL, "selection.ts"));

    expect(selection).toContain("SELECTION_KINDS");
    expect(selection).toMatch(/isSelectionKind/);
    expect(selection).toMatch(/if \(!isSelectionKind\(kind\)/);
  });

  it("never sends a selection key to the backend", () => {
    for (const path of WORKSPACE_FILES) {
      const source = code(path);

      expect(source, path).not.toMatch(/apiClient\.\w+\([^)]*selection/);
    }
  });
});
