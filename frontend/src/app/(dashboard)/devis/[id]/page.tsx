"use client";

import { use } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { quotesApi } from "@/lib/api/quotes";
import { clientsApi } from "@/lib/api/clients";
import { formatCents } from "@/lib/utils/money";
import { formatDateFr } from "@/lib/utils/format-dates";
import { QuoteStatusBadge } from "@/components/ui/QuoteStatusBadge";
import {
  ArrowLeft, CheckCircle, XCircle, Send, ShoppingCart,
  Loader2, ClipboardList, ChevronRight,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function DevisDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const qc = useQueryClient();
  const router = useRouter();

  const { data: quote, isLoading } = useQuery({
    queryKey: ["quotes", id],
    queryFn: () => quotesApi.get(id),
  });

  const { data: client } = useQuery({
    queryKey: ["clients", quote?.client_id],
    queryFn: () => clientsApi.get(quote!.client_id),
    enabled: !!quote?.client_id,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["quotes", id] });
    qc.invalidateQueries({ queryKey: ["quotes"] });
  };

  const sendMut = useMutation({
    mutationFn: () => quotesApi.send(id),
    onSuccess: invalidate,
  });

  const acceptMut = useMutation({
    mutationFn: () => quotesApi.accept(id),
    onSuccess: invalidate,
  });

  const rejectMut = useMutation({
    mutationFn: () => quotesApi.reject(id),
    onSuccess: invalidate,
  });

  const convertMut = useMutation({
    mutationFn: () => quotesApi.convert(id),
    onSuccess: (data) => {
      invalidate();
      if (data.converted_to_order_id) {
        router.push(`/commandes/${data.converted_to_order_id}`);
      }
    },
  });

  const deleteMut = useMutation({
    mutationFn: () => quotesApi.delete(id),
    onSuccess: () => router.push("/devis"),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!quote) {
    return <div className="text-center py-16 text-gray-400">Devis introuvable</div>;
  }

  const isDraft = quote.status === "draft";
  const isSent = quote.status === "sent";
  const isAccepted = quote.status === "accepted";
  const canSend = isDraft;
  const canAccept = isDraft || isSent;
  const canReject = isDraft || isSent || isAccepted;
  const canConvert = isDraft || isSent || isAccepted;
  const canDelete = isDraft;
  const anyPending =
    sendMut.isPending || acceptMut.isPending || rejectMut.isPending ||
    convertMut.isPending || deleteMut.isPending;

  const mutError =
    (sendMut.error || acceptMut.error || rejectMut.error || convertMut.error || deleteMut.error) as any;

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <Link href="/devis" className="btn-secondary py-1.5 px-3">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-gray-900 font-mono">{quote.quote_number}</h1>
            <QuoteStatusBadge status={quote.status} />
          </div>
          <p className="text-sm text-gray-400 mt-0.5">Créé le {formatDateFr(quote.created_at)}</p>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2 flex-wrap">
          {canSend && (
            <button
              onClick={() => sendMut.mutate()}
              disabled={anyPending}
              className="btn-primary bg-blue-600 hover:bg-blue-700"
            >
              {sendMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Envoyer
            </button>
          )}
          {canAccept && (
            <button
              onClick={() => acceptMut.mutate()}
              disabled={anyPending}
              className="btn-primary bg-emerald-600 hover:bg-emerald-700"
            >
              {acceptMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
              Accepter
            </button>
          )}
          {canConvert && (
            <button
              onClick={() => convertMut.mutate()}
              disabled={anyPending}
              className="btn-primary bg-purple-600 hover:bg-purple-700"
            >
              {convertMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShoppingCart className="w-4 h-4" />}
              Convertir en commande
            </button>
          )}
          {canReject && (
            <button
              onClick={() => rejectMut.mutate()}
              disabled={anyPending}
              className="btn-secondary text-red-600 hover:bg-red-50 border-red-200"
            >
              {rejectMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
              Refuser
            </button>
          )}
          {canDelete && (
            <button
              onClick={() => {
                if (window.confirm("Supprimer ce devis ?")) deleteMut.mutate();
              }}
              disabled={anyPending}
              className="btn-secondary text-red-600 hover:bg-red-50 border-red-200"
            >
              {deleteMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              Supprimer
            </button>
          )}
        </div>
      </div>

      {mutError && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg">
          {mutError?.response?.data?.detail ?? "Une erreur est survenue"}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Lignes */}
        <div className="lg:col-span-2 space-y-5">
          <div className="card overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100">
              <h2 className="font-semibold text-gray-900">Lignes du devis</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="table-header">Description</th>
                    <th className="table-header text-right">Qté</th>
                    <th className="table-header text-right">P.U.</th>
                    <th className="table-header text-right">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {quote.items.map((item) => (
                    <tr key={item.id}>
                      <td className="table-cell font-medium">{item.description}</td>
                      <td className="table-cell text-right text-gray-500">{item.quantity}</td>
                      <td className="table-cell text-right">{formatCents(item.unit_price_cents, quote.currency)}</td>
                      <td className="table-cell text-right font-semibold">{formatCents(item.total_cents, quote.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {quote.notes && (
            <div className="card p-5">
              <h2 className="font-semibold text-gray-900 mb-2">Notes</h2>
              <p className="text-sm text-gray-600 whitespace-pre-wrap">{quote.notes}</p>
            </div>
          )}

          {/* Lien vers la commande convertie */}
          {quote.converted_to_order_id && (
            <div className="card p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm text-gray-700">
                  <ShoppingCart className="w-4 h-4 text-purple-600" />
                  <span>Ce devis a été converti en commande</span>
                </div>
                <Link
                  href={`/commandes/${quote.converted_to_order_id}`}
                  className="flex items-center gap-1 text-sm font-medium text-purple-600 hover:text-purple-700"
                >
                  Voir la commande
                  <ChevronRight className="w-4 h-4" />
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-5">
          {/* Récapitulatif */}
          <div className="card p-5">
            <h2 className="font-semibold text-gray-900 mb-4">Récapitulatif</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between text-gray-600">
                <span>Sous-total HT</span>
                <span>{formatCents(quote.subtotal_cents, quote.currency)}</span>
              </div>
              <div className="flex justify-between text-gray-600">
                <span>TVA ({Number(quote.tax_rate)}%)</span>
                <span>{formatCents(quote.tax_cents, quote.currency)}</span>
              </div>
              <div className="flex justify-between font-bold text-gray-900 text-base pt-2 border-t border-gray-100">
                <span>Total TTC</span>
                <span className="text-blue-700">{formatCents(quote.total_cents, quote.currency)}</span>
              </div>
            </div>
          </div>

          {/* Dates */}
          <div className="card p-5">
            <h2 className="font-semibold text-gray-900 mb-3">Dates</h2>
            <div className="space-y-2 text-sm text-gray-600">
              <div className="flex justify-between">
                <span className="text-gray-500">Créé le</span>
                <span>{formatDateFr(quote.created_at)}</span>
              </div>
              {quote.valid_until && (
                <div className="flex justify-between">
                  <span className="text-gray-500">Valide jusqu'au</span>
                  <span>{formatDateFr(quote.valid_until)}</span>
                </div>
              )}
              {quote.sent_at && (
                <div className="flex justify-between">
                  <span className="text-gray-500">Envoyé le</span>
                  <span>{formatDateFr(quote.sent_at)}</span>
                </div>
              )}
              {quote.accepted_at && (
                <div className="flex justify-between">
                  <span className="text-gray-500">Accepté le</span>
                  <span className="text-emerald-600">{formatDateFr(quote.accepted_at)}</span>
                </div>
              )}
              {quote.rejected_at && (
                <div className="flex justify-between">
                  <span className="text-gray-500">Refusé le</span>
                  <span className="text-red-600">{formatDateFr(quote.rejected_at)}</span>
                </div>
              )}
            </div>
          </div>

          {/* Client */}
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

          {/* Actions rapides */}
          {isDraft && (
            <div className="card p-5">
              <h2 className="font-semibold text-gray-900 mb-3">Actions</h2>
              <div className="space-y-2">
                <Link
                  href={`/devis/${id}?edit=1`}
                  className="w-full flex items-center gap-2 py-2 px-3 rounded-lg text-sm font-medium bg-gray-50 text-gray-700 border border-gray-200 hover:bg-gray-100 transition-colors"
                >
                  <ClipboardList className="w-4 h-4 text-gray-500" />
                  Modifier le devis
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
