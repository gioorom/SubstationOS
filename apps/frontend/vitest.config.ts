import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

/**
 * `@vitejs/plugin-react` is deliberately absent: its Fast Refresh
 * transform is a dev-server concern, and its current peer range
 * conflicts with this project's toolchain. Vitest's own esbuild pass
 * handles TSX with the automatic JSX runtime, which is all the tests
 * need.
 */
export default defineConfig({
  esbuild: {
    jsx: "automatic",
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
  },
});
