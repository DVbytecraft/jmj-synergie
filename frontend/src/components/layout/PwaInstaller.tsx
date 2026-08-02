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
    // Disable all service workers and clear old PWA caches.
    // This app must prefer fresh production assets over offline caching.
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.getRegistrations().then((registrations) => {
        registrations.forEach((registration) => {
          void registration.unregister();
        });
      });
    }

    if ("caches" in window) {
      caches.keys().then((keys) => {
        keys
          .filter((key) => key.startsWith("jmj-synergie"))
          .forEach((key) => {
            void caches.delete(key);
          });
      });
    }

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

  if (!installPrompt || dismissed) return null;

  return (
    <div className="fixed bottom-4 left-1/2 z-50 flex w-[calc(100%-2rem)] max-w-sm -translate-x-1/2 items-center gap-3 rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm shadow-lg">
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl bg-blue-600">
        <span className="text-xs font-bold text-white">JS</span>
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-semibold text-gray-900">Installer l&apos;application</p>
        <p className="truncate text-xs text-gray-500">Acces rapide depuis votre appareil</p>
      </div>
      <button
        onClick={handleInstall}
        className="flex flex-shrink-0 items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-blue-700"
      >
        <Download className="h-3 w-3" />
        Installer
      </button>
      <button
        onClick={() => setDismissed(true)}
        className="flex-shrink-0 text-gray-400 hover:text-gray-600"
        aria-label="Fermer"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
