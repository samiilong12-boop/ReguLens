import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ReguLens — Regulatory Intelligence & Export Readiness",
  description: "B2B SaaS platform for multi-sector regulatory intelligence, document verification, and export readiness.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ar" dir="rtl">
      <body className="antialiased min-h-screen flex flex-col bg-slate-50 text-slate-900">
        {children}
      </body>
    </html>
  );
}
