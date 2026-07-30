import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

/**
 * No test is allowed a real network call. `fetch` is replaced for every
 * test, so a component that reaches the backend by some route other than
 * the API client fails loudly rather than silently hitting nothing.
 */
beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => {
      throw new Error(
        "Unexpected fetch: the test did not declare this request.",
      );
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
