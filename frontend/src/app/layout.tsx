import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { Footer } from "@/components/Footer";
import { Navbar } from "@/components/Navbar";
import { StoreProvider } from "@/context/StoreProvider";

import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "Haus&Home — Modern Household Furniture",
    template: "%s | Haus&Home",
  },
  description:
    "Shop sofas, beds, tables, chairs and storage. Quality household furniture with fast delivery.",
  openGraph: {
    type: "website",
    title: "Haus&Home — Modern Household Furniture",
    description: "Quality household furniture with fast delivery.",
    url: siteUrl,
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="flex min-h-screen flex-col">
        <StoreProvider>
          <Navbar />
          <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
          <Footer />
        </StoreProvider>
      </body>
    </html>
  );
}
