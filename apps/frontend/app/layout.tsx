import type { Metadata } from "next";

import AppSidebar from "@/components/layout/AppSidebar";
import AppTopBar from "@/components/layout/AppTopBar";
import { Toaster } from "@/components/ui/sonner";

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
        <div className="min-h-screen">
          <AppSidebar />

          <div className="lg:pl-72">
            <AppTopBar />

            <main className="min-h-[calc(100vh-5rem)]">
              {children}
            </main>
          </div>
        </div>

        <Toaster
          position="top-right"
          richColors
          closeButton
        />
      </body>
    </html>
  );
}