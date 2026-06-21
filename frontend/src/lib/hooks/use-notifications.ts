/**
 * Hook React — connexion SSE aux notifications temps réel.
 * Maintient une liste des 20 dernières notifications et un compteur non lu.
 */
"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth.store";

export interface NotificationItem {
  id: string;
  type: string;
  message?: string;
  amount_cents?: number;
  receivedAt: Date;
  read: boolean;
}

const MAX_NOTIFICATIONS = 20;

export function useNotifications() {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const esRef = useRef<EventSource | null>(null);
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((s) => s.accessToken);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const markAllRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  useEffect(() => {
    if (!accessToken) return;

    // On passe le token en query param car EventSource ne supporte pas les headers
    const url = `/api/v1/notifications/stream`;

    const es = new EventSource(url, { withCredentials: true });
    esRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as Record<string, unknown>;

        // Ignorer les events système (connected, error…)
        if (data.type === "connected" || data.error) return;

        const item: NotificationItem = {
          id: `${Date.now()}-${Math.random()}`,
          type: String(data.type ?? "notification"),
          message: data.message ? String(data.message) : undefined,
          amount_cents: typeof data.amount_cents === "number" ? data.amount_cents : undefined,
          receivedAt: new Date(),
          read: false,
        };

        setNotifications((prev) => [item, ...prev].slice(0, MAX_NOTIFICATIONS));

        // Invalider les requêtes liées aux paiements pour rafraîchir les listes
        if (data.type === "payment.new") {
          queryClient.invalidateQueries({ queryKey: ["journal-paiements"] });
          queryClient.invalidateQueries({ queryKey: ["paiements"] });
        }

        console.info("[SSE notification]", item);
      } catch {
        // Données non-JSON (ping keepalive, etc.) — ignorer silencieusement
      }
    };

    es.onerror = () => {
      // La reconnexion est automatique via l'EventSource browser API
      console.warn("[SSE] Connexion perdue, tentative de reconnexion…");
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [accessToken, queryClient]);

  return { notifications, unreadCount, markAllRead };
}
