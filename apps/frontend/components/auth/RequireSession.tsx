"use client";

import type { ReactNode } from "react";

import LoginForm from "@/components/auth/LoginForm";
import { Skeleton } from "@/components/ui/skeleton";
import { useSession } from "@/hooks/useSession";

/**
 * The route guard.
 *
 * Wraps the whole authenticated application once, in the root layout,
 * rather than being remembered on each page. A screen added next year is
 * protected because nobody did anything - the same deny-by-default shape
 * the backend's middleware has, for the same reason.
 *
 * **This is a usability guard, not a security boundary.** Nothing here
 * protects data: the backend refuses every request without a session,
 * and would do so whether or not this component existed. What it
 * prevents is an application that renders empty screens and error
 * banners to somebody who simply needs to sign in.
 *
 * The three states are kept apart deliberately. Rendering the login form
 * during the first session read would sign every user out, visibly, on
 * every page load.
 */
export default function RequireSession({
  children,
}: {
  children: ReactNode;
}) {
  const { status } = useSession();

  if (status === "loading") {
    return (
      <div
        className="flex min-h-screen items-center justify-center p-8"
        aria-busy="true"
      >
        <span className="sr-only">Verifica della sessione in corso…</span>
        <Skeleton className="h-64 w-full max-w-sm rounded-3xl" />
      </div>
    );
  }

  if (status === "anonymous") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
        <LoginForm />
      </main>
    );
  }

  return <>{children}</>;
}
