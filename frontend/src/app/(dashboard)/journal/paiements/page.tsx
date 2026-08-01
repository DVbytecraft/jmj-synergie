"use client";
import { formatDateFr, formatDateTimeFr } from "@/lib/utils/format-dates";

import { useState } from "react";
import { useJournalPaiements } from "@/lib/hooks/use-journal";
import { BookOpen, Loader2, CreditCard, Building2, FileText, Smartphone, Download } from "lucide-react";
import type { PaymentMethod } from "@/types";
import { formatCents } from "@/lib/utils/money";
import { downloadJournal, type ExportFormat } from "@/lib/api/exports";

const METHOD_LABEL: Record<string, { label: string; icon: React.ReactNode }> = {
  cash:          { label: "Espèces",      icon: <FileText className="w-3.5 h-3.5" /> },
  bank_transfer: { label: "Virement",     icon: <Building2 className="w-3.5 h-3.5" /> },
  mobile_money:  { label: "Mobile Money (manuel)", icon: <Smartphone className="w-3.5 h-3.5" /> },
  check:         { label: "Chèque",       icon: <FileText className="w-3.5 h-3.5" /> },
  card:          { label: "Carte (manuelle)",        icon: <CreditCard className="w-3.5 h-3.5" /> },
};

// Format YYYY-MM-DD pour la date du jour et il y a 30 jours
function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}
function thirtyDaysAgoStr(): string {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return d.toISOString().slice(0, 10);
}

export default function JournalPaiementsPage() {
  const [page, setPage] = useState(0);
  const [exportStart, setExportStart] = useState(thirtyDaysAgoStr);
  const [exportEnd, setExportEnd] = useState(todayStr);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const limit = 25;

  const { data, isLoading } = useJournalPaiements({ skip: page * limit, limit });

  const paiements = data?.items ?? [];
  const totalCents = data?.total_completed_cents ?? 0;
  const currency = paiements[0]?.currency ?? "XAF";

  const handleExport = async (format: ExportFormat) => {
    setExporting(format);
    try {
      await downloadJournal(exportStart, exportEnd, format);
    } catch (err) {
      console.error("Export échoué :", err);
      alert("L'export a échoué. Veuillez réessayer.");
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Journal des paiements</h1>
          <p className="text-sm text-gray-500 mt-1">{paiements.length} entrées</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Sélecteurs de période pour l'export */}
          <input
            type="date"
            value={exportStart}
            onChange={(e) => setExportStart(e.target.value)}
            className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label="Date de début"
          />
          <span className="text-gray-400 text-sm">→</span>
          <input
            type="date"
            value={exportEnd}
            onChange={(e) => setExportEnd(e.target.value)}
            className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label="Date de fin"
          />
          <button
            onClick={() => handleExport("csv")}
            disabled={exporting !== null}
            className="btn-secondary py-1.5 flex items-center gap-1.5 text-sm"
          >
            {exporting === "csv" ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            Exporter CSV
          </button>
          <button
            onClick={() => handleExport("xlsx")}
            disabled={exporting !== null}
            className="btn-primary py-1.5 flex items-center gap-1.5 text-sm"
          >
            {exporting === "xlsx" ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            Exporter Excel
          </button>
          <div className="card px-4 py-2 text-right">
            <p className="text-xs text-gray-500">Total encaissé</p>
            <p className="text-lg font-bold text-emerald-700">{formatCents(totalCents, currency)}</p>
          </div>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="table-header">N° Transaction</th>
                <th className="table-header">Commande</th>
                <th className="table-header">Méthode</th>
                <th className="table-header">Statut</th>
                <th className="table-header text-right">Montant</th>
                <th className="table-header">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="py-10 text-center">
                    <Loader2 className="w-5 h-5 animate-spin text-blue-600 mx-auto" />
                  </td>
                </tr>
              ) : paiements.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-10 text-center text-gray-400">Aucune entrée</td>
                </tr>
              ) : (
                paiements.map((e) => {
                  const m = METHOD_LABEL[e.method] ?? { label: e.method, icon: <BookOpen className="w-3.5 h-3.5" /> };
                  return (
                    <tr key={e.id} className="hover:bg-gray-50 transition-colors">
                      <td className="table-cell font-mono text-xs text-gray-500">{e.transaction_number}</td>
                      <td className="table-cell">
                        {e.order_id ? (
                          <a href={`/commandes/${e.order_id}`} className="font-mono text-blue-600 hover:text-blue-700 text-xs">
                            {e.order_id.slice(0, 8)}…
                          </a>
                        ) : "—"}
                      </td>
                      <td className="table-cell">
                        <div className="flex items-center gap-1.5 text-gray-600">
                          {m.icon}{m.label}
                        </div>
                      </td>
                      <td className="table-cell">
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                          {e.status}
                        </span>
                      </td>
                      <td className="table-cell text-right font-semibold">{formatCents(e.amount_cents, e.currency)}</td>
                      <td className="table-cell text-gray-400">
                        {formatDateFr(e.transaction_date)}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
          <p className="text-sm text-gray-400">{data?.total ?? 0} résultats</p>
          <div className="flex gap-2">
            <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0} className="btn-secondary py-1.5">Précédent</button>
            <button onClick={() => setPage((p) => p + 1)} disabled={(page + 1) * limit >= (data?.total ?? 0)} className="btn-secondary py-1.5">Suivant</button>
          </div>
        </div>
      </div>
    </div>
  );
}
