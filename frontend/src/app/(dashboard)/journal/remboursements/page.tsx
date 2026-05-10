"use client";

import { useState } from "react";
import { useJournalRemboursements } from "@/lib/hooks/use-journal";
import { RotateCcw, Loader2 } from "lucide-react";
import { formatCents } from "@/lib/utils/money";

const STATUS_CFG: Record<string, { label: string; className: string }> = {
  requested:     { label: "Demandé",       className: "bg-orange-100 text-orange-700" },
  under_review:  { label: "En révision",   className: "bg-yellow-100 text-yellow-700" },
  approved:      { label: "Approuvé",      className: "bg-blue-100 text-blue-700" },
  rejected:      { label: "Rejeté",        className: "bg-red-100 text-red-700" },
  completed:     { label: "Complété",      className: "bg-green-100 text-green-700" },
  cancelled:     { label: "Annulé",        className: "bg-gray-100 text-gray-700" },
};

export default function JournalRemboursementsPage() {
  const [page, setPage] = useState(0);
  const limit = 25;

  const { data, isLoading } = useJournalRemboursements({ skip: page * limit, limit });

  const remboursements = data?.items ?? [];
  const currency = "XAF";
  const totalCents = remboursements.reduce((s, e) => s + e.requested_amount_cents, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Journal des remboursements</h1>
          <p className="text-sm text-gray-500 mt-1">{data?.total ?? 0} entrées</p>
        </div>
        <div className="card px-4 py-2 text-right">
          <p className="text-xs text-gray-500">Total demandé (page)</p>
          <p className="text-lg font-bold text-orange-600">{formatCents(totalCents, currency)}</p>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="table-header">N° Remboursement</th>
                <th className="table-header">Commande</th>
                <th className="table-header">Motif</th>
                <th className="table-header">Statut</th>
                <th className="table-header text-right">Montant demandé</th>
                <th className="table-header text-right">Montant approuvé</th>
                <th className="table-header">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="py-10 text-center">
                    <Loader2 className="w-5 h-5 animate-spin text-blue-600 mx-auto" />
                  </td>
                </tr>
              ) : remboursements.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-10 text-center text-gray-400">Aucun remboursement</td>
                </tr>
              ) : (
                remboursements.map((e) => {
                  const cfg = STATUS_CFG[e.status] ?? { label: e.status, className: "bg-gray-100 text-gray-700" };
                  return (
                    <tr key={e.id} className="hover:bg-gray-50 transition-colors">
                      <td className="table-cell font-mono text-xs text-gray-500">{e.refund_number}</td>
                      <td className="table-cell">
                        {e.order_id ? (
                          <a href={`/commandes/${e.order_id}`} className="font-mono text-blue-600 hover:text-blue-700 text-xs">
                            {e.order_id.slice(0, 8)}…
                          </a>
                        ) : "—"}
                      </td>
                      <td className="table-cell text-gray-600">{e.reason}</td>
                      <td className="table-cell">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${cfg.className}`}>{cfg.label}</span>
                      </td>
                      <td className="table-cell text-right">{formatCents(e.requested_amount_cents, e.currency)}</td>
                      <td className="table-cell text-right font-semibold">
                        {e.approved_amount_cents != null ? formatCents(e.approved_amount_cents, e.currency) : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="table-cell text-gray-400">
                        {new Date(e.requested_at).toLocaleDateString("fr-FR")}
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
            <button onClick={() => setPage((p) => p + 1)} disabled={remboursements.length < limit} className="btn-secondary py-1.5">Suivant</button>
          </div>
        </div>
      </div>
    </div>
  );
}
