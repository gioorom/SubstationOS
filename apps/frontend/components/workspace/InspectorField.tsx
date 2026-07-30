"use client";

import { Copy } from "lucide-react";
import { type ReactNode, useState } from "react";

interface InspectorFieldProps {
  label: string;
  children: ReactNode;
  /** When given, a copy control is offered for this exact string. */
  copyValue?: string;
}

/**
 * One labelled fact about the selected artefact.
 *
 * Copying an identifier is the only thing the Inspector lets an engineer
 * *do* with an artefact. It is a read, and it is what makes a key usable
 * in a ticket, a query or a message - the Workspace has no write of any
 * kind, in this milestone by design.
 */
export default function InspectorField({
  label,
  children,
  copyValue,
}: InspectorFieldProps) {
  const [copied, setCopied] = useState(false);

  return (
    <div className="border-b border-slate-100 py-2 last:border-b-0">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>

      <dd className="mt-1 flex items-start gap-2 text-sm text-foreground">
        <span className="min-w-0 flex-1 break-words">{children}</span>

        {copyValue !== undefined && (
          <button
            type="button"
            aria-label={`Copia ${label}`}
            onClick={() => {
              void navigator.clipboard
                ?.writeText(copyValue)
                .then(() => setCopied(true))
                .catch(() => setCopied(false));
            }}
            className="shrink-0 rounded-lg p-1 text-muted-foreground hover:bg-slate-100 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Copy className="h-3.5 w-3.5" />
          </button>
        )}

        {copied && (
          <span role="status" className="sr-only">
            {`${label} copiato`}
          </span>
        )}
      </dd>
    </div>
  );
}
