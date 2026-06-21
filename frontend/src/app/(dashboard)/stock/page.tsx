"use client";

import { useState } from "react";
import { useStockList, useAdjustStock, useConfigStock } from "@/lib/hooks/use-stock";
import type { StockItem, AdjustReason } from "@/lib/api/stock";
import { formatCents } from "@/lib/utils/money";
import { Package, AlertTriangle, X, SlidersHorizontal, Plus, Minus } from "lucide-react";

// ── Skeleton ──────────────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <tr>
      {Array.from({ length: 6 }).map((_, i) => (
        <td key={i} className="table-cell">
          <div className="skeleton h-4 w-full max-w-[100px] rounded" />
        </td>
      ))}
    </tr>
  );
}

// ── Modal Ajustement ──────────────────────────────────────────────────────────

function AdjustModal({
  item,
  onClose,
}: {
  item: StockItem;
  onClose: () => void;
}) {
  const [delta, setDelta] = useState(0);
  const [reason, setReason] = useState<AdjustReason>("correction");
  const [note, setNote] = useState("");
  const adjust = useAdjustStock(item.id);

  const newQty = (item.stock_quantity ?? 0) + delta;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (delta === 0) return;
    await adjust.mutateAsync({ delta, reason, note: note || undefined });
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="font-semibold text-slate-900">Ajuster le stock</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <p className="text-sm font-medium text-slate-700 mb-0.5">{item.name}</p>
            <p className="text-xs text-slate-400">
              Stock actuel :{" "}
              <span className="font-semibold text-slate-700">
                {item.stock_quantity ?? 0}
              </span>{" "}
              {item.unit ?? ""}
            </p>
          </div>

          {/* Delta */}
          <div>
            <label className="label">Ajustement</label>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setDelta((d) => d - 1)}
                className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
              >
                <Minus className="w-4 h-4" />
              </button>
              <input
                type="number"
                value={delta}
                onChange={(e) => setDelta(Number(e.target.value))}
                className="input text-center w-28 tabular-nums"
              />
              <button
                type="button"
                onClick={() => setDelta((d) => d + 1)}
                className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
              >
                <Plus className="w-4 h-4" />
              </button>
              <span className="text-sm text-slate-500">
                {delta > 0 ? (
                  <span className="text-emerald-600">+{delta} entrée</span>
                ) : delta < 0 ? (
                  <span className="text-red-600">{delta} sortie</span>
                ) : (
                  "aucun changement"
                )}
              </span>
            </div>
            {newQty < 0 && (
              <p className="text-xs text-red-600 mt-1">
                Stock insuffisant (nouveau total = {newQty})
              </p>
            )}
            {delta !== 0 && newQty >= 0 && (
              <p className="text-xs text-slate-400 mt-1">
                Nouveau stock : <span className="font-semibold text-slate-700">{newQty}</span>
              </p>
            )}
          </div>

          {/* Raison */}
          <div>
            <label className="label">Raison</label>
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value as AdjustReason)}
              className="input"
            >
              <option value="restock">Réapprovisionnement</option>
              <option value="sale">Vente manuelle</option>
              <option value="return">Retour client</option>
              <option value="loss">Perte / casse</option>
              <option value="correction">Correction inventaire</option>
            </select>
          </div>

          {/* Note */}
          <div>
            <label className="label">Note (optionnel)</label>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Détails supplémentaires…"
              className="input"
              maxLength={500}
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary">
              Annuler
            </button>
            <button
              type="submit"
              disabled={delta === 0 || newQty < 0 || adjust.isPending}
              className="btn-primary"
            >
              {adjust.isPending ? "Enregistrement…" : "Confirmer"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Modal Config ──────────────────────────────────────────────────────────────

function ConfigModal({
  item,
  onClose,
}: {
  item: StockItem;
  onClose: () => void;
}) {
  const [trackStock, setTrackStock] = useState(item.track_stock);
  const [threshold, setThreshold] = useState<number | "">(
    item.low_stock_threshold ?? ""
  );
  const [initQty, setInitQty] = useState<number | "">(item.stock_quantity ?? "");
  const config = useConfigStock(item.id);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await config.mutateAsync({
      track_stock: trackStock,
      low_stock_threshold: threshold === "" ? null : Number(threshold),
      stock_quantity: initQty === "" ? null : Number(initQty),
    });
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="font-semibold text-slate-900">Configurer le stock</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <p className="text-sm font-medium text-slate-700">{item.name}</p>

          <label className="flex items-center gap-3 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={trackStock}
              onChange={(e) => setTrackStock(e.target.checked)}
              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-4 h-4"
            />
            <span className="text-sm text-slate-700">Activer le suivi de stock</span>
          </label>

          {trackStock && (
            <>
              <div>
                <label className="label">Seuil d'alerte (stock bas)</label>
                <input
                  type="number"
                  min={0}
                  value={threshold}
                  onChange={(e) => setThreshold(e.target.value === "" ? "" : Number(e.target.value))}
                  placeholder="ex. 5"
                  className="input"
                />
              </div>
              <div>
                <label className="label">Quantité en stock (initialisation)</label>
                <input
                  type="number"
                  min={0}
                  value={initQty}
                  onChange={(e) => setInitQty(e.target.value === "" ? "" : Number(e.target.value))}
                  placeholder="ex. 100"
                  className="input"
                />
              </div>
            </>
          )}

          <div className="flex items-center justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary">
              Annuler
            </button>
            <button
              type="submit"
              disabled={config.isPending}
              className="btn-primary"
            >
              {config.isPending ? "Enregistrement…" : "Sauvegarder"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Row ───────────────────────────────────────────────────────────────────────

function StockRow({
  item,
  onAdjust,
  onConfig,
}: {
  item: StockItem;
  onAdjust: () => void;
  onConfig: () => void;
}) {
  return (
    <tr className="hover:bg-slate-50/60 transition-colors">
      <td className="table-cell font-mono text-xs text-slate-400">{item.code}</td>
      <td className="table-cell">
        <p className="font-medium text-slate-900">{item.name}</p>
        {item.category && (
          <p className="text-xs text-slate-400 mt-0.5">{item.category}</p>
        )}
      </td>
      <td className="table-cell text-right tabular-nums">
        {formatCents(item.unit_price_cents, item.currency)}
      </td>
      <td className="table-cell text-center tabular-nums">
        <span
          className={`font-semibold ${
            item.is_low_stock ? "text-red-600" : "text-slate-900"
          }`}
        >
          {item.stock_quantity ?? "—"}
        </span>
        {item.unit && (
          <span className="text-xs text-slate-400 ml-1">{item.unit}</span>
        )}
      </td>
      <td className="table-cell text-center">
        {item.is_low_stock ? (
          <span className="badge bg-red-50 text-red-700 gap-1">
            <AlertTriangle className="w-3 h-3" />
            Stock bas
          </span>
        ) : item.track_stock ? (
          <span className="badge bg-emerald-50 text-emerald-700">OK</span>
        ) : (
          <span className="badge bg-slate-100 text-slate-500">Non suivi</span>
        )}
      </td>
      <td className="table-cell text-center text-slate-400 tabular-nums">
        {item.low_stock_threshold ?? "—"}
      </td>
      <td className="table-cell">
        <div className="flex items-center justify-end gap-1">
          <button
            onClick={onAdjust}
            disabled={!item.track_stock}
            title={item.track_stock ? "Ajuster le stock" : "Activez le suivi de stock d'abord"}
            className="text-xs px-2 py-1 rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Ajuster
          </button>
          <button
            onClick={onConfig}
            title="Configurer le stock"
            className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 transition-colors"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
          </button>
        </div>
      </td>
    </tr>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function StockPage() {
  const [alertsOnly, setAlertsOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [adjustItem, setAdjustItem] = useState<StockItem | null>(null);
  const [configItem, setConfigItem] = useState<StockItem | null>(null);
  const limit = 50;

  const { data, isLoading } = useStockList({
    alerts_only: alertsOnly,
    skip: page * limit,
    limit,
  });

  const items = data?.items ?? [];

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Stock</h1>
          <p className="page-subtitle">
            {data?.total ?? 0} produit{(data?.total ?? 0) !== 1 ? "s" : ""} suivis
            {(data?.alerts_count ?? 0) > 0 && (
              <span className="ml-2 text-red-600 font-medium">
                · {data!.alerts_count} alerte{data!.alerts_count > 1 ? "s" : ""}
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Filtres */}
      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={alertsOnly}
            onChange={(e) => { setAlertsOnly(e.target.checked); setPage(0); }}
            className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
          />
          <AlertTriangle className="w-3.5 h-3.5 text-red-500" />
          Alertes seulement
        </label>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-100">
              <tr>
                <th className="table-header">Code</th>
                <th className="table-header">Produit</th>
                <th className="table-header text-right">Prix HT</th>
                <th className="table-header text-center">Stock actuel</th>
                <th className="table-header text-center">Statut</th>
                <th className="table-header text-center">Seuil alerte</th>
                <th className="table-header w-28" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <div className="empty-state py-14">
                      <Package className="empty-state-icon" />
                      <p className="empty-state-title">Aucun produit trouvé</p>
                      <p className="empty-state-desc">
                        {alertsOnly
                          ? "Aucune alerte de stock en ce moment"
                          : "Activez le suivi de stock sur vos produits depuis le catalogue"}
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <StockRow
                    key={item.id}
                    item={item}
                    onAdjust={() => setAdjustItem(item)}
                    onConfig={() => setConfigItem(item)}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {(data?.total ?? 0) > limit && (
          <div className="flex items-center justify-between px-5 py-3.5 border-t border-slate-100 bg-slate-50/40">
            <p className="text-sm text-slate-400">
              {page * limit + 1}–{Math.min((page + 1) * limit, data?.total ?? 0)} sur{" "}
              {data?.total}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="pagination-btn"
              >
                Précédent
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={(page + 1) * limit >= (data?.total ?? 0)}
                className="pagination-btn"
              >
                Suivant
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      {adjustItem && (
        <AdjustModal item={adjustItem} onClose={() => setAdjustItem(null)} />
      )}
      {configItem && (
        <ConfigModal item={configItem} onClose={() => setConfigItem(null)} />
      )}
    </div>
  );
}
