"use client";

import Link from "next/link";
import { useState, useRef, useCallback } from "react";
import {
  ScanLine, Upload, X, FileText, AlertCircle,
  ChevronRight, Loader2, CheckCircle, Sparkles,
} from "lucide-react";
import { documentsApi } from "@/lib/api/documents";

interface LineItem {
  description: string;
  quantity: number;
  unit_price: number;
  unit?: string;
  total?: number;
}

interface VendorInfo {
  name?: string;
  address?: string;
  phone?: string;
  email?: string;
  tax_id?: string;
}

interface ExtractedData {
  invoice_number?: string;
  date?: string;
  due_date?: string;
  vendor?: VendorInfo | string;
  client?: { name?: string; email?: string; phone?: string } | string;
  line_items?: LineItem[];
  subtotal?: number;
  tax_rate?: number;
  tax_amount?: number;
  total_amount?: number;
  currency?: string;
  notes?: string;
  payment_method?: string;
}

type ScanStep = "upload" | "preview" | "extracted";

export default function ScanPage() {
  const [step, setStep] = useState<ScanStep>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [extracted, setExtracted] = useState<ExtractedData | null>(null);
  const [confidence, setConfidence] = useState<number>(0);
  const [rawText, setRawText] = useState<string>("");
  const [extractError, setExtractError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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
      setExtracted(result.extracted_data as ExtractedData);
      setConfidence(result.confidence);
      setRawText(result.raw_text);
      setStep("extracted");
    } catch (e: any) {
      setExtractError(
        e.response?.data?.detail || "Erreur lors de l'analyse. Vérifiez le fichier et réessayez."
      );
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
    setRawText("");
  };

  const vendorName = extracted?.vendor
    ? typeof extracted.vendor === "string"
      ? extracted.vendor
      : extracted.vendor?.name ?? ""
    : "";
  const clientName = extracted?.client
    ? typeof extracted.client === "string"
      ? extracted.client
      : extracted.client?.name ?? ""
    : "";
  const clientEmail = extracted?.client && typeof extracted.client !== "string"
    ? extracted.client.email ?? ""
    : "";

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Scan de facture</h1>
        <p className="text-sm text-gray-500 mt-1">
          Importez une photo ou PDF de facture — l&apos;IA extrait automatiquement toutes les données
        </p>
      </div>

      {/* Progress steps */}
      <div className="flex items-center gap-2">
        {(["upload", "preview", "extracted"] as const).map((s, i) => {
          const labels = ["Import", "Aperçu", "Extraction"];
          const done = ["upload", "preview", "extracted"].indexOf(step) > i;
          const active = step === s;
          return (
            <div key={s} className="flex items-center gap-2">
              <div className={`flex items-center gap-2 text-sm font-medium ${active ? "text-blue-700" : done ? "text-emerald-600" : "text-gray-400"}`}>
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 ${
                  done ? "bg-emerald-500 border-emerald-500 text-white" :
                  active ? "border-blue-600 text-blue-600" :
                  "border-gray-200 text-gray-400"
                }`}>
                  {done ? <CheckCircle className="w-4 h-4" /> : i + 1}
                </div>
                {labels[i]}
              </div>
              {i < 2 && <ChevronRight className="w-4 h-4 text-gray-300" />}
            </div>
          );
        })}
      </div>

      {/* ── Step: Upload ── */}
      {step === "upload" && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`card p-12 flex flex-col items-center justify-center gap-4 cursor-pointer transition-all border-2 border-dashed ${
            dragging ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-blue-300 hover:bg-gray-50"
          }`}
        >
          <div className="p-4 bg-blue-100 rounded-full">
            <Upload className="w-8 h-8 text-blue-600" />
          </div>
          <div className="text-center">
            <p className="font-semibold text-gray-900">Glissez votre facture ici</p>
            <p className="text-sm text-gray-400 mt-1">ou cliquez pour parcourir vos fichiers</p>
            <p className="text-xs text-gray-400 mt-2">PNG, JPG, PDF — max 10 Mo</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-blue-600 bg-blue-50 px-3 py-1.5 rounded-full">
            <Sparkles className="w-3.5 h-3.5" />
            Extraction IA des données
          </div>
          <input
            ref={inputRef}
            type="file"
            accept="image/*,application/pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
            }}
          />
        </div>
      )}

      {/* ── Step: Preview ── */}
      {step === "preview" && file && (
        <div className="space-y-4">
          <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <FileText className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <p className="font-medium text-gray-900">{file.name}</p>
                  <p className="text-xs text-gray-400">
                    {(file.size / 1024).toFixed(1)} Ko · {file.type}
                  </p>
                </div>
              </div>
              <button onClick={reset} className="p-1.5 hover:bg-gray-100 rounded-lg">
                <X className="w-4 h-4 text-gray-500" />
              </button>
            </div>

            {previewUrl && (
              <div className="rounded-lg overflow-hidden border border-gray-100 bg-gray-50">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={previewUrl}
                  alt="Aperçu facture"
                  className="w-full max-h-80 object-contain"
                />
              </div>
            )}

            {file.type === "application/pdf" && !previewUrl && (
              <div className="h-32 flex items-center justify-center bg-gray-50 rounded-lg border border-gray-100">
                <p className="text-sm text-gray-400">Aperçu PDF — l&apos;extraction démarre au clic</p>
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
                <><Loader2 className="w-4 h-4 animate-spin" /> Analyse IA en cours…</>
              ) : (
                <><ScanLine className="w-4 h-4" /> Extraire les données</>
              )}
            </button>
          </div>
        </div>
      )}

      {/* ── Step: Extracted ── */}
      {step === "extracted" && extracted && (
        <div className="space-y-5">
          {/* Confidence banner */}
          <div className={`flex items-center gap-3 rounded-xl px-4 py-3 border text-sm font-medium ${
            confidence >= 0.7
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : confidence >= 0.4
              ? "bg-amber-50 border-amber-200 text-amber-800"
              : "bg-red-50 border-red-200 text-red-800"
          }`}>
            {confidence >= 0.7 ? (
              <CheckCircle className="w-5 h-5 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
            )}
            <div>
              Confiance de l&apos;extraction : <strong>{Math.round(confidence * 100)}%</strong>
              {confidence < 0.7 && " — vérifiez et corrigez les champs avant de créer la commande"}
            </div>
          </div>

          {/* Extracted form */}
          <div className="card p-6 space-y-5">
            <h2 className="font-semibold text-gray-900 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-blue-600" />
              Données extraites
            </h2>

            {/* Identité */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="label">N° Facture</label>
                <input defaultValue={extracted.invoice_number ?? ""} className="input" />
              </div>
              <div>
                <label className="label">Date</label>
                <input defaultValue={extracted.date ?? ""} className="input" type="date" />
              </div>
              <div>
                <label className="label">Émetteur (vendeur)</label>
                <input defaultValue={vendorName} className="input" />
              </div>
              <div>
                <label className="label">Client</label>
                <input defaultValue={clientName} className="input" />
              </div>
              <div>
                <label className="label">Email client</label>
                <input defaultValue={clientEmail} type="email" className="input" />
              </div>
              <div>
                <label className="label">Devise</label>
                <input defaultValue={extracted.currency ?? "XAF"} className="input" />
              </div>
            </div>

            {/* Lignes */}
            {extracted.line_items && extracted.line_items.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <label className="label mb-0">Lignes de commande ({extracted.line_items.length})</label>
                </div>
                <div className="space-y-2">
                  {extracted.line_items.map((l, i) => (
                    <div key={i} className="grid grid-cols-12 gap-2">
                      <div className="col-span-6">
                        <input defaultValue={l.description} className="input text-sm" placeholder="Description" />
                      </div>
                      <div className="col-span-2">
                        <input defaultValue={l.quantity} type="number" className="input text-sm" placeholder="Qté" />
                      </div>
                      <div className="col-span-2">
                        <input defaultValue={l.unit ?? ""} className="input text-sm" placeholder="Unité" />
                      </div>
                      <div className="col-span-2">
                        <input defaultValue={l.unit_price} type="number" className="input text-sm" placeholder="Prix" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Totaux */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {extracted.subtotal !== undefined && (
                <div>
                  <label className="label">Sous-total HT</label>
                  <input defaultValue={extracted.subtotal} type="number" className="input" />
                </div>
              )}
              {extracted.tax_amount !== undefined && (
                <div>
                  <label className="label">TVA</label>
                  <input defaultValue={extracted.tax_amount} type="number" className="input" />
                </div>
              )}
              {extracted.total_amount !== undefined && (
                <div>
                  <label className="label">Total TTC</label>
                  <input
                    defaultValue={extracted.total_amount}
                    type="number"
                    className="input font-semibold text-blue-700"
                  />
                </div>
              )}
            </div>

            {extracted.notes && (
              <div>
                <label className="label">Notes</label>
                <textarea defaultValue={extracted.notes} rows={2} className="input resize-none" />
              </div>
            )}
          </div>

          {/* Raw text accordion */}
          {rawText && (
            <details className="card p-4">
              <summary className="text-sm font-medium text-gray-600 cursor-pointer select-none">
                Texte brut extrait (debug)
              </summary>
              <pre className="mt-3 text-xs text-gray-500 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                {rawText}
              </pre>
            </details>
          )}

          <div className="flex gap-3 justify-end">
            <button onClick={reset} className="btn-secondary">
              <X className="w-4 h-4" /> Recommencer
            </button>
            <Link href="/commandes/new" className="btn-primary">
              <ChevronRight className="w-4 h-4" />
              Créer la commande
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
