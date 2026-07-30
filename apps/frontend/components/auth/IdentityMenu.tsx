"use client";

import { useState } from "react";
import { LogOut, UserRound } from "lucide-react";

import { ROLE_LABELS } from "@/lib/contracts";
import { useSession } from "@/hooks/useSession";

/**
 * Who you are, and the way out.
 *
 * The role is shown next to the name because it is the thing that
 * explains why a control is or is not there - an engineer who cannot see
 * the audit trail should be able to work out why without asking.
 */
export default function IdentityMenu() {
  const { identity, signOut } = useSession();
  const [pending, setPending] = useState(false);

  if (identity === null) {
    return null;
  }

  return (
    <div className="flex items-center gap-3">
      <div className="hidden text-right sm:block">
        <p className="text-sm font-medium leading-tight text-foreground">
          {identity.display_name}
        </p>

        <p className="text-xs leading-tight text-muted-foreground">
          {ROLE_LABELS[identity.role]}
        </p>
      </div>

      <span
        aria-hidden="true"
        className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-primary"
      >
        <UserRound className="h-5 w-5" strokeWidth={1.8} />
      </span>

      <button
        type="button"
        onClick={() => {
          setPending(true);
          void signOut().finally(() => setPending(false));
        }}
        disabled={pending}
        className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-slate-100 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
      >
        <LogOut className="h-4 w-4" aria-hidden="true" />
        <span className="hidden sm:inline">
          {pending ? "Uscita…" : "Esci"}
        </span>
        <span className="sr-only sm:hidden">Esci</span>
      </button>
    </div>
  );
}
