"use client";

import Link from "next/link";
import { useState, useRef, useCallback } from "react";
import {
  ScanLine, Upload, X, FileText, AlertCircle,
  ChevronRight, Loader2, CheckCircle, ShieldAlert, Cpu, Camera,
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
  needs_review?: boolean;
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
      setExtracted(result.extracted_data as ExtractedData);
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

  return (
    <div className="space-y-6 max-w-3xl">
      {/* En-tête */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Scan de facture</h1>
        <p className="text-sm text-slate-500 mt-1">
          Importez une photo ou un PDF de facture — l&apos;OCR extrait automatiquement toutes les données
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

            {/* Lignes de commande */}
            {extracted.line_items && extracted.line_items.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <label className="label mb-0">
                    Lignes de commande ({extracted.line_items.length})
                  </label>
                </div>
                <div className="overflow-x-auto rounded-lg border border-slate-200">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="table-header text-left w-1/2">Description</th>
                        <th className="table-header text-right">Qté</th>
                        <th className="table-header text-right">Unité</th>
                        <th className="table-header text-right">Prix U.</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {extracted.line_items.map((l, i) => (
                        <tr key={i}>
                          <td className="px-4 py-2">
                            <input
                              defaultValue={l.description}
                              className="input text-sm py-1.5"
                              placeholder="Description"
                            />
                          </td>
                          <td className="px-2 py-2 w-20">
                            <input
                              defaultValue={l.quantity}
                              type="number"
                              className="input text-sm py-1.5 text-right"
                              placeholder="Qté"
                            />
                          </td>
                          <td className="px-2 py-2 w-24">
                            <input
                              defaultValue={l.unit ?? ""}
                              className="input text-sm py-1.5"
                              placeholder="Unité"
                            />
                          </td>
                          <td className="px-2 py-2 w-28">
                            <input
                              defaultValue={l.unit_price}
                              type="number"
                              className="input text-sm py-1.5 text-right"
                              placeholder="Prix"
                            />
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
                    defaultValue={extracted.subtotal}
                    type="number"
                    className={`input ${extracted.needs_review ? "border-amber-300 focus:ring-amber-400" : ""}`}
                  />
                </div>
              )}
              {extracted.tax_amount !== undefined && (
                <div>
                  <label className="label">
                    TVA
                    {extracted.needs_review && (
                      <span className="ml-1 text-amber-500 text-xs font-normal">⚠ à vérifier</span>
                    )}
                  </label>
                  <input
                    defaultValue={extracted.tax_amount}
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
                    defaultValue={extracted.total_amount}
                    type="number"
                    className={`input font-semibold text-blue-700 ${
                      extracted.needs_review ? "border-amber-300 focus:ring-amber-400" : ""
                    }`}
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
