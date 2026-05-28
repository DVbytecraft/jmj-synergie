"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { formatCents } from "@/lib/utils/money";
import { refundsApi, type RefundItem } from "@/lib/api/refunds";
import { useAuthStore } from "@/store/auth.store";
import {
  CheckCircle2, Loader2, RotateCcw, X, XCircle,
} from "lucide-react";

const STATUS_CFG: Record<string, { label: string; className: string }> = {
  requested:    { label: "Demandé",     className: "bg-orange-100 text-orange-700"  },
  under_review: { label: "En révision", className: "bg-yellow-100 text-yellow-700"  },
  approved:     { label: "Approuvé",    className: "bg-blue-100 text-blue-700"      },
  rejected:     { label: "Rejeté",      className: "bg-red-100 text-red-700"        },
  completed:    { label: "Complété",    className: "bg-green-100 text-green-700"    },
  cancelled:    { label: "Annulé",      className: "bg-gray-100 text-gray-700"      },
};

const REASON_LABELS: Record<string, string> = {
  product_defect:     "Produit défectueux",
  wrong_item:         "Mauvais article",
  not_delivered:      "Non livré",
  customer_request:   "Demande client",
  duplicate_payment:  "Paiement en double",
  billing_error:      "Erreur de facturation",
  other:              "Autre",
};

const METHOD_LABELS: Record<string, string> = {
  cash:          "Espèces",
  bank_transfer: "Virement",
  mobile_money:  "Mobile Money",
  check:         "Chèque",
  card:          "Carte",
};

const CAN_ACTION = ["requested", "under_review"];

// ─── Modals ───────────────────────────────────────────────────────────────────

function ApproveModal({
  refund,
  onClose,
}: {
  refund: RefundItem;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [method, setMethod] = useState("bank_transfer");
  const [amount, setAmount] = useState(String(refund.requested_amount_cents));
  const [error, setError] = useState<string | null>(null);

  const mut = useMutation({
    mutationFn: () =>
      refundsApi.approve(refund.id, {
        method,
        approved_amount_cents: parseInt(amount, 10) || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["remboursements"] });
      onClose();
    },
    onError: (e: any) => setError(e?.response?.data?.detail ?? "Erreur"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900">Approuver le remboursement</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X className="w-5 h-5" /></button>
        </div>

        <p className="text-sm text-slate-500">
          Réf. <span className="font-mono font-medium text-slate-700">{refund.refund_number}</span>
          {" — "}Montant demandé : <strong>{formatCents(refund.requested_amount_cents, refund.currency)}</strong>
        </p>

        <div>
          <label className="label">Montant approuvé ({refund.currency})</label>
          <input
            type="number"
            min={1}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="input"
          />
        </div>

        <div>
          <label className="label">Méthode de remboursement</label>
          <select value={method} onChange={(e) => setMethod(e.target.value)} className="input">
            {Object.entries(METHOD_LABELS).map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </div>

        {error && <div className="alert-error">{error}</div>}

        <div className="flex gap-3 justify-end">
          <button onClick={onClose} className="btn-secondary">Annuler</button>
          <button
            onClick={() => mut.mutate()}
            disabled={mut.isPending}
            className="btn-primary bg-emerald-600 hover:bg-emerald-700"
          >
            {mut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
            Confirmer l&apos;approbation
          </button>
        </div>
      </div>
    </div>
  );
}

function RejectModal({
  refund,
  onClose,
}: {
  refund: RefundItem;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mut = useMutation({
    mutationFn: () => refundsApi.reject(refund.id, { rejection_reason: reason }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["remboursements"] });
      onClose();
    },
    onError: (e: any) => setError(e?.response?.data?.detail ?? "Erreur"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900">Rejeter le remboursement</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X className="w-5 h-5" /></button>
        </div>

        <p className="text-sm text-slate-500">
          Réf. <span className="font-mono font-medium text-slate-700">{refund.refund_number}</span>
        </p>

        <div>
          <label className="label">Motif du rejet <span className="text-red-500">*</span></label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder="Expliquez pourquoi ce remboursement est rejeté…"
            className="input resize-none"
          />
          {reason.trim().length > 0 && reason.trim().length < 5 && (
            <p className="field-error">Minimum 5 caractères</p>
          )}
        </div>

        {error && <div className="alert-error">{error}</div>}

        <div className="flex gap-3 justify-end">
          <button onClick={onClose} className="btn-secondary">Annuler</button>
          <button
            onClick={() => mut.mutate()}
            disabled={mut.isPending || reason.trim().length < 5}
            className="btn-primary bg-red-600 hover:bg-red-700 disabled:opacity-50"
          >
            {mut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
            Confirmer le rejet
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function JournalRemboursementsPage() {
  const user = useAuthStore((s) => s.user);
  const isManager = ["super_admin", "admin", "manager"].includes(user?.role ?? "");

  const [page, setPage] = useState(0);
  const [approveTarget, setApproveTarget] = useState<RefundItem | null>(null);
  const [rejectTarget, setRejectTarget] = useState<RefundItem | null>(null);
  const limit = 25;

  const { data, isLoading } = useQuery({
    queryKey: ["remboursements", page],
    queryFn: () => refundsApi.list({ skip: page * limit, limit }),
  });

  const remboursements = data?.items ?? [];
  const totalCents = remboursements.reduce((s, e) => s + e.requested_amount_cents, 0);
  const currency = remboursements[0]?.currency ?? "XAF";

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
                <th className="table-header text-right">Demandé</th>
                <th className="table-header text-right">Approuvé</th>
                <th className="table-header">Date</th>
                {isManager && <th className="table-header">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {isLoading ? (
                <tr>
                  <td colSpan={isManager ? 8 : 7} className="py-10 text-center">
                    <Loader2 className="w-5 h-5 animate-spin text-blue-600 mx-auto" />
                  </td>
                </tr>
              ) : remboursements.length === 0 ? (
                <tr>
                  <td colSpan={isManager ? 8 : 7} className="py-10 text-center text-gray-400">
                    Aucun remboursement
                  </td>
                </tr>
              ) : (
                remboursements.map((e) => {
                  const cfg = STATUS_CFG[e.status] ?? { label: e.status, className: "bg-gray-100 text-gray-700" };
                  const canAct = isManager && CAN_ACTION.includes(e.status);
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
                      <td className="table-cell text-gray-600">
                        {REASON_LABELS[e.reason] ?? e.reason}
                      </td>
                      <td className="table-cell">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${cfg.className}`}>{cfg.label}</span>
                      </td>
                      <td className="table-cell text-right">{formatCents(e.requested_amount_cents, e.currency)}</td>
                      <td className="table-cell text-right font-semibold">
                        {e.approved_amount_cents != null
                          ? formatCents(e.approved_amount_cents, e.currency)
                          : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="table-cell text-gray-400">
                        {new Date(e.requested_at).toLocaleDateString("fr-FR")}
                      </td>
                      {isManager && (
                        <td className="table-cell">
                          {canAct ? (
                            <div className="flex gap-1.5">
                              <button
                                onClick={() => setApproveTarget(e)}
                                className="px-2 py-1 text-xs font-medium bg-emerald-50 text-emerald-700 rounded-lg hover:bg-emerald-100 transition-colors"
                              >
                                Approuver
                              </button>
                              <button
                                onClick={() => setRejectTarget(e)}
                                className="px-2 py-1 text-xs font-medium bg-red-50 text-red-700 rounded-lg hover:bg-red-100 transition-colors"
                              >
                                Rejeter
                              </button>
                            </div>
                          ) : (
                            <span className="text-gray-300 text-xs">—</span>
                          )}
                        </td>
                      )}
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

      {approveTarget && (
        <ApproveModal refund={approveTarget} onClose={() => setApproveTarget(null)} />
      )}
      {rejectTarget && (
        <RejectModal refund={rejectTarget} onClose={() => setRejectTarget(null)} />
      )}
    </div>
  );
}
