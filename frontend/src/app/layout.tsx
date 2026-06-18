import type { Metadata } from "next";
import { Poppins } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/layout/Providers";

const poppins = Poppins({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-poppins",
  display: "swap",
  preload: true,
});

export const metadata: Metadata = {
  title: "Biloz — Gestion Commerciale",
  description: "Plateforme professionnelle de gestion des commandes, clients, paiements et factures",
  robots: "noindex, nofollow",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" suppressHydrationWarning className={poppins.variable}>
      <head>
        {/*
          Chargé depuis public/ pour éviter la sérialisation RSC qui encode && en &&.
          Ce script s'exécute avant React et intercepte les ChunkLoadError webpack :
          il masque le body + nextjs-portal puis recharge la page en silence.
        */}
        {/* eslint-disable-next-line @next/next/no-sync-scripts */}
        <script src="/chunk-guard.js" />
      </head>
      <body className="font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
