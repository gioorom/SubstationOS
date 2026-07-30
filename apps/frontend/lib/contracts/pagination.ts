/**
 * The pagination contract, transcribed from the backend.
 *
 * Source of truth: `app/domain/shared_kernel/pagination.py` and
 * `app/schemas/pagination.py`. Page-based (`page` / `page_size`), one
 * convention across every list endpoint.
 */

/** Server-side default when the caller expresses no preference. */
export const DEFAULT_PAGE_SIZE = 25;

/**
 * Hard ceiling. A larger request is **refused with 422**, never clamped -
 * a client that asked for 10 000 and silently received 100 would believe
 * it had read the whole registry.
 */
export const MAX_PAGE_SIZE = 100;

export interface PageMetadata {
  page: number;
  page_size: number;
  /** Items matching the query across all pages - not the number returned. */
  total: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface PageRequest {
  page?: number;
  page_size?: number;
}

export const SORT_DIRECTIONS = ["asc", "desc"] as const;

export type SortDirection = (typeof SORT_DIRECTIONS)[number];

/** Every list response in this API has exactly this shape. */
export interface PagedResponse<T> {
  items: T[];
  pagination: PageMetadata;
}

export const EMPTY_PAGE: PageMetadata = {
  page: 1,
  page_size: DEFAULT_PAGE_SIZE,
  total: 0,
  total_pages: 0,
  has_next: false,
  has_previous: false,
};
