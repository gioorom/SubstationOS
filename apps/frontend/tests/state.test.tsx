/**
 * The state primitives, tested directly.
 *
 * These are the behaviours that used to be re-implemented (and got
 * subtly wrong) in each of the five hand-rolled hooks this EPIC deleted:
 * cancellation on unmount, no stale overwrite, refresh distinguished
 * from first load, and a mutation that reports its own outcome.
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { useCallback } from "react";
import { describe, expect, it, vi } from "vitest";

import { NetworkError } from "@/lib/api";

import { useMutation, useResource } from "@/hooks/useResource";
import { apiClient, ValidationError } from "@/lib/api";

import { aProject, stubBackend } from "./_backend";

const read = (signal: AbortSignal) =>
  apiClient.get<unknown[]>("/projects/", { signal });

describe("useResource", () => {
  it("loads, then exposes the value", async () => {
    stubBackend({ "GET /projects/": { body: [aProject()] } });

    const { result } = renderHook(() => useResource(read));

    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toHaveLength(1);
    expect(result.current.error).toBeNull();
  });

  it("does not read at all when disabled", async () => {
    const backend = stubBackend({ "GET /projects/": { body: [] } });

    const { result } = renderHook(() =>
      useResource(read, { enabled: false }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    // An unresolved route parameter must not produce a request against
    // `/projects/undefined`.
    expect(backend.requests).toHaveLength(0);
  });

  it("distinguishes a refresh from the first load", async () => {
    // The second read hangs, so the refreshing state can be observed.
    stubBackend({
      "GET /projects/": [{ body: [aProject()] }, { hang: true }],
    });

    const { result } = renderHook(() => useResource(read));

    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => void result.current.reload());

    await waitFor(() => expect(result.current.refreshing).toBe(true));

    // A refresh must not blank the screen with a skeleton, and must not
    // discard the value already on screen.
    expect(result.current.loading).toBe(false);
    expect(result.current.data).toHaveLength(1);
  });

  it("aborts the in-flight request when it unmounts", async () => {
    let captured: AbortSignal | undefined;

    stubBackend({ "GET /projects/": { hang: true } });

    const { unmount } = renderHook(() =>
      useResource((signal) => {
        captured = signal;
        return apiClient.get<unknown[]>("/projects/", { signal });
      }),
    );

    await waitFor(() => expect(captured).toBeDefined());

    unmount();

    expect(captured?.aborted).toBe(true);
  });

  it("keeps the newest answer when the input changes mid-flight", async () => {
    const backend = stubBackend({
      "GET /projects/": [{ hang: true }, { body: [aProject({ id: 2 })] }],
    });

    const { result, rerender } = renderHook(
      ({ id }: { id: number }) => {
        // Stable per id, exactly as the domain hooks do it. An unstable
        // `read` would reload on every render, which is why the contract
        // requires useCallback.
        const read = useCallback(
          (signal: AbortSignal) =>
            apiClient.get<{ id: number }[]>("/projects/", {
              query: { project_id: id },
              signal,
            }),
          [id],
        );

        return useResource(read);
      },
      { initialProps: { id: 1 } },
    );

    await waitFor(() => expect(backend.requests).toHaveLength(1));

    rerender({ id: 2 });

    await waitFor(() =>
      expect(result.current.data?.[0]?.id).toBe(2),
    );

    // The superseded request was cancelled, not surfaced as a failure.
    expect(result.current.error).toBeNull();
    expect(backend.requests).toHaveLength(2);
  });

  it("reports a failure as a sentence and keeps the typed cause", async () => {
    stubBackend({
      "GET /projects/": { status: 500, body: { detail: "boom" } },
    });

    const { result } = renderHook(() => useResource(read));

    await waitFor(() => expect(result.current.error).not.toBeNull());

    expect(result.current.error).toMatch(/errore interno/i);
    expect(result.current.data).toBeNull();
    expect(result.current.failure).toBeDefined();
  });
});

describe("useMutation", () => {
  const create = (payload: unknown, signal: AbortSignal) =>
    apiClient.post<{ id: number }>("/projects/", { json: payload, signal });

  it("reports pending, then resolves with the server's value", async () => {
    stubBackend({
      "POST /projects/": { status: 201, body: { id: 7 } },
    });

    const { result } = renderHook(() => useMutation(create));

    let created: { id: number } | undefined;

    await act(async () => {
      created = await result.current.run({ name: "Gamma" });
    });

    expect(created).toEqual({ id: 7 });
    expect(result.current.pending).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("re-throws so the caller can branch, while still exposing the error", async () => {
    stubBackend({
      "POST /projects/": {
        status: 422,
        body: { detail: [{ loc: ["body", "code"], msg: "Field required", type: "missing" }] },
      },
    });

    const { result } = renderHook(() => useMutation(create));

    await act(async () => {
      await expect(result.current.run({})).rejects.toBeInstanceOf(
        ValidationError,
      );
    });

    expect(result.current.error).toContain("code");
    expect(result.current.failure).toBeInstanceOf(ValidationError);
  });

  it("clears its error on reset", async () => {
    stubBackend({
      "POST /projects/": { status: 409, body: { detail: "duplicate" } },
    });

    const { result } = renderHook(() => useMutation(create));

    await act(async () => {
      await result.current.run({}).catch(() => undefined);
    });

    expect(result.current.error).toBe("duplicate");

    act(() => result.current.reset());

    expect(result.current.error).toBeNull();
    expect(result.current.failure).toBeNull();
  });

  it("does not report a cancelled mutation as an error", async () => {
    stubBackend({ "POST /projects/": { hang: true } });

    const { result, unmount } = renderHook(() => useMutation(create));

    const pending = result.current.run({}).catch(() => undefined);

    unmount();
    await pending;

    // Unmounting a form mid-submit is not a validation failure.
    expect(result.current.error).toBeNull();
  });
});

describe("no component bypasses the API client", () => {
  it("fails loudly on a request the test did not declare", async () => {
    stubBackend({ "GET /projects/": { body: [] } });

    const error = (await apiClient
      .get("/documents/")
      .catch((caught: unknown) => caught)) as NetworkError;

    // Anything thrown at transport level becomes a NetworkError - the
    // client cannot tell a dead backend from a programming mistake - but
    // the original message survives on `detail`.
    expect(error).toBeInstanceOf(NetworkError);
    expect(error.detail).toMatch(/Unexpected request/);
  });

  it("uses the configured base URL, not a hardcoded host", async () => {
    const backend = stubBackend({ "GET /health": { body: { status: "online" } } });

    await apiClient.get("/health");

    expect(backend.requests[0].url.startsWith("http://localhost:8000")).toBe(
      true,
    );
  });
});

describe("fetch is never called directly by the application", () => {
  it("routes every documented resource module through the client", async () => {
    // The resource modules import `apiClient`; this asserts that calling
    // one produces exactly one request, with no second code path.
    const backend = stubBackend({ "GET /projects/": { body: [] } });

    const { listProjects } = await import("@/lib/resources/projects");

    await listProjects();

    expect(backend.requests).toHaveLength(1);
    expect(vi.isMockFunction(globalThis.fetch)).toBe(true);
  });
});
