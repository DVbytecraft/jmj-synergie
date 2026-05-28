"use client";

import { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { commandesApi } from "@/lib/api/commandes";
import { clientsApi } from "@/lib/api/clients";
import { paiementsApi } from "@/lib/api/paiements";
import { apiClient } from "@/lib/api/client";
import { formatCents } from "@/lib/utils/money";
import type { PaymentMethod } from "@/types";
import {
  ArrowLeft, CheckCircle, XCircle, Download, FileText,
  CreditCard, Loader2, Package, Truck, Wallet, Receipt,
  ShoppingCart, ClipboardList, ChevronRight,
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

type DocType = "purchase_order" | "pro_forma" | "invoice" | "delivery_note" | "payment_receipt";

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

  const { data: payments } = useQuery({
    queryKey: ["payments", id],
    queryFn: () => paiementsApi.list({ order_id: id }),
    enabled: !!commande && commande.paid_cents > 0,
  });

  const confirmerMut = useMutation({
    mutationFn: () => commandesApi.confirmer(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["commandes", id] }),
  });

  const annulerMut = useMutation({
    mutationFn: () => commandesApi.annuler(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["commandes", id] }),
  });

  const [docLoading, setDocLoading] = useState<DocType | string | null>(null);
  const [docError, setDocError] = useState<string | null>(null);

  const generateAndDownload = async (endpoint: string, fileName: string, loadingKey: string) => {
    setDocLoading(loadingKey);
    setDocError(null);
    try {
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
      setDocError(err?.response?.data?.detail ?? "Erreur lors de la génération du document");
    } finally {
      setDocLoading(null);
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
  const isConfirmed = ["confirmed", "in_progress", "in_production", "ready", "partially_delivered", "delivered"].includes(commande.status);
  const hasPaid = commande.paid_cents > 0;

  const latestPayment = payments?.items?.find((p) => p.status === "completed") ?? payments?.items?.[0];

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

        {/* Action buttons */}
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

      {docError && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg flex items-center justify-between">
          <span>{docError}</span>
          <button onClick={() => setDocError(null)} className="ml-3 text-red-400 hover:text-red-600">✕</button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Lines table */}
        <div className="lg:col-span-2 space-y-5">
          <div className="card overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h2 className="font-semibold text-gray-900">Lignes de commande</h2>
            </div>
            <div className="overflow-x-auto">
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
          </div>

          {commande.notes && (
            <div className="card p-5">
              <h2 className="font-semibold text-gray-900 mb-2">Notes</h2>
              <p className="text-sm text-gray-600 whitespace-pre-wrap">{commande.notes}</p>
            </div>
          )}
        </div>

        {/* Sidebar */}
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
              {hasPaid && (
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

          {/* Documents flow */}
          <div className="card p-5">
            <h2 className="font-semibold text-gray-900 mb-4">Documents</h2>
            <div className="space-y-2">

              {/* 1. Bon de commande */}
              <DocStep
                icon={<ShoppingCart className="w-4 h-4" />}
                label="Bon de commande"
                available={true}
                loading={docLoading === "purchase_order"}
                onGenerate={() =>
                  generateAndDownload(
                    `/documents/purchase-order/${id}`,
                    `bon_commande-${id.slice(0, 8)}.pdf`,
                    "purchase_order"
                  )
                }
              />

              {/* 2. Pro forma */}
              <DocStep
                icon={<ClipboardList className="w-4 h-4" />}
                label="Pro forma"
                available={true}
                loading={docLoading === "pro_forma"}
                onGenerate={() =>
                  generateAndDownload(
                    `/documents/pro-forma/${id}`,
                    `proforma-${id.slice(0, 8)}.pdf`,
                    "pro_forma"
                  )
                }
              />

              {/* Separator — confirm step */}
              {canConfirm && (
                <div className="py-1">
                  <button
                    onClick={() => confirmerMut.mutate()}
                    disabled={confirmerMut.isPending}
                    className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 transition-colors"
                  >
                    {confirmerMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                    Confirmer la commande
                  </button>
                </div>
              )}

              {/* 3. Facture */}
              <DocStep
                icon={<FileText className="w-4 h-4" />}
                label="Facture"
                available={isConfirmed}
                disabledReason="Confirmez la commande d'abord"
                loading={docLoading === "invoice"}
                onGenerate={() =>
                  generateAndDownload(
                    `/documents/invoice/${id}`,
                    `facture-${id.slice(0, 8)}.pdf`,
                    "invoice"
                  )
                }
              />

              {/* 4. Bon de livraison */}
              <DocStep
                icon={<Truck className="w-4 h-4" />}
                label="Bon de livraison"
                available={isConfirmed}
                disabledReason="Confirmez la commande d'abord"
                loading={docLoading === "delivery_note"}
                onGenerate={() =>
                  generateAndDownload(
                    `/documents/delivery-note/${id}`,
                    `bon_livraison-${id.slice(0, 8)}.pdf`,
                    "delivery_note"
                  )
                }
              />

              {/* Separator — payment step */}
              {isConfirmed && !hasPaid && (
                <div className="py-1">
                  <button
                    onClick={() => setShowPayModal(true)}
                    className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm font-medium bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 transition-colors"
                  >
                    <CreditCard className="w-4 h-4" />
                    Enregistrer un paiement
                  </button>
                </div>
              )}

              {/* 5. Reçu de paiement */}
              {hasPaid && latestPayment ? (
                <DocStep
                  icon={<Receipt className="w-4 h-4" />}
                  label="Reçu de paiement"
                  available={true}
                  loading={docLoading === "payment_receipt"}
                  onGenerate={() =>
                    generateAndDownload(
                      `/documents/payment-receipt/${id}/${latestPayment.id}`,
                      `recu_paiement-${id.slice(0, 8)}.pdf`,
                      "payment_receipt"
                    )
                  }
                />
              ) : (
                <DocStep
                  icon={<Receipt className="w-4 h-4" />}
                  label="Reçu de paiement"
                  available={false}
                  disabledReason="Enregistrez un paiement d'abord"
                  loading={false}
                  onGenerate={() => {}}
                />
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

      {/* Modals */}
      {showPayModal && (
        <PaymentModal
          orderId={id}
          currency={commande.currency}
          balanceCents={commande.balance_due_cents}
          onClose={() => setShowPayModal(false)}
          onSuccess={() => {
            setShowPayModal(false);
            qc.invalidateQueries({ queryKey: ["commandes", id] });
            qc.invalidateQueries({ queryKey: ["payments", id] });
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

function DocStep({
  icon,
  label,
  available,
  loading,
  disabledReason,
  onGenerate,
}: {
  icon: React.ReactNode;
  label: string;
  available: boolean;
  loading: boolean;
  disabledReason?: string;
  onGenerate: () => void;
}) {
  return (
    <div
      className={`flex items-center justify-between gap-2 py-2 px-3 rounded-lg border transition-colors ${
        available
          ? "border-gray-200 bg-white hover:bg-gray-50"
          : "border-gray-100 bg-gray-50 opacity-60"
      }`}
      title={!available ? disabledReason : undefined}
    >
      <div className="flex items-center gap-2 text-sm text-gray-700">
        <span className={available ? "text-blue-600" : "text-gray-400"}>{icon}</span>
        <span className={available ? "font-medium" : "text-gray-400"}>{label}</span>
      </div>
      <button
        onClick={onGenerate}
        disabled={!available || loading}
        className={`flex items-center gap-1 text-xs px-2 py-1 rounded-md font-medium transition-colors ${
          available
            ? "bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200"
            : "bg-gray-100 text-gray-400 cursor-not-allowed border border-gray-200"
        }`}
      >
        {loading ? (
          <Loader2 className="w-3 h-3 animate-spin" />
        ) : (
          <Download className="w-3 h-3" />
        )}
        Générer
      </button>
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
