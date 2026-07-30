"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Boxes,
  FileText,
  FolderKanban,
  Gauge,
  Menu,
} from "lucide-react";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

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
    label: "Projects",
    href: "/projects",
    icon: FolderKanban,
  },
  {
    label: "Documents",
    href: "/documents",
    icon: FileText,
  },
];

export default function MobileSidebar() {
  const pathname = usePathname();

  return (
    <Sheet>
      <SheetTrigger
        aria-label="Apri menu"
        className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/70 bg-white/72 text-muted-foreground shadow-sm transition hover:bg-white hover:text-foreground lg:hidden"
      >
        <Menu className="h-5 w-5" strokeWidth={1.8} />
      </SheetTrigger>

      <SheetContent
        side="left"
        className="w-[310px] border-r border-white/60 bg-white/92 p-0 backdrop-blur-2xl"
      >
        <SheetHeader className="sr-only">
          <SheetTitle>Menu principale</SheetTitle>
        </SheetHeader>

        <div className="flex h-full flex-col px-5 py-6">
          <div className="flex items-center gap-3 px-2">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg shadow-blue-500/20">
              <Boxes
                className="h-6 w-6"
                strokeWidth={1.8}
              />
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
                      : "text-muted-foreground hover:bg-white hover:text-foreground",
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

          <div className="mt-auto rounded-3xl border border-white/70 bg-white/70 p-4 shadow-sm">
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

          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}