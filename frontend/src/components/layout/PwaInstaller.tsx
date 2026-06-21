"use client";

import { useEffect, useState } from "react";
import { Download, X } from "lucide-react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function PwaInstaller() {
  const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Enregistrement du Service Worker
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker
        .register("/sw.js", { scope: "/" })
        .catch((err) => console.warn("[PWA] SW registration failed:", err));
    }

    // Capturer l'événement d'installation
    const handler = (e: Event) => {
      e.preventDefault();
      setInstallPrompt(e as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const handleInstall = async () => {
    if (!installPrompt) return;
    await installPrompt.prompt();
    const { outcome } = await installPrompt.userChoice;
    if (outcome === "accepted") {
      setInstallPrompt(null);
    }
  };

  // Ne rien afficher si pas de prompt ou si déjà rejeté
  if (!installPrompt || dismissed) return null;

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 bg-white border border-gray-200 shadow-lg rounded-2xl px-4 py-3 text-sm max-w-sm w-[calc(100%-2rem)]">
      <div className="w-8 h-8 bg-blue-600 rounded-xl flex items-center justify-center flex-shrink-0">
        <span className="text-white font-bold text-xs">B</span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-gray-900 text-xs">Installer l&apos;application</p>
        <p className="text-gray-500 text-xs truncate">Accès rapide, mode hors ligne</p>
      </div>
      <button
        onClick={handleInstall}
        className="flex items-center gap-1.5 bg-blue-600 text-white text-xs font-semibold px-3 py-1.5 rounded-lg hover:bg-blue-700 transition-colors flex-shrink-0"
      >
        <Download className="w-3 h-3" />
        Installer
      </button>
      <button
        onClick={() => setDismissed(true)}
        className="text-gray-400 hover:text-gray-600 flex-shrink-0"
        aria-label="Fermer"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
