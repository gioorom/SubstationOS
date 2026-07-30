/**
 * Turns a typed API failure into something an engineer can act on.
 *
 * The rule: **never invent a cause**. When the backend explains itself -
 * a duplicate project code, a read-only project, an unsupported format -
 * that explanation is shown. The copy below only covers the cases where
 * the backend says nothing a user could read, and is the reason
 * "Si è verificato un errore" appears nowhere in this application.
 */

import {
  ApiError,
  ConflictError,
  ForbiddenError,
  type FieldViolation,
  NetworkError,
  NotFoundError,
  RequestCancelledError,
  RequestError,
  ServerError,
  TimeoutError,
  UnauthenticatedError,
  ValidationError,
} from "./errors";

/** Per-call-site wording, used only where the backend supplies none. */
export interface ErrorCopy {
  validation?: string;
  unauthenticated?: string;
  forbidden?: string;
  notFound?: string;
  conflict?: string;
  server?: string;
  network?: string;
  fallback?: string;
}

const DEFAULT_COPY: Required<ErrorCopy> = {
  validation: "I dati inviati non sono validi.",
  unauthenticated:
    "La sessione non è più valida. Effettua di nuovo l'accesso.",
  forbidden:
    "Il tuo ruolo non consente questa operazione.",
  notFound: "La risorsa richiesta non esiste.",
  conflict:
    "L'operazione è in conflitto con lo stato attuale della risorsa.",
  server:
    "Il backend ha risposto con un errore interno. Riprova o consulta i log del server.",
  network:
    "Impossibile contattare il backend SubstationOS. Verifica che il servizio sia in esecuzione.",
  fallback: "Richiesta non riuscita.",
};

/**
 * Pydantic's own wording, translated. Anything not listed falls through
 * verbatim - an untranslated but accurate message beats a translated
 * guess.
 */
function translateViolation(violation: FieldViolation): string {
  const message = violation.message;

  const minLength = /String should have at least (\d+) character/.exec(
    message,
  );

  if (minLength) {
    return `Deve contenere almeno ${minLength[1]} caratteri.`;
  }

  const maxLength = /String should have at most (\d+) character/.exec(
    message,
  );

  if (maxLength) {
    return `Non può superare ${maxLength[1]} caratteri.`;
  }

  if (message === "Field required") {
    return "Campo obbligatorio.";
  }

  if (message.startsWith("Input should be")) {
    return `Valore non ammesso. ${message.replace(
      "Input should be",
      "Valori validi:",
    )}`;
  }

  if (message.startsWith("Input should be a valid integer")) {
    return "Deve essere un numero intero.";
  }

  return message;
}

/** Field name -> message, for binding validation onto form inputs. */
export function fieldMessages(
  error: unknown,
): Record<string, string> {
  if (!(error instanceof ValidationError)) {
    return {};
  }

  const messages: Record<string, string> = {};

  for (const violation of error.violations) {
    if (messages[violation.field] === undefined) {
      messages[violation.field] = translateViolation(violation);
    }
  }

  return messages;
}

/**
 * One sentence describing the failure.
 *
 * Returns `null` for a cancelled request: a superseded or unmounted
 * request is not something the user did wrong, and showing it as an
 * error would be a lie.
 */
export function describeError(
  error: unknown,
  copy: ErrorCopy = {},
): string | null {
  if (error instanceof RequestCancelledError) {
    return null;
  }

  const wording = { ...DEFAULT_COPY, ...copy };

  if (error instanceof ValidationError) {
    if (error.violations.length > 0) {
      return error.violations
        .map(
          (violation) =>
            `${violation.field}: ${translateViolation(violation)}`,
        )
        .join(" ");
    }

    return error.detail ?? copy.validation ?? wording.validation;
  }

  if (error instanceof ConflictError) {
    return error.detail ?? wording.conflict;
  }

  if (error instanceof UnauthenticatedError) {
    return (
      copy.unauthenticated ??
      "La sessione non è più valida. Effettua di nuovo l'accesso."
    );
  }

  if (error instanceof ForbiddenError) {
    return error.detail ?? wording.forbidden;
  }

  if (error instanceof NotFoundError) {
    return copy.notFound ?? error.detail ?? wording.notFound;
  }

  if (error instanceof ServerError) {
    return wording.server;
  }

  if (error instanceof TimeoutError) {
    return "Il backend non ha risposto entro il tempo previsto.";
  }

  if (error instanceof NetworkError) {
    return wording.network;
  }

  if (error instanceof RequestError) {
    return error.detail ?? wording.fallback;
  }

  if (error instanceof ApiError) {
    return error.message;
  }

  return wording.fallback;
}
