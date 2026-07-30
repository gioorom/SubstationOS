/**
 * `POST /auth/login`, `POST /auth/logout`, `GET /auth/session`.
 *
 * Goes through the same `apiClient` as everything else - there is no
 * second HTTP path for authentication, and an architecture test asserts
 * it. The session token is never seen by any function here: the backend
 * sets an `HttpOnly` cookie, the browser attaches it, and this module
 * only ever learns *who* the session belongs to.
 */

import { apiClient, NotFoundError, UnauthenticatedError } from "@/lib/api";
import type {
  AuditAction,
  AuditEventListResponse,
  Identity,
  Role,
  Session,
  User,
  UserListResponse,
  UserStatus,
} from "@/lib/contracts";

export function login(
  email: string,
  password: string,
  signal?: AbortSignal,
): Promise<Session> {
  return apiClient.post<Session>("/auth/login", {
    json: { email, password },
    signal,
  });
}

/**
 * Always resolves.
 *
 * Logging out with no session, an unknown token or an already-revoked
 * one is a `204` from the backend, deliberately - and a transport
 * failure must not leave a user stuck on a page they wanted to leave, so
 * it is swallowed here too. The cookie is cleared by the response when
 * there is one, and the client clears its own state either way.
 */
export async function logout(signal?: AbortSignal): Promise<void> {
  try {
    await apiClient.post<void>("/auth/logout", { signal });
  } catch {
    // Deliberately ignored. See above.
  }
}

/**
 * The current session, or `null`.
 *
 * `null` means "not signed in" and is the normal state of a first page
 * load. It is not a failure and is never rendered as one - which is why
 * the 401 is translated here rather than escaping to a caller that would
 * have to know to expect it.
 */
export async function readSession(
  signal?: AbortSignal,
): Promise<Session | null> {
  try {
    return await apiClient.get<Session>("/auth/session", { signal });
  } catch (error) {
    if (
      error instanceof UnauthenticatedError ||
      error instanceof NotFoundError
    ) {
      return null;
    }

    throw error;
  }
}

export function readMe(signal?: AbortSignal): Promise<Identity> {
  return apiClient.get<Identity>("/users/me", { signal });
}

/**
 * Changes the caller's own password.
 *
 * **Ends every session, including this one.** The backend revokes them
 * all, because a password changed because it may be known to someone
 * else is worth nothing while the sessions it opened keep working. The
 * caller must sign in again; the UI says so before submitting.
 */
export function changePassword(
  currentPassword: string,
  newPassword: string,
  signal?: AbortSignal,
): Promise<void> {
  return apiClient.post<void>("/users/me/password", {
    json: {
      current_password: currentPassword,
      new_password: newPassword,
    },
    signal,
  });
}

// --- Administration ------------------------------------------------------

export function listUsers(signal?: AbortSignal): Promise<UserListResponse> {
  return apiClient.get<UserListResponse>("/users/", { signal, retries: 1 });
}

export function createUser(
  input: {
    email: string;
    displayName: string;
    password: string;
    role: Role;
  },
  signal?: AbortSignal,
): Promise<User> {
  return apiClient.post<User>("/users/", {
    json: {
      email: input.email,
      display_name: input.displayName,
      password: input.password,
      role: input.role,
    },
    signal,
  });
}

export function setUserStatus(
  userId: number,
  status: UserStatus,
  signal?: AbortSignal,
): Promise<User> {
  return apiClient.post<User>(`/users/${userId}/status`, {
    json: { status },
    signal,
  });
}

export function listAuditEvents(
  query: { limit?: number; action?: AuditAction; user_id?: number } = {},
  signal?: AbortSignal,
): Promise<AuditEventListResponse> {
  return apiClient.get<AuditEventListResponse>("/audit/events", {
    query: {
      limit: query.limit,
      action: query.action,
      user_id: query.user_id,
    },
    signal,
    retries: 1,
  });
}
