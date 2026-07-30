"use client";

/**
 * Who is signed in, for the whole application.
 *
 * One provider at the root, one read of `GET /auth/session` per page
 * load, and one place that knows what to do when a session ends. Every
 * screen asks this rather than the backend.
 *
 * **The session token is not here, and cannot be.** It lives in an
 * `HttpOnly` cookie the browser attaches and script cannot read. What
 * this module holds is the *identity* the backend resolved from it -
 * an id, an address, a name and a role, none of which is worth stealing.
 * There is deliberately no `localStorage` anywhere in this file: a
 * credential kept where script can read it is a credential an injected
 * script can walk away with.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { describeError, onUnauthenticated } from "@/lib/api";
import type { Identity, Session } from "@/lib/contracts";
import {
  login as performLogin,
  logout as performLogout,
  readSession,
} from "@/lib/resources/authentication";

/**
 * - `loading`   the first `GET /auth/session` has not answered yet
 * - `anonymous` there is no session; the login screen is the whole app
 * - `signed_in` there is one, and `identity` says whose
 *
 * `loading` is distinct from `anonymous` on purpose: rendering the login
 * screen for the half-second before the session read answers would sign
 * out every user on every page load, visibly.
 */
export type SessionStatus = "loading" | "anonymous" | "signed_in";

export interface SessionState {
  status: SessionStatus;
  identity: Identity | null;
  /** The absolute ceiling of the current session, if there is one. */
  expiresAt: string | null;
  /**
   * True when the session ended while the user was working, rather than
   * never having existed. The login screen says something different.
   */
  expired: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<SessionStatus>("loading");
  const [expired, setExpired] = useState(false);

  const controller = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    controller.current?.abort();

    const current = new AbortController();
    controller.current = current;

    try {
      const found = await readSession(current.signal);

      if (current.signal.aborted) {
        return;
      }

      setSession(found);
      setStatus(found === null ? "anonymous" : "signed_in");
    } catch {
      // A session read that fails at transport level is not evidence
      // that the user is signed out - but it is not evidence that they
      // are, either, and the safe reading is the one that shows the
      // login screen rather than an application that will 401 on every
      // request.
      if (!current.signal.aborted) {
        setSession(null);
        setStatus("anonymous");
      }
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();

    return () => controller.current?.abort();
  }, [refresh]);

  /**
   * A `401` from **any** request means the session ended - it expired, an
   * administrator disabled the account, or somebody logged out in
   * another tab. Observed in one place so no screen has to recognise it.
   */
  useEffect(() => {
    onUnauthenticated(() => {
      setSession((previous) => {
        if (previous !== null) {
          setExpired(true);
        }

        return null;
      });

      setStatus("anonymous");
    });

    return () => onUnauthenticated(null);
  }, []);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const opened = await performLogin(email, password);

      setSession(opened);
      setStatus("signed_in");
      setExpired(false);
    },
    [],
  );

  const signOut = useCallback(async () => {
    await performLogout();

    setSession(null);
    setStatus("anonymous");
    // A deliberate sign-out is not an expiry, and must not be reported
    // as one on the login screen.
    setExpired(false);
  }, []);

  const value = useMemo<SessionState>(
    () => ({
      status,
      identity: session?.identity ?? null,
      expiresAt: session?.expires_at ?? null,
      expired,
      signIn,
      signOut,
      refresh,
    }),
    [status, session, expired, signIn, signOut, refresh],
  );

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionState {
  const value = useContext(SessionContext);

  if (value === null) {
    throw new Error(
      "useSession must be used inside a SessionProvider. Without one a " +
        "screen would render as though nobody were signed in.",
    );
  }

  return value;
}

/** A user-facing sentence for a failed sign-in. Never invents a cause. */
export function describeSignInFailure(error: unknown): string {
  return (
    describeError(error, {
      unauthenticated: "Email o password non corretti.",
      network:
        "Impossibile contattare il backend SubstationOS. Verifica che il servizio sia in esecuzione.",
    }) ?? "Accesso non riuscito."
  );
}
