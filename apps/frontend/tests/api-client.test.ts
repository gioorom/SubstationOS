/**
 * The API client's contract with the rest of the application.
 *
 * Each status code the backend actually returns is asserted here once,
 * so no screen has to rediscover what a 404 from a pipeline stage means.
 */

import { describe, expect, it, vi } from "vitest";

import {
  ConflictError,
  NetworkError,
  NotFoundError,
  RequestCancelledError,
  ServerError,
  TimeoutError,
  ValidationError,
  apiClient,
  describeError,
  fieldMessages,
} from "@/lib/api";

import { stubBackend } from "./_backend";

describe("request construction", () => {
  it("prefixes the configured backend base URL", async () => {
    const backend = stubBackend({ "GET /projects/": { body: [] } });

    await apiClient.get("/projects/");

    expect(backend.requests[0].url).toBe(
      "http://127.0.0.1:8000/projects/",
    );
  });

  it("omits undefined and empty query parameters", async () => {
    const backend = stubBackend({ "GET /documents/": { body: [] } });

    await apiClient.get("/documents/", {
      query: { project_id: 7, search: undefined, category: "" },
    });

    expect(backend.requests[0].url).toBe(
      "http://127.0.0.1:8000/documents/?project_id=7",
    );
  });

  it("sends JSON bodies with the JSON content type", async () => {
    const backend = stubBackend({
      "POST /projects/": { status: 201, body: { id: 1 } },
    });

    await apiClient.post("/projects/", { json: { name: "Gamma" } });

    expect(backend.requests[0].body).toEqual({ name: "Gamma" });
  });

  it("leaves FormData alone so the browser sets the boundary", async () => {
    const backend = stubBackend({
      "POST /documents/upload": { body: { id: 1 } },
    });

    const form = new FormData();
    form.append("project_id", "1");

    await apiClient.post("/documents/upload", { body: form });

    expect(backend.requests[0].body).toEqual({ project_id: "1" });
  });
});

describe("failure translation", () => {
  it("turns a Pydantic 422 into field-level violations", async () => {
    stubBackend({
      "POST /projects/": {
        status: 422,
        body: {
          detail: [
            {
              loc: ["body", "customer"],
              msg: "String should have at least 2 characters",
              type: "string_too_short",
            },
          ],
        },
      },
    });

    const failure = await apiClient
      .post("/projects/", { json: {} })
      .catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ValidationError);

    const error = failure as ValidationError;

    // `body` is stripped: the form binds on the field name.
    expect(error.forField("customer")).toBe(
      "String should have at least 2 characters",
    );

    expect(fieldMessages(error)).toEqual({
      customer: "Deve contenere almeno 2 caratteri.",
    });
  });

  it("keeps a domain 422 that arrives as a plain string", async () => {
    stubBackend({
      "POST /documents/upload": {
        status: 422,
        body: { detail: "A project_id is required for scope 'project'" },
      },
    });

    const error = (await apiClient
      .post("/documents/upload", { body: new FormData() })
      .catch((caught: unknown) => caught)) as ValidationError;

    expect(error).toBeInstanceOf(ValidationError);
    expect(error.violations).toHaveLength(0);
    expect(describeError(error)).toBe(
      "A project_id is required for scope 'project'",
    );
  });

  it("maps 404 to NotFoundError", async () => {
    stubBackend({
      "GET /projects/9": { status: 404, body: { detail: "Project not found" } },
    });

    const error = await apiClient
      .get("/projects/9")
      .catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(NotFoundError);
  });

  it("maps 409 to ConflictError and shows the backend's reason", async () => {
    stubBackend({
      "POST /projects/": {
        status: 409,
        body: { detail: "Project code 'CP-1' already exists" },
      },
    });

    const error = await apiClient
      .post("/projects/", { json: {} })
      .catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ConflictError);
    expect(describeError(error)).toBe(
      "Project code 'CP-1' already exists",
    );
  });

  it("maps 500 to ServerError without leaking the backend's message", async () => {
    stubBackend({
      "GET /projects/": {
        status: 500,
        body: { detail: "sqlalchemy.exc.OperationalError: no such table" },
      },
    });

    const error = await apiClient
      .get("/projects/")
      .catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ServerError);
    expect((error as ServerError).status).toBe(500);

    // A stack-trace-shaped detail is not shown to an engineer.
    expect(describeError(error)).not.toContain("sqlalchemy");
  });

  it("maps a transport fault to NetworkError", async () => {
    stubBackend({ "GET /health": { networkFailure: true } });

    const error = await apiClient
      .get("/health")
      .catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(NetworkError);
    expect(describeError(error)).toContain("Impossibile contattare");
  });

  it("survives an error response with no JSON body", async () => {
    stubBackend({ "GET /projects/": { status: 502 } });

    const error = await apiClient
      .get("/projects/")
      .catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ServerError);
  });
});

describe("cancellation and timeouts", () => {
  it("reports a caller abort as a cancellation, not a failure", async () => {
    stubBackend({ "GET /projects/": { hang: true } });

    const controller = new AbortController();
    const pending = apiClient.get("/projects/", {
      signal: controller.signal,
    });

    controller.abort();

    const error = await pending.catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(RequestCancelledError);

    // A cancelled request has nothing to say to the user.
    expect(describeError(error)).toBeNull();
  });

  it("reports its own timeout as a timeout", async () => {
    vi.useFakeTimers();
    stubBackend({ "GET /projects/": { hang: true } });

    const pending = apiClient
      .get("/projects/", { timeoutMs: 50 })
      .catch((caught: unknown) => caught);

    await vi.advanceTimersByTimeAsync(60);

    expect(await pending).toBeInstanceOf(TimeoutError);

    vi.useRealTimers();
  });
});

describe("retry policy", () => {
  it("replays a GET after a transport fault", async () => {
    const backend = stubBackend({
      "GET /projects/": [{ networkFailure: true }, { body: [] }],
    });

    await expect(apiClient.get("/projects/", { retries: 1 })).resolves.toEqual(
      [],
    );

    expect(backend.requestsFor("GET", "/projects/")).toHaveLength(2);
  });

  it("never replays a POST", async () => {
    const backend = stubBackend({
      "POST /projects/": { networkFailure: true },
    });

    await apiClient
      .post("/projects/", { json: {}, retries: 3 })
      .catch(() => undefined);

    // Replaying a create that may have been received would produce a
    // second project.
    expect(backend.requestsFor("POST", "/projects/")).toHaveLength(1);
  });

  it("does not replay a 500 - the backend answered", async () => {
    const backend = stubBackend({
      "GET /projects/": { status: 500, body: { detail: "boom" } },
    });

    await apiClient
      .get("/projects/", { retries: 2 })
      .catch(() => undefined);

    expect(backend.requestsFor("GET", "/projects/")).toHaveLength(1);
  });
});
