"use client";

import { useState } from "react";
import { Download, FileSpreadsheet, FileText, Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { downloadJournal, type ExportFormat } from "@/lib/api/exports";

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

function firstDayOfMonthStr(): string {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}

type ExportState = "idle" | "loading" | "success" | "error";

export default function ExportsPage() {
  const [start, setStart] = useState(firstDayOfMonthStr());
  const [end, setEnd] = useState(todayStr());
  const [format, setFormat] = useState<ExportFormat>("csv");
  const [state, setState] = useState<ExportState>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  async function handleDownload() {
    if (!start || !end) return;
    if (start > end) {
      setErrorMsg("La date de début doit être antérieure à la date de fin.");
      setState("error");
      return;
    }
    setState("loading");
    setErrorMsg("");
    try {
      await downloadJournal(start, end, format);
      setState("success");
      setTimeout(() => setState("idle"), 3000);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Erreur lors de l'export.");
      setState("error");
    }
  }

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Download className="w-6 h-6 text-blue-400" />
          Exports comptables
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Téléchargez le journal de ventes au format OHADA pour votre comptabilité.
        </p>
      </div>

      <div className="bg-slate-800 border border-white/5 rounded-xl p-6 space-y-6">
        <h2 className="text-base font-semibold text-white">Journal de ventes</h2>

        {/* Date range */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5">
              Date de début
            </label>
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              max={end}
              className="w-full bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5">
              Date de fin
            </label>
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              min={start}
              max={todayStr()}
              className="w-full bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500"
            />
          </div>
        </div>

        {/* Format selector */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-2">
            Format d&apos;export
          </label>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setFormat("csv")}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors ${
                format === "csv"
                  ? "bg-blue-500/10 border-blue-500/50 text-blue-400"
                  : "bg-slate-900 border-white/10 text-slate-400 hover:border-white/20 hover:text-slate-200"
              }`}
            >
              <FileText className="w-4 h-4" />
              CSV
            </button>
            <button
              type="button"
              onClick={() => setFormat("xlsx")}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors ${
                format === "xlsx"
                  ? "bg-blue-500/10 border-blue-500/50 text-blue-400"
                  : "bg-slate-900 border-white/10 text-slate-400 hover:border-white/20 hover:text-slate-200"
              }`}
            >
              <FileSpreadsheet className="w-4 h-4" />
              Excel (.xlsx)
            </button>
          </div>
        </div>

        {/* Feedback */}
        {state === "error" && (
          <div className="flex items-start gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2.5">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            {errorMsg}
          </div>
        )}
        {state === "success" && (
          <div className="flex items-center gap-2 text-emerald-400 text-sm bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2.5">
            <CheckCircle className="w-4 h-4 flex-shrink-0" />
            Fichier téléchargé avec succès.
          </div>
        )}

        {/* Download button */}
        <button
          type="button"
          onClick={handleDownload}
          disabled={state === "loading" || !start || !end}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium text-sm rounded-lg transition-colors"
        >
          {state === "loading" ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Génération en cours…
            </>
          ) : (
            <>
              <Download className="w-4 h-4" />
              Télécharger le journal
            </>
          )}
        </button>

        <p className="text-xs text-slate-500 leading-relaxed">
          Le journal de ventes liste toutes les transactions de paiement complétées sur la période
          sélectionnée, avec montants HT, TVA et TTC, conformément aux exigences OHADA.
        </p>
      </div>
    </div>
  );
}
