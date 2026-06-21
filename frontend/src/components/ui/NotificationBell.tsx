"use client";

import { useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";
import { useNotifications } from "@/lib/hooks/use-notifications";
import { formatCents } from "@/lib/utils/money";

export function NotificationBell() {
  const { notifications, unreadCount, markAllRead } = useNotifications();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Fermer au clic extérieur
  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const handleToggle = () => {
    setOpen((v) => {
      if (!v && unreadCount > 0) markAllRead();
      return !v;
    });
  };

  const recent = notifications.slice(0, 5);

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={handleToggle}
        className="btn-icon relative"
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} non lues)` : ""}`}
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[1.1rem] h-[1.1rem] bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-0.5 leading-none">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-10 w-80 bg-white rounded-xl shadow-lg border border-gray-100 z-50 overflow-hidden">
          <div className="px-4 py-2.5 border-b border-gray-100 flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-800">Notifications</span>
            {notifications.length > 0 && (
              <button
                onClick={markAllRead}
                className="text-xs text-blue-600 hover:underline"
              >
                Tout marquer lu
              </button>
            )}
          </div>

          <ul className="divide-y divide-gray-50 max-h-72 overflow-y-auto">
            {recent.length === 0 ? (
              <li className="px-4 py-6 text-center text-sm text-gray-400">
                Aucune notification récente
              </li>
            ) : (
              recent.map((n) => (
                <li
                  key={n.id}
                  className={`px-4 py-3 flex flex-col gap-0.5 ${!n.read ? "bg-blue-50/50" : ""}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-blue-700 uppercase tracking-wide">
                      {n.type.replace(".", " ")}
                    </span>
                    <span className="text-xs text-gray-400 whitespace-nowrap">
                      {n.receivedAt.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                  {n.message && (
                    <p className="text-sm text-gray-700 leading-snug">{n.message}</p>
                  )}
                  {n.amount_cents !== undefined && (
                    <p className="text-sm font-semibold text-emerald-700">
                      {formatCents(n.amount_cents)}
                    </p>
                  )}
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
