"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { commandesApi } from "@/lib/api/commandes";
import type { OrderStatus } from "@/types";
import { Plus, Search, FileText, CreditCard, ShoppingCart } from "lucide-react";
import Link from "next/link";
import { OrderStatusBadge } from "@/components/ui/OrderStatusBadge";
import { formatCents } from "@/lib/utils/money";

const STATUTS: { value: OrderStatus | ""; label: string }[] = [
  { value: "",            label: "Toutes" },
  { value: "draft",       label: "Brouillon" },
  { value: "confirmed",   label: "Confirmée" },
  { value: "in_progress", label: "En cours" },
  { value: "partially_delivered", label: "Reliquat" },
  { value: "delivered",   label: "Livrée" },
  { value: "cancelled",   label: "Annulée" },
  { value: "refunded",    label: "Remboursée" },
];

function SkeletonRow() {
  return (
    <tr>
      <td className="table-cell"><div className="skeleton h-4 w-28 rounded" /></td>
      <td className="table-cell"><div className="skeleton h-5 w-24 rounded-full" /></td>
      <td className="table-cell text-right"><div className="skeleton h-4 w-24 rounded ml-auto" /></td>
      <td className="table-cell text-right"><div className="skeleton h-4 w-16 rounded ml-auto" /></td>
      <td className="table-cell text-right"><div className="skeleton h-4 w-24 rounded ml-auto" /></td>
      <td className="table-cell"><div className="skeleton h-4 w-20 rounded" /></td>
      <td className="table-cell"><div className="skeleton h-7 w-16 rounded mx-auto" /></td>
    </tr>
  );
}

export default function CommandesPage() {
  const [search, setSearch] = useState("");
  const [statut, setStatut] = useState<OrderStatus | "">("");
  const [page, setPage] = useState(0);
  const limit = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["commandes", page, statut],
    queryFn: () =>
      commandesApi.list({ skip: page * limit, limit, status: statut || undefined }),
  });

  const filtered = data?.items.filter(
    (c) =>
      c.order_number.toLowerCase().includes(search.toLowerCase()) ||
      c.client_id.toLowerCase().includes(search.toLowerCase())
  ) ?? [];

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Commandes</h1>
          <p className="page-subtitle">{data?.total ?? 0} commandes au total</p>
        </div>
        <Link href="/commandes/new" className="btn-primary flex-shrink-0">
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">Nouvelle commande</span>
          <span className="sm:hidden">Nouveau</span>
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative sm:max-w-xs w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Numéro ou client…"
            className="input pl-10"
          />
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {STATUTS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => { setStatut(value); setPage(0); }}
              className={statut === value ? "filter-tab-active" : "filter-tab-inactive"}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-100">
              <tr>
                <th className="table-header">N° commande</th>
                <th className="table-header">Statut</th>
                <th className="table-header text-right">HT</th>
                <th className="table-header text-right">TVA</th>
                <th className="table-header text-right">TTC</th>
                <th className="table-header">Date</th>
                <th className="table-header text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {isLoading ? (
                Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} />)
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <div className="empty-state py-14">
                      <ShoppingCart className="empty-state-icon" />
                      <p className="empty-state-title">Aucune commande trouvée</p>
                      <p className="empty-state-desc">
                        {statut || search ? "Modifiez vos filtres" : "Créez votre première commande"}
                      </p>
                      {!statut && !search && (
                        <Link href="/commandes/new" className="btn-primary btn-sm">
                          <Plus className="w-3.5 h-3.5" />
                          Nouvelle commande
                        </Link>
                      )}
                    </div>
                  </td>
                </tr>
              ) : (
                filtered.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="table-cell">
                      <Link
                        href={`/commandes/${c.id}`}
                        className="font-mono font-medium text-blue-600 hover:text-blue-700"
                      >
                        {c.order_number}
                      </Link>
                    </td>
                    <td className="table-cell">
                      <OrderStatusBadge status={c.status} />
                    </td>
                    <td className="table-cell text-right tabular-nums">
                      {formatCents(c.subtotal_cents, c.currency)}
                    </td>
                    <td className="table-cell text-right tabular-nums text-slate-400">
                      {formatCents(c.tax_cents, c.currency)}
                    </td>
                    <td className="table-cell text-right tabular-nums font-semibold text-slate-900">
                      {formatCents(c.total_cents, c.currency)}
                    </td>
                    <td className="table-cell text-slate-400 tabular-nums">
                      {new Date(c.created_at).toLocaleDateString("fr-FR")}
                    </td>
                    <td className="table-cell">
                      <div className="flex items-center justify-center gap-1">
                        <Link
                          href={`/commandes/${c.id}`}
                          className="btn-icon p-1.5"
                          title="Voir le détail"
                        >
                          <FileText className="w-4 h-4" />
                        </Link>
                        {c.status === "confirmed" && (
                          <Link
                            href={`/paiements?order_id=${c.id}`}
                            className="p-1.5 rounded-lg text-emerald-600 hover:bg-emerald-50 transition-colors"
                            title="Enregistrer un paiement"
                          >
                            <CreditCard className="w-4 h-4" />
                          </Link>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-5 py-3.5 border-t border-slate-100 bg-slate-50/40">
          <p className="text-sm text-slate-400">
            {data?.total
              ? `${page * limit + 1}–${Math.min((page + 1) * limit, data.total)} sur ${data.total}`
              : "0 résultat"}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="pagination-btn"
            >
              Précédent
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={(page + 1) * limit >= (data?.total ?? 0)}
              className="pagination-btn"
            >
              Suivant
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
