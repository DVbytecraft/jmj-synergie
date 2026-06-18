"use client";
import { formatDateFr, formatDateTimeFr } from "@/lib/utils/format-dates";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { commandesApi } from "@/lib/api/commandes";
import { documentsApi } from "@/lib/api/documents";
import {
  useDocumentsOrder,
  useGenererBonLivraison,
  useGenererFacture,
  useGenererProForma,
  useSignerDocument,
} from "@/lib/hooks/use-documents";
import {
  Download, PenLine, Loader2, Plus, Mail, Send,
  CheckCircle2, Clock, ChevronDown, Receipt, Truck,
  List, FolderOpen, AlertCircle, X, Filter,
  Pencil,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import Link from "next/link";

type ActiveTab = "all" | "by-order";

const DOC_TYPE_LABELS: Record<string, string> = {
  pro_forma: "Pro Forma",
  invoice: "Facture",
  delivery_note: "Bon de livraison",
  purchase_order: "Bon de commande",
  payment_receipt: "Reçu de paiement",
  scanned: "Scanné",
};

const DOC_TYPE_OPTIONS = [
  { value: "", label: "Tous les types" },
  { value: "invoice", label: "Factures" },
  { value: "pro_forma", label: "Pro Formas" },
  { value: "delivery_note", label: "Bons de livraison" },
  { value: "purchase_order", label: "Bons de commande" },
  { value: "payment_receipt", label: "Reçus de paiement" },
];

const CLIENT_TYPE_OPTIONS = [
  { value: "", label: "Tous les clients" },
  { value: "individual", label: "Particuliers" },
  { value: "company", label: "Entreprises" },
  { value: "government", label: "Administrations" },
  { value: "ngo", label: "ONG" },
];

export default function DocumentsPage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("all");
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [emailModalDocId, setEmailModalDocId] = useState<string | null>(null);
  const [emailRecipient, setEmailRecipient] = useState("");
  const [emailSuccess, setEmailSuccess] = useState<string | null>(null);
  const [allPage, setAllPage] = useState(0);

  // Filters
  const [docTypeFilter, setDocTypeFilter] = useState("");
  const [clientTypeFilter, setClientTypeFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const LIMIT = 20;
  /* ── Data ─────────────────────────────────────────────────────────────── */
  const { data: orders, isLoading: loadingOrders } = useQuery({
    queryKey: ["commandes", "docs"],
    queryFn: () => commandesApi.list({ limit: 100 }),
  });

  const { data: allDocs, isLoading: loadingAll } = useQuery({
    queryKey: ["documents", "all", allPage, docTypeFilter, clientTypeFilter, dateFrom, dateTo],
    queryFn: () =>
      documentsApi.listAll({
        skip: allPage * LIMIT,
        limit: LIMIT,
        document_type: docTypeFilter || undefined,
        client_type: clientTypeFilter || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      }),
    enabled: activeTab === "all",
  });

  const { data: orderDocs, isLoading: loadingDocs } = useDocumentsOrder(
    activeTab === "by-order" ? (selectedOrderId ?? "") : ""
  );

  /* ── Mutations ────────────────────────────────────────────────────────── */
  const genererMut = useGenererProForma();
  const invoiceMut = useGenererFacture();
  const deliveryMut = useGenererBonLivraison();
  const signerMut = useSignerDocument();

  const sendEmailMut = useMutation({
    mutationFn: ({ docId, email }: { docId: string; email: string }) =>
      documentsApi.sendEmail(docId, email || undefined),
    onSuccess: (data) => {
      setEmailSuccess(data.message);
      setEmailModalDocId(null);
      setEmailRecipient("");
      setTimeout(() => setEmailSuccess(null), 4000);
    },
  });

  /* ── Download ─────────────────────────────────────────────────────────── */
  const handleDownload = async (docId: string, fileName: string) => {
    const res = await apiClient.get(`/documents/${docId}/download`, { responseType: "blob" });
    const url = URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = fileName;
    a.click();
    URL.revokeObjectURL(url);
  };

  const resetFilters = () => {
    setDocTypeFilter("");
    setClientTypeFilter("");
    setDateFrom("");
    setDateTo("");
    setAllPage(0);
  };

  const hasActiveFilters = docTypeFilter || clientTypeFilter || dateFrom || dateTo;

  /* ── Row renderer ─────────────────────────────────────────────────────── */
  const renderDocRow = (doc: {
    id: string;
    document_type: string;
    document_number: string;
    file_name: string;
    is_signed: boolean;
    is_stamped?: boolean;
    order_id?: string | null;
    created_at: string;
  }) => (
    <tr key={doc.id} className="hover:bg-gray-50">
      <td className="table-cell font-mono text-xs">{doc.document_number}</td>
      <td className="table-cell">
        <span className={`badge text-xs ${
          doc.document_type === "invoice"          ? "badge-blue" :
          doc.document_type === "pro_forma"        ? "badge-gray" :
          doc.document_type === "delivery_note"    ? "badge-emerald" :
          doc.document_type === "purchase_order"   ? "badge-amber" :
          doc.document_type === "payment_receipt"  ? "badge-blue" :
          "badge-amber"
        }`}>
          {DOC_TYPE_LABELS[doc.document_type] ?? doc.document_type}
        </span>
      </td>
      <td className="table-cell text-gray-400 text-xs truncate max-w-[140px]">{doc.file_name}</td>
      <td className="table-cell text-center">
        {doc.is_signed ? (
          <CheckCircle2 className="w-4 h-4 text-green-500 mx-auto" />
        ) : (
          <Clock className="w-4 h-4 text-gray-300 mx-auto" />
        )}
      </td>
      <td className="table-cell text-gray-500 text-xs">
        {formatDateFr(doc.created_at)}
      </td>
      <td className="table-cell">
        <div className="flex items-center justify-center gap-1">
          <button
            onClick={() => handleDownload(doc.id, doc.file_name)}
            className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-blue-600"
            title="Télécharger"
          >
            <Download className="w-4 h-4" />
          </button>
          <button
            onClick={() => { setEmailModalDocId(doc.id); setEmailRecipient(""); }}
            className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-indigo-600"
            title="Envoyer par email"
          >
            <Mail className="w-4 h-4" />
          </button>
          {!doc.is_signed && doc.order_id && (
            <button
              onClick={() =>
                signerMut.mutate({ document_id: doc.id, order_id: doc.order_id! })
              }
              disabled={signerMut.isPending}
              className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-emerald-600"
              title="Apposer signature et cachet"
            >
              <PenLine className="w-4 h-4" />
            </button>
          )}
          {/* Modifier la commande liée (édition des lignes) */}
          {doc.order_id && (
            <Link
              href={`/commandes/${doc.order_id}`}
              className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-orange-600"
              title="Modifier la commande (lignes, montants)"
            >
              <Pencil className="w-4 h-4" />
            </Link>
          )}
        </div>
      </td>
    </tr>
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Documents</h1>
        <p className="text-sm text-gray-500 mt-1">Pro formas, factures, bons de livraison et reçus</p>
      </div>

      {/* Success toast */}
      {emailSuccess && (
        <div className="flex items-center gap-3 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3 text-sm text-emerald-800">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          {emailSuccess}
        </div>
      )}

      {/* Onglets */}
      <div className="flex gap-1 border-b border-gray-200">
        {(["all", "by-order"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px flex items-center gap-2 transition-colors ${
              activeTab === tab
                ? "border-blue-600 text-blue-700"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab === "all" ? <List className="w-4 h-4" /> : <FolderOpen className="w-4 h-4" />}
            {tab === "all" ? "Tous les documents" : "Par commande"}
          </button>
        ))}
      </div>

      {/* ── Tab: Tous les documents ── */}
      {activeTab === "all" && (
        <div className="space-y-4">
          {/* Filtres */}
          <div className="card p-4">
            <div className="flex items-center gap-2 mb-3">
              <Filter className="w-4 h-4 text-blue-600" />
              <span className="text-sm font-medium text-gray-900">Filtres</span>
              {hasActiveFilters && (
                <button
                  onClick={resetFilters}
                  className="ml-auto text-xs text-gray-500 hover:text-red-600 flex items-center gap-1"
                >
                  <X className="w-3 h-3" /> Réinitialiser
                </button>
              )}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div>
                <label className="label">Type de document</label>
                <div className="relative">
                  <select
                    className="input appearance-none pr-8"
                    value={docTypeFilter}
                    onChange={(e) => { setDocTypeFilter(e.target.value); setAllPage(0); }}
                  >
                    {DOC_TYPE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                </div>
              </div>
              <div>
                <label className="label">Type de client</label>
                <div className="relative">
                  <select
                    className="input appearance-none pr-8"
                    value={clientTypeFilter}
                    onChange={(e) => { setClientTypeFilter(e.target.value); setAllPage(0); }}
                  >
                    {CLIENT_TYPE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                </div>
              </div>
              <div>
                <label className="label">Du</label>
                <input
                  type="date"
                  className="input"
                  value={dateFrom}
                  onChange={(e) => { setDateFrom(e.target.value); setAllPage(0); }}
                />
              </div>
              <div>
                <label className="label">Au</label>
                <input
                  type="date"
                  className="input"
                  value={dateTo}
                  onChange={(e) => { setDateTo(e.target.value); setAllPage(0); }}
                />
              </div>
            </div>
          </div>

          <div className="card overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">
                Documents ({allDocs?.total ?? 0})
              </h2>
            </div>

            {loadingAll ? (
              <div className="flex justify-center py-10">
                <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
              </div>
            ) : !allDocs?.items.length ? (
              <div className="py-12 text-center text-gray-400 text-sm">
                Aucun document{hasActiveFilters ? " pour ces critères" : " généré pour l'instant"}
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="table-header">N° Document</th>
                        <th className="table-header">Type</th>
                        <th className="table-header">Fichier</th>
                        <th className="table-header text-center">Signé</th>
                        <th className="table-header">Date</th>
                        <th className="table-header text-center">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {allDocs.items.map(renderDocRow)}
                    </tbody>
                  </table>
                </div>
                {allDocs.total > LIMIT && (
                  <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100">
                    <span className="text-xs text-gray-400">
                      {allPage * LIMIT + 1}–{Math.min((allPage + 1) * LIMIT, allDocs.total)} sur {allDocs.total}
                    </span>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setAllPage((p) => Math.max(0, p - 1))}
                        disabled={allPage === 0}
                        className="btn-secondary text-xs px-3 py-1"
                      >
                        Précédent
                      </button>
                      <button
                        onClick={() => setAllPage((p) => p + 1)}
                        disabled={(allPage + 1) * LIMIT >= allDocs.total}
                        className="btn-secondary text-xs px-3 py-1"
                      >
                        Suivant
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Tab: Par commande ── */}
      {activeTab === "by-order" && (
        <>
          <div className="card p-5">
            <h2 className="font-semibold text-gray-900 mb-3">Sélectionner une commande</h2>
            <div className="relative max-w-md">
              <select
                className="input appearance-none pr-10"
                value={selectedOrderId ?? ""}
                onChange={(e) => setSelectedOrderId(e.target.value || null)}
              >
                <option value="">— Choisir une commande —</option>
                {orders?.items.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.order_number} — {o.status}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
            </div>

            {selectedOrderId && (
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  onClick={() => genererMut.mutate(selectedOrderId)}
                  disabled={genererMut.isPending}
                  className="btn-primary"
                >
                  {genererMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  Générer pro forma
                </button>
                <button
                  onClick={() => deliveryMut.mutate({ order_id: selectedOrderId })}
                  disabled={deliveryMut.isPending}
                  className="btn-secondary"
                >
                  {deliveryMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Truck className="w-4 h-4" />}
                  Bon de livraison
                </button>
                <button
                  onClick={() => invoiceMut.mutate(selectedOrderId)}
                  disabled={invoiceMut.isPending}
                  className="btn-secondary"
                >
                  {invoiceMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Receipt className="w-4 h-4" />}
                  Facture définitive
                </button>
                <Link
                  href={`/commandes/${selectedOrderId}`}
                  className="btn-secondary inline-flex items-center gap-2"
                >
                  <Pencil className="w-4 h-4" />
                  Modifier la commande
                </Link>
              </div>
            )}
          </div>

          {selectedOrderId && (
            <div className="card overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100">
                <h2 className="font-semibold text-gray-900">Documents ({orderDocs?.length ?? 0})</h2>
              </div>
              {loadingDocs ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
                </div>
              ) : !orderDocs?.length ? (
                <div className="py-10 text-center text-gray-400 text-sm">Aucun document généré</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="table-header">N° Document</th>
                        <th className="table-header">Type</th>
                        <th className="table-header">Fichier</th>
                        <th className="table-header text-center">Signé</th>
                        <th className="table-header">Date</th>
                        <th className="table-header text-center">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {orderDocs.map((doc) => renderDocRow({ ...doc, order_id: selectedOrderId }))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* ── Email modal ── */}
      {emailModalDocId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Send className="w-4 h-4 text-blue-600" />
                Envoyer par email
              </h3>
              <button onClick={() => setEmailModalDocId(null)} className="p-1.5 hover:bg-gray-100 rounded-lg">
                <X className="w-4 h-4 text-gray-500" />
              </button>
            </div>
            <div>
              <label className="label">Destinataire supplémentaire (optionnel)</label>
              <input
                type="email"
                value={emailRecipient}
                onChange={(e) => setEmailRecipient(e.target.value)}
                className="input"
                placeholder="client@exemple.com — laissez vide pour envoyer à votre email"
              />
              <p className="text-xs text-gray-400 mt-1.5">
                Le document sera envoyé à votre email de compte. Ajoutez un destinataire si besoin.
              </p>
            </div>
            {sendEmailMut.isError && (
              <div className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                {(sendEmailMut.error as any)?.response?.data?.detail ?? "Erreur lors de l'envoi"}
              </div>
            )}
            <div className="flex gap-3 justify-end">
              <button onClick={() => setEmailModalDocId(null)} className="btn-secondary">
                Annuler
              </button>
              <button
                disabled={sendEmailMut.isPending}
                onClick={() => sendEmailMut.mutate({ docId: emailModalDocId, email: emailRecipient })}
                className="btn-primary"
              >
                {sendEmailMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                Envoyer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
