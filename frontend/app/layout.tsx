import type { Metadata } from "next";
import "./globals.css";
import Header from "./components/Header";

export const metadata: Metadata = {
  title: "MediKiosk – AI Patient Intake & Case-Taking",
  description: "Next-generation Clinical History and Intake Kiosk for Hospital OPDs",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col bg-slate-50 text-slate-900 antialiased selection:bg-teal-100">
        <Header />
        <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 md:p-8">
          {children}
        </main>
        <footer className="bg-white border-t border-slate-200 py-3 px-6 text-center text-xs text-slate-500 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>MediKiosk v1.0 • AI Clinical Intake Assistant • High-Volume OPD Terminal</span>
          <span className="text-slate-400 font-mono">Terminal #01 (General Medicine)</span>
        </footer>
      </body>
    </html>
  );
}
