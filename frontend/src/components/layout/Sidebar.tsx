"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Users, ShoppingCart, FileText,
  CreditCard, ScanLine, Settings, LogOut, Package,
  BookOpen, RotateCcw, ShieldCheck, X, UserCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/auth.store";
import { apiClient } from "@/lib/api/client";
import { useRouter } from "next/navigation";
import { useSidebar } from "./sidebar-context";
import type { RoleUtilisateur } from "@/types";

interface NavItem {
  href: string;
  icon: React.ElementType;
  label: string;
  roles?: RoleUtilisateur[];
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    label: "Principal",
    items: [
      { href: "/dashboard", icon: LayoutDashboard, label: "Tableau de bord" },
    ],
  },
  {
    label: "Commercial",
    items: [
      { href: "/clients",   icon: Users,        label: "Clients" },
      { href: "/commandes", icon: ShoppingCart,  label: "Commandes" },
      { href: "/produits",  icon: Package,       label: "Produits", roles: ["super_admin", "admin", "manager"] },
    ],
  },
  {
    label: "Finance",
    items: [
      { href: "/paiements",              icon: CreditCard, label: "Paiements" },
      { href: "/journal/paiements",      icon: BookOpen,   label: "Journal paiements" },
      { href: "/journal/remboursements", icon: RotateCcw,  label: "Remboursements" },
    ],
  },
  {
    label: "Documents",
    items: [
      { href: "/documents", icon: FileText, label: "Documents" },
      { href: "/scan",      icon: ScanLine, label: "Scan facture" },
    ],
  },
  {
    label: "Administration",
    items: [
      { href: "/admin/users", icon: ShieldCheck, label: "Panneau admin", roles: ["super_admin"] },
    ],
  },
];

const ROLE_LABELS: Record<string, string> = {
  super_admin: "Super Admin",
  admin:       "Administrateur",
  manager:     "Manager",
  operator:    "Opérateur",
};

function NavContent({ onClose }: { onClose?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { clearAuth, user } = useAuthStore();

  const handleLogout = async () => {
    try {
      // Revoke the HttpOnly 'rt' cookie on the server before clearing local state
      await apiClient.post("/auth/logout");
    } catch {
      // Server unavailable — still clear client-side auth
    }
    clearAuth();
    router.replace("/login");
  };

  return (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center justify-between px-5 h-16 border-b border-white/5 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center flex-shrink-0 shadow-lg">
            <span className="text-white font-bold text-xs tracking-tight">B</span>
          </div>
          <div>
            <p className="text-white text-sm font-semibold leading-none">Biloz</p>
            <p className="text-slate-500 text-xs mt-0.5">Gestion commerciale</p>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-white/5 transition-colors lg:hidden"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-5 px-3 space-y-5">
        {navGroups.map((group) => {
          const visibleItems = group.items.filter(
            ({ roles }) => !roles || (user?.role && roles.includes(user.role as RoleUtilisateur))
          );
          if (visibleItems.length === 0) return null;
          return (
            <div key={group.label}>
              <p className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-600">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {visibleItems.map(({ href, icon: Icon, label }) => {
                  const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href + "/"));
                  return (
                    <Link
                      key={href}
                      href={href}
                      onClick={onClose}
                      className={cn(
                        "relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150 group",
                        active
                          ? "bg-white/8 text-white"
                          : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                      )}
                    >
                      {active && (
                        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-blue-400 rounded-r-full" />
                      )}
                      <Icon
                        className={cn(
                          "w-4 h-4 flex-shrink-0 transition-colors",
                          active ? "text-blue-400" : "text-slate-500 group-hover:text-slate-300"
                        )}
                      />
                      <span className="truncate">{label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-3 pb-4 border-t border-white/5 pt-3 flex-shrink-0 space-y-0.5">
        <Link
          href="/profil"
          onClick={onClose}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-400 hover:bg-white/5 hover:text-slate-200 transition-colors"
        >
          <UserCircle className="w-4 h-4 flex-shrink-0 text-slate-500" />
          Mon profil
        </Link>
        <Link
          href="/settings"
          onClick={onClose}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-400 hover:bg-white/5 hover:text-slate-200 transition-colors"
        >
          <Settings className="w-4 h-4 flex-shrink-0 text-slate-500" />
          Paramètres
        </Link>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-400 hover:bg-red-500/10 hover:text-red-400 transition-colors"
        >
          <LogOut className="w-4 h-4 flex-shrink-0" />
          Déconnexion
        </button>

        {/* User chip */}
        <div className="flex items-center gap-3 px-3 py-2.5 mt-1 bg-white/5 rounded-lg">
          <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-700 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
            {user?.name?.charAt(0).toUpperCase() ?? "U"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-white text-sm font-medium truncate leading-none">
              {user?.name ?? "Utilisateur"}
            </p>
            <p className="text-slate-500 text-xs mt-0.5">
              {ROLE_LABELS[user?.role ?? ""] ?? user?.role ?? ""}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export function Sidebar() {
  const { isOpen, close } = useSidebar();

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden animate-fade-in"
          onClick={close}
        />
      )}

      {/* Mobile drawer */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 bg-slate-900 flex flex-col shadow-2xl lg:hidden transition-transform duration-250 ease-out",
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <NavContent onClose={close} />
      </aside>

      {/* Desktop sidebar — always visible */}
      <aside className="hidden lg:flex w-64 bg-slate-900 flex-col flex-shrink-0 h-full">
        <NavContent />
      </aside>
    </>
  );
}
