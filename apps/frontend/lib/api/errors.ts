/**
 * The error model every request failure is expressed in.
 *
 * A caller never sees a bare `Error` or a raw HTTP status: it sees one of
 * these types, each carrying what the UI needs to say something true. The
 * backend's own typed detail is preserved on `detail` - the frontend
 * invents no cause it was not told.
 */

/** FastAPI's `{"detail": [...]}` for a request that failed validation. */
export interface FieldViolation {
  /** Dotted path into the request body, e.g. `body.name` -> `name`. */
  field: string;
  message: string;
  type: string;
}

export abstract class ApiError extends Error {
  /** The HTTP status, or `null` when the request never got a response. */
  abstract readonly status: number | null;

  /** A short machine-readable discriminator, stable across releases. */
  abstract readonly kind: string;

  /** The backend's own `detail`, verbatim, when it sent one. */
  readonly detail: string | null;

  constructor(message: string, detail: string | null = null) {
    super(message);
    this.name = new.target.name;
    this.detail = detail;
  }
}

/**
 * 422 - the request was understood and refused by validation.
 *
 * The backend answers in two shapes and both arrive here: Pydantic's
 * per-field array, and a plain string raised by a domain rule (an
 * invalid project name, an upload with no project). `violations` is
 * empty for the second, which is exactly why `message` exists.
 */
export class ValidationError extends ApiError {
  readonly status = 422;
  readonly kind = "validation";
  readonly violations: readonly FieldViolation[];

  constructor(
    message: string,
    violations: readonly FieldViolation[] = [],
    detail: string | null = null,
  ) {
    super(message, detail);
    this.violations = violations;
  }

  /** The first violation for a field, if validation named that field. */
  forField(field: string): string | undefined {
    return this.violations.find(
      (violation) => violation.field === field,
    )?.message;
  }
}

/** 404 - the resource does not exist, or the stage has not run yet. */
export class NotFoundError extends ApiError {
  readonly status = 404;
  readonly kind = "not_found";
}

/**
 * 409 - the request conflicts with the resource's current state.
 *
 * A duplicate project code, or a project whose lifecycle state makes it
 * read-only. Never a reason to retry unchanged.
 */
export class ConflictError extends ApiError {
  readonly status = 409;
  readonly kind = "conflict";
}

/** 400/401/403/405/... - a client error with no more specific type. */
export class RequestError extends ApiError {
  readonly kind = "request";

  constructor(
    readonly status: number,
    message: string,
    detail: string | null = null,
  ) {
    super(message, detail);
  }
}

/** 5xx - the backend failed. Retrying an idempotent read may help. */
export class ServerError extends ApiError {
  readonly kind = "server";

  constructor(
    readonly status: number,
    message: string,
    detail: string | null = null,
  ) {
    super(message, detail);
  }
}

/** The request never reached the backend, or the response was not JSON. */
export class NetworkError extends ApiError {
  readonly status = null;
  readonly kind = "network";
}

/** The request exceeded the client's timeout. */
export class TimeoutError extends ApiError {
  readonly status = null;
  readonly kind = "timeout";
}

/**
 * The caller cancelled the request - a superseded search, an unmounted
 * component. **Not a failure**, and never rendered as one.
 */
export class RequestCancelledError extends ApiError {
  readonly status = null;
  readonly kind = "cancelled";
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function isCancellation(error: unknown): boolean {
  return error instanceof RequestCancelledError;
}
