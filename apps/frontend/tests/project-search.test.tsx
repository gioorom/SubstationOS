/**
 * Searching a project's documents, from the engineer's side.
 *
 * What these tests hold the interface to is the part an engineer would
 * notice if it were wrong: the designation they typed is the one shown
 * back to them, the position of a hit is either stated or declared
 * unknown, and an empty result says so instead of looking like a page
 * that has not finished loading.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ProjectSearchPanel, {
  describeLocation,
} from "@/components/projects/ProjectSearchPanel";
import type {
  ProjectSearchResponse,
  SearchDocumentResult,
  SearchLocation,
} from "@/lib/contracts";

function aLocation(
  overrides: Partial<SearchLocation> = {},
): SearchLocation {
  return {
    determined: true,
    page_number: null,
    worksheet_name: null,
    row_number: null,
    cell_reference: null,
    ...overrides,
  };
}

function aDiagramResult(): SearchDocumentResult {
  return {
    document_id: 7,
    filename: "schema_unifilare.pdf",
    source_type: "pdf",
    content_checksum: "a".repeat(64),
    matches: [
      {
        location: aLocation({ page_number: 3 }),
        snippet: {
          text: "Sezionatore -Q1 lato alta tensione",
          highlights: [{ start: 12, end: 15 }],
          truncated_before: false,
          truncated_after: false,
        },
      },
    ],
  };
}

function aScheduleResult(): SearchDocumentResult {
  return {
    document_id: 9,
    filename: "elenco_cavi.xlsx",
    source_type: "spreadsheet",
    content_checksum: "b".repeat(64),
    matches: [
      {
        location: aLocation({
          worksheet_name: "Cavi",
          row_number: 3,
          cell_reference: "C3",
        }),
        snippet: {
          text: "-W2 | TR2 | -Q1 | 150 | 185",
          highlights: [{ start: 12, end: 15 }],
          truncated_before: false,
          truncated_after: false,
        },
      },
    ],
  };
}

function aResponse(
  overrides: Partial<ProjectSearchResponse> = {},
): ProjectSearchResponse {
  return {
    project_id: 1,
    query: "-Q1",
    terms: ["-q1"],
    total_matches: 2,
    total_documents: 2,
    documents: [aDiagramResult(), aScheduleResult()],
    suggestions: [],
    ...overrides,
  };
}

function renderPanel(
  results: ProjectSearchResponse,
  overrides: {
    submitted?: string;
    searching?: boolean;
    error?: string | null;
  } = {},
) {
  return render(
    <ProjectSearchPanel
      query={results.query}
      onQueryChange={vi.fn()}
      results={results}
      submitted={overrides.submitted ?? results.query}
      searching={overrides.searching ?? false}
      error={overrides.error ?? null}
    />,
  );
}

describe("what a result shows", () => {
  it("groups matches under the document they came from", () => {
    renderPanel(aResponse());

    expect(screen.getByText("schema_unifilare.pdf")).toBeInTheDocument();
    expect(screen.getByText("elenco_cavi.xlsx")).toBeInTheDocument();
  });

  it("says how many matches in how many documents", () => {
    renderPanel(aResponse());

    const summary = screen.getByRole("status");

    expect(summary).toHaveTextContent("2");
    expect(summary).toHaveTextContent(/document/i);
  });

  it("shows what was actually searched for after folding", () => {
    renderPanel(aResponse({ query: "TR1 KV", terms: ["tr1", "kv"] }));

    expect(screen.getByRole("status")).toHaveTextContent("tr1 kv");
  });

  it("names the page a PDF match is on", () => {
    renderPanel(aResponse());

    expect(screen.getByText("Pagina 3")).toBeInTheDocument();
  });

  it("names the sheet and cell a spreadsheet match is in", () => {
    renderPanel(aResponse());

    expect(
      screen.getByText(/Foglio "Cavi".*cella C3/),
    ).toBeInTheDocument();
  });

  it("links each result to its document", () => {
    renderPanel(aResponse());

    expect(
      screen.getByRole("link", { name: "schema_unifilare.pdf" }),
    ).toHaveAttribute("href", "/documents/7");
  });
});

describe("the highlighted text", () => {
  /** The emphasised runs, and only those - not the help text's `code`. */
  function highlights(container: HTMLElement): string[] {
    return [...container.querySelectorAll("mark")].map(
      (mark) => mark.textContent ?? "",
    );
  }

  it("emphasises exactly the designation that was searched", () => {
    const { container } = renderPanel(aResponse());

    expect(highlights(container)).toEqual(["-Q1", "-Q1"]);
  });

  it("keeps the aspect prefix inside the emphasis", () => {
    /**
     * Highlighting `Q1` while the document says `-Q1` would show the
     * engineer a designation the document does not contain.
     */

    const { container } = renderPanel(aResponse());

    for (const emphasised of highlights(container)) {
      expect(emphasised.startsWith("-")).toBe(true);
      expect(emphasised).not.toBe("Q1");
    }
  });

  it("shows the source text around the match", () => {
    renderPanel(aResponse());

    expect(
      screen.getByText(/lato alta tensione/),
    ).toBeInTheDocument();
  });

  it("marks a snippet that was cut", () => {
    const response = aResponse();
    response.documents = [
      {
        ...aDiagramResult(),
        matches: [
          {
            location: aLocation({ page_number: 1 }),
            snippet: {
              text: "…contenuto centrale con -Q1 dentro…",
              highlights: [{ start: 24, end: 27 }],
              truncated_before: true,
              truncated_after: true,
            },
          },
        ],
      },
    ];

    renderPanel(response);

    expect(screen.getByText(/…/)).toBeInTheDocument();
  });
});

describe("a position that is not known", () => {
  it("is stated in words rather than left blank", () => {
    const response = aResponse({ total_matches: 1, total_documents: 1 });
    response.documents = [
      {
        ...aDiagramResult(),
        matches: [
          {
            location: aLocation({ determined: false }),
            snippet: {
              text: "Sezionatore -Q1",
              highlights: [{ start: 12, end: 15 }],
              truncated_before: false,
              truncated_after: false,
            },
          },
        ],
      },
    ];

    renderPanel(response);

    expect(
      screen.getByText(/Posizione nel documento non disponibile/),
    ).toBeInTheDocument();
  });

  it("never invents a page number", () => {
    expect(describeLocation(aLocation({ determined: false }))).not.toMatch(
      /\d/,
    );
  });

  it("falls back to the row when the cell is unknown", () => {
    expect(
      describeLocation(
        aLocation({ worksheet_name: "Cavi", row_number: 12 }),
      ),
    ).toMatch(/riga 12/);
  });

  it("reports an unknown position for a location with no coordinates", () => {
    expect(describeLocation(aLocation())).toMatch(
      /non disponibile/,
    );
  });
});

describe("when nothing matches", () => {
  it("says so plainly", () => {
    renderPanel(
      aResponse({
        query: "TR9",
        terms: ["tr9"],
        total_matches: 0,
        total_documents: 0,
        documents: [],
      }),
    );

    expect(screen.getByText(/Nessun risultato/)).toBeInTheDocument();
  });

  it("offers a designation the project does contain without applying it", () => {
    renderPanel(
      aResponse({
        query: "Q1",
        terms: ["q1"],
        total_matches: 0,
        total_documents: 0,
        documents: [],
        suggestions: [{ term: "q1", present_variants: ["-q1"] }],
      }),
    );

    const notice = screen.getByText(/Il progetto contiene/);

    expect(within(notice).getByText("-q1")).toBeInTheDocument();
    expect(notice).toHaveTextContent(/sigla diversa/);
  });

  it("offers nothing when the project has no near miss", () => {
    renderPanel(
      aResponse({
        query: "TR9",
        terms: ["tr9"],
        total_matches: 0,
        total_documents: 0,
        documents: [],
        suggestions: [{ term: "tr9", present_variants: [] }],
      }),
    );

    expect(
      screen.queryByText(/Il progetto contiene/),
    ).not.toBeInTheDocument();
  });

  it("says nothing at all before a search has been made", () => {
    renderPanel(
      aResponse({
        query: "",
        terms: [],
        total_matches: 0,
        total_documents: 0,
        documents: [],
      }),
      { submitted: "" },
    );

    expect(screen.queryByText(/Nessun risultato/)).not.toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

describe("the search box", () => {
  it("reports what the engineer types", async () => {
    const onQueryChange = vi.fn();
    const user = userEvent.setup();

    render(
      <ProjectSearchPanel
        query=""
        onQueryChange={onQueryChange}
        results={aResponse({
          total_matches: 0,
          total_documents: 0,
          documents: [],
        })}
        submitted=""
        searching={false}
        error={null}
      />,
    );

    await user.type(screen.getByRole("searchbox"), "-Q1");

    await waitFor(() => expect(onQueryChange).toHaveBeenCalled());
  });

  it("explains that an aspect prefix matters", () => {
    renderPanel(aResponse());

    expect(screen.getByText(/sigle diverse/)).toBeInTheDocument();
  });

  it("reports a failure instead of pretending there were no results", () => {
    renderPanel(
      aResponse({
        total_matches: 0,
        total_documents: 0,
        documents: [],
      }),
      { error: "Il backend SubstationOS non risponde." },
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Il backend SubstationOS non risponde.",
    );
    expect(screen.queryByText(/Nessun risultato/)).not.toBeInTheDocument();
  });
});
