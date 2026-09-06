"use client";

import { useRouter } from "next/navigation";
import { useState, useRef, useCallback } from "react";
import {
  ScanLine, Upload, X, FileText, AlertCircle,
  ChevronRight, Loader2, CheckCircle, ShieldAlert, Cpu, Camera, Plus, Trash2,
} from "lucide-react";
import { documentsApi } from "@/lib/api/documents";
import { clientsApi } from "@/lib/api/clients";
import { commandesApi } from "@/lib/api/commandes";
import { amountToCents } from "@/lib/utils/money";

interface LineItem {
  description: string;
  quantity: number;
  unit_price: number;
  unit?: string;
  total?: number;
}

interface PartyInfo {
  name?: string;
  address?: string;
  phone?: string;
  email?: string;
  tax_id?: string;
}

interface ExtractedData {
  document_type?: "invoice" | "purchase_order";
  invoice_number?: string;
  date?: string;
  due_date?: string;
  vendor?: PartyInfo | string;
  client?: PartyInfo | string;
  line_items?: LineItem[];
  subtotal?: number;
  tax_rate?: number;
  tax_amount?: number;
  total_amount?: number;
  currency?: string;
  notes?: string;
  payment_method?: string;
  purchase_order_ref?: string;
  needs_review?: boolean;
}

type ScanStep = "upload" | "preview" | "extracted";

const partyFrom = (value: PartyInfo | string | undefined): PartyInfo =>
  typeof value === "string" ? { name: value } : { ...(value ?? {}) };

const apiErrorMessage = (error: unknown, fallback: string) => {
  const response = (error as { response?: { data?: { detail?: string } } })?.response;
  return response?.data?.detail || fallback;
};

export default function ScanPage() {
  const router = useRouter();
  const [step, setStep] = useState<ScanStep>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [extracted, setExtracted] = useState<ExtractedData | null>(null);
  const [confidence, setConfidence] = useState<number>(0);
  const [rawText, setRawText] = useState<string>("");
  const [extractError, setExtractError] = useState<string | null>(null);
  const [creatingDocuments, setCreatingDocuments] = useState(false);
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());
  const inputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File) => {
    setFile(f);
    setExtractError(null);
    if (f.type.startsWith("image/")) {
      const url = URL.createObjectURL(f);
      setPreviewUrl(url);
    } else {
      setPreviewUrl(null);
    }
    setStep("preview");
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f && (f.type.startsWith("image/") || f.type === "application/pdf")) {
      handleFile(f);
    }
  }, []);

  const runExtraction = async () => {
    if (!file) return;
    setProcessing(true);
    setExtractError(null);
    try {
      const result = await documentsApi.scanFacture(file);
      const data = result.extracted_data as ExtractedData;
      const detectedClient = partyFrom(
        data.document_type === "purchase_order" ? data.vendor : data.client
      );
      const fallbackClient = partyFrom(data.client);
      const fallbackVendor = partyFrom(data.vendor);
      data.client = detectedClient.name
        ? detectedClient
        : fallbackClient.name
          ? fallbackClient
          : fallbackVendor;
      setExtracted(data);
      setConfidence(result.confidence);
      setRawText(result.raw_text);
      setStep("extracted");
    } catch (e: unknown) {
      const err = e as { response?: { status?: number; data?: { detail?: string } } };
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      if (status === 413) {
        setExtractError("Fichier trop volumineux. Maximum 15 Mo.");
      } else if (status === 415) {
        setExtractError("Format non supporté. Utilisez PNG, JPG ou PDF.");
      } else if (status === 503) {
        setExtractError(detail || "Ressources insuffisantes. Réduisez la résolution de l'image ou utilisez un fichier plus léger.");
      } else {
        setExtractError(detail || "Erreur lors de l'analyse. Vérifiez la qualité du fichier et réessayez.");
      }
    } finally {
      setProcessing(false);
    }
  };

  const reset = () => {
    setStep("upload");
    setFile(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setExtracted(null);
    setExtractError(null);
    setWorkflowError(null);
    setCreatingDocuments(false);
    setIdempotencyKey(crypto.randomUUID());
    setRawText("");
  };

  const vendorName = extracted?.vendor
    ? typeof extracted.vendor === "string"
      ? extracted.vendor
      : (extracted.vendor?.name ?? "")
    : "";

  const clientName = extracted?.client
    ? typeof extracted.client === "string"
      ? extracted.client
      : (extracted.client?.name ?? "")
    : "";

  const clientEmail =
    extracted?.client && typeof extracted.client !== "string"
      ? (extracted.client.email ?? "")
      : "";

  const clientPhone =
    extracted?.client && typeof extracted.client !== "string"
      ? (extracted.client.phone ?? "")
      : "";

  const clientAddress =
    extracted?.client && typeof extracted.client !== "string"
      ? (extracted.client.address ?? "")
      : "";

  const updateExtracted = <K extends keyof ExtractedData>(field: K, value: ExtractedData[K]) => {
    setExtracted((current) => current ? { ...current, [field]: value } : current);
  };

  const updateClient = (field: keyof PartyInfo, value: string) => {
    setExtracted((current) => current
      ? { ...current, client: { ...partyFrom(current.client), [field]: value } }
      : current
    );
  };

  const updateLine = (index: number, field: keyof LineItem, value: string | number) => {
    setExtracted((current) => current ? {
      ...current,
      line_items: (current.line_items ?? []).map((line, lineIndex) =>
        lineIndex === index ? { ...line, [field]: value } : line
      ),
    } : current);
  };

  const createOrderAndDocuments = async () => {
    if (!extracted) return;
    setWorkflowError(null);

    const client = partyFrom(extracted.client);
    const name = client.name?.trim() ?? "";
    const phone = client.phone?.trim() ?? "";
    const currency = (extracted.currency || "XAF").trim().toUpperCase();
    const items = (extracted.line_items ?? []).filter((line) => line.description.trim());

    if (name.length < 2) {
      setWorkflowError("Renseignez le nom du client avant de continuer.");
      return;
    }
    if (phone.length < 6) {
      setWorkflowError("Renseignez un numéro de téléphone client valide (6 caractères minimum).");
      return;
    }
    if (!/^[A-Z]{3}$/.test(currency)) {
      setWorkflowError("La devise doit contenir exactement 3 lettres, par exemple XAF.");
      return;
    }
    if (!items.length || items.some((line) =>
      !Number.isInteger(Number(line.quantity)) || Number(line.quantity) <= 0 || Number(line.unit_price) < 0
    )) {
      setWorkflowError("Vérifiez les lignes : description, quantité entière positive et prix positif ou nul.");
      return;
    }

    setCreatingDocuments(true);
    let createdOrderId: string | null = null;
    try {
      const lookup = await clientsApi.list({
        limit: 100,
        search: client.email?.trim() || phone || name,
      });
      const normalizedPhone = phone.replace(/\s+/g, "");
      const normalizedEmail = client.email?.trim().toLowerCase();
      const normalizedName = name.toLowerCase();
      const existingClient = lookup.items.find((candidate) =>
        (normalizedEmail && candidate.email?.toLowerCase() === normalizedEmail) ||
        candidate.phone.replace(/\s+/g, "") === normalizedPhone ||
        candidate.full_name.trim().toLowerCase() === normalizedName
      );
      const orderClient = existingClient ?? await clientsApi.create({
        client_type: "company",
        full_name: name,
        company_name: name,
        phone,
        email: client.email?.trim() || undefined,
        address_line1: client.address?.trim() || undefined,
        tax_id: client.tax_id?.trim() || undefined,
        currency,
        default_tax_rate: Number(extracted.tax_rate) || 0,
      });

      const taxRate = Number(extracted.tax_rate) || (
        Number(extracted.subtotal) > 0
          ? (Number(extracted.tax_amount) / Number(extracted.subtotal)) * 100
          : 0
      );
      const sourceReference = extracted.purchase_order_ref || extracted.invoice_number;
      const sourceLabel = extracted.document_type === "purchase_order"
        ? "Bon de commande scanné"
        : "Facture scannée";
      const order = await commandesApi.create({
        client_id: orderClient.id,
        currency,
        tax_rate: Math.max(0, Math.min(100, taxRate)),
        purchase_order_ref: sourceReference || undefined,
        due_date: extracted.due_date || undefined,
        notes: [extracted.notes?.trim(), `${sourceLabel}${sourceReference ? ` : ${sourceReference}` : ""}`]
          .filter(Boolean)
          .join("\n"),
        items: items.map((line) => ({
          description: line.description.trim(),
          quantity: Number(line.quantity),
          unit_price_cents: amountToCents(Number(line.unit_price)),
          unit: line.unit?.trim() || undefined,
        })),
      }, idempotencyKey);
      createdOrderId = order.id;

      const confirmed = await commandesApi.confirmer(order.id);
      await commandesApi.enregistrerLivraison(
        order.id,
        confirmed.items.map((line) => ({ item_id: line.id, quantity: line.quantity }))
      );
      const [deliveryNote, invoice] = await Promise.all([
        documentsApi.genererBonLivraison(order.id),
        documentsApi.genererFacture(order.id),
      ]);
      const query = new URLSearchParams({
        delivery_document_id: deliveryNote.document_id,
        invoice_document_id: invoice.document_id,
      });
      router.push(`/commandes/${order.id}?${query.toString()}#documents`);
    } catch (error) {
      const suffix = createdOrderId
        ? " La commande a été créée : ouvrez-la depuis la liste pour terminer les documents."
        : "";
      setWorkflowError(apiErrorMessage(error, "La création automatique n’a pas pu être terminée.") + suffix);
    } finally {
      setCreatingDocuments(false);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      {/* En-tête */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Scan de facture ou bon de commande</h1>
        <p className="text-sm text-slate-500 mt-1">
          Importez une photo ou un PDF : les données alimentent directement la commande et ses documents.
        </p>
      </div>

      {/* Étapes */}
      <div className="flex items-center gap-2">
        {(["upload", "preview", "extracted"] as const).map((s, i) => {
          const labels = ["Import", "Aperçu", "Extraction"];
          const done = (["upload", "preview", "extracted"] as const).indexOf(step) > i;
          const active = step === s;
          return (
            <div key={s} className="flex items-center gap-2">
              <div
                className={`flex items-center gap-2 text-sm font-medium ${
                  active ? "text-blue-700" : done ? "text-emerald-600" : "text-slate-400"
                }`}
              >
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 ${
                    done
                      ? "bg-emerald-500 border-emerald-500 text-white"
                      : active
                      ? "border-blue-600 text-blue-600"
                      : "border-slate-200 text-slate-400"
                  }`}
                >
                  {done ? <CheckCircle className="w-4 h-4" /> : i + 1}
                </div>
                {labels[i]}
              </div>
              {i < 2 && <ChevronRight className="w-4 h-4 text-slate-300" />}
            </div>
          );
        })}
      </div>

      {/* ── Étape : Import ── */}
      {step === "upload" && (
        <div className="space-y-4">
          {/* Inputs cachés */}
          <input
            ref={inputRef}
            type="file"
            accept="image/*,application/pdf"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
          />
          <input
            ref={cameraInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
          />

          {/* Deux options */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Option caméra */}
            <button
              type="button"
              onClick={() => cameraInputRef.current?.click()}
              className="card p-8 flex flex-col items-center justify-center gap-3 cursor-pointer transition-all border-2 border-dashed border-slate-200 hover:border-blue-300 hover:bg-blue-50/40 group"
            >
              <div className="p-4 bg-blue-100 rounded-full group-hover:bg-blue-200 transition-colors">
                <Camera className="w-7 h-7 text-blue-600" />
              </div>
              <div className="text-center">
                <p className="font-semibold text-slate-900">Prendre une photo</p>
                <p className="text-xs text-slate-400 mt-1">Ouvrir l&apos;appareil photo</p>
              </div>
            </button>

            {/* Option fichier avec drag-and-drop */}
            <div
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
              className={`card p-8 flex flex-col items-center justify-center gap-3 cursor-pointer transition-all border-2 border-dashed group ${
                dragging
                  ? "border-blue-400 bg-blue-50"
                  : "border-slate-200 hover:border-blue-300 hover:bg-blue-50/40"
              }`}
            >
              <div className="p-4 bg-slate-100 rounded-full group-hover:bg-blue-100 transition-colors">
                <Upload className="w-7 h-7 text-slate-500 group-hover:text-blue-600 transition-colors" />
              </div>
              <div className="text-center">
                <p className="font-semibold text-slate-900">Choisir un fichier</p>
                <p className="text-xs text-slate-400 mt-1">PNG, JPG, PDF — max 10 Mo</p>
              </div>
            </div>
          </div>

          <div className="flex justify-center">
            <div className="flex items-center gap-2 text-xs text-blue-600 bg-blue-50 border border-blue-100 px-3 py-1.5 rounded-full">
              <Cpu className="w-3.5 h-3.5" />
              OCR local — aucune donnée envoyée en ligne
            </div>
          </div>
        </div>
      )}

      {/* ── Étape : Aperçu ── */}
      {step === "preview" && file && (
        <div className="space-y-4">
          <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <FileText className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <p className="font-medium text-slate-900">{file.name}</p>
                  <p className="text-xs text-slate-400">
                    {(file.size / 1024).toFixed(1)} Ko · {file.type}
                  </p>
                </div>
              </div>
              <button onClick={reset} className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
                <X className="w-4 h-4 text-slate-500" />
              </button>
            </div>

            {previewUrl && (
              <div className="rounded-lg overflow-hidden border border-slate-100 bg-slate-50">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={previewUrl}
                  alt="Aperçu facture"
                  className="w-full max-h-80 object-contain"
                />
              </div>
            )}

            {file.type === "application/pdf" && !previewUrl && (
              <div className="h-32 flex items-center justify-center bg-slate-50 rounded-lg border border-slate-100">
                <p className="text-sm text-slate-400">Aperçu PDF — l&apos;extraction démarre au clic</p>
              </div>
            )}
          </div>

          {extractError && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-800">{extractError}</p>
            </div>
          )}

          <div className="flex gap-3 justify-end">
            <button onClick={reset} className="btn-secondary">
              <X className="w-4 h-4" /> Annuler
            </button>
            <button onClick={runExtraction} disabled={processing} className="btn-primary">
              {processing ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Analyse OCR en cours…</>
              ) : (
                <><ScanLine className="w-4 h-4" /> Extraire les données</>
              )}
            </button>
          </div>
        </div>
      )}

      {/* ── Étape : Données extraites ── */}
      {step === "extracted" && extracted && (
        <div className="space-y-5">

          {/* Bandeau de confiance */}
          <div
            className={`flex items-center gap-3 rounded-xl px-4 py-3 border text-sm font-medium ${
              confidence >= 0.7
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : confidence >= 0.4
                ? "bg-amber-50 border-amber-200 text-amber-800"
                : "bg-red-50 border-red-200 text-red-800"
            }`}
          >
            {confidence >= 0.7 ? (
              <CheckCircle className="w-5 h-5 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
            )}
            <div>
              Fiabilité OCR : <strong>{Math.round(confidence * 100)}%</strong>
              {confidence < 0.7 && " — vérifiez et corrigez les champs avant de créer la commande"}
            </div>
          </div>

          {/* Bandeau validation mathématique */}
          {extracted.needs_review && (
            <div className="flex items-start gap-3 rounded-xl px-4 py-3 border bg-amber-50 border-amber-300 text-amber-900 text-sm">
              <ShieldAlert className="w-5 h-5 flex-shrink-0 mt-0.5 text-amber-600" />
              <div>
                <p className="font-semibold">Vérification mathématique échouée</p>
                <p className="text-amber-800 mt-0.5">
                  Les montants extraits sont incohérents (la somme des lignes ne correspond pas au
                  sous-total HT, ou HT + TVA ≠ TTC). Corrigez les valeurs avant de créer la commande.
                </p>
              </div>
            </div>
          )}

          {/* Formulaire de données extraites */}
          <div className="card p-6 space-y-5">
            <h2 className="font-semibold text-slate-900 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-blue-600" />
              Données extraites
            </h2>

            {/* Identité */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="label">Type de document source</label>
                <select
                  value={extracted.document_type ?? "invoice"}
                  onChange={(event) => updateExtracted("document_type", event.target.value as ExtractedData["document_type"])}
                  className="input"
                >
                  <option value="invoice">Facture</option>
                  <option value="purchase_order">Bon de commande</option>
                </select>
              </div>
              <div>
                <label className="label">Référence du document</label>
                <input
                  value={extracted.purchase_order_ref ?? extracted.invoice_number ?? ""}
                  onChange={(event) => updateExtracted(
                    extracted.document_type === "purchase_order" ? "purchase_order_ref" : "invoice_number",
                    event.target.value
                  )}
                  className="input"
                />
              </div>
              <div>
                <label className="label">Date</label>
                <input value={extracted.date ?? ""} onChange={(event) => updateExtracted("date", event.target.value)} className="input" type="date" />
              </div>
              <div>
                <label className="label">Émetteur détecté</label>
                <input value={vendorName} className="input bg-slate-50" readOnly />
              </div>
              <div>
                <label className="label">Client *</label>
                <input value={clientName} onChange={(event) => updateClient("name", event.target.value)} className="input" />
              </div>
              <div>
                <label className="label">Email client</label>
                <input value={clientEmail} onChange={(event) => updateClient("email", event.target.value)} type="email" className="input" />
              </div>
              <div>
                <label className="label">Téléphone client *</label>
                <input value={clientPhone} onChange={(event) => updateClient("phone", event.target.value)} className="input" />
              </div>
              <div>
                <label className="label">Adresse client</label>
                <input value={clientAddress} onChange={(event) => updateClient("address", event.target.value)} className="input" />
              </div>
              <div>
                <label className="label">Devise</label>
                <input value={extracted.currency ?? "XAF"} onChange={(event) => updateExtracted("currency", event.target.value)} className="input" maxLength={3} />
              </div>
            </div>

            {/* Lignes de commande */}
            {(
              <div>
                <div className="flex items-center justify-between mb-3">
                  <label className="label mb-0">
                    Lignes de commande ({extracted.line_items?.length ?? 0})
                  </label>
                  <button
                    type="button"
                    onClick={() => updateExtracted("line_items", [
                      ...(extracted.line_items ?? []),
                      { description: "", quantity: 1, unit_price: 0 },
                    ])}
                    className="btn-secondary py-1.5 px-2 text-xs"
                  >
                    <Plus className="w-3.5 h-3.5" /> Ajouter
                  </button>
                </div>
                <div className="overflow-x-auto rounded-lg border border-slate-200">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="table-header text-left w-1/2">Description</th>
                        <th className="table-header text-right">Qté</th>
                        <th className="table-header text-right">Unité</th>
                        <th className="table-header text-right">Prix U.</th>
                        <th className="table-header"><span className="sr-only">Actions</span></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {(extracted.line_items ?? []).map((l, i) => (
                        <tr key={i}>
                          <td className="px-4 py-2">
                            <input
                              value={l.description}
                              onChange={(event) => updateLine(i, "description", event.target.value)}
                              className="input text-sm py-1.5"
                              placeholder="Description"
                            />
                          </td>
                          <td className="px-2 py-2 w-20">
                            <input
                              value={l.quantity}
                              onChange={(event) => updateLine(i, "quantity", Number(event.target.value))}
                              type="number"
                              className="input text-sm py-1.5 text-right"
                              placeholder="Qté"
                            />
                          </td>
                          <td className="px-2 py-2 w-24">
                            <input
                              value={l.unit ?? ""}
                              onChange={(event) => updateLine(i, "unit", event.target.value)}
                              className="input text-sm py-1.5"
                              placeholder="Unité"
                            />
                          </td>
                          <td className="px-2 py-2 w-28">
                            <input
                              value={l.unit_price}
                              onChange={(event) => updateLine(i, "unit_price", Number(event.target.value))}
                              type="number"
                              className="input text-sm py-1.5 text-right"
                              placeholder="Prix"
                            />
                          </td>
                          <td className="px-2 py-2 w-12">
                            <button
                              type="button"
                              onClick={() => updateExtracted(
                                "line_items",
                                (extracted.line_items ?? []).filter((_, lineIndex) => lineIndex !== i)
                              )}
                              className="p-2 text-slate-400 hover:text-red-600"
                              aria-label="Supprimer la ligne"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Totaux */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {extracted.subtotal !== undefined && (
                <div>
                  <label className="label">
                    Sous-total HT
                    {extracted.needs_review && (
                      <span className="ml-1 text-amber-500 text-xs font-normal">⚠ à vérifier</span>
                    )}
                  </label>
                  <input
                    value={extracted.subtotal ?? ""}
                    onChange={(event) => updateExtracted("subtotal", Number(event.target.value))}
                    type="number"
                    className={`input ${extracted.needs_review ? "border-amber-300 focus:ring-amber-400" : ""}`}
                  />
                </div>
              )}
              <div>
                <label className="label">Taux TVA (%)</label>
                <input
                  value={extracted.tax_rate ?? ""}
                  onChange={(event) => updateExtracted("tax_rate", Number(event.target.value))}
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  className="input"
                />
              </div>
              {extracted.tax_amount !== undefined && (
                <div>
                  <label className="label">
                    TVA
                    {extracted.needs_review && (
                      <span className="ml-1 text-amber-500 text-xs font-normal">⚠ à vérifier</span>
                    )}
                  </label>
                  <input
                    value={extracted.tax_amount ?? ""}
                    onChange={(event) => updateExtracted("tax_amount", Number(event.target.value))}
                    type="number"
                    className={`input ${extracted.needs_review ? "border-amber-300 focus:ring-amber-400" : ""}`}
                  />
                </div>
              )}
              {extracted.total_amount !== undefined && (
                <div>
                  <label className="label">
                    Total TTC
                    {extracted.needs_review && (
                      <span className="ml-1 text-amber-500 text-xs font-normal">⚠ à vérifier</span>
                    )}
                  </label>
                  <input
                    value={extracted.total_amount ?? ""}
                    onChange={(event) => updateExtracted("total_amount", Number(event.target.value))}
                    type="number"
                    className={`input font-semibold text-blue-700 ${
                      extracted.needs_review ? "border-amber-300 focus:ring-amber-400" : ""
                    }`}
                  />
                </div>
              )}
            </div>

            <div>
              <label className="label">Notes</label>
              <textarea
                value={extracted.notes ?? ""}
                onChange={(event) => updateExtracted("notes", event.target.value)}
                rows={2}
                className="input resize-none"
              />
            </div>
          </div>

          {/* Texte brut (debug) */}
          {rawText && (
            <details className="card p-4">
              <summary className="text-sm font-medium text-slate-600 cursor-pointer select-none">
                Texte brut extrait (debug)
              </summary>
              <pre className="mt-3 text-xs text-slate-500 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                {rawText}
              </pre>
            </details>
          )}

          {workflowError && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-800">{workflowError}</p>
            </div>
          )}

          <div className="flex gap-3 justify-end">
            <button onClick={reset} className="btn-secondary">
              <X className="w-4 h-4" /> Recommencer
            </button>
            <button onClick={createOrderAndDocuments} disabled={creatingDocuments} className="btn-primary">
              {creatingDocuments
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <ChevronRight className="w-4 h-4" />}
              {creatingDocuments ? "Création des documents…" : "Créer livraison et facture"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
