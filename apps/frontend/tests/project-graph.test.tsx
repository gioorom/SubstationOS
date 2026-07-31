/**
 * The project Knowledge Graph page, after EPIC 31.1.
 *
 * This route used to read `/projects/{id}/knowledge-graph` - the legacy
 * endpoint serving LLM-extracted entities written straight from upload
 * with no review gate. That endpoint is gone. The route survives because
 * engineers have it bookmarked; what it shows does not.
 *
 * The behaviours asserted here are the ones that would undo the
 * consolidation: reaching for the retired API, showing knowledge without
 * provenance, or presenting an empty graph as a failure.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ProjectKnowledgeGraphPage from "@/app/projects/[projectId]/knowledge-graph/page";

import {
  aGraphEdge,
  aGraphNode,
  aGraphNodeList,
  stubBackend,
  type Routes,
} from "./_backend";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => ({ projectId: "1" }),
  usePathname: () => "/projects/1/knowledge-graph",
  useSearchParams: () => new URLSearchParams(),
}));

const NODES = "GET /knowledge-graph/nodes";

const ASSET = aGraphNode();

const QUANTITY = aGraphNode({
  node_id: "b".repeat(64),
  kind: "engineering_quantity",
  label: "630 kVA",
  normalized_value: "630",
  unit: "kVA",
});

function page(overrides: Routes = {}) {
  const backend = stubBackend({
    [NODES]: { body: aGraphNodeList([ASSET, QUANTITY]) },
    ...overrides,
  });

  render(<ProjectKnowledgeGraphPage />);

  return backend;
}

// --- It reads the governed graph, and only the governed graph ----------

describe("the page's data source", () => {
  it("reads the governed graph scoped to the project", async () => {
    const backend = page();

    await screen.findByText("TR1");

    const request = backend.requestsFor("GET", "/knowledge-graph/nodes")[0];

    expect(request.url).toContain("project_id=1");
  });

  it("never calls the retired legacy endpoint", async () => {
    /**
     * The endpoint no longer exists. A request to it would 404 in
     * production and pass unnoticed in a stub that answered everything -
     * so the assertion is on what was actually requested.
     */
    const backend = page();

    await screen.findByText("TR1");

    for (const request of backend.requests) {
      expect(request.url).not.toContain("/projects/1/knowledge-graph");
      expect(request.url).not.toContain("/entities");
    }
  });
});

// --- What it shows -----------------------------------------------------

describe("governed knowledge", () => {
  it("lists governed concepts with who approved them", async () => {
    page();

    const list = await screen.findByRole("list", {
      name: "Nodi del grafo",
    });

    const rows = within(list).getAllByRole("button");

    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("TR1")).toBeInTheDocument();
    expect(
      within(rows[0]).getByText(/Approvato da Ada Lovelace/),
    ).toBeInTheDocument();
  });

  it("says the graph is a projection that can be rebuilt", async () => {
    page();

    expect(
      await screen.findByText(/può sempre essere ricostruita/),
    ).toBeInTheDocument();
  });

  it("says only approved, current statements are in it", async () => {
    page();

    expect(
      await screen.findByText(
        /approvate da un ingegnere e ancora attuali/,
      ),
    ).toBeInTheDocument();
  });

  it("treats an empty graph as a state, not a failure", async () => {
    /**
     * An empty graph is the normal state of a project nobody has
     * reviewed yet. Rendering it as an error would misdescribe the
     * difference between what the pipeline interpreted and what somebody
     * sustained.
     */
    page({ [NODES]: { body: aGraphNodeList([]) } });

    expect(
      await screen.findByText(/Nessuna conoscenza governata/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("reports a failed read as a failure", async () => {
    page({ [NODES]: { status: 500, body: { detail: "boom" } } });

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});

// --- Navigating to a node's relationships ------------------------------

describe("navigation", () => {
  const DETAIL = `GET /knowledge-graph/nodes/${ASSET.node_id}`;

  function withDetail(overrides: Routes = {}) {
    return page({
      [DETAIL]: {
        body: {
          node: ASSET,
          relationships: [
            {
              edge: aGraphEdge(),
              direction: "outgoing",
              other_node: QUANTITY,
            },
          ],
        },
      },
      ...overrides,
    });
  }

  it("shows a node's governed relationships when it is selected", async () => {
    withDetail();

    await userEvent.click(await screen.findByText("TR1"));

    const relationships = await screen.findByRole("list", {
      name: "Relazioni governate",
    });

    expect(
      within(relationships).getByText("ha potenza nominale"),
    ).toBeInTheDocument();
    expect(
      within(relationships).getByText("630 kVA"),
    ).toBeInTheDocument();
  });

  it("shows the provenance of every relationship, not behind a click", async () => {
    /**
     * A governed graph whose value is that every answer is explainable
     * should not make the explanation optional.
     */
    withDetail();

    await userEvent.click(await screen.findByText("TR1"));

    expect(
      await screen.findByText(/Approvata da Ada Lovelace · revisione 1/),
    ).toBeInTheDocument();
    // Twice: once on the node row, once beside the relationship. Both
    // are provenance, and both belong where they are.
    expect(
      screen.getAllByText(/rated_power_from_associated_power_quantity@1\.0/),
    ).not.toHaveLength(0);
  });

  it("links a relationship back to the statement it came from", async () => {
    withDetail();

    await userEvent.click(await screen.findByText("TR1"));

    const link = await screen.findByRole("link", {
      name: /Apri l'affermazione nel Workspace/,
    });

    expect(link).toHaveAttribute(
      "href",
      "/documents/10/workspace?kind=semantic&key=statement-tr1-power",
    );
  });

  it("keeps the list usable when the detail read fails", async () => {
    withDetail({
      [DETAIL]: { status: 500, body: { detail: "boom" } },
    });

    await userEvent.click(await screen.findByText("TR1"));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("list", { name: "Nodi del grafo" }),
      ).toBeInTheDocument(),
    );
  });
});

// --- Filtering ---------------------------------------------------------

describe("filtering", () => {
  it("asks the backend to filter by kind rather than filtering locally", async () => {
    const backend = page();

    await screen.findByText("TR1");

    await userEvent.selectOptions(
      screen.getByLabelText("Tipo"),
      "engineering_asset",
    );

    await waitFor(() =>
      expect(
        backend
          .requestsFor("GET", "/knowledge-graph/nodes")
          .some((request) =>
            request.url.includes("kind=engineering_asset"),
          ),
      ).toBe(true),
    );
  });
});
