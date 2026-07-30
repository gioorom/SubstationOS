/**
 * The one HTTP client. **Every** request to the SubstationOS backend
 * passes through here.
 *
 * It owns the base URL, the JSON contract, timeouts, cancellation and
 * the translation of a status code into a typed error. No component,
 * hook or resource module calls `fetch` directly - an architecture test
 * asserts it.
 *
 * What it deliberately does not own: what a resource *is*. It knows
 * nothing about projects, documents or the engineering pipeline; those
 * live in `lib/resources`, over the contracts in `lib/contracts`.
 */

import { env } from "@/config/env";

import {
  ConflictError,
  type FieldViolation,
  ForbiddenError,
  NetworkError,
  NotFoundError,
  RequestCancelledError,
  RequestError,
  ServerError,
  TimeoutError,
  UnauthenticatedError,
  ValidationError,
} from "./errors";

/** Requests that may be retried: reads, and only on a transport fault. */
const RETRYABLE_METHODS = new Set(["GET", "HEAD"]);

/** Methods the backend requires a CSRF token for. Mirrors its own list. */
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

/**
 * The CSRF cookie the backend sets alongside the session.
 *
 * It is readable by script **on purpose**: echoing it in a header is the
 * half of the check an attacker on another origin cannot perform. The
 * session token itself is `HttpOnly` and is never touched by this file -
 * the browser attaches it, and nothing here can read it, which is what
 * makes an XSS flaw in this application a limited incident rather than a
 * credential theft.
 */
const CSRF_COOKIE = "substationos_csrf";

const CSRF_HEADER = "X-CSRF-Token";

/**
 * Notified whenever any request is answered `401`.
 *
 * The one piece of module state in this file, and it earns its place: a
 * session can expire between two page loads, and without a single place
 * to observe that, every hook in the application would have to recognise
 * a 401 and decide what it means. One handler, registered by the session
 * provider, turns "this request was refused" into "you have been signed
 * out" exactly once.
 *
 * It is a notification, not a retry: nothing here re-issues the request
 * or attempts to refresh anything.
 */
let unauthenticatedHandler: (() => void) | null = null;

export function onUnauthenticated(handler: (() => void) | null): void {
  unauthenticatedHandler = handler;
}

function csrfToken(): string | null {
  if (typeof document === "undefined") {
    return null;
  }

  const match = document.cookie
    .split(";")
    .map((entry) => entry.trim())
    .find((entry) => entry.startsWith(`${CSRF_COOKIE}=`));

  return match === undefined
    ? null
    : decodeURIComponent(match.slice(CSRF_COOKIE.length + 1));
}

const DEFAULT_TIMEOUT_MS = 30_000;

/**
 * Pipeline stages parse a whole PDF; 30s is not enough on a large one.
 * Callers raise the limit explicitly rather than the client guessing.
 */
export const PIPELINE_TIMEOUT_MS = 120_000;

export interface RequestOptions {
  method?: string;
  /** Serialised as JSON. Mutually exclusive with `body`. */
  json?: unknown;
  /** Sent as-is (used for `FormData` uploads, which set their own type). */
  body?: BodyInit;
  query?: Record<string, string | number | boolean | undefined>;
  /** Caller-owned cancellation, composed with the timeout. */
  signal?: AbortSignal;
  timeoutMs?: number;
  /**
   * Transport-fault retries. Applies to `GET`/`HEAD` only: replaying a
   * POST that may have been received would create a second project.
   */
  retries?: number;
  /**
   * Return the `Response` itself instead of a parsed JSON body, for the
   * one endpoint that serves bytes (`GET /documents/{id}/content`).
   *
   * Failures are still translated into the same typed errors: a raw read
   * changes what a *success* looks like, never what a failure does.
   */
  raw?: boolean;
}

function buildUrl(
  path: string,
  query: RequestOptions["query"],
): string {
  const url = `${env.apiBaseUrl}${path}`;

  if (query === undefined) {
    return url;
  }

  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  }

  const queryString = params.toString();

  return queryString ? `${url}?${queryString}` : url;
}

/**
 * Reads FastAPI's `detail`, which arrives in two shapes: Pydantic's
 * per-field array, and a plain string raised by a domain rule. Both are
 * carried through; neither is flattened into the other.
 */
function readFailure(payload: unknown): {
  detail: string | null;
  violations: FieldViolation[];
} {
  if (payload === null || typeof payload !== "object") {
    return { detail: null, violations: [] };
  }

  const detail = (payload as { detail?: unknown }).detail;

  if (typeof detail === "string") {
    return { detail, violations: [] };
  }

  if (!Array.isArray(detail)) {
    return { detail: null, violations: [] };
  }

  const violations: FieldViolation[] = [];

  for (const item of detail) {
    if (item === null || typeof item !== "object") {
      continue;
    }

    const entry = item as {
      loc?: unknown;
      msg?: unknown;
      type?: unknown;
    };

    const location = Array.isArray(entry.loc)
      ? entry.loc.filter(
          (part): part is string | number =>
            typeof part === "string" || typeof part === "number",
        )
      : [];

    // `loc` is prefixed with its source (`body`, `query`, `path`); the
    // form binds on the field name, so the prefix is dropped.
    const field = location
      .slice(1)
      .map(String)
      .join(".");

    violations.push({
      field: field || location.map(String).join("."),
      message: typeof entry.msg === "string" ? entry.msg : "",
      type: typeof entry.type === "string" ? entry.type : "",
    });
  }

  return { detail: null, violations };
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text();

  if (text === "") {
    return null;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

function failureFor(
  response: Response,
  payload: unknown,
): Error {
  const { detail, violations } = readFailure(payload);
  const status = response.status;

  if (status === 422) {
    return new ValidationError(
      detail ?? "Validazione fallita.",
      violations,
      detail,
    );
  }

  if (status === 401) {
    return new UnauthenticatedError(
      detail ?? "È necessario autenticarsi.",
      detail,
    );
  }

  if (status === 403) {
    return new ForbiddenError(
      detail ?? "Il tuo ruolo non consente questa operazione.",
      detail,
    );
  }

  if (status === 404) {
    return new NotFoundError(detail ?? "Risorsa non trovata.", detail);
  }

  if (status === 409) {
    return new ConflictError(detail ?? "Conflitto di stato.", detail);
  }

  if (status >= 500) {
    return new ServerError(
      status,
      detail ?? `Errore interno del backend (${status}).`,
      detail,
    );
  }

  return new RequestError(
    status,
    detail ?? `Richiesta rifiutata (${status}).`,
    detail,
  );
}

/**
 * Composes the caller's signal with this request's timeout so either can
 * abort it, and reports which one did - a timeout is a failure worth
 * surfacing, a cancellation is not.
 */
function withTimeout(
  timeoutMs: number,
  callerSignal: AbortSignal | undefined,
): {
  signal: AbortSignal;
  timedOut: () => boolean;
  dispose: () => void;
} {
  const controller = new AbortController();
  let timedOut = false;

  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  const forward = () => controller.abort();

  if (callerSignal !== undefined) {
    if (callerSignal.aborted) {
      controller.abort();
    } else {
      callerSignal.addEventListener("abort", forward, { once: true });
    }
  }

  return {
    signal: controller.signal,
    timedOut: () => timedOut,
    dispose: () => {
      clearTimeout(timer);
      callerSignal?.removeEventListener("abort", forward);
    },
  };
}

async function performRequest(
  path: string,
  options: RequestOptions,
): Promise<Response> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined = options.body;

  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  }

  if (!SAFE_METHODS.has(method)) {
    const token = csrfToken();

    if (token !== null) {
      headers[CSRF_HEADER] = token;
    }
  }

  const timeout = withTimeout(
    options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
    options.signal,
  );

  try {
    return await fetch(buildUrl(path, options.query), {
      method,
      headers,
      body,
      signal: timeout.signal,
      // The session lives in a cookie the browser will not send
      // cross-origin unless asked. Without this every request arrives
      // anonymous and every page looks signed out.
      credentials: "include",
    });
  } catch (cause) {
    if (timeout.timedOut()) {
      throw new TimeoutError(
        "Il backend non ha risposto entro il tempo previsto.",
      );
    }

    if (options.signal?.aborted === true) {
      throw new RequestCancelledError("Richiesta annullata.");
    }

    throw new NetworkError(
      "Impossibile contattare il backend SubstationOS.",
      cause instanceof Error ? cause.message : null,
    );
  } finally {
    timeout.dispose();
  }
}

/**
 * Sends one request and returns its parsed body.
 *
 * @throws {ValidationError} on 422
 * @throws {NotFoundError} on 404
 * @throws {ConflictError} on 409
 * @throws {ServerError} on 5xx
 * @throws {RequestError} on any other 4xx
 * @throws {NetworkError} when the backend cannot be reached
 * @throws {TimeoutError} when it does not answer in time
 * @throws {RequestCancelledError} when the caller aborted
 */
export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const method = options.method ?? "GET";

  const attempts =
    RETRYABLE_METHODS.has(method) && options.retries !== undefined
      ? options.retries + 1
      : 1;

  let lastTransportFailure: Error | null = null;

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    let response: Response;

    try {
      response = await performRequest(path, options);
    } catch (error) {
      // Only a transport fault is replayed. A 4xx or 5xx is an answer,
      // and repeating the question does not change it.
      if (
        error instanceof NetworkError ||
        error instanceof TimeoutError
      ) {
        lastTransportFailure = error;
        continue;
      }

      throw error;
    }

    if (!response.ok) {
      const failure = failureFor(response, await readBody(response));

      if (failure instanceof UnauthenticatedError) {
        unauthenticatedHandler?.();
      }

      throw failure;
    }

    if (options.raw === true) {
      return response as T;
    }

    return (await readBody(response)) as T;
  }

  throw lastTransportFailure ??
    new NetworkError("Impossibile contattare il backend SubstationOS.");
}

/** Convenience wrappers. Each is `request` with the method filled in. */
export const apiClient = {
  get: <T>(path: string, options: Omit<RequestOptions, "method"> = {}) =>
    request<T>(path, { ...options, method: "GET" }),

  post: <T>(path: string, options: Omit<RequestOptions, "method"> = {}) =>
    request<T>(path, { ...options, method: "POST" }),

  patch: <T>(path: string, options: Omit<RequestOptions, "method"> = {}) =>
    request<T>(path, { ...options, method: "PATCH" }),

  delete: <T>(path: string, options: Omit<RequestOptions, "method"> = {}) =>
    request<T>(path, { ...options, method: "DELETE" }),
} as const;
