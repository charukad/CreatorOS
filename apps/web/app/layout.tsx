import type { Metadata } from "next";
import { AppShell } from "../components/app-shell";
import { getViewerSession } from "../lib/api";
import "./globals.css";

export const metadata: Metadata = {
  title: "CreatorOS",
  description: "Personal AI social media automation dashboard",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  let session = null;
  let sessionError: string | null = null;

  try {
    session = await getViewerSession();
  } catch (error) {
    sessionError =
      error instanceof Error
        ? error.message
        : "Unable to confirm the configured personal session.";
  }

  return (
    <html lang="en">
      <body>
        <AppShell session={session} sessionError={sessionError}>
          {children}
        </AppShell>
      </body>
    </html>
  );
}
