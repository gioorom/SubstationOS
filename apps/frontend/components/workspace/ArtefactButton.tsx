"use client";

import type { ReactNode } from "react";

interface ArtefactButtonProps {
  selected: boolean;
  onSelect: () => void;
  /** Read by assistive technology in place of the row's layout. */
  label: string;
  children: ReactNode;
}

/**
 * One selectable artefact in an explorer.
 *
 * A real `<button>`, so it is in the tab order, activates on Enter and
 * Space, and is announced as a control - none of which a `div` with an
 * `onClick` would be. Selection is carried by `aria-current`, by a
 * left rule, by a background **and** by a visible marker, so it survives
 * a monochrome display and a colour-blind reader alike.
 */
export default function ArtefactButton({
  selected,
  onSelect,
  label,
  children,
}: ArtefactButtonProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected ? "true" : undefined}
      aria-label={label}
      className={`w-full rounded-2xl border px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
        selected
          ? "border-l-4 border-slate-400 border-l-slate-900 bg-slate-100"
          : "border-slate-200 bg-white hover:bg-slate-50"
      }`}
    >
      {/*
        `aria-current` announces the selection; the marker below repeats
        it visually for a reader who cannot rely on the background.
      */}
      {selected && (
        <span aria-hidden="true" className="mr-1 font-bold">
          ▸
        </span>
      )}
      {children}
    </button>
  );
}
