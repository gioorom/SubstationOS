"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavigationItem {
  label: string;
  href: string;
  icon: React.ReactNode;
}

const navigationItems: NavigationItem[] = [
  {
    label: "Dashboard",
    href: "/",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        className="h-5 w-5"
      >
        <rect x="3" y="3" width="7" height="7" rx="2" />
        <rect x="14" y="3" width="7" height="7" rx="2" />
        <rect x="3" y="14" width="7" height="7" rx="2" />
        <rect x="14" y="14" width="7" height="7" rx="2" />
      </svg>
    ),
  },
  {
    label: "Documents",
    href: "/documents",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        className="h-5 w-5"
      >
        <path d="M6 3h8l4 4v14H6z" />
        <path d="M14 3v5h5" />
        <path d="M9 13h6" />
        <path d="M9 17h6" />
      </svg>
    ),
  },
  {
    label: "Projects",
    href: "/projects",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        className="h-5 w-5"
      >
        <path d="M3 7h7l2 2h9v11H3z" />
        <path d="M3 7V4h7l2 3" />
      </svg>
    ),
  },
  {
    label: "Commissioning",
    href: "/commissioning",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        className="h-5 w-5"
      >
        <path d="M12 3v7" />
        <path d="M8 7h8" />
        <path d="M5 13h14" />
        <path d="M7 13v8" />
        <path d="M17 13v8" />
      </svg>
    ),
  },
  {
    label: "Relay Testing",
    href: "/relay-testing",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        className="h-5 w-5"
      >
        <path d="M4 18h4l2-12 4 12 2-7 2 7h2" />
      </svg>
    ),
  },
  {
    label: "AI Assistant",
    href: "/ai",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        className="h-5 w-5"
      >
        <rect x="4" y="5" width="16" height="14" rx="4" />
        <path d="M9 10h.01" />
        <path d="M15 10h.01" />
        <path d="M9 15h6" />
        <path d="M12 2v3" />
      </svg>
    ),
  },
  {
    label: "Reports",
    href: "/reports",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        className="h-5 w-5"
      >
        <path d="M5 20V10" />
        <path d="M12 20V4" />
        <path d="M19 20v-7" />
      </svg>
    ),
  },
];

export default function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-72 border-r border-white/60 bg-white/72 px-5 py-6 shadow-[12px_0_40px_rgba(15,23,42,0.04)] backdrop-blur-2xl lg:flex lg:flex-col">
      <div className="flex items-center gap-3 px-2">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg shadow-blue-500/20">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            className="h-6 w-6"
          >
            <path d="M12 2 4 7v10l8 5 8-5V7z" />
            <path d="m8 10 4-3 4 3" />
            <path d="M12 7v10" />
          </svg>
        </div>

        <div>
          <p className="text-base font-semibold tracking-tight text-foreground">
            SubstationOS
          </p>

          <p className="text-xs text-muted-foreground">
            Engineering Intelligence
          </p>
        </div>
      </div>

      <nav className="mt-10 space-y-1.5">
        {navigationItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={[
                "group flex items-center gap-3 rounded-2xl px-4 py-3",
                "text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-primary text-primary-foreground shadow-md shadow-blue-500/15"
                  : "text-muted-foreground hover:bg-white/80 hover:text-foreground",
              ].join(" ")}
            >
              <span
                className={
                  isActive
                    ? "text-primary-foreground"
                    : "text-muted-foreground transition group-hover:text-foreground"
                }
              >
                {item.icon}
              </span>

              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto">
        <div className="rounded-3xl border border-white/70 bg-white/65 p-4 shadow-sm backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-secondary text-sm font-semibold text-secondary-foreground">
              PR
            </div>

            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-foreground">
                Pietro Romano
              </p>

              <p className="truncate text-xs text-muted-foreground">
                Commissioning Engineer
              </p>
            </div>
          </div>

          <Link
            href="/settings"
            className="mt-4 flex items-center justify-center rounded-xl border border-border bg-white/70 px-3 py-2 text-xs font-medium text-muted-foreground transition hover:bg-white hover:text-foreground"
          >
            Impostazioni
          </Link>
        </div>
      </div>
    </aside>
  );
}