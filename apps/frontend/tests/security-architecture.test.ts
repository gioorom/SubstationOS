/**
 * Structural security properties of the frontend.
 *
 * Every assertion here reads the source. A comment promising that the
 * session token is never stored in `localStorage` is worth nothing; a
 * test that fails when somebody writes one is worth something, and will
 * still be worth something when nobody remembers why the rule existed.
 */

import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = resolve(__dirname, "..");

function sourcesIn(directory: string): string[] {
  if (!existsSync(directory)) {
    return [];
  }

  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);

    if (entry.isDirectory()) {
      return sourcesIn(path);
    }

    return entry.name.endsWith(".ts") || entry.name.endsWith(".tsx")
      ? [path]
      : [];
  });
}

/** Every first-party source file. Excludes tests and dependencies. */
const APPLICATION_SOURCES = [
  ...sourcesIn(join(ROOT, "app")),
  ...sourcesIn(join(ROOT, "components")),
  ...sourcesIn(join(ROOT, "hooks")),
  ...sourcesIn(join(ROOT, "lib")),
  ...sourcesIn(join(ROOT, "config")),
];

function read(path: string): string {
  return readFileSync(path, "utf-8");
}

/** Source with comments stripped - a rule may be *named* in prose. */
function code(path: string): string {
  return read(path)
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

describe("the source tree", () => {
  it("is found, so an empty sweep cannot pass silently", () => {
    expect(APPLICATION_SOURCES.length).toBeGreaterThan(30);
  });
});

// --- Credentials are never stored where script can reach them ------------

describe("credential storage", () => {
  it("uses no web storage anywhere", () => {
    /**
     * The session lives in an `HttpOnly` cookie the browser attaches and
     * script cannot read. Anything in `localStorage` or `sessionStorage`
     * is readable by an injected script, which is the difference between
     * an XSS flaw being a bad afternoon and being an account takeover
     * that outlives the page.
     */
    for (const path of APPLICATION_SOURCES) {
      const source = code(path);

      expect(source, path).not.toContain("localStorage");
      expect(source, path).not.toContain("sessionStorage");
      expect(source, path).not.toContain("indexedDB");
    }
  });

  it("never looks for the session cookie", () => {
    /**
     * It cannot be found - it is `HttpOnly`. Code that looked for it
     * would have been written expecting a readable session token, which
     * is the design this application deliberately does not have.
     */
    for (const path of APPLICATION_SOURCES) {
      expect(code(path), path).not.toContain("substationos_session");
    }
  });

  it("reads only the CSRF cookie, and only in the API client", () => {
    const readers = APPLICATION_SOURCES.filter((path) =>
      code(path).includes("document.cookie"),
    ).map((path) => path.split(/[\\/]/).pop());

    expect(readers).toEqual(["client.ts"]);
  });

  it("never puts a credential in a URL", () => {
    /**
     * A query string is logged by every proxy it passes and lands in
     * browser history.
     */
    for (const path of APPLICATION_SOURCES) {
      const source = code(path);

      expect(source, path).not.toMatch(/[?&]password=/);
      expect(source, path).not.toMatch(/[?&]token=/);
    }
  });
});

// --- One HTTP path -------------------------------------------------------

describe("the API surface", () => {
  it("keeps `fetch` inside the one client", () => {
    const callers = APPLICATION_SOURCES.filter((path) =>
      /(^|[^.\w])fetch\s*\(/.test(code(path)),
    ).map((path) => path.split(/[\\/]/).pop());

    expect(callers).toEqual(["client.ts"]);
  });

  it("sends credentials from that one client", () => {
    const client = code(join(ROOT, "lib", "api", "client.ts"));

    expect(client).toContain('credentials: "include"');
  });

  it("attaches a CSRF token to unsafe methods only", () => {
    const client = code(join(ROOT, "lib", "api", "client.ts"));

    expect(client).toContain("SAFE_METHODS");
    expect(client).toContain("X-CSRF-Token");
  });

  it("has exactly one authentication resource module", () => {
    /**
     * A second, duplicated authentication client is how two definitions
     * of "signed in" come to disagree.
     */
    const modules = sourcesIn(join(ROOT, "lib", "resources"))
      .filter((path) => code(path).includes("/auth/"))
      .map((path) => path.split(/[\\/]/).pop());

    expect(modules).toEqual(["authentication.ts"]);
  });
});

// --- Authorization is never decided in the frontend ----------------------

describe("authorization", () => {
  it("declares no capability rules of its own", () => {
    /**
     * The frontend may *hide* a control the backend would refuse. It may
     * not decide anything: every permission question is answered by the
     * API, and a rule duplicated here is a rule that will eventually
     * disagree with the one that matters.
     */
    for (const path of APPLICATION_SOURCES) {
      const source = code(path);

      expect(source, path).not.toMatch(/canManageUsers|hasPermission\(/);
      expect(source, path).not.toMatch(/CAPABILITIES\s*[:=]/);
    }
  });

  it("treats 401 and 403 as different things", () => {
    /**
     * A `403` that signed the user out would send them round a login
     * loop that cannot succeed: they are already the right person.
     */
    const session = code(join(ROOT, "hooks", "useSession.tsx"));

    expect(session).toContain("onUnauthenticated");
    expect(session).not.toContain("Forbidden");
  });
});

// --- No unsafe rendering -------------------------------------------------

describe("rendering", () => {
  it("inserts no unsanitised HTML anywhere", () => {
    for (const path of APPLICATION_SOURCES) {
      expect(code(path), path).not.toContain("dangerouslySetInnerHTML");
      expect(code(path), path).not.toContain("innerHTML");
    }
  });

  it("performs no redirect to an address it was handed", () => {
    /**
     * An open redirect turns this application into a credible-looking
     * hop to somebody else's login page. There is no `?next=` parameter
     * here, and this is what keeps one from appearing.
     */
    for (const path of APPLICATION_SOURCES) {
      const source = code(path);

      expect(source, path).not.toMatch(/window\.location\s*=/);
      expect(source, path).not.toMatch(/location\.href\s*=/);
      expect(source, path).not.toMatch(/redirect_uri|returnUrl|next=/);
    }
  });
});
