import type { Metadata } from "next";

import RequireSession from "@/components/auth/RequireSession";
import AppSidebar from "@/components/layout/AppSidebar";
import AppTopBar from "@/components/layout/AppTopBar";
import { Toaster } from "@/components/ui/sonner";
import { SessionProvider } from "@/hooks/useSession";

import "./globals.css";

export const metadata: Metadata = {
  title: "SubstationOS",
  description:
    "Engineering intelligence platform for substations and commissioning.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="it">
      <body>
        {/*
          One provider, one session read per page load, and one guard
          around the whole authenticated application. A screen added next
          year is protected because nobody did anything - the same
          deny-by-default shape the backend's middleware has.

          The guard is usability, not security: the backend refuses every
          request without a session regardless of what renders here.
        */}
        <SessionProvider>
          <RequireSession>
            <div className="min-h-screen">
              <AppSidebar />

              <div className="lg:pl-72">
                <AppTopBar />

                <main className="min-h-[calc(100vh-5rem)]">
                  {children}
                </main>
              </div>
            </div>
          </RequireSession>
        </SessionProvider>

        <Toaster
          position="top-right"
          richColors
          closeButton
        />
      </body>
    </html>
  );
}