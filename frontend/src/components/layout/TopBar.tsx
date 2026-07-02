"use client";

import { Menu } from "lucide-react";
import { useAuthStore } from "@/store/auth.store";
import { useSidebar } from "./sidebar-context";
import { usePathname } from "next/navigation";
import { NotificationBell } from "@/components/ui/NotificationBell";

const PAGE_TITLES: Record<string, string> = {
  "/dashboard":              "Tableau de bord",
  "/clients":                "Clients",
  "/commandes":              "Commandes",
  "/devis":                  "Devis",
  "/produits":               "Produits",
  "/stock":                  "Stock",
  "/paiements":              "Paiements",
  "/documents":              "Documents",
  "/scan":                   "Scan de facture",
  "/journal/paiements":      "Journal des paiements",
  "/journal/remboursements": "Journal des remboursements",
  "/admin/users":            "Gestion des utilisateurs",
  "/settings":               "Paramètres",
  "/profil":                 "Mon profil",
  "/pdf":                    "Génération de documents",
};

function getPageTitle(pathname: string): string {
  if (PAGE_TITLES[pathname]) return PAGE_TITLES[pathname];
  for (const [key, label] of Object.entries(PAGE_TITLES)) {
    if (pathname.startsWith(key + "/")) return label;
  }
  return "";
}

export function TopBar() {
  const { user } = useAuthStore();
  const { toggle } = useSidebar();
  const pathname = usePathname();
  const title = getPageTitle(pathname);

  return (
    <header className="h-16 bg-white border-b border-slate-200 flex items-center gap-3 px-4 lg:px-6 flex-shrink-0">
      {/* Hamburger — mobile only */}
      <button
        onClick={toggle}
        className="btn-icon lg:hidden flex-shrink-0"
        aria-label="Ouvrir le menu"
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Page title */}
      <div className="flex-1 min-w-0">
        {title && (
          <h1 className="text-base font-semibold text-slate-800 truncate">{title}</h1>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1.5">
        <NotificationBell />

        {/* Separator */}
        <div className="w-px h-6 bg-slate-200 mx-1" />

        {/* User chip */}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-700 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
            {user?.name?.charAt(0).toUpperCase() ?? "U"}
          </div>
          <span className="hidden sm:block text-sm font-medium text-slate-700 leading-none">
            {user?.name}
          </span>
        </div>
      </div>
    </header>
  );
}
