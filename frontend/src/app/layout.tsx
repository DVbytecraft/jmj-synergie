import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/layout/Providers";
import { PwaInstaller } from "@/components/layout/PwaInstaller";

export const metadata: Metadata = {
  title: "JMJ Synergie — Gestion Commerciale",
  description: "Plateforme professionnelle de gestion des commandes, clients, paiements et factures",
  robots: "noindex, nofollow",
  icons: {
    icon: [
      { url: "/favicon.ico" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    shortcut: "/favicon.ico",
    apple: "/icon-192.png",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <head>
        {/*
          Chargé depuis public/ pour éviter la sérialisation RSC qui encode && en &&.
          Ce script s'exécute avant React et intercepte les ChunkLoadError webpack :
          il masque le body + nextjs-portal puis recharge la page en silence.
        */}
        {/* eslint-disable-next-line @next/next/no-sync-scripts */}
        <script src="/chunk-guard.js" />
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#1a56db" />
      </head>
      <body className="font-sans">
        <Providers>{children}</Providers>
        <PwaInstaller />
      </body>
    </html>
  );
}
