/**
 * The Human Review endpoints.
 *
 * Resource-oriented, like the API they call: a judgement is a member
 * appended to a collection, not an `approve()` call. There is no
 * `updateReview` and no `deleteReview` here, because the API declares
 * neither - the append-only guarantee is visible from this file.
 *
 * Goes through the same `apiClient` as everything else; an architecture
 * test asserts no second HTTP path exists.
 */

import { apiClient, NotFoundError } from "@/lib/api";
import type {
  CurrentReview,
  DocumentReviewSummaryResponse,
  RecordReviewRequest,
  Review,
  ReviewHistoryResponse,
  ReviewVocabulary,
} from "@/lib/contracts";

const readOptions = (signal?: AbortSignal) => ({ signal, retries: 1 });

function statementPath(documentId: number, statementKey: string): string {
  return (
    `/documents/${documentId}/engineering-semantics/` +
    encodeURIComponent(statementKey)
  );
}

/**
 * Which reasons may accompany which decision.
 *
 * Read from the backend rather than duplicated here: a client that
 * hard-coded the pairing would eventually offer a combination the API
 * refuses, and the reviewer would discover it on submit.
 */
export function readReviewVocabulary(
  signal?: AbortSignal,
): Promise<ReviewVocabulary> {
  return apiClient.get<ReviewVocabulary>(
    "/engineering-reviews/vocabulary",
    readOptions(signal),
  );
}

/**
 * The current decision for every reviewed statement in one document.
 *
 * One request, so a Workspace listing statements does not make one per
 * row. Statements nobody has reviewed are absent from `items`; the
 * caller treats an absent key as "never reviewed", which is what it is.
 */
export function readDocumentReviews(
  documentId: number,
  signal?: AbortSignal,
): Promise<DocumentReviewSummaryResponse> {
  return apiClient.get<DocumentReviewSummaryResponse>(
    `/documents/${documentId}/engineering-semantics/reviews`,
    readOptions(signal),
  );
}

/**
 * The effective decision for one statement.
 *
 * Answers for a statement that no longer exists too - that is what the
 * snapshot is for, and the projection reports `requires_revalidation` or
 * `orphaned` rather than a 404.
 */
export function readCurrentReview(
  documentId: number,
  statementKey: string,
  signal?: AbortSignal,
): Promise<CurrentReview> {
  return apiClient.get<CurrentReview>(
    `${statementPath(documentId, statementKey)}/current-review`,
    readOptions(signal),
  );
}

/** One page of a statement's history, newest first. */
export function readReviewHistory(
  documentId: number,
  statementKey: string,
  query: { page?: number; page_size?: number } = {},
  signal?: AbortSignal,
): Promise<ReviewHistoryResponse> {
  return apiClient.get<ReviewHistoryResponse>(
    `${statementPath(documentId, statementKey)}/reviews`,
    {
      query: { page: query.page, page_size: query.page_size },
      ...readOptions(signal),
    },
  );
}

/**
 * Appends one judgement.
 *
 * Nothing is updated. A second review of the same statement creates a
 * second record and the first stays exactly as it was written - the API
 * answers `201` either way, and this function has no "update" sibling.
 */
export function recordReview(
  documentId: number,
  statementKey: string,
  input: RecordReviewRequest,
  signal?: AbortSignal,
): Promise<Review> {
  return apiClient.post<Review>(
    `${statementPath(documentId, statementKey)}/reviews`,
    { json: input, signal },
  );
}

/**
 * `readCurrentReview`, with a missing document treated as unreviewed.
 *
 * A document whose semantics have never been read is not an error state
 * for a review panel; it is a statement nobody could have reviewed.
 */
export async function readOptionalCurrentReview(
  documentId: number,
  statementKey: string,
  signal?: AbortSignal,
): Promise<CurrentReview | null> {
  try {
    return await readCurrentReview(documentId, statementKey, signal);
  } catch (error) {
    if (error instanceof NotFoundError) {
      return null;
    }

    throw error;
  }
}
