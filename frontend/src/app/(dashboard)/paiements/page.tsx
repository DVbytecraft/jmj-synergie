"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { paiementsApi } from "@/lib/api/paiements";
import type { PaymentMethod } from "@/types";
import { RotateCcw, Search, CreditCard, TrendingDown, Banknote, ArrowRight } from "lucide-react";
import { formatCents } from "@/lib/utils/money";
import Link from "next/link";
import { Loader2 } from "lucide-react";

const STATUS_CFG: Record<string, { label: string; dot: string; bg: string; text: string }> = {
  pending:   { label: "En attente", dot: "bg-orange-400", bg: "bg-orange-50",  text: "text-orange-700"  },
  completed: { label: "Complété",   dot: "bg-emerald-500",bg: "bg-emerald-50", text: "text-emerald-700" },
  failed:    { label: "Échoué",     dot: "bg-red-400",    bg: "bg-red-50",     text: "text-red-700"     },
  refunded:  { label: "Remboursé",  dot: "bg-purple-400", bg: "bg-purple-50",  text: "text-purple-700"  },
};

const METHODE_LABEL: Record<PaymentMethod, string> = {
  cash:          "Espèces",
  bank_transfer: "Virement",
  mobile_money:  "Mobile Money",
  check:         "Chèque",
  card:          "Carte",
};

function SkeletonRow() {
  return (
    <tr>
      {Array.from({ length: 7 }).map((_, i) => (
        <td key={i} className="table-cell">
          <div className="skeleton h-4 w-full max-w-[120px] rounded" />
        </td>
      ))}
    </tr>
  );
}

export default function PaiementsPage() {
  const [search, setSearch] = useState("");
  const [showRefundModal, setShowRefundModal] = useState<string | null>(null);
  const qc = useQueryClient();

  const { data: paiements, isLoading } = useQuery({
    queryKey: ["paiements"],
    queryFn: () => paiementsApi.list({ limit: 100 }),
  });

  const filtered = paiements?.filter(
    (p) =>
      p.id.toLowerCase().includes(search.toLowerCase()) ||
      (p.order_id ?? "").toLowerCase().includes(search.toLowerCase())
  ) ?? [];

  const currency = paiements?.[0]?.currency ?? "XAF";

  const totalCompleted = paiements?.filter((p) => p.status === "completed").reduce((s, p) => s + p.amount_cents, 0) ?? 0;
  const totalRefunded  = paiements?.filter((p) => p.status === "refunded").reduce((s, p) => s + p.amount_cents, 0) ?? 0;
  const totalNet       = totalCompleted - totalRefunded;

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Paiements</h1>
          <p className="page-subtitle">{paiements?.length ?? 0} transactions</p>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="stat-card">
          <div className="stat-icon bg-emerald-600">
            <Banknote className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="stat-label">Total encaissé</p>
            <p className="stat-value text-emerald-700">{formatCents(totalCompleted, currency)}</p>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon bg-purple-600">
            <TrendingDown className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="stat-label">Total remboursé</p>
            <p className="stat-value text-purple-700">{formatCents(totalRefunded, currency)}</p>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon bg-blue-600">
            <CreditCard className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="stat-label">Net encaissé</p>
            <p className="stat-value text-blue-700">{formatCents(totalNet, currency)}</p>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher par transaction ou commande…"
          className="input pl-10"
        />
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-100">
              <tr>
                <th className="table-header">Transaction</th>
                <th className="table-header">Commande</th>
                <th className="table-header">Méthode</th>
                <th className="table-header">Statut</th>
                <th className="table-header text-right">Montant</th>
                <th className="table-header">Date</th>
                <th className="table-header text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <div className="empty-state py-14">
                      <CreditCard className="empty-state-icon" />
                      <p className="empty-state-title">Aucun paiement trouvé</p>
                      <p className="empty-state-desc">Les paiements apparaîtront ici</p>
                    </div>
                  </td>
                </tr>
              ) : (
                filtered.map((p) => {
                  const cfg = STATUS_CFG[p.status] ?? { label: p.status, dot: "bg-slate-400", bg: "bg-slate-100", text: "text-slate-700" };
                  return (
                    <tr key={p.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="table-cell font-mono text-xs text-slate-500 whitespace-nowrap">
                        {p.transaction_number}
                      </td>
                      <td className="table-cell">
                        {p.order_id ? (
                          <Link
                            href={`/commandes/${p.order_id}`}
                            className="inline-flex items-center gap-1 font-mono text-blue-600 hover:text-blue-700 text-xs"
                          >
                            {p.order_id.slice(0, 8)}…
                            <ArrowRight className="w-3 h-3" />
                          </Link>
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                      <td className="table-cell">
                        <div className="flex items-center gap-1.5 text-slate-600">
                          <CreditCard className="w-3.5 h-3.5 text-slate-400" />
                          {METHODE_LABEL[p.method as PaymentMethod] ?? p.method}
                        </div>
                      </td>
                      <td className="table-cell">
                        <span className={`badge ${cfg.bg} ${cfg.text}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
                          {cfg.label}
                        </span>
                      </td>
                      <td className="table-cell text-right font-semibold text-slate-900 tabular-nums">
                        {formatCents(p.amount_cents, p.currency)}
                      </td>
                      <td className="table-cell text-slate-400 tabular-nums">
                        {new Date(p.transaction_date).toLocaleDateString("fr-FR")}
                      </td>
                      <td className="table-cell text-center">
                        {p.status === "completed" && (
                          <button
                            onClick={() => setShowRefundModal(p.id)}
                            className="p-1.5 rounded-lg text-purple-500 hover:bg-purple-50 hover:text-purple-700 transition-colors"
                            title="Demander un remboursement"
                          >
                            <RotateCcw className="w-4 h-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Refund modal */}
      {showRefundModal && (
        <RefundModal
          transactionId={showRefundModal}
          orderId={paiements?.find((p) => p.id === showRefundModal)?.order_id ?? ""}
          amountCents={paiements?.find((p) => p.id === showRefundModal)?.amount_cents ?? 0}
          currency={currency}
          onClose={() => setShowRefundModal(null)}
          onSuccess={() => {
            setShowRefundModal(null);
            qc.invalidateQueries({ queryKey: ["paiements"] });
          }}
        />
      )}
    </div>
  );
}

/* ── Refund modal ──────────────────────────────────── */
function RefundModal({
  transactionId,
  orderId,
  amountCents,
  currency,
  onClose,
  onSuccess,
}: {
  transactionId: string;
  orderId: string;
  amountCents: number;
  currency: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [montant, setMontant]           = useState(String(amountCents));
  const [reason, setReason]             = useState("customer_request");
  const [reasonDetail, setReasonDetail] = useState("");

  const { mutate, isPending, error } = useMutation({
    mutationFn: () =>
      paiementsApi.demanderRemboursement({
        order_id: orderId,
        original_transaction_id: transactionId,
        amount_cents: parseInt(montant, 10) || amountCents,
        reason,
        reason_detail: reasonDetail || "Remboursement demandé",
      }),
    onSuccess,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-fade-in">
      <div className="bg-white rounded-2xl shadow-card-lg w-full max-w-md p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Demande de remboursement</h2>
            <p className="text-sm text-slate-500 mt-0.5">Transaction {transactionId.slice(0, 8)}…</p>
          </div>
          <button onClick={onClose} className="btn-icon">
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        <div className="divider" />

        <div className="space-y-4">
          <div>
            <label className="label">Montant à rembourser ({currency})</label>
            <input
              type="number"
              min={1}
              value={montant}
              onChange={(e) => setMontant(e.target.value)}
              className="input"
            />
          </div>

          <div>
            <label className="label">Motif du remboursement</label>
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="input"
            >
              <option value="customer_request">Demande client</option>
              <option value="product_defect">Produit défectueux</option>
              <option value="wrong_item">Article incorrect</option>
              <option value="not_delivered">Non livré</option>
              <option value="duplicate_payment">Paiement en double</option>
              <option value="billing_error">Erreur de facturation</option>
              <option value="other">Autre</option>
            </select>
          </div>

          <div>
            <label className="label">Précisions <span className="text-slate-400 font-normal">(optionnel)</span></label>
            <textarea
              value={reasonDetail}
              onChange={(e) => setReasonDetail(e.target.value)}
              rows={2}
              placeholder="Informations complémentaires…"
              className="input resize-none"
            />
          </div>
        </div>

        {error && (
          <div className="alert-error">
            {(error as any)?.response?.data?.detail ?? "Erreur lors de la demande"}
          </div>
        )}

        <div className="flex gap-3 pt-1">
          <button onClick={onClose} className="btn-secondary flex-1">
            Annuler
          </button>
          <button
            onClick={() => mutate()}
            disabled={isPending}
            className="btn flex-1 bg-purple-600 text-white hover:bg-purple-700 shadow-sm"
          >
            {isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RotateCcw className="w-4 h-4" />
            )}
            Confirmer
          </button>
        </div>
      </div>
    </div>
  );
}
