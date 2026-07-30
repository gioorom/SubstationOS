"use client";

/**
 * The selected artefact, kept in the URL.
 *
 * `?kind=semantic&key=statement-…` is the whole of it. Refreshing
 * restores the inspection, Back and Forward step through inspections,
 * and the link can be sent to a colleague.
 *
 * Written with the **native History API**, which the App Router
 * supports and keeps `useSearchParams` in sync with. `router.push` would
 * re-render the route segment on every click in an explorer; changing
 * which artefact is inspected must not re-read the document.
 */

import { usePathname, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

import {
  selectionFromQuery,
  selectionsEqual,
  type Selection,
  type SelectionKind,
} from "@/lib/workspace";

export interface SelectionState {
  selection: Selection | null;
  select: (kind: SelectionKind, key: string) => void;
  clear: () => void;
}

export function useWorkspaceSelection(): SelectionState {
  const searchParams = useSearchParams();
  const pathname = usePathname();

  const selection = useMemo(
    () =>
      selectionFromQuery(
        searchParams.get("kind"),
        searchParams.get("key"),
      ),
    [searchParams],
  );

  const write = useCallback(
    (next: Selection | null) => {
      const params = new URLSearchParams(searchParams.toString());

      if (next === null) {
        params.delete("kind");
        params.delete("key");
      } else {
        params.set("kind", next.kind);
        params.set("key", next.key);
      }

      const query = params.toString();
      const url = query === "" ? pathname : `${pathname}?${query}`;

      window.history.pushState(null, "", url);
    },
    [pathname, searchParams],
  );

  const select = useCallback(
    (kind: SelectionKind, key: string) => {
      const next: Selection = { kind, key };

      // Re-selecting what is already selected would push a history
      // entry that Back could not distinguish from the one before it.
      if (!selectionsEqual(selection, next)) {
        write(next);
      }
    },
    [selection, write],
  );

  const clear = useCallback(() => {
    if (selection !== null) {
      write(null);
    }
  }, [selection, write]);

  return { selection, select, clear };
}
