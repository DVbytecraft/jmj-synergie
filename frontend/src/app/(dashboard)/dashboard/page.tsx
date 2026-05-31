"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { usersApi } from "@/lib/api/users";
import { formatCents } from "@/lib/utils/money";
import { formatDateFr } from "@/lib/utils/format-dates";
import { Users, ShoppingCart, CreditCard, TrendingUp, ArrowRight } from "lucide-react";
import Link from "next/link";
import { OrderStatusBadge } from "@/components/ui/OrderStatusBadge";
import { OnboardingBanner } from "@/components/ui/OnboardingBanner";

// ── Types ────────────────────────────────────────────────────────────────────

interface OrdersByStatus {
  draft:       number;
  confirmed:   number;
  in_progress: number;
  delivered:   number;
  cancelled:   number;
  refunded:    number;
}

interface RecentOrder {
  id:           string;
  order_number: string;
  status:       string;
  total_cents:  number;
  currency:     string;
  created_at:   string;
}

interface DashboardKPI {
  total_orders:      number;
  total_clients:     number;
  ca_total_cents:    number;
  total_paid_cents:  number;
  orders_by_status:  OrdersByStatus;
  recent_orders:     RecentOrder[];
}

// ── Skeleton ─────────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="card p-5 flex items-center gap-4">
      <div className="skeleton w-11 h-11 rounded-xl" />
      <div className="flex-1 space-y-2">
        <div className="skeleton h-3 w-24 rounded" />
        <div className="skeleton h-6 w-32 rounded" />
        <div className="skeleton h-2.5 w-20 rounded" />
      </div>
    </div>
  );
}

// ── KPI card ──────────────────────────────────────────────────────────────────

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  iconBg,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  sub?: string;
  iconBg: string;
}) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${iconBg}`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="stat-label">{label}</p>
        <p className="stat-value">{value}</p>
        {sub && <p className="stat-sub">{sub}</p>}
      </div>
    </div>
  );
}

// ── Status bar config ─────────────────────────────────────────────────────────

const STATUS_CONFIG = [
  { key: "draft",       label: "Brouillon", color: "bg-slate-400" },
  { key: "confirmed",   label: "Confirmée", color: "bg-blue-500" },
  { key: "in_progress", label: "En cours",  color: "bg-amber-400" },
  { key: "delivered",   label: "Livrée",    color: "bg-emerald-500" },
  { key: "cancelled",   label: "Annulée",   color: "bg-red-400" },
] as const;

// ── Page ─────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { data: kpi, isLoading } = useQuery<DashboardKPI>({
    queryKey: ["dashboard", "kpi"],
    queryFn: () => apiClient.get<DashboardKPI>("/orders/kpi").then((r) => r.data),
    staleTime: 60_000,
  });

  const { data: profile } = useQuery({
    queryKey: ["users", "me", "issuer-profile"],
    queryFn: usersApi.getMyIssuerProfile,
    staleTime: 5 * 60_000,
  });

  const currency = kpi?.recent_orders[0]?.currency ?? "XAF";

  return (
    <div className="space-y-6">
      {/* ── Onboarding — shown once to new users ── */}
      <OnboardingBanner
        hasLogo={!!profile?.logo_path}
        hasDisplayName={!!(profile?.display_name || profile?.company_name)}
        hasCompanyName={!!(profile?.display_name || profile?.company_name)}
        hasSignature={!!(profile?.signature_path || profile?.signature_text)}
      />

      {/* ── KPI row ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)
        ) : (
          <>
            <StatCard
              icon={Users}
              label="Clients actifs"
              value={kpi?.total_clients ?? 0}
              sub="Comptes enregistrés"
              iconBg="bg-blue-600"
            />
            <StatCard
              icon={ShoppingCart}
              label="Commandes"
              value={kpi?.total_orders ?? 0}
              sub={`${kpi?.orders_by_status.draft ?? 0} en attente`}
              iconBg="bg-violet-600"
            />
            <StatCard
              icon={TrendingUp}
              label="CA encaissé"
              value={formatCents(kpi?.ca_total_cents ?? 0, currency)}
              sub="Montants collectés"
              iconBg="bg-emerald-600"
            />
            <StatCard
              icon={CreditCard}
              label="Total payé"
              value={formatCents(kpi?.total_paid_cents ?? 0, currency)}
              sub="Paiements complétés"
              iconBg="bg-orange-500"
            />
          </>
        )}
      </div>

      {/* ── Bottom row ── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Recent orders */}
        <div className="xl:col-span-2 card overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
            <h2 className="font-semibold text-slate-800">Dernières commandes</h2>
            <Link
              href="/commandes"
              className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 font-medium transition-colors"
            >
              Voir tout <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="overflow-x-auto">
            {isLoading ? (
              <div className="divide-y divide-slate-50">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-4 px-5 py-3.5">
                    <div className="skeleton h-4 w-24 rounded" />
                    <div className="skeleton h-5 w-20 rounded-full" />
                    <div className="skeleton h-4 w-28 rounded ml-auto" />
                    <div className="skeleton h-4 w-16 rounded" />
                  </div>
                ))}
              </div>
            ) : (kpi?.recent_orders.length ?? 0) === 0 ? (
              <div className="empty-state">
                <ShoppingCart className="empty-state-icon" />
                <p className="empty-state-title">Aucune commande</p>
                <p className="empty-state-desc">Les commandes apparaîtront ici</p>
                <Link href="/commandes/new" className="btn-primary btn-sm">
                  Créer une commande
                </Link>
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b border-slate-100">
                  <tr>
                    <th className="table-header">N° commande</th>
                    <th className="table-header">Statut</th>
                    <th className="table-header text-right">Encaissé</th>
                    <th className="table-header">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {kpi?.recent_orders.map((c) => (
                    <tr key={c.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="table-cell">
                        <Link
                          href={`/commandes/${c.id}`}
                          className="font-mono text-blue-600 hover:text-blue-700 font-medium"
                        >
                          {c.order_number}
                        </Link>
                      </td>
                      <td className="table-cell">
                        <OrderStatusBadge status={c.status} />
                      </td>
                      <td className="table-cell text-right font-semibold text-slate-900">
                        {formatCents(c.total_cents, c.currency)}
                      </td>
                      <td className="table-cell text-slate-400 tabular-nums">
                        {formatDateFr(c.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Status breakdown */}
        <div className="card p-5 flex flex-col gap-5">
          <h2 className="font-semibold text-slate-800">Répartition des statuts</h2>

          {isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="space-y-1.5">
                  <div className="skeleton h-3 w-28 rounded" />
                  <div className="skeleton h-2 rounded-full" />
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-3.5">
              {STATUS_CONFIG.map(({ key, label, color }) => {
                const count = kpi?.orders_by_status[key] ?? 0;
                const total = kpi?.total_orders || 1;
                const pct = Math.round((count / total) * 100);
                return (
                  <div key={key}>
                    <div className="flex justify-between items-center text-sm mb-1.5">
                      <span className="font-medium text-slate-700">{label}</span>
                      <span className="text-slate-400 tabular-nums text-xs">
                        {count} · {pct}%
                      </span>
                    </div>
                    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${color}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="divider" />
          <div className="space-y-2">
            <Link href="/commandes/new" className="btn-primary w-full">
              <ShoppingCart className="w-4 h-4" />
              Nouvelle commande
            </Link>
            <Link href="/clients/new" className="btn-secondary w-full">
              <Users className="w-4 h-4" />
              Nouveau client
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
