"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  BarChart3,
  Bot,
  Boxes,
  FileText,
  FolderKanban,
  Gauge,
  Settings,
  SlidersHorizontal,
  TestTube2,
  Zap,
} from "lucide-react";

interface NavigationItem {
  label: string;
  href: string;
  icon: React.ComponentType<{
    className?: string;
    strokeWidth?: number;
  }>;
}

const navigationItems: NavigationItem[] = [
  {
    label: "Dashboard",
    href: "/",
    icon: Gauge,
  },
  {
    label: "Documents",
    href: "/documents",
    icon: FileText,
  },
  {
    label: "Projects",
    href: "/projects",
    icon: FolderKanban,
  },
  {
    label: "Commissioning",
    href: "/commissioning",
    icon: Zap,
  },
  {
    label: "Relay Testing",
    href: "/relay-testing",
    icon: TestTube2,
  },
  {
    label: "AI Assistant",
    href: "/ai",
    icon: Bot,
  },
  {
    label: "Reports",
    href: "/reports",
    icon: BarChart3,
  },
];

export default function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-72 border-r border-white/60 bg-white/72 px-5 py-6 shadow-[12px_0_40px_rgba(15,23,42,0.04)] backdrop-blur-2xl lg:flex lg:flex-col">
      <div className="flex items-center gap-3 px-2">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg shadow-blue-500/20">
          <Boxes className="h-6 w-6" strokeWidth={1.8} />
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
          const Icon = item.icon;

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
              <Icon
                className={[
                  "h-5 w-5 transition",
                  isActive
                    ? "text-primary-foreground"
                    : "text-muted-foreground group-hover:text-foreground",
                ].join(" ")}
                strokeWidth={1.8}
              />

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
            className="mt-4 flex items-center justify-center gap-2 rounded-xl border border-border bg-white/70 px-3 py-2 text-xs font-medium text-muted-foreground transition hover:bg-white hover:text-foreground"
          >
            <Settings className="h-4 w-4" strokeWidth={1.8} />
            Impostazioni
          </Link>
        </div>
      </div>

      <div className="pointer-events-none absolute bottom-6 right-5 opacity-0">
        <SlidersHorizontal className="h-4 w-4" />
      </div>
    </aside>
  );
}
