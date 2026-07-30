"use client";

import { Bell, Search } from "lucide-react";
import { usePathname } from "next/navigation";

import IdentityMenu from "@/components/auth/IdentityMenu";
import MobileSidebar from "@/components/layout/MobileSidebar";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/documents": "Documents",
  "/projects": "Projects",
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
      <div className="flex min-h-20 items-center justify-between gap-4 px-4 sm:px-6 lg:px-10">
        <div className="flex min-w-0 items-center gap-3">
          <MobileSidebar />

          <div className="min-w-0">
            <p className="hidden text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground sm:block">
              Engineering workspace
            </p>

            <h1 className="truncate text-xl font-semibold tracking-tight text-foreground sm:mt-1 sm:text-2xl">
              {pageTitle}
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <label className="hidden min-w-64 items-center gap-3 rounded-2xl border border-white/70 bg-white/72 px-4 py-3 shadow-sm backdrop-blur-xl md:flex lg:min-w-72">
            <Search
              className="h-5 w-5 shrink-0 text-muted-foreground"
              strokeWidth={1.8}
              aria-hidden="true"
            />

            <input
              type="search"
              placeholder="Cerca in SubstationOS..."
              aria-label="Cerca in SubstationOS"
              className="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
            />
          </label>

          <button
            type="button"
            aria-label="Notifiche"
            className="relative flex h-11 w-11 items-center justify-center rounded-2xl border border-white/70 bg-white/72 text-muted-foreground shadow-sm transition hover:-translate-y-0.5 hover:bg-white hover:text-foreground"
          >
            <Bell
              className="h-5 w-5"
              strokeWidth={1.8}
            />

            <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-blue-500 ring-2 ring-white" />
          </button>

          {/*
            Was a hardcoded name and role until EPIC 30.3. It is now the
            authenticated identity, which is the only version of this
            control that means anything.
          */}
          <IdentityMenu />
        </div>
      </div>
    </header>
  );
}