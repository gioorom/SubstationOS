"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { PageMetadata } from "@/lib/contracts";

interface PaginationProps {
  pagination: PageMetadata;
  onPageChange: (page: number) => void;
  /** What is being counted, for the summary line. */
  itemLabel: { singular: string; plural: string };
  disabled?: boolean;
}

/**
 * The one pagination control.
 *
 * It reports the **total**, not the page length: without it a user
 * cannot tell whether they have seen everything, which is the same
 * reason the API returns it.
 */
export default function Pagination({
  pagination,
  onPageChange,
  itemLabel,
  disabled = false,
}: PaginationProps) {
  const { page, page_size, total, total_pages, has_next, has_previous } =
    pagination;

  if (total === 0) {
    return null;
  }

  const first = (page - 1) * page_size + 1;
  const last = Math.min(page * page_size, total);
  const noun = total === 1 ? itemLabel.singular : itemLabel.plural;

  return (
    <nav
      aria-label="Paginazione"
      className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white/70 px-5 py-3"
    >
      <p className="text-sm text-muted-foreground">
        {first}–{last} di <strong>{total}</strong> {noun}
        {total_pages > 1 && (
          <span className="ml-2 text-xs">
            (pagina {page} di {total_pages})
          </span>
        )}
      </p>

      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled || !has_previous}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft className="h-4 w-4" />
          Precedente
        </Button>

        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled || !has_next}
          onClick={() => onPageChange(page + 1)}
        >
          Successiva
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </nav>
  );
}
