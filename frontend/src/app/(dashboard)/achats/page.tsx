"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, CheckCircle, Download, Loader2, PackageCheck, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { achatsApi, type PurchaseInput, type PurchaseOrder } from "@/lib/api/achats";
import { produitsApi } from "@/lib/api/produits";
import { commandesApi } from "@/lib/api/commandes";
import { amountToCents, formatCents } from "@/lib/utils/money";
import { apiClient } from "@/lib/api/client";

type DraftLine = { product_id: string; description: string; quantity: number; purchase_price: number; unit: string };
const blankLine = (): DraftLine => ({ product_id: "", description: "", quantity: 1, purchase_price: 0, unit: "" });

function AchatsContent() {
  const params = useSearchParams();
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(Boolean(params.get("sales_order_id")));
  const [editing, setEditing] = useState<PurchaseOrder | null>(null);
  const [supplierId, setSupplierId] = useState("");
  const [salesOrderId, setSalesOrderId] = useState(params.get("sales_order_id") ?? "");
  const [currency, setCurrency] = useState("XAF");
  const [applyTax, setApplyTax] = useState(false);
  const [taxRate, setTaxRate] = useState(19.25);
  const [expectedDate, setExpectedDate] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([blankLine()]);
  const [supplierName, setSupplierName] = useState("");
  const [supplierPhone, setSupplierPhone] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const { data: purchases, isLoading } = useQuery({ queryKey: ["purchases"], queryFn: achatsApi.list });
  const { data: suppliers } = useQuery({ queryKey: ["suppliers"], queryFn: achatsApi.suppliers });
  const { data: products } = useQuery({ queryKey: ["products", "purchase"], queryFn: () => produitsApi.list({ limit: 100, status: "active" }) });
  const { data: orders } = useQuery({ queryKey: ["commandes", "purchase-link"], queryFn: () => commandesApi.list({ limit: 100 }) });

  const resetForm = () => {
    setEditing(null); setSupplierId(""); setSalesOrderId(""); setCurrency("XAF");
    setApplyTax(false); setTaxRate(19.25); setExpectedDate(""); setNotes("");
    setLines([blankLine()]); setFormError(null); setShowForm(false);
  };

  const loadForEdit = (purchase: PurchaseOrder) => {
    setEditing(purchase); setSupplierId(purchase.supplier_id); setSalesOrderId(purchase.sales_order_id ?? "");
    setCurrency(purchase.currency); setApplyTax(purchase.tax_rate > 0); setTaxRate(purchase.tax_rate || 19.25);
    setExpectedDate(purchase.expected_date ?? ""); setNotes(purchase.notes ?? "");
    setLines(purchase.items.map((item) => ({
      product_id: item.product_id ?? "", description: item.description, quantity: item.quantity,
      purchase_price: item.purchase_unit_price_cents / 100, unit: item.unit ?? "",
    })));
    setShowForm(true); window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const payload = (): PurchaseInput => ({
    supplier_id: supplierId, sales_order_id: salesOrderId || undefined, currency,
    apply_tax: applyTax, tax_rate: applyTax ? taxRate : 0,
    expected_date: expectedDate || undefined, notes: notes || undefined,
    items: lines.map((line) => ({
      product_id: line.product_id || undefined, description: line.description.trim(), quantity: Number(line.quantity),
      unit: line.unit || undefined, purchase_unit_price_cents: amountToCents(Number(line.purchase_price)),
    })),
  });

  const saveMut = useMutation({
    mutationFn: () => editing ? achatsApi.update(editing.id, payload()) : achatsApi.create(payload()),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["purchases"] }); resetForm(); },
    onError: (error: any) => setFormError(error?.response?.data?.detail ?? "Impossible d'enregistrer le bon d'achat"),
  });
  const supplierMut = useMutation({
    mutationFn: () => achatsApi.createSupplier({ name: supplierName, phone: supplierPhone, currency, email: null }),
    onSuccess: (supplier) => {
      setSupplierId(supplier.id); setSupplierName(""); setSupplierPhone("");
      qc.invalidateQueries({ queryKey: ["suppliers"] });
    },
  });
  const actionMut = useMutation({
    mutationFn: ({ purchase, action }: { purchase: PurchaseOrder; action: "confirm" | "receive" }) =>
      action === "confirm" ? achatsApi.confirm(purchase.id) : achatsApi.receiveAll(purchase),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["purchases"] }); qc.invalidateQueries({ queryKey: ["stock"] }); },
  });

  const downloadPdf = async (purchase: PurchaseOrder) => {
    const response = await apiClient.get(`/purchases/${purchase.id}/pdf`, { responseType: "blob" });
    const url = URL.createObjectURL(response.data);
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${purchase.purchase_number}.pdf`; anchor.click();
    URL.revokeObjectURL(url);
  };

  const submit = () => {
    if (!supplierId || !lines.length || lines.some((line) => !line.description.trim() || line.quantity <= 0 || line.purchase_price < 0)) {
      setFormError("Choisissez le fournisseur et vérifiez chaque ligne d'achat."); return;
    }
    setFormError(null); saveMut.mutate();
  };

  return (
    <div className="page-container space-y-6">
      <div className="page-header">
        <div><h1 className="page-title">Achats fournisseurs</h1><p className="page-subtitle">Approvisionner une commande client sans mélanger prix d’achat et prix de vente</p></div>
        <button onClick={() => setShowForm(true)} className="btn-primary"><Plus className="w-4 h-4" /> Nouveau bon d’achat</button>
      </div>

      {showForm && (
        <div className="card p-5 space-y-5">
          <div className="flex justify-between"><div><h2 className="font-semibold">{editing ? `Modifier ${editing.purchase_number}` : "Bon de commande fournisseur"}</h2><p className="text-xs text-slate-500">Les prix ci-dessous sont vos coûts d’achat et ne sont jamais repris comme prix de vente.</p></div><button onClick={resetForm} className="btn-secondary">Fermer</button></div>
          <div className="grid md:grid-cols-2 gap-4">
            <div><label className="label">Entreprise fournisseur C *</label><select value={supplierId} onChange={(e) => setSupplierId(e.target.value)} className="input"><option value="">— Choisir —</option>{suppliers?.items.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
            <div><label className="label">Commande client A liée (optionnel)</label><select value={salesOrderId} onChange={(e) => setSalesOrderId(e.target.value)} className="input"><option value="">— Achat libre —</option>{orders?.items.map((o) => <option key={o.id} value={o.id}>{o.order_number}</option>)}</select></div>
          </div>
          {!editing && <div className="rounded-lg bg-slate-50 p-3 grid md:grid-cols-3 gap-2"><input value={supplierName} onChange={(e) => setSupplierName(e.target.value)} placeholder="Nouveau fournisseur" className="input" /><input value={supplierPhone} onChange={(e) => setSupplierPhone(e.target.value)} placeholder="Téléphone" className="input" /><button onClick={() => supplierMut.mutate()} disabled={supplierMut.isPending || supplierName.length < 2 || supplierPhone.length < 6} className="btn-secondary"><Building2 className="w-4 h-4" /> Ajouter le fournisseur</button></div>}

          <div className="space-y-3">
            {lines.map((line, index) => <div key={index} className="grid md:grid-cols-12 gap-2 items-end border rounded-lg p-3">
              <div className="md:col-span-3"><label className="label">Produit stocké</label><select value={line.product_id} onChange={(e) => { const product = products?.items.find((p) => p.id === e.target.value); setLines((all) => all.map((v, i) => i === index ? { ...v, product_id: e.target.value, description: product?.name ?? v.description, unit: product?.unit ?? v.unit } : v)); }} className="input"><option value="">Non lié au stock</option>{products?.items.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></div>
              <div className="md:col-span-4"><label className="label">Description *</label><input value={line.description} onChange={(e) => setLines((all) => all.map((v, i) => i === index ? { ...v, description: e.target.value } : v))} className="input" /></div>
              <div className="md:col-span-2"><label className="label">Quantité</label><input type="number" min="1" value={line.quantity} onChange={(e) => setLines((all) => all.map((v, i) => i === index ? { ...v, quantity: Number(e.target.value) } : v))} className="input" /></div>
              <div className="md:col-span-2"><label className="label">Prix d’achat</label><input type="number" min="0" value={line.purchase_price} onChange={(e) => setLines((all) => all.map((v, i) => i === index ? { ...v, purchase_price: Number(e.target.value) } : v))} className="input" /></div>
              <button onClick={() => setLines((all) => all.filter((_, i) => i !== index))} disabled={lines.length === 1} className="p-2 text-red-500 disabled:opacity-30"><Trash2 className="w-4 h-4" /></button>
            </div>)}
            <button onClick={() => setLines((all) => [...all, blankLine()])} className="btn-secondary"><Plus className="w-4 h-4" /> Ajouter une ligne</button>
          </div>

          <div className="grid md:grid-cols-3 gap-4">
            <label className="flex items-center gap-2 mt-6"><input type="checkbox" checked={applyTax} onChange={(e) => setApplyTax(e.target.checked)} /> Appliquer la TVA à cet achat</label>
            {applyTax && <div><label className="label">Taux TVA (%)</label><input type="number" min="0" max="100" step="0.01" value={taxRate} onChange={(e) => setTaxRate(Number(e.target.value))} className="input" /></div>}
            <div><label className="label">Livraison prévue</label><input type="date" value={expectedDate} onChange={(e) => setExpectedDate(e.target.value)} className="input" /></div>
          </div>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Conditions d'achat, délai, transport…" className="input" rows={2} />
          {formError && <p className="text-sm text-red-700 bg-red-50 border border-red-200 p-3 rounded-lg">{formError}</p>}
          <div className="flex justify-end"><button onClick={submit} disabled={saveMut.isPending} className="btn-primary">{saveMut.isPending && <Loader2 className="w-4 h-4 animate-spin" />} {editing ? "Enregistrer les modifications" : "Créer le bon d’achat"}</button></div>
        </div>
      )}

      <div className="card overflow-hidden"><div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50"><tr><th className="table-header">Bon d’achat</th><th className="table-header">Fournisseur C</th><th className="table-header">Commande client A</th><th className="table-header">Statut</th><th className="table-header text-right">Coût d’achat HT</th><th className="table-header text-right">Vente HT</th><th className="table-header text-right">Marge brute</th><th className="table-header">Actions</th></tr></thead><tbody>
        {isLoading ? <tr><td colSpan={8} className="p-10 text-center"><Loader2 className="animate-spin mx-auto" /></td></tr> : purchases?.items.map((purchase) => {
          const sale = orders?.items.find((order) => order.id === purchase.sales_order_id);
          const comparable = sale?.currency === purchase.currency;
          return <tr key={purchase.id} className="border-t">
            <td className="table-cell font-mono">{purchase.purchase_number}</td><td className="table-cell font-medium">{purchase.supplier_name}</td><td className="table-cell">{purchase.sales_order_id ? <Link className="text-blue-600" href={`/commandes/${purchase.sales_order_id}`}>Voir la vente</Link> : "—"}</td><td className="table-cell">{purchase.status}</td><td className="table-cell text-right font-semibold text-orange-700">{formatCents(purchase.subtotal_cents, purchase.currency)}</td>
            <td className="table-cell text-right font-semibold text-blue-700">{sale ? formatCents(sale.subtotal_cents, sale.currency) : "—"}</td>
            <td className="table-cell text-right font-bold text-emerald-700">{sale && comparable ? formatCents(sale.subtotal_cents - purchase.subtotal_cents, sale.currency) : "—"}</td>
            <td className="table-cell"><div className="flex flex-wrap gap-1"><button onClick={() => loadForEdit(purchase)} disabled={!(["draft", "ordered"].includes(purchase.status))} className="btn-secondary py-1 text-xs">Modifier</button><button onClick={() => downloadPdf(purchase)} className="btn-secondary py-1 text-xs"><Download className="w-3 h-3" /> PDF</button>{purchase.status === "draft" && <button onClick={() => actionMut.mutate({ purchase, action: "confirm" })} className="btn-primary py-1 text-xs"><CheckCircle className="w-3 h-3" /> Envoyer</button>}{["ordered", "partially_received"].includes(purchase.status) && <button onClick={() => actionMut.mutate({ purchase, action: "receive" })} className="btn-primary py-1 text-xs"><PackageCheck className="w-3 h-3" /> Réceptionner</button>}</div></td>
          </tr>;
        })}</tbody></table></div></div>
      <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900"><strong>Lecture du flux :</strong> A commande chez vous (vente) → vous créez ce bon pour C (achat) → la réception augmente le stock → vous livrez et facturez A avec votre propre prix de vente.</div>
    </div>
  );
}

export default function AchatsPage() {
  return <Suspense fallback={<Loader2 className="animate-spin" />}><AchatsContent /></Suspense>;
}
