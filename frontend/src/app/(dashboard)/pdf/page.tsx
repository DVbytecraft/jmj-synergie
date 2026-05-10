"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { commandesApi } from "@/lib/api/commandes";
import { pdfApi } from "@/lib/api/pdf";
import { FileText, Package, Search, Loader2, Download } from "lucide-react";
import { OrderStatusBadge } from "@/components/ui/OrderStatusBadge";
import { formatCents } from "@/lib/utils/money";
import Link from "next/link";

export default function PDFPage() {
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState<{ id: string; type: "facture" | "bon" } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["commandes", "pdf"],
    queryFn: () => commandesApi.list({ limit: 100 }),
  });

  const filtered = data?.items.filter((c) =>
    c.order_number.toLowerCase().includes(search.toLowerCase()) ||
    c.client_id.toLowerCase().includes(search.toLowerCase())
  ) ?? [];

  const handleDownload = async (id: string, type: "facture" | "bon") => {
    setLoading({ id, type });
    try {
      if (type === "facture") await pdfApi.downloadFacture(id);
      else await pdfApi.downloadBonCommande(id);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Documents PDF</h1>
        <p className="text-sm text-gray-500 mt-1">
          Générer et télécharger les factures et bons de commande
        </p>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="card p-5 flex items-start gap-4">
          <div className="p-3 bg-blue-100 rounded-xl">
            <FileText className="w-5 h-5 text-blue-700" />
          </div>
          <div>
            <p className="font-semibold text-gray-900">Factures</p>
            <p className="text-sm text-gray-500 mt-0.5">
              Document officiel avec TVA et coordonnées bancaires
            </p>
          </div>
        </div>
        <div className="card p-5 flex items-start gap-4">
          <div className="p-3 bg-emerald-100 rounded-xl">
            <Package className="w-5 h-5 text-emerald-700" />
          </div>
          <div>
            <p className="font-semibold text-gray-900">Bons de commande</p>
            <p className="text-sm text-gray-500 mt-0.5">
              Document de confirmation pour le client et les équipes
            </p>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher une commande…"
          className="input pl-10"
        />
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="table-header">ID Commande</th>
                <th className="table-header">Client</th>
                <th className="table-header">Statut</th>
                <th className="table-header text-right">Total TTC</th>
                <th className="table-header">Date</th>
                <th className="table-header text-center">Téléchargements</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="table-cell text-center py-10">
                    <Loader2 className="w-5 h-5 animate-spin text-blue-600 mx-auto" />
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="table-cell text-center py-10 text-gray-400">
                    Aucune commande trouvée
                  </td>
                </tr>
              ) : (
                filtered.map((c) => {
                  const isLoadingFacture = loading?.id === c.id && loading.type === "facture";
                  const isLoadingBon = loading?.id === c.id && loading.type === "bon";
                  return (
                    <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                      <td className="table-cell">
                        <Link
                          href={`/commandes/${c.id}`}
                          className="font-mono text-blue-600 hover:text-blue-700"
                        >
                          {c.order_number}
                        </Link>
                      </td>
                      <td className="table-cell font-mono text-xs text-gray-400">
                        {c.client_id.slice(0, 8)}…
                      </td>
                      <td className="table-cell">
                        <OrderStatusBadge status={c.status} />
                      </td>
                      <td className="table-cell text-right font-semibold">
                        {formatCents(c.total_cents, c.currency)}
                      </td>
                      <td className="table-cell text-gray-400">
                        {new Date(c.created_at).toLocaleDateString("fr-FR")}
                      </td>
                      <td className="table-cell">
                        <div className="flex items-center justify-center gap-2">
                          <button
                            onClick={() => handleDownload(c.id, "facture")}
                            disabled={!!loading}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors disabled:opacity-50"
                          >
                            {isLoadingFacture ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <FileText className="w-3.5 h-3.5" />
                            )}
                            Facture
                          </button>
                          <button
                            onClick={() => handleDownload(c.id, "bon")}
                            disabled={!!loading}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded-lg transition-colors disabled:opacity-50"
                          >
                            {isLoadingBon ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Package className="w-3.5 h-3.5" />
                            )}
                            Bon cmd.
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
