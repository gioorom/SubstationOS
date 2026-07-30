/**
 * Authentication in the frontend.
 *
 * The behaviours asserted here are the ones a careless client destroys:
 * a password that outlives its request, a login screen that flashes on
 * every page load, an expired session that shows an error banner instead
 * of a sign-in form, and a `403` that logs the user out of an
 * application they are perfectly entitled to use.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import IdentityMenu from "@/components/auth/IdentityMenu";
import LoginForm from "@/components/auth/LoginForm";
import RequireSession from "@/components/auth/RequireSession";
import { SessionProvider } from "@/hooks/useSession";
import { apiClient } from "@/lib/api";

import { aSession, stubBackend, type Routes } from "./_backend";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => ({}),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

const CSRF_COOKIE = "substationos_csrf";

beforeEach(() => {
  // jsdom keeps cookies between tests in the same document.
  document.cookie = `${CSRF_COOKIE}=; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
});

function guarded(routes: Routes) {
  const backend = stubBackend(routes);

  render(
    <SessionProvider>
      <RequireSession>
        <p>Contenuto riservato</p>
      </RequireSession>
    </SessionProvider>,
  );

  return backend;
}

// --- The guard -----------------------------------------------------------

describe("the route guard", () => {
  it("shows the sign-in form when there is no session", async () => {
    guarded({ "GET /auth/session": { status: 401 } });

    expect(
      await screen.findByRole("heading", { name: "Accedi" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Contenuto riservato")).toBeNull();
  });

  it("shows the application when there is one", async () => {
    guarded({ "GET /auth/session": { body: aSession() } });

    expect(
      await screen.findByText("Contenuto riservato"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Accedi" })).toBeNull();
  });

  it("shows neither while the session is still being read", async () => {
    /**
     * `loading` is distinct from `anonymous` on purpose. Rendering the
     * login form for the half-second before the session read answers
     * would sign every user out, visibly, on every page load.
     */
    guarded({ "GET /auth/session": { hang: true } });

    expect(screen.queryByRole("heading", { name: "Accedi" })).toBeNull();
    expect(screen.queryByText("Contenuto riservato")).toBeNull();
    expect(
      screen.getByText(/Verifica della sessione in corso/),
    ).toBeInTheDocument();
  });

  it("reads the session exactly once per page load", async () => {
    const backend = guarded({
      "GET /auth/session": { body: aSession() },
    });

    await screen.findByText("Contenuto riservato");

    expect(backend.requestsFor("GET", "/auth/session")).toHaveLength(1);
  });

  it("treats an unreachable backend as signed out, not as an error", async () => {
    guarded({ "GET /auth/session": { networkFailure: true } });

    expect(
      await screen.findByRole("heading", { name: "Accedi" }),
    ).toBeInTheDocument();
  });
});

// --- Signing in ----------------------------------------------------------

describe("signing in", () => {
  it("exchanges credentials for a session and reveals the app", async () => {
    const backend = guarded({
      "GET /auth/session": { status: 401 },
      "POST /auth/login": { body: aSession() },
    });

    await screen.findByRole("heading", { name: "Accedi" });

    await userEvent.type(
      screen.getByLabelText("Email"),
      "ada@substationos.test",
    );
    await userEvent.type(
      screen.getByLabelText("Password"),
      "cavallo batteria graffetta",
    );
    await userEvent.click(screen.getByRole("button", { name: "Accedi" }));

    expect(
      await screen.findByText("Contenuto riservato"),
    ).toBeInTheDocument();

    const login = backend.requestsFor("POST", "/auth/login")[0];

    expect(login.body).toEqual({
      email: "ada@substationos.test",
      password: "cavallo batteria graffetta",
    });
  });

  it("sends credentials so the session cookie can come back", async () => {
    /**
     * Without `credentials: "include"` the browser will not attach the
     * cookie cross-origin, and every request would arrive anonymous.
     */
    const backend = stubBackend({ "GET /auth/session": { body: aSession() } });

    await apiClient.get("/auth/session");

    expect(backend.requests[0].credentials).toBe("include");
  });

  it("does not keep the password after the request", async () => {
    /**
     * The form on its own, without the guard: once the guard swaps it
     * for the application the input is detached, and asserting on a
     * detached node would prove nothing about what the form does.
     */
    stubBackend({
      "GET /auth/session": { status: 401 },
      "POST /auth/login": { body: aSession() },
    });

    render(
      <SessionProvider>
        <LoginForm />
      </SessionProvider>,
    );

    const password = screen.getByLabelText(
      "Password",
    ) as HTMLInputElement;

    await userEvent.type(screen.getByLabelText("Email"), "ada@x.test");
    await userEvent.type(password, "cavallo batteria graffetta");
    await userEvent.click(screen.getByRole("button", { name: "Accedi" }));

    await waitFor(() => expect(password.value).toBe(""));
  });

  it("never writes anything to local storage", () => {
    /**
     * A credential kept where script can read it is a credential an
     * injected script can walk away with. The session lives in an
     * `HttpOnly` cookie precisely so that nothing here has to.
     */
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it("does not say which half of the credentials was wrong", async () => {
    guarded({
      "GET /auth/session": { status: 401 },
      "POST /auth/login": {
        status: 401,
        body: { detail: "Email address or password is not correct." },
      },
    });

    await screen.findByRole("heading", { name: "Accedi" });

    await userEvent.type(screen.getByLabelText("Email"), "nobody@x.test");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-one-12");
    await userEvent.click(screen.getByRole("button", { name: "Accedi" }));

    const message = (await screen.findByRole("alert")).textContent ?? "";

    expect(message).toMatch(/non corretti/i);
    expect(message).not.toMatch(/utente|account|esiste|password errata/i);
  });

  it("clears the password after a failed attempt too", async () => {
    guarded({
      "GET /auth/session": { status: 401 },
      "POST /auth/login": { status: 401, body: { detail: "no" } },
    });

    await screen.findByRole("heading", { name: "Accedi" });

    const password = screen.getByLabelText(
      "Password",
    ) as HTMLInputElement;

    await userEvent.type(screen.getByLabelText("Email"), "ada@x.test");
    await userEvent.type(password, "cavallo batteria graffetta");
    await userEvent.click(screen.getByRole("button", { name: "Accedi" }));

    await screen.findByRole("alert");

    expect(password.value).toBe("");
  });
});

// --- Identity display and signing out ------------------------------------

describe("identity", () => {
  function withIdentity(routes: Routes) {
    const backend = stubBackend(routes);

    render(
      <SessionProvider>
        <IdentityMenu />
      </SessionProvider>,
    );

    return backend;
  }

  it("shows the authenticated name and role", async () => {
    withIdentity({ "GET /auth/session": { body: aSession() } });

    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("Ingegnere")).toBeInTheDocument();
  });

  it("shows an administrator as one", async () => {
    withIdentity({
      "GET /auth/session": {
        body: aSession({ role: "administrator" }),
      },
    });

    expect(
      await screen.findByText("Amministratore"),
    ).toBeInTheDocument();
  });

  it("renders nothing at all when nobody is signed in", async () => {
    withIdentity({ "GET /auth/session": { status: 401 } });

    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /Esci/ })).toBeNull(),
    );
  });

  it("signs out and returns to the sign-in form", async () => {
    const backend = stubBackend({
      "GET /auth/session": { body: aSession() },
      "POST /auth/logout": { status: 204 },
    });

    render(
      <SessionProvider>
        <RequireSession>
          <IdentityMenu />
        </RequireSession>
      </SessionProvider>,
    );

    await screen.findByText("Ada Lovelace");

    await userEvent.click(screen.getByRole("button", { name: /Esci/ }));

    expect(
      await screen.findByRole("heading", { name: "Accedi" }),
    ).toBeInTheDocument();
    expect(backend.requestsFor("POST", "/auth/logout")).toHaveLength(1);
  });

  it("signs out locally even if the backend cannot be reached", async () => {
    /**
     * A user who wants to leave a shared machine must be able to. A
     * failed logout request is not a reason to keep them signed in.
     */
    stubBackend({
      "GET /auth/session": { body: aSession() },
      "POST /auth/logout": { networkFailure: true },
    });

    render(
      <SessionProvider>
        <RequireSession>
          <IdentityMenu />
        </RequireSession>
      </SessionProvider>,
    );

    await screen.findByText("Ada Lovelace");
    await userEvent.click(screen.getByRole("button", { name: /Esci/ }));

    expect(
      await screen.findByRole("heading", { name: "Accedi" }),
    ).toBeInTheDocument();
  });
});

// --- Expiry --------------------------------------------------------------

describe("an expiring session", () => {
  /** A child of the guard that makes one ordinary authenticated read. */
  function Probe() {
    return (
      <button
        type="button"
        onClick={() => {
          void apiClient.get("/projects/").catch(() => undefined);
        }}
      >
        Carica progetti
      </button>
    );
  }

  it("signs the user out when any request answers 401", async () => {
    stubBackend({
      "GET /auth/session": { body: aSession() },
      "GET /projects/": { status: 401, body: { detail: "no" } },
    });

    render(
      <SessionProvider>
        <RequireSession>
          <Probe />
        </RequireSession>
      </SessionProvider>,
    );

    await screen.findByRole("button", { name: "Carica progetti" });

    await userEvent.click(
      screen.getByRole("button", { name: "Carica progetti" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Accedi" }),
    ).toBeInTheDocument();
  });

  it("says the session expired, rather than showing a blank form", async () => {
    stubBackend({
      "GET /auth/session": { body: aSession() },
      "GET /projects/": { status: 401, body: { detail: "no" } },
    });

    render(
      <SessionProvider>
        <RequireSession>
          <Probe />
        </RequireSession>
      </SessionProvider>,
    );

    await screen.findByRole("button", { name: "Carica progetti" });
    await userEvent.click(
      screen.getByRole("button", { name: "Carica progetti" }),
    );

    expect(
      await screen.findByText(/La sessione è scaduta/),
    ).toBeInTheDocument();
  });

  it("does not claim an expiry when the user was never signed in", async () => {
    guarded({ "GET /auth/session": { status: 401 } });

    await screen.findByRole("heading", { name: "Accedi" });

    expect(screen.queryByText(/La sessione è scaduta/)).toBeNull();
  });

  it("keeps the user signed in on a 403", async () => {
    /**
     * Authenticated and not permitted. Signing in again as the same
     * person cannot change the answer, so sending them to the login
     * screen would be a loop that never succeeds.
     */
    stubBackend({
      "GET /auth/session": { body: aSession() },
      "GET /projects/": { status: 403, body: { detail: "nope" } },
    });

    render(
      <SessionProvider>
        <RequireSession>
          <Probe />
        </RequireSession>
      </SessionProvider>,
    );

    await screen.findByRole("button", { name: "Carica progetti" });
    await userEvent.click(
      screen.getByRole("button", { name: "Carica progetti" }),
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Carica progetti" }),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByRole("heading", { name: "Accedi" })).toBeNull();
  });
});

// --- CSRF ----------------------------------------------------------------

describe("CSRF", () => {
  it("echoes the CSRF cookie on an unsafe request", async () => {
    document.cookie = `${CSRF_COOKIE}=csrf-value-from-the-backend`;

    const backend = stubBackend({ "POST /projects/": { body: {} } });

    await apiClient.post("/projects/", { json: { name: "x" } });

    expect(backend.requests[0].headers["x-csrf-token"]).toBe(
      "csrf-value-from-the-backend",
    );
  });

  it("sends no CSRF header on a read", async () => {
    document.cookie = `${CSRF_COOKIE}=csrf-value-from-the-backend`;

    const backend = stubBackend({ "GET /projects/": { body: [] } });

    await apiClient.get("/projects/");

    expect(backend.requests[0].headers["x-csrf-token"]).toBeUndefined();
  });

  it("cannot see the session cookie", () => {
    /**
     * `HttpOnly` means `document.cookie` never contains it. That the
     * client does not even look is asserted structurally in
     * `security-architecture.test.ts`.
     */
    document.cookie = `${CSRF_COOKIE}=csrf-value-from-the-backend`;

    expect(document.cookie).not.toContain("substationos_session");
  });
});
