"use client";

import { use, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { commandesApi } from "@/lib/api/commandes";
import { paiementsApi } from "@/lib/api/paiements";
import { useEnregistrerPaiement } from "@/lib/hooks/use-paiements";
import { PaymentStatusBadge } from "@/components/ui/PaymentStatusBadge";
import { formatCents } from "@/lib/utils/money";
import type { PaymentMethod } from "@/types";
import {
  ArrowLeft, CreditCard, Loader2, Plus,
  Banknote, Receipt, Smartphone,
} from "lucide-react";
import Link from "next/link";

const METHOD_LABELS: Record<PaymentMethod, string> = {
  cash:          "Espèces",
  bank_transfer: "Virement",
  mobile_money:  "Mobile Money",
  check:         "Chèque",
  card:          "Carte bancaire",
};

export default function CommandePaiementsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [showModal, setShowModal] = useState(false);

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
          <button onClick={() => setShowModal(true)} className="btn-primary">
            <Plus className="w-4 h-4" />
            Nouveau paiement
          </button>
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
          <h2 className="font-semibold text-gray-900">Transactions ({paiements?.length ?? 0})</h2>
        </div>
        {!paiements?.length ? (
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
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {paiements.map((p) => (
                <tr key={p.id} className="hover:bg-gray-50">
                  <td className="table-cell font-mono text-xs">{p.transaction_number}</td>
                  <td className="table-cell">{METHOD_LABELS[p.method as PaymentMethod] ?? p.method}</td>
                  <td className="table-cell"><PaymentStatusBadge status={p.status} /></td>
                  <td className="table-cell text-right font-semibold">{formatCents(p.amount_cents, p.currency)}</td>
                  <td className="table-cell text-gray-400">{new Date(p.transaction_date).toLocaleDateString("fr-FR")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showModal && (
        <PaymentModal
          orderId={id}
          currency={currency}
          balanceCents={commande.balance_due_cents}
          onClose={() => setShowModal(false)}
          onSuccess={() => setShowModal(false)}
          enregistrerMut={enregistrerMut}
        />
      )}
    </div>
  );
}

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
