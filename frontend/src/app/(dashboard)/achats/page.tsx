"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, CheckCircle, Download, Loader2, PackageCheck, Plus, Trash2, UserRoundCheck } from "lucide-react";
import Link from "next/link";
import { achatsApi, type PurchaseInput, type PurchaseOrder } from "@/lib/api/achats";
import { produitsApi } from "@/lib/api/produits";
import { commandesApi } from "@/lib/api/commandes";
import { clientsApi } from "@/lib/api/clients";
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
  const [partnerClientId, setPartnerClientId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const { data: purchases, isLoading } = useQuery({ queryKey: ["purchases"], queryFn: achatsApi.list });
  const { data: suppliers } = useQuery({ queryKey: ["suppliers"], queryFn: achatsApi.suppliers });
  const { data: products } = useQuery({ queryKey: ["products", "purchase"], queryFn: () => produitsApi.list({ limit: 100, status: "active" }) });
  const { data: orders } = useQuery({ queryKey: ["commandes", "purchase-link"], queryFn: () => commandesApi.list({ limit: 100 }) });
  const { data: clients } = useQuery({ queryKey: ["clients", "supplier-link"], queryFn: () => clientsApi.list({ limit: 100, client_type: "company" }) });

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
    source_document_id: editing?.source_document_id || undefined,
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
  const partnerMut = useMutation({
    mutationFn: () => achatsApi.supplierFromClient(partnerClientId),
    onSuccess: (supplier) => {
      setSupplierId(supplier.id); setPartnerClientId("");
      qc.invalidateQueries({ queryKey: ["suppliers"] });
    },
    onError: (error: any) => setFormError(error?.response?.data?.detail ?? "Impossible d'activer le rôle fournisseur"),
  });
  const supplierAsClientMut = useMutation({
    mutationFn: (id: string) => achatsApi.supplierAsClient(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["suppliers"] });
      qc.invalidateQueries({ queryKey: ["clients"] });
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

  const purchaseActions = (purchase: PurchaseOrder, mobile = false) => (
    <div className={`flex flex-wrap gap-2 ${mobile ? "[&>*]:flex-1" : ""}`}>
      <button onClick={() => loadForEdit(purchase)} disabled={!(["draft", "ordered"].includes(purchase.status))} className="btn-secondary py-1 text-xs">Modifier</button>
      <button onClick={() => downloadPdf(purchase)} className="btn-secondary py-1 text-xs"><Download className="w-3 h-3" /> PDF</button>
      {purchase.status === "draft" && <button onClick={() => actionMut.mutate({ purchase, action: "confirm" })} className="btn-primary py-1 text-xs"><CheckCircle className="w-3 h-3" /> Envoyer</button>}
      {["ordered", "partially_received"].includes(purchase.status) && <button onClick={() => actionMut.mutate({ purchase, action: "receive" })} className="btn-primary py-1 text-xs"><PackageCheck className="w-3 h-3" /> Réceptionner</button>}
      {!suppliers?.items.find((supplier) => supplier.id === purchase.supplier_id)?.client_id && <button onClick={() => supplierAsClientMut.mutate(purchase.supplier_id)} className="btn-secondary py-1 text-xs" title="Cette entreprise pourra aussi acheter chez vous"><UserRoundCheck className="h-3 w-3" /> Rôle client</button>}
    </div>
  );

  return (
    <div className="page-container space-y-6">
      <div className="page-header">
        <div><h1 className="page-title">Achats fournisseurs</h1><p className="page-subtitle">Approvisionner une commande client sans mélanger prix d’achat et prix de vente</p></div>
        <button onClick={() => setShowForm(true)} className="btn-primary w-full sm:w-auto"><Plus className="w-4 h-4" /> Nouveau bon d’achat</button>
      </div>

      <section className="card space-y-4 p-4 sm:p-5">
        <div><h2 className="font-semibold text-slate-900">Entreprises fournisseurs</h2><p className="text-xs text-slate-500">Une même entreprise peut être cliente, fournisseur, ou les deux.</p></div>
        <div className="grid gap-2 md:grid-cols-3"><input value={supplierName} onChange={(e) => setSupplierName(e.target.value)} placeholder="Nom du nouveau fournisseur" className="input" /><input value={supplierPhone} onChange={(e) => setSupplierPhone(e.target.value)} placeholder="Téléphone" className="input" /><button onClick={() => supplierMut.mutate()} disabled={supplierMut.isPending || supplierName.length < 2 || supplierPhone.length < 6} className="btn-secondary"><Building2 className="h-4 w-4" /> Ajouter le fournisseur</button></div>
        <div className="flex flex-wrap gap-2">
          {suppliers?.items.map((supplier) => <div key={supplier.id} className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"><span className="font-medium text-slate-800">{supplier.name}</span><span className={supplier.client_id ? "badge-green" : "badge-blue"}>{supplier.client_id ? "Client + fournisseur" : "Fournisseur"}</span>{!supplier.client_id && <button onClick={() => supplierAsClientMut.mutate(supplier.id)} className="text-xs font-medium text-blue-700 hover:underline">Activer aussi comme client</button>}</div>)}
          {!suppliers?.items.length && <p className="text-sm text-slate-500">Aucun fournisseur enregistré.</p>}
        </div>
      </section>

      {showForm && (
        <div className="card space-y-5 p-4 sm:p-5">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3"><div><h2 className="font-semibold">{editing ? `Modifier ${editing.purchase_number}` : "Bon de commande fournisseur"}</h2><p className="text-xs text-slate-500">Les prix ci-dessous sont vos coûts d’achat et ne sont jamais repris comme prix de vente.</p></div><button onClick={resetForm} className="btn-secondary w-full sm:w-auto">Fermer</button></div>
          <div className="grid md:grid-cols-2 gap-4">
            <div><label className="label">Entreprise fournisseur C *</label><select value={supplierId} onChange={(e) => setSupplierId(e.target.value)} className="input"><option value="">— Choisir —</option>{suppliers?.items.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
            <div><label className="label">Commande client A liée (optionnel)</label><select value={salesOrderId} onChange={(e) => setSalesOrderId(e.target.value)} className="input"><option value="">— Achat libre —</option>{orders?.items.map((o) => <option key={o.id} value={o.id}>{o.order_number}</option>)}</select></div>
          </div>
          {!editing && <div className="rounded-lg border border-blue-100 bg-blue-50 p-3"><p className="mb-2 text-xs font-medium text-blue-900">Entreprise déjà cliente ? Activez aussi son rôle fournisseur sans créer de doublon.</p><div className="grid gap-2 md:grid-cols-[1fr_auto]"><select value={partnerClientId} onChange={(event) => setPartnerClientId(event.target.value)} className="input"><option value="">— Choisir une entreprise cliente —</option>{clients?.items.map((client) => <option key={client.id} value={client.id}>{client.company_name || client.full_name}</option>)}</select><button onClick={() => partnerMut.mutate()} disabled={!partnerClientId || partnerMut.isPending} className="btn-secondary"><Building2 className="h-4 w-4" /> Activer comme fournisseur</button></div></div>}

          <div className="space-y-3">
            {lines.map((line, index) => <div key={index} className="grid md:grid-cols-12 gap-2 items-end border rounded-lg p-3">
              <div className="md:col-span-3"><label className="label">Produit stocké</label><select value={line.product_id} onChange={(e) => { const product = products?.items.find((p) => p.id === e.target.value); setLines((all) => all.map((v, i) => i === index ? { ...v, product_id: e.target.value, description: product?.name ?? v.description, unit: product?.unit ?? v.unit } : v)); }} className="input"><option value="">Non lié au stock</option>{products?.items.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></div>
              <div className="md:col-span-4"><label className="label">Description *</label><input value={line.description} onChange={(e) => setLines((all) => all.map((v, i) => i === index ? { ...v, description: e.target.value } : v))} className="input" /></div>
              <div className="md:col-span-2"><label className="label">Quantité</label><input type="number" min="1" value={line.quantity} onChange={(e) => setLines((all) => all.map((v, i) => i === index ? { ...v, quantity: Number(e.target.value) } : v))} className="input" /></div>
              <div className="md:col-span-2"><label className="label">Prix d’achat</label><input type="number" min="0" value={line.purchase_price} onChange={(e) => setLines((all) => all.map((v, i) => i === index ? { ...v, purchase_price: Number(e.target.value) } : v))} className="input" /></div>
              <button aria-label="Supprimer la ligne" onClick={() => setLines((all) => all.filter((_, i) => i !== index))} disabled={lines.length === 1} className="min-h-10 min-w-10 rounded-lg p-2 text-red-500 hover:bg-red-50 disabled:opacity-30"><Trash2 className="mx-auto h-4 w-4" /></button>
            </div>)}
            <button onClick={() => setLines((all) => [...all, blankLine()])} className="btn-secondary w-full sm:w-auto"><Plus className="w-4 h-4" /> Ajouter une ligne</button>
          </div>

          <div className="grid md:grid-cols-3 gap-4">
            <label className="flex items-center gap-2 md:mt-6"><input type="checkbox" checked={applyTax} onChange={(e) => setApplyTax(e.target.checked)} /> Appliquer la TVA à cet achat</label>
            {applyTax && <div><label className="label">Taux TVA (%)</label><input type="number" min="0" max="100" step="0.01" value={taxRate} onChange={(e) => setTaxRate(Number(e.target.value))} className="input" /></div>}
            <div><label className="label">Livraison prévue</label><input type="date" value={expectedDate} onChange={(e) => setExpectedDate(e.target.value)} className="input" /></div>
          </div>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Conditions d'achat, délai, transport…" className="input" rows={2} />
          {formError && <p className="text-sm text-red-700 bg-red-50 border border-red-200 p-3 rounded-lg">{formError}</p>}
          <div className="flex justify-end"><button onClick={submit} disabled={saveMut.isPending} className="btn-primary w-full sm:w-auto">{saveMut.isPending && <Loader2 className="w-4 h-4 animate-spin" />} {editing ? "Enregistrer les modifications" : "Créer le bon d’achat"}</button></div>
        </div>
      )}

      <div className="space-y-3 md:hidden">
        {isLoading ? <div className="card p-10"><Loader2 className="animate-spin mx-auto" /></div> : purchases?.items.length === 0 ? <div className="card p-6 text-center text-sm text-slate-500">Aucun bon d&apos;achat pour le moment.</div> : purchases?.items.map((purchase) => {
          const sale = orders?.items.find((order) => order.id === purchase.sales_order_id);
          const comparable = sale?.currency === purchase.currency;
          return <article key={purchase.id} className="card p-4 space-y-4">
            <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="font-mono text-sm font-semibold truncate">{purchase.purchase_number}</p><p className="text-sm text-slate-600 truncate">{purchase.supplier_name}</p></div><span className="badge-blue flex-shrink-0">{purchase.status}</span></div>
            {purchase.sales_order_id && <Link className="block text-sm text-blue-600 font-medium" href={`/commandes/${purchase.sales_order_id}`}>Commande client liée →</Link>}
            <dl className="grid grid-cols-1 gap-2 text-center min-[380px]:grid-cols-3"><div className="rounded-lg bg-orange-50 p-2"><dt className="text-[11px] text-orange-700">Achat HT</dt><dd className="break-words text-xs font-bold text-orange-800">{formatCents(purchase.subtotal_cents, purchase.currency)}</dd></div><div className="rounded-lg bg-blue-50 p-2"><dt className="text-[11px] text-blue-700">Vente HT</dt><dd className="break-words text-xs font-bold text-blue-800">{sale ? formatCents(sale.subtotal_cents, sale.currency) : "—"}</dd></div><div className="rounded-lg bg-emerald-50 p-2"><dt className="text-[11px] text-emerald-700">Marge</dt><dd className="break-words text-xs font-bold text-emerald-800">{sale && comparable ? formatCents(sale.subtotal_cents - purchase.subtotal_cents, sale.currency) : "—"}</dd></div></dl>
            {purchaseActions(purchase, true)}
          </article>;
        })}
      </div>

      <div className="card overflow-hidden hidden md:block"><div className="overflow-x-auto"><table className="w-full min-w-[1050px] text-sm"><thead className="bg-slate-50"><tr><th className="table-header">Bon d’achat</th><th className="table-header">Fournisseur C</th><th className="table-header">Commande client A</th><th className="table-header">Statut</th><th className="table-header text-right">Coût d’achat HT</th><th className="table-header text-right">Vente HT</th><th className="table-header text-right">Marge brute</th><th className="table-header">Actions</th></tr></thead><tbody>
        {isLoading ? <tr><td colSpan={8} className="p-10 text-center"><Loader2 className="animate-spin mx-auto" /></td></tr> : purchases?.items.map((purchase) => {
          const sale = orders?.items.find((order) => order.id === purchase.sales_order_id);
          const comparable = sale?.currency === purchase.currency;
          return <tr key={purchase.id} className="border-t">
            <td className="table-cell font-mono">{purchase.purchase_number}</td><td className="table-cell font-medium">{purchase.supplier_name}</td><td className="table-cell">{purchase.sales_order_id ? <Link className="text-blue-600" href={`/commandes/${purchase.sales_order_id}`}>Voir la vente</Link> : "—"}</td><td className="table-cell">{purchase.status}</td><td className="table-cell text-right font-semibold text-orange-700">{formatCents(purchase.subtotal_cents, purchase.currency)}</td>
            <td className="table-cell text-right font-semibold text-blue-700">{sale ? formatCents(sale.subtotal_cents, sale.currency) : "—"}</td>
            <td className="table-cell text-right font-bold text-emerald-700">{sale && comparable ? formatCents(sale.subtotal_cents - purchase.subtotal_cents, sale.currency) : "—"}</td>
            <td className="table-cell">{purchaseActions(purchase)}</td>
          </tr>;
        })}</tbody></table></div></div>
      <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900"><strong>Lecture du flux :</strong> A commande chez vous (vente) → vous créez ce bon pour C (achat) → la réception augmente le stock → vous livrez et facturez A avec votre propre prix de vente.</div>
    </div>
  );
}

export default function AchatsPage() {
  return <Suspense fallback={<Loader2 className="animate-spin" />}><AchatsContent /></Suspense>;
}
