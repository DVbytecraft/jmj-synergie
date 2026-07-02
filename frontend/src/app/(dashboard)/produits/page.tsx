"use client";

import { useState } from "react";
import { useProduits, useDeleteProduit } from "@/lib/hooks/use-produits";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";
import { Plus, Search, Package, Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
import type { Product } from "@/types";
import { formatCents } from "@/lib/utils/money";

function SkeletonRow() {
  return (
    <tr>
      {Array.from({ length: 8 }).map((_, i) => (
        <td key={i} className="table-cell">
          <div className="skeleton h-4 w-full max-w-[100px] rounded" />
        </td>
      ))}
    </tr>
  );
}

function ProduitRow({
  produit,
  onDelete,
}: {
  produit: Product;
  onDelete: () => void;
}) {
  const [confirming, setConfirming] = useState(false);

  return (
    <tr className={`hover:bg-slate-50/60 transition-colors ${produit.status !== "active" ? "opacity-50" : ""}`}>
      <td className="table-cell font-mono text-xs text-slate-400">{produit.code}</td>
      <td className="table-cell">
        <p className="font-medium text-slate-900">{produit.name}</p>
        {produit.category && (
          <p className="text-xs text-slate-400 mt-0.5">{produit.category}</p>
        )}
      </td>
      <td className="table-cell text-right tabular-nums">
        {formatCents(produit.unit_price_cents, produit.currency)}
      </td>
      <td className="table-cell text-right text-slate-400 tabular-nums">
        {produit.tax_rate}%
      </td>
      <td className="table-cell text-right font-semibold text-slate-900 tabular-nums">
        {formatCents(produit.unit_price_tax_included_cents, produit.currency)}
      </td>
      <td className="table-cell text-center text-slate-500">
        {produit.unit ?? "—"}
      </td>
      <td className="table-cell text-center">
        <span
          className={`badge ${
            produit.status === "active"
              ? "bg-emerald-50 text-emerald-700"
              : "bg-slate-100 text-slate-500"
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              produit.status === "active" ? "bg-emerald-500" : "bg-slate-400"
            }`}
          />
          {produit.status === "active" ? "Actif" : "Inactif"}
        </span>
      </td>
      <td className="table-cell">
        <div className="flex items-center justify-end gap-1">
          <Link
            href={`/produits/${produit.id}`}
            className="btn-icon p-1.5"
            title="Modifier"
          >
            <Pencil className="w-3.5 h-3.5" />
          </Link>
          {confirming ? (
            <div className="flex items-center gap-1">
              <button
                onClick={() => { onDelete(); setConfirming(false); }}
                className="text-xs px-2 py-1 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                Oui
              </button>
              <button
                onClick={() => setConfirming(false)}
                className="text-xs px-2 py-1 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 transition-colors"
              >
                Non
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirming(true)}
              className="p-1.5 rounded-lg text-slate-400 hover:bg-red-50 hover:text-red-600 transition-colors"
              title="Supprimer"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

export default function ProduitsPage() {
  const [search, setSearch]       = useState("");
  const [page, setPage]           = useState(0);
  const [activeOnly, setActiveOnly] = useState(false);
  const limit = 20;
  const debouncedSearch = useDebouncedValue(search);

  const { data, isLoading } = useProduits({
    skip: page * limit,
    limit,
    status: activeOnly ? "active" : undefined,
    search: debouncedSearch || undefined,
  });
  const deleteMut = useDeleteProduit();

  const filtered = data?.items ?? [];

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Produits</h1>
          <p className="page-subtitle">{data?.total ?? 0} produits au catalogue</p>
        </div>
        <Link href="/produits/new" className="btn-primary flex-shrink-0">
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">Nouveau produit</span>
          <span className="sm:hidden">Nouveau</span>
        </Link>
      </div>

      {/* Filtres */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
        <div className="relative sm:max-w-xs w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            placeholder="Nom ou code produit…"
            className="input pl-10"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer select-none whitespace-nowrap">
          <input
            type="checkbox"
            checked={activeOnly}
            onChange={(e) => { setActiveOnly(e.target.checked); setPage(0); }}
            className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
          />
          Actifs seulement
        </label>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-100">
              <tr>
                <th className="table-header">Code</th>
                <th className="table-header">Produit</th>
                <th className="table-header text-right">Prix HT</th>
                <th className="table-header text-right">TVA</th>
                <th className="table-header text-right">Prix TTC</th>
                <th className="table-header text-center">Unité</th>
                <th className="table-header text-center">Statut</th>
                <th className="table-header w-20" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={8}>
                    <div className="empty-state py-14">
                      <Package className="empty-state-icon" />
                      <p className="empty-state-title">Aucun produit trouvé</p>
                      <p className="empty-state-desc">
                        {search || activeOnly
                          ? "Modifiez vos filtres de recherche"
                          : "Commencez par créer votre premier produit"}
                      </p>
                      {!search && !activeOnly && (
                        <Link href="/produits/new" className="btn-primary btn-sm">
                          <Plus className="w-3.5 h-3.5" />
                          Créer un produit
                        </Link>
                      )}
                    </div>
                  </td>
                </tr>
              ) : (
                filtered.map((produit) => (
                  <ProduitRow
                    key={produit.id}
                    produit={produit}
                    onDelete={() => deleteMut.mutate(produit.id)}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {(data?.total ?? 0) > limit && (
          <div className="flex items-center justify-between px-5 py-3.5 border-t border-slate-100 bg-slate-50/40">
            <p className="text-sm text-slate-400">
              {page * limit + 1}–{Math.min((page + 1) * limit, data?.total ?? 0)} sur{" "}
              {data?.total}
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
        )}
      </div>
    </div>
  );
}
