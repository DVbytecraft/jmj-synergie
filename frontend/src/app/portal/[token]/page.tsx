"use client";

import Image from "next/image";
import { use, useEffect, useState } from "react";
import { portalApi, type PortalOrderInfo } from "@/lib/api/portal";
import { formatCents } from "@/lib/utils/money";
import { FileText, Package, CheckCircle, XCircle, Clock, Truck, Receipt } from "lucide-react";

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  draft:               { label: "Brouillon",            color: "text-slate-700",   bg: "bg-slate-100"   },
  confirmed:           { label: "Confirmée",            color: "text-blue-700",    bg: "bg-blue-50"     },
  in_progress:         { label: "En cours",             color: "text-amber-700",   bg: "bg-amber-50"    },
  in_production:       { label: "En production",        color: "text-amber-700",   bg: "bg-amber-50"    },
  ready:               { label: "Prête",                color: "text-teal-700",    bg: "bg-teal-50"     },
  partially_delivered: { label: "Partiell. livrée",     color: "text-orange-700",  bg: "bg-orange-50"   },
  delivered:           { label: "Livrée",               color: "text-emerald-700", bg: "bg-emerald-50"  },
  cancelled:           { label: "Annulée",              color: "text-red-700",     bg: "bg-red-50"      },
  refunded:            { label: "Remboursée",           color: "text-purple-700",  bg: "bg-purple-50"   },
};

const DOC_LABELS: Record<string, { label: string; icon: React.ReactNode }> = {
  purchase_order:  { label: "Bon de commande",  icon: <Package className="w-4 h-4" /> },
  pro_forma:       { label: "Pro forma",         icon: <FileText className="w-4 h-4" /> },
  invoice:         { label: "Facture",           icon: <FileText className="w-4 h-4" /> },
  delivery_note:   { label: "Bon de livraison", icon: <Truck className="w-4 h-4" /> },
  payment_receipt: { label: "Reçu de paiement", icon: <Receipt className="w-4 h-4" /> },
};

const remoteImageLoader = ({ src }: { src: string }) => src;

export default function PortalPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [order, setOrder] = useState<PortalOrderInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    portalApi
      .getOrderByToken(token)
      .then(setOrder)
      .catch(() => setExpired(true))
      .finally(() => setLoading(false));
  }, [token]);

  const status = order ? (STATUS_CONFIG[order.status] ?? { label: order.status, color: "text-gray-700", bg: "bg-gray-100" }) : null;
  const balance = order ? Math.max(0, order.total_cents - order.paid_cents) : 0;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-4">
        <div className="max-w-2xl mx-auto flex items-center gap-3">
          <Image
            loader={remoteImageLoader}
            src={order?.organization_logo_url || "/logo.svg"}
            alt={order?.organization_name || "JMJ Synergie"}
            width={32}
            height={32}
            unoptimized
            className="w-8 h-8 rounded-xl"
          />
          <span className="font-bold text-gray-900 text-lg">
            {order?.organization_name || "JMJ Synergie"}
          </span>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-10 space-y-6">
        {loading && (
          <div className="text-center py-20">
            <div className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
            <p className="text-gray-500 mt-4 text-sm">Chargement…</p>
          </div>
        )}

        {expired && !loading && (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-10 text-center space-y-4">
            <div className="w-16 h-16 mx-auto bg-red-50 rounded-full flex items-center justify-center">
              <XCircle className="w-8 h-8 text-red-400" />
            </div>
            <h1 className="text-xl font-bold text-gray-900">Lien expiré</h1>
            <p className="text-gray-500 text-sm max-w-sm mx-auto">
              Ce lien de partage est invalide ou a expiré. Contactez votre fournisseur pour obtenir un nouveau lien.
            </p>
          </div>
        )}

        {order && status && !loading && (
          <>
            {/* Commande header */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <p className="text-xs text-gray-400 uppercase tracking-wide font-medium mb-1">Commande</p>
                  <h1 className="text-2xl font-bold text-gray-900 font-mono">{order.order_number}</h1>
                  <p className="text-sm text-gray-500 mt-1">Client : <span className="font-medium text-gray-700">{order.client_name}</span></p>
                </div>
                <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-semibold ${status.bg} ${status.color}`}>
                  <span className="w-2 h-2 rounded-full bg-current opacity-70" />
                  {status.label}
                </span>
              </div>
            </div>

            {/* Montants */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-3">
              <h2 className="font-semibold text-gray-900 text-base">Récapitulatif financier</h2>
              <div className="space-y-2.5 text-sm">
                <div className="flex justify-between items-center">
                  <span className="text-gray-500">Total TTC</span>
                  <span className="font-bold text-gray-900 text-base">{formatCents(order.total_cents, order.currency)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 flex items-center gap-1.5">
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
                    Montant payé
                  </span>
                  <span className="font-semibold text-emerald-600">{formatCents(order.paid_cents, order.currency)}</span>
                </div>
                {balance > 0 && (
                  <div className="flex justify-between items-center pt-2 border-t border-gray-100">
                    <span className="text-gray-500 flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-orange-400" />
                      Reste à payer
                    </span>
                    <span className="font-bold text-orange-600">{formatCents(balance, order.currency)}</span>
                  </div>
                )}
                {balance === 0 && order.paid_cents > 0 && (
                  <div className="flex items-center gap-2 pt-2 border-t border-gray-100 text-emerald-600">
                    <CheckCircle className="w-4 h-4" />
                    <span className="font-semibold text-sm">Entièrement payé</span>
                  </div>
                )}
              </div>
            </div>

            {/* Documents */}
            {order.document_types.length > 0 && (
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-3">
                <h2 className="font-semibold text-gray-900 text-base">Documents disponibles</h2>
                <p className="text-xs text-gray-400">Contactez votre fournisseur pour recevoir ces documents.</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {order.document_types.map((type) => {
                    const doc = DOC_LABELS[type] ?? { label: type, icon: <FileText className="w-4 h-4" /> };
                    return (
                      <div
                        key={type}
                        className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl border border-gray-100 bg-gray-50 text-sm text-gray-700"
                      >
                        <span className="text-blue-500">{doc.icon}</span>
                        <span className="font-medium">{doc.label}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            <p className="text-center text-xs text-gray-400 pb-4">
              Lien généré par <span className="font-semibold text-gray-600">{order.organization_name}</span> — plateforme de gestion commerciale
            </p>
          </>
        )}
      </main>
    </div>
  );
}
