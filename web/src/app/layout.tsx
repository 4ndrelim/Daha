import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import { QueryProvider } from "@/components/providers/query-provider";
import { BACKGROUND, THEME } from "@/lib/theme";
import "./globals.css";

const inter = Inter({ variable: "--font-sans", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "DAHA · share stuff across campus",
  description: "Lend, borrow, give away and swap everyday things with people in your dorm.",
  applicationName: "DAHA",
  icons: {
    icon: [
      { url: "/icons/favicon-48.png", sizes: "48x48", type: "image/png" },
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180" }],
  },
  // iPhone "Add to Home Screen": open full-screen with a status bar that matches our background.
  appleWebApp: { capable: true, title: "DAHA", statusBarStyle: "default" },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: BACKGROUND[THEME],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" data-theme={THEME} className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-dvh bg-background">
        <QueryProvider>
          {children}
          <Toaster theme="light" position="top-center" richColors />
        </QueryProvider>
      </body>
    </html>
  );
}
