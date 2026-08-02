"use client";

import { useEffect } from "react";

export function PwaInstaller() {
  useEffect(() => {
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
  }, []);

  return null;
}
