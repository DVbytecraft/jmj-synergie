"use client";

import { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { commandesApi } from "@/lib/api/commandes";
import { clientsApi } from "@/lib/api/clients";
import { paiementsApi } from "@/lib/api/paiements";
import { apiClient } from "@/lib/api/client";
import { amountToCents, formatCents } from "@/lib/utils/money";
import type { PaymentMethod } from "@/types";
import {
  ArrowLeft, CheckCircle, XCircle, Download, FileText,
  CreditCard, Loader2, Package, Truck, Wallet,
} from "lucide-react";
import Link from "next/link";
import { OrderStatusBadge } from "@/components/ui/OrderStatusBadge";

const METHODE_LABELS: Record<PaymentMethod, string> = {
  cash: "Espèces",
  bank_transfer: "Virement bancaire",
  mobile_money: "Mobile Money",
  check: "Chèque",
  card: "Carte bancaire",
};

export default function CommandeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const qc = useQueryClient();
  const [showPayModal, setShowPayModal] = useState(false);
  const [showDeliveryModal, setShowDeliveryModal] = useState(false);

  const { data: commande, isLoading } = useQuery({
    queryKey: ["commandes", id],
    queryFn: () => commandesApi.get(id),
  });

  const { data: client } = useQuery({
    queryKey: ["clients", commande?.client_id],
    queryFn: () => clientsApi.get(commande!.client_id),
    enabled: !!commande?.client_id,
  });

  const confirmerMut = useMutation({
    mutationFn: () => commandesApi.confirmer(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["commandes", id] }),
  });

  const annulerMut = useMutation({
    mutationFn: () => commandesApi.annuler(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["commandes", id] }),
  });

  const [pdfLoading, setPdfLoading] = useState<"facture" | "proforma" | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);

  const handleDownload = async (type: "facture" | "proforma") => {
    setPdfLoading(type);
    setPdfError(null);
    try {
      const endpoint = type === "facture" ? `/documents/invoice/${id}` : `/documents/pro-forma/${id}`;
      const fileName = type === "facture" ? `facture-${id.slice(0, 8)}.pdf` : `proforma-${id.slice(0, 8)}.pdf`;
      const postRes = await apiClient.post<{ document_id: string }>(endpoint);
      const { document_id } = postRes.data;
      const fileRes = await apiClient.get(`/documents/${document_id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([fileRes.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      const detail = err?.response?.data?.detail ?? "Erreur lors de la génération du PDF";
      setPdfError(detail);
    } finally {
      setPdfLoading(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!commande) {
    return <div className="text-center py-16 text-gray-400">Commande introuvable</div>;
  }

  const canConfirm = commande.status === "draft";
  const canCancel = !["delivered", "cancelled", "refunded"].includes(commande.status);
  const canPay = commande.status === "confirmed";
  const canRecordDelivery = ["confirmed", "in_progress", "partially_delivered"].includes(commande.status);

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <Link href="/commandes" className="btn-secondary py-1.5 px-3">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-gray-900 font-mono">
              {commande.order_number}
            </h1>
            <OrderStatusBadge status={commande.status} />
          </div>
          <p className="text-sm text-gray-400 mt-0.5">
            Créée le {new Date(commande.created_at).toLocaleDateString("fr-FR", { dateStyle: "long" })}
          </p>
        </div>

        {/* Actions */}
        <div className="flex gap-2 flex-wrap">
          {canConfirm && (
            <button
              onClick={() => confirmerMut.mutate()}
              disabled={confirmerMut.isPending}
              className="btn-primary bg-emerald-600 hover:bg-emerald-700"
            >
              {confirmerMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
              Confirmer
            </button>
          )}
          <Link href={`/commandes/${id}/paiements`} className="btn-secondary">
            <Wallet className="w-4 h-4" />
            Paiements
          </Link>
          {canPay && (
            <button onClick={() => setShowPayModal(true)} className="btn-primary">
              <CreditCard className="w-4 h-4" />
              Payer
            </button>
          )}
          {canRecordDelivery && (
            <button onClick={() => setShowDeliveryModal(true)} className="btn-secondary">
              <Truck className="w-4 h-4" />
              Livraison
            </button>
          )}
          <button
            onClick={() => handleDownload("proforma")}
            disabled={pdfLoading === "proforma"}
            className="btn-secondary"
            title="Pro forma — document avant confirmation"
          >
            {pdfLoading === "proforma" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Package className="w-4 h-4" />}
            Pro forma
          </button>
          {["confirmed", "in_progress", "partially_delivered", "delivered"].includes(commande.status) && (
            <button
              onClick={() => handleDownload("facture")}
              disabled={pdfLoading === "facture"}
              className="btn-secondary text-emerald-700 border-emerald-200 hover:bg-emerald-50"
              title="Facture définitive — commande confirmée"
            >
              {pdfLoading === "facture" ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
              Facture
            </button>
          )}
          {canCancel && (
            <button
              onClick={() => annulerMut.mutate()}
              disabled={annulerMut.isPending}
              className="btn-secondary text-red-600 hover:bg-red-50 border-red-200"
            >
              {annulerMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
              Annuler
            </button>
          )}
        </div>
      </div>

      {pdfError && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg flex items-center justify-between">
          <span>{pdfError}</span>
          <button onClick={() => setPdfError(null)} className="ml-3 text-red-400 hover:text-red-600">✕</button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Lines table */}
        <div className="lg:col-span-2 space-y-5">
          <div className="card overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h2 className="font-semibold text-gray-900">Lignes de commande</h2>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="table-header">Description</th>
                  <th className="table-header text-right">Qté cmd</th>
                  <th className="table-header text-right">Qté livrée</th>
                  <th className="table-header text-right">Reliquat</th>
                  <th className="table-header text-right">P.U.</th>
                  <th className="table-header text-right">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {commande.items.map((l) => (
                  <tr key={l.id}>
                    <td className="table-cell font-medium">{l.description}</td>
                    <td className="table-cell text-right text-gray-500">{l.quantity}</td>
                    <td className="table-cell text-right text-emerald-600">{l.delivered_quantity}</td>
                    <td className="table-cell text-right text-orange-600">{l.remaining_quantity}</td>
                    <td className="table-cell text-right">{formatCents(l.unit_price_cents, commande.currency)}</td>
                    <td className="table-cell text-right font-semibold">{formatCents(l.line_total_cents, commande.currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {commande.notes && (
            <div className="card p-5">
              <h2 className="font-semibold text-gray-900 mb-2">Notes</h2>
              <p className="text-sm text-gray-600 whitespace-pre-wrap">{commande.notes}</p>
            </div>
          )}
        </div>

        {/* Summary sidebar */}
        <div className="space-y-5">
          {/* Totaux */}
          <div className="card p-5">
            <h2 className="font-semibold text-gray-900 mb-4">Récapitulatif</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between text-gray-600">
                <span>Sous-total HT</span>
                <span>{formatCents(commande.subtotal_cents, commande.currency)}</span>
              </div>
              {commande.discount_cents > 0 && (
                <div className="flex justify-between text-gray-600">
                  <span>Remise</span>
                  <span className="text-red-600">-{formatCents(commande.discount_cents, commande.currency)}</span>
                </div>
              )}
              <div className="flex justify-between text-gray-600">
                <span>TVA ({commande.tax_rate}%)</span>
                <span>{formatCents(commande.tax_cents, commande.currency)}</span>
              </div>
              {commande.delivered_total_cents > 0 && (
                <div className="flex justify-between text-blue-600">
                  <span>Total livré facturable</span>
                  <span>{formatCents(commande.delivered_total_cents, commande.currency)}</span>
                </div>
              )}
              <div className="flex justify-between font-bold text-gray-900 text-base pt-2 border-t border-gray-100">
                <span>Total TTC</span>
                <span className="text-blue-700">{formatCents(commande.total_cents, commande.currency)}</span>
              </div>
              {commande.has_reliquat && (
                <div className="flex justify-between font-semibold text-orange-600">
                  <span>Reliquat en attente</span>
                  <span>Oui</span>
                </div>
              )}
              {commande.paid_cents > 0 && (
                <>
                  <div className="flex justify-between text-emerald-600">
                    <span>Payé</span>
                    <span>{formatCents(commande.paid_cents, commande.currency)}</span>
                  </div>
                  <div className="flex justify-between font-semibold text-orange-600">
                    <span>Reste dû</span>
                    <span>{formatCents(commande.balance_due_cents, commande.currency)}</span>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Client info */}
          {client && (
            <div className="card p-5">
              <h2 className="font-semibold text-gray-900 mb-3">Client</h2>
              <div className="space-y-1.5 text-sm text-gray-600">
                <p className="font-semibold text-gray-900">{client.full_name}</p>
                {client.company_name && <p className="text-gray-400">{client.company_name}</p>}
                {client.email && <p>{client.email}</p>}
                <p>{client.phone}</p>
              </div>
              <Link
                href={`/clients/${client.id}`}
                className="btn-secondary w-full justify-center mt-3 text-xs py-1.5"
              >
                Voir le profil client
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Payment modal */}
      {showPayModal && (
        <PaymentModal
          orderId={id}
          currency={commande.currency}
          balanceCents={commande.balance_due_cents}
          onClose={() => setShowPayModal(false)}
          onSuccess={() => {
            setShowPayModal(false);
            qc.invalidateQueries({ queryKey: ["commandes", id] });
          }}
        />
      )}
      {showDeliveryModal && (
        <DeliveryModal
          order={commande}
          onClose={() => setShowDeliveryModal(false)}
          onSuccess={() => {
            setShowDeliveryModal(false);
            qc.invalidateQueries({ queryKey: ["commandes", id] });
          }}
        />
      )}
    </div>
  );
}

function DeliveryModal({
  order,
  onClose,
  onSuccess,
}: {
  order: any;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(order.items.map((item: any) => [item.id, item.remaining_quantity > 0 ? String(item.remaining_quantity) : "0"]))
  );

  const { mutate, isPending, error } = useMutation({
    mutationFn: () =>
      commandesApi.enregistrerLivraison(
        order.id,
        order.items
          .map((item: any) => ({
            item_id: item.id,
            quantity: Number(values[item.id] ?? "0"),
          }))
          .filter((item: any) => item.quantity > 0)
      ),
    onSuccess,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900">Enregistrer une livraison</h2>
          <button onClick={onClose} className="btn-secondary py-1.5">Fermer</button>
        </div>

        <div className="space-y-3">
          {order.items.map((item: any) => (
            <div key={item.id} className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end border border-gray-100 rounded-xl p-3">
              <div className="md:col-span-2">
                <p className="font-medium text-gray-900">{item.description}</p>
                <p className="text-xs text-gray-500">
                  Commandée: {item.quantity} | Déjà livrée: {item.delivered_quantity} | Reliquat: {item.remaining_quantity}
                </p>
              </div>
              <div>
                <label className="label">Qté à livrer</label>
                <input
                  type="number"
                  min="0"
                  max={item.remaining_quantity}
                  step="any"
                  value={values[item.id] ?? "0"}
                  onChange={(e) => setValues((prev) => ({ ...prev, [item.id]: e.target.value }))}
                  className="input"
                />
              </div>
              <div className="text-sm text-gray-500">
                {formatCents(item.unit_price_cents, order.currency)} / unité
              </div>
            </div>
          ))}
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg">
            {(error as any)?.response?.data?.detail ?? "Erreur lors de l'enregistrement de la livraison"}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary" disabled={isPending}>
            Annuler
          </button>
          <button onClick={() => mutate()} className="btn-primary" disabled={isPending}>
            {isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Truck className="w-4 h-4" />}
            Enregistrer la livraison
          </button>
        </div>
      </div>
    </div>
  );
}

function PaymentModal({
  orderId,
  currency,
  balanceCents,
  onClose,
  onSuccess,
}: {
  orderId: string;
  currency: string;
  balanceCents: number;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [methode, setMethode] = useState<PaymentMethod>("bank_transfer");
  const [montantXAF, setMontantXAF] = useState(String(balanceCents));
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");

  const { mutate, isPending, error } = useMutation({
    mutationFn: () =>
      paiementsApi.enregistrer({
        order_id: orderId,
        amount_cents: parseInt(montantXAF, 10) || balanceCents,
        method: methode,
        external_reference: reference || undefined,
        notes: notes || undefined,
      }),
    onSuccess,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-5">
        <div>
          <h2 className="text-lg font-bold text-gray-900">Enregistrer un paiement</h2>
          <p className="text-sm text-gray-500 mt-1">
            Solde restant : <span className="font-semibold text-gray-900">{formatCents(balanceCents, currency)}</span>
          </p>
        </div>

        <div>
          <label className="label">Méthode de paiement</label>
          <select
            value={methode}
            onChange={(e) => setMethode(e.target.value as PaymentMethod)}
            className="input"
          >
            {(Object.keys(METHODE_LABELS) as PaymentMethod[]).map((m) => (
              <option key={m} value={m}>{METHODE_LABELS[m]}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="label">Montant (en {currency})</label>
          <input
            type="number"
            min={1}
            value={montantXAF}
            onChange={(e) => setMontantXAF(e.target.value)}
            className="input"
          />
        </div>

        <div>
          <label className="label">Référence externe (optionnel)</label>
          <input
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            placeholder="N° virement, N° chèque…"
            className="input"
          />
        </div>

        <div>
          <label className="label">Notes (optionnel)</label>
          <input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Observations…"
            className="input"
          />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg">
            {(error as any)?.response?.data?.detail ?? "Erreur lors de l'enregistrement"}
          </div>
        )}

        <div className="flex gap-3 justify-end pt-2 border-t border-gray-100">
          <button onClick={onClose} className="btn-secondary">Annuler</button>
          <button onClick={() => mutate()} disabled={isPending} className="btn-primary">
            {isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
            Confirmer le paiement
          </button>
        </div>
      </div>
    </div>
  );
}
