"use client";

import { formatDateFr } from "@/lib/utils/format-dates";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { commandesApi } from "@/lib/api/commandes";
import { apiClient } from "@/lib/api/client";
import { documentsApi } from "@/lib/api/documents";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";
import { FileText, Package, Search, Loader2, Eye, Download } from "lucide-react";
import { OrderStatusBadge } from "@/components/ui/OrderStatusBadge";
import { PdfPreviewPanel } from "@/components/ui/PdfPreviewPanel";
import { useBlobPreview } from "@/lib/hooks/use-blob-preview";
import { formatCents } from "@/lib/utils/money";
import Link from "next/link";

type PreviewType = "facture" | "bon";

export default function PDFPage() {
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState<{ id: string; type: PreviewType } | null>(null);
  const { previewUrl, previewTitle, run: runPreview, close: closePreview, download: downloadPreview } = useBlobPreview();

  const debouncedSearch = useDebouncedValue(search);

  const { data, isLoading } = useQuery({
    queryKey: ["commandes", "pdf", debouncedSearch],
    queryFn: () => commandesApi.list({ limit: 20, search: debouncedSearch || undefined }),
  });

  const filtered = data?.items ?? [];

  const handlePreview = async (id: string, type: PreviewType, orderNumber: string) => {
    setLoading({ id, type });
    try {
      await runPreview(async () => {
        const generated =
          type === "facture"
            ? await documentsApi.genererFacture(id)
            : await documentsApi.genererProForma(id);
        const response = await apiClient.get(`/documents/${generated.document_id}/preview`, {
          responseType: "blob",
        });
        return new Blob([response.data], { type: "application/pdf" });
      }, type === "facture" ? `Facture - ${orderNumber}` : `Pro forma - ${orderNumber}`);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Documents PDF</h1>
        <p className="mt-1 text-sm text-gray-500">
          Générez un aperçu à droite avant de télécharger la facture ou la pro forma.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="card flex items-start gap-4 p-5">
              <div className="rounded-xl bg-blue-100 p-3">
                <FileText className="h-5 w-5 text-blue-700" />
              </div>
              <div>
                <p className="font-semibold text-gray-900">Factures</p>
                <p className="mt-0.5 text-sm text-gray-500">
                  Document officiel avec TVA facultative et coordonnées bancaires.
                </p>
              </div>
            </div>
            <div className="card flex items-start gap-4 p-5">
              <div className="rounded-xl bg-emerald-100 p-3">
                <Package className="h-5 w-5 text-emerald-700" />
              </div>
              <div>
                <p className="font-semibold text-gray-900">Pro formas</p>
                <p className="mt-0.5 text-sm text-gray-500">
                  Prévisualisez le rendu commercial avant export.
                </p>
              </div>
            </div>
          </div>

          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Rechercher une commande…"
              className="input pl-10"
            />
          </div>

          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-gray-100 bg-gray-50">
                  <tr>
                    <th className="table-header">ID Commande</th>
                    <th className="table-header">Client</th>
                    <th className="table-header">Statut</th>
                    <th className="table-header text-right">Total TTC</th>
                    <th className="table-header">Date</th>
                    <th className="table-header text-center">Aperçus</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {isLoading ? (
                    <tr>
                      <td colSpan={6} className="table-cell py-10 text-center">
                        <Loader2 className="mx-auto h-5 w-5 animate-spin text-blue-600" />
                      </td>
                    </tr>
                  ) : filtered.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="table-cell py-10 text-center text-gray-400">
                        Aucune commande trouvée
                      </td>
                    </tr>
                  ) : (
                    filtered.map((c) => {
                      const isLoadingFacture = loading?.id === c.id && loading.type === "facture";
                      const isLoadingBon = loading?.id === c.id && loading.type === "bon";
                      return (
                        <tr key={c.id} className="transition-colors hover:bg-gray-50">
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
                            {formatDateFr(c.created_at)}
                          </td>
                          <td className="table-cell">
                            <div className="flex items-center justify-center gap-2">
                              <button
                                onClick={() => handlePreview(c.id, "facture", c.order_number)}
                                disabled={!!loading}
                                className="flex items-center gap-1.5 rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 transition-colors hover:bg-blue-100 disabled:opacity-50"
                              >
                                {isLoadingFacture ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <Eye className="h-3.5 w-3.5" />
                                )}
                                Facture
                              </button>
                              <button
                                onClick={() => handlePreview(c.id, "bon", c.order_number)}
                                disabled={!!loading}
                                className="flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 transition-colors hover:bg-emerald-100 disabled:opacity-50"
                              >
                                {isLoadingBon ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <Eye className="h-3.5 w-3.5" />
                                )}
                                Pro forma
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

        <PdfPreviewPanel
          title={previewTitle}
          previewUrl={previewUrl}
          loading={loading !== null}
          emptyTitle="Aperçu PDF"
          emptyDescription="Sélectionnez une facture ou une pro forma dans la liste pour voir le rendu à droite."
          onDownload={() => downloadPreview(`${previewTitle.toLowerCase().replace(/\s+/g, "-")}.pdf`)}
          onClose={closePreview}
        />
      </div>
    </div>
  );
}
