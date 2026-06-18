"use client";
import { formatDateFr, formatDateTimeFr } from "@/lib/utils/format-dates";

import { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { commandesApi } from "@/lib/api/commandes";
import { paiementsApi } from "@/lib/api/paiements";
import { refundsApi } from "@/lib/api/refunds";
import { useEnregistrerPaiement } from "@/lib/hooks/use-paiements";
import { PaymentStatusBadge } from "@/components/ui/PaymentStatusBadge";
import { formatCents } from "@/lib/utils/money";
import type { PaymentMethod } from "@/types";
import {
  ArrowLeft, CreditCard, Loader2, Plus, RotateCcw, X,
} from "lucide-react";
import Link from "next/link";

const METHOD_LABELS: Record<PaymentMethod, string> = {
  cash:          "Espèces",
  bank_transfer: "Virement",
  mobile_money:  "Mobile Money",
  check:         "Chèque",
  card:          "Carte bancaire",
};

const REFUND_REASONS = [
  { value: "product_defect",    label: "Produit défectueux" },
  { value: "wrong_item",        label: "Mauvais article" },
  { value: "not_delivered",     label: "Non livré" },
  { value: "customer_request",  label: "Demande client" },
  { value: "duplicate_payment", label: "Paiement en double" },
  { value: "billing_error",     label: "Erreur de facturation" },
  { value: "other",             label: "Autre" },
];

// ─── Refund request modal ─────────────────────────────────────────────────────

function RefundModal({
  orderId,
  transaction,
  onClose,
}: {
  orderId: string;
  transaction: { id: string; amount_cents: number; currency: string; transaction_number: string };
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [reason, setReason] = useState("customer_request");
  const [detail, setDetail] = useState("");
  const [amount, setAmount] = useState(String(transaction.amount_cents));
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const mut = useMutation({
    mutationFn: () =>
      refundsApi.request({
        order_id: orderId,
        original_transaction_id: transaction.id,
        amount_cents: parseInt(amount, 10),
        reason,
        reason_detail: detail,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["remboursements"] });
      setSuccess(true);
      setTimeout(onClose, 1500);
    },
    onError: (e: any) => setError(e?.response?.data?.detail ?? "Erreur lors de la demande."),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900">Demande de remboursement</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-sm text-slate-500">
          Transaction <span className="font-mono font-medium text-slate-700">{transaction.transaction_number}</span>
          {" — "}<strong>{formatCents(transaction.amount_cents, transaction.currency)}</strong>
        </p>

        {success ? (
          <div className="py-4 text-center text-emerald-600 font-medium">
            Demande enregistrée. En attente de traitement.
          </div>
        ) : (
          <>
            <div>
              <label className="label">Motif <span className="text-red-500">*</span></label>
              <select value={reason} onChange={(e) => setReason(e.target.value)} className="input">
                {REFUND_REASONS.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="label">Détail <span className="text-red-500">*</span></label>
              <textarea
                value={detail}
                onChange={(e) => setDetail(e.target.value)}
                rows={3}
                minLength={10}
                placeholder="Décrivez la raison en détail (min. 10 caractères)…"
                className="input resize-none"
              />
              {detail.length > 0 && detail.length < 10 && (
                <p className="field-error">Minimum 10 caractères</p>
              )}
            </div>

            <div>
              <label className="label">Montant à rembourser ({transaction.currency})</label>
              <input
                type="number"
                min={1}
                max={transaction.amount_cents}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="input"
              />
            </div>

            {error && <div className="alert-error">{error}</div>}

            <div className="flex gap-3 justify-end">
              <button onClick={onClose} className="btn-secondary">Annuler</button>
              <button
                onClick={() => mut.mutate()}
                disabled={mut.isPending || detail.length < 10 || !parseInt(amount, 10)}
                className="btn-primary bg-orange-600 hover:bg-orange-700 disabled:opacity-50"
              >
                {mut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
                Soumettre la demande
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CommandePaiementsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [showPayModal, setShowPayModal] = useState(false);
  const [refundTarget, setRefundTarget] = useState<{
    id: string; amount_cents: number; currency: string; transaction_number: string;
  } | null>(null);

  const { data: commande, isLoading: loadingCmd } = useQuery({
    queryKey: ["commandes", id],
    queryFn: () => commandesApi.get(id),
  });

  const { data: paiements, isLoading: loadingPay } = useQuery({
    queryKey: ["paiements", { order_id: id }],
    queryFn: () => paiementsApi.list({ order_id: id }),
  });

  const enregistrerMut = useEnregistrerPaiement();

  if (loadingCmd || loadingPay) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!commande) {
    return <div className="text-center py-16 text-gray-400">Commande introuvable</div>;
  }

  const currency = commande.currency;

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-3">
        <Link href={`/commandes/${id}`} className="btn-secondary py-1.5 px-3">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-900">Paiements — {commande.order_number}</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Solde restant : <span className="font-semibold text-orange-600">{formatCents(commande.balance_due_cents, currency)}</span>
          </p>
        </div>
        {commande.status === "confirmed" && commande.balance_due_cents > 0 && (
          <button onClick={() => setShowPayModal(true)} className="btn-primary">
            <Plus className="w-4 h-4" />
            Nouveau paiement
          </button>
        )}
        {commande.status === "draft" && (
          <span className="text-xs text-amber-600 bg-amber-50 border border-amber-200 px-3 py-1.5 rounded-lg">
            Confirmez la commande pour enregistrer un paiement
          </span>
        )}
        {commande.balance_due_cents === 0 && commande.status !== "draft" && (
          <span className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-lg">
            Commande entièrement payée
          </span>
        )}
      </div>

      {/* Récap */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card p-4 text-center">
          <p className="text-xs text-gray-500 mb-1">Total TTC</p>
          <p className="text-lg font-bold text-gray-900">{formatCents(commande.total_cents, currency)}</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-xs text-gray-500 mb-1">Payé</p>
          <p className="text-lg font-bold text-emerald-700">{formatCents(commande.paid_cents, currency)}</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-xs text-gray-500 mb-1">Reste dû</p>
          <p className={`text-lg font-bold ${commande.balance_due_cents > 0 ? "text-orange-600" : "text-emerald-600"}`}>
            {formatCents(commande.balance_due_cents, currency)}
          </p>
        </div>
      </div>

      {/* Liste paiements */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Transactions ({paiements?.total ?? 0})</h2>
        </div>
        {!paiements?.items?.length ? (
          <div className="py-10 text-center text-gray-400 text-sm">Aucun paiement enregistré</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="table-header">N° Transaction</th>
                <th className="table-header">Méthode</th>
                <th className="table-header">Statut</th>
                <th className="table-header text-right">Montant</th>
                <th className="table-header">Date</th>
                <th className="table-header"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {paiements.items.map((p) => (
                <tr key={p.id} className="hover:bg-gray-50">
                  <td className="table-cell font-mono text-xs">{p.transaction_number}</td>
                  <td className="table-cell">{METHOD_LABELS[p.method as PaymentMethod] ?? p.method}</td>
                  <td className="table-cell"><PaymentStatusBadge status={p.status} /></td>
                  <td className="table-cell text-right font-semibold">{formatCents(p.amount_cents, p.currency)}</td>
                  <td className="table-cell text-gray-400">{formatDateFr(p.transaction_date)}</td>
                  <td className="table-cell">
                    {p.status === "completed" && (
                      <button
                        onClick={() => setRefundTarget({
                          id: p.id,
                          amount_cents: p.amount_cents,
                          currency: p.currency,
                          transaction_number: p.transaction_number,
                        })}
                        className="text-xs text-orange-600 hover:text-orange-700 font-medium flex items-center gap-1"
                      >
                        <RotateCcw className="w-3 h-3" />
                        Rembourser
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showPayModal && (
        <PaymentModal
          orderId={id}
          currency={currency}
          balanceCents={commande.balance_due_cents}
          onClose={() => setShowPayModal(false)}
          onSuccess={() => setShowPayModal(false)}
          enregistrerMut={enregistrerMut}
        />
      )}

      {refundTarget && (
        <RefundModal
          orderId={id}
          transaction={refundTarget}
          onClose={() => setRefundTarget(null)}
        />
      )}
    </div>
  );
}

// ─── Payment modal (unchanged) ────────────────────────────────────────────────

function PaymentModal({
  orderId, currency, balanceCents, onClose, onSuccess, enregistrerMut,
}: {
  orderId: string;
  currency: string;
  balanceCents: number;
  onClose: () => void;
  onSuccess: () => void;
  enregistrerMut: ReturnType<typeof useEnregistrerPaiement>;
}) {
  const [methode, setMethode] = useState<PaymentMethod>("bank_transfer");
  const [montant, setMontant] = useState(String(balanceCents));
  const [reference, setReference] = useState("");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-5">
        <h2 className="text-lg font-bold text-gray-900">Enregistrer un paiement</h2>

        <div>
          <label className="label">Méthode</label>
          <select value={methode} onChange={(e) => setMethode(e.target.value as PaymentMethod)} className="input">
            {(Object.keys(METHOD_LABELS) as PaymentMethod[]).map((m) => (
              <option key={m} value={m}>{METHOD_LABELS[m]}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="label">Montant ({currency})</label>
          <input type="number" min={1} value={montant} onChange={(e) => setMontant(e.target.value)} className="input" />
        </div>

        <div>
          <label className="label">Référence (optionnel)</label>
          <input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="N° virement, chèque…" className="input" />
        </div>

        {enregistrerMut.error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg">
            {(enregistrerMut.error as any)?.response?.data?.detail ?? "Erreur"}
          </div>
        )}

        <div className="flex gap-3 justify-end">
          <button onClick={onClose} className="btn-secondary">Annuler</button>
          <button
            onClick={() =>
              enregistrerMut.mutate(
                { order_id: orderId, amount_cents: parseInt(montant, 10) || balanceCents, method: methode, external_reference: reference || undefined },
                { onSuccess }
              )
            }
            disabled={enregistrerMut.isPending}
            className="btn-primary"
          >
            {enregistrerMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
            Confirmer
          </button>
        </div>
      </div>
    </div>
  );
}
