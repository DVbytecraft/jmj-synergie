"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { quotesApi } from "@/lib/api/quotes";
import type { QuoteStatus } from "@/types";
import { Plus, Search, FileText, ClipboardList } from "lucide-react";
import Link from "next/link";
import { QuoteStatusBadge } from "@/components/ui/QuoteStatusBadge";
import { formatCents } from "@/lib/utils/money";
import { formatDateFr } from "@/lib/utils/format-dates";

const STATUTS: { value: QuoteStatus | ""; label: string }[] = [
  { value: "",          label: "Tous" },
  { value: "draft",     label: "Brouillon" },
  { value: "sent",      label: "Envoyé" },
  { value: "accepted",  label: "Accepté" },
  { value: "rejected",  label: "Refusé" },
  { value: "expired",   label: "Expiré" },
  { value: "converted", label: "Converti" },
];

function SkeletonRow() {
  return (
    <tr>
      <td className="table-cell"><div className="skeleton h-4 w-28 rounded" /></td>
      <td className="table-cell"><div className="skeleton h-4 w-24 rounded" /></td>
      <td className="table-cell"><div className="skeleton h-5 w-20 rounded-full" /></td>
      <td className="table-cell text-right"><div className="skeleton h-4 w-24 rounded ml-auto" /></td>
      <td className="table-cell text-right"><div className="skeleton h-4 w-24 rounded ml-auto" /></td>
      <td className="table-cell"><div className="skeleton h-4 w-20 rounded" /></td>
      <td className="table-cell"><div className="skeleton h-7 w-16 rounded mx-auto" /></td>
    </tr>
  );
}

export default function DevisPage() {
  const [search, setSearch] = useState("");
  const [statut, setStatut] = useState<QuoteStatus | "">("");
  const [page, setPage] = useState(0);
  const limit = 20;

  const { data, isLoading } = useQuery({
    queryKey: ["quotes", page, statut, search],
    queryFn: () =>
      quotesApi.list({
        skip: page * limit,
        limit,
        status: statut || undefined,
        search: search || undefined,
      }),
  });

  const quotes = data?.items ?? [];

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Devis</h1>
          <p className="page-subtitle">{data?.total ?? 0} devis au total</p>
        </div>
        <Link href="/devis/new" className="btn-primary flex-shrink-0">
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">Nouveau devis</span>
          <span className="sm:hidden">Nouveau</span>
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative sm:max-w-xs w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            placeholder="Numéro de devis…"
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
                <th className="table-header">N° devis</th>
                <th className="table-header">Client</th>
                <th className="table-header">Statut</th>
                <th className="table-header text-right">HT</th>
                <th className="table-header text-right">TTC</th>
                <th className="table-header">Date</th>
                <th className="table-header text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {isLoading ? (
                Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} />)
              ) : quotes.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-0">
                    <div className="empty-state py-14">
                      <ClipboardList className="empty-state-icon" />
                      <p className="empty-state-title">Aucun devis trouvé</p>
                      <p className="empty-state-desc">
                        {statut || search ? "Modifiez vos filtres" : "Créez votre premier devis"}
                      </p>
                      {!statut && !search && (
                        <Link href="/devis/new" className="btn-primary btn-sm">
                          <Plus className="w-3.5 h-3.5" />
                          Nouveau devis
                        </Link>
                      )}
                    </div>
                  </td>
                </tr>
              ) : (
                quotes.map((q) => (
                  <tr key={q.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="table-cell">
                      <Link
                        href={`/devis/${q.id}`}
                        className="font-mono font-medium text-blue-600 hover:text-blue-700"
                      >
                        {q.quote_number}
                      </Link>
                    </td>
                    <td className="table-cell text-slate-600 max-w-[140px] truncate">
                      {q.client_name ?? "—"}
                    </td>
                    <td className="table-cell">
                      <QuoteStatusBadge status={q.status} />
                    </td>
                    <td className="table-cell text-right tabular-nums">
                      {formatCents(q.subtotal_cents, q.currency)}
                    </td>
                    <td className="table-cell text-right tabular-nums font-semibold text-slate-900">
                      {formatCents(q.total_cents, q.currency)}
                    </td>
                    <td className="table-cell text-slate-400 tabular-nums">
                      {formatDateFr(q.created_at)}
                    </td>
                    <td className="table-cell">
                      <div className="flex items-center justify-center gap-1">
                        <Link
                          href={`/devis/${q.id}`}
                          className="btn-icon p-1.5"
                          title="Voir le détail"
                        >
                          <FileText className="w-4 h-4" />
                        </Link>
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
