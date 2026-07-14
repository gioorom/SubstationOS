"use client";

import { usePathname } from "next/navigation";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/documents": "Documents",
  "/projects": "Projects",
  "/commissioning": "Commissioning",
  "/relay-testing": "Relay Testing",
  "/ai": "AI Assistant",
  "/reports": "Reports",
  "/settings": "Settings",
};

function getPageTitle(pathname: string) {
  if (pageTitles[pathname]) {
    return pageTitles[pathname];
  }

  const matchingPath = Object.keys(pageTitles)
    .filter((path) => path !== "/")
    .find((path) => pathname.startsWith(path));

  return matchingPath
    ? pageTitles[matchingPath]
    : "SubstationOS";
}

export default function AppTopBar() {
  const pathname = usePathname();
  const pageTitle = getPageTitle(pathname);

  return (
    <header className="sticky top-0 z-30 border-b border-white/60 bg-white/68 backdrop-blur-2xl">
      <div className="flex min-h-20 items-center justify-between gap-6 px-6 lg:px-10">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
            Engineering workspace
          </p>

          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
            {pageTitle}
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden min-w-72 items-center gap-3 rounded-2xl border border-white/70 bg-white/72 px-4 py-3 shadow-sm backdrop-blur-xl md:flex">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              className="h-5 w-5 text-muted-foreground"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-4-4" />
            </svg>

            <input
              type="search"
              placeholder="Cerca in SubstationOS..."
              aria-label="Cerca in SubstationOS"
              className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
            />
          </div>

          <button
            type="button"
            aria-label="Notifiche"
            className="relative flex h-11 w-11 items-center justify-center rounded-2xl border border-white/70 bg-white/72 text-muted-foreground shadow-sm transition hover:bg-white hover:text-foreground"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              className="h-5 w-5"
            >
              <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
              <path d="M10 21h4" />
            </svg>

            <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-blue-500 ring-2 ring-white" />
          </button>

          <button
            type="button"
            aria-label="Profilo utente"
            className="flex h-11 items-center gap-3 rounded-2xl border border-white/70 bg-white/72 px-2.5 pr-4 shadow-sm transition hover:bg-white"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
              PR
            </div>

            <div className="hidden text-left sm:block">
              <p className="text-sm font-semibold leading-none text-foreground">
                Pietro Romano
              </p>

              <p className="mt-1 text-xs text-muted-foreground">
                Engineer
              </p>
            </div>
          </button>
        </div>
      </div>
    </header>
  );
}