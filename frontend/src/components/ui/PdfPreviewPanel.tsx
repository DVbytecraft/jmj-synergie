"use client";

import { Download, Eye, Loader2, X } from "lucide-react";

interface PdfPreviewPanelProps {
  title: string;
  previewUrl: string | null;
  loading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  onDownload?: () => void;
  onClose?: () => void;
}

export function PdfPreviewPanel({
  title,
  previewUrl,
  loading = false,
  emptyTitle = "Aucun aperçu",
  emptyDescription = "Sélectionnez un document exportable pour voir son rendu ici.",
  onDownload,
  onClose,
}: PdfPreviewPanelProps) {
  return (
    <div className="card overflow-hidden lg:sticky lg:top-6">
      <div className="flex items-center justify-between border-b border-gray-100 bg-gray-50 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
          ) : (
            <Eye className="h-4 w-4 text-blue-600" />
          )}
          {title}
        </div>
        <div className="flex items-center gap-1.5">
          {previewUrl && onDownload && (
            <button onClick={onDownload} className="btn-secondary px-2 py-1 text-xs">
              <Download className="h-3.5 w-3.5" />
              Télécharger
            </button>
          )}
          {previewUrl && onClose && (
            <button onClick={onClose} className="btn-icon p-1.5" aria-label="Fermer l'aperçu">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {previewUrl ? (
        <iframe
          src={previewUrl}
          className="h-[640px] w-full border-0 bg-white"
          title={title}
        />
      ) : (
        <div className="flex h-[640px] flex-col items-center justify-center px-6 text-center">
          {loading ? (
            <>
              <Loader2 className="mb-4 h-8 w-8 animate-spin text-blue-600" />
              <p className="text-sm font-medium text-gray-700">Génération du document…</p>
              <p className="mt-2 max-w-xs text-xs leading-5 text-gray-400">
                Le rendu PDF va s&apos;afficher ici dès qu&apos;il est prêt.
              </p>
            </>
          ) : (
            <>
              <Eye className="mb-4 h-8 w-8 text-gray-300" />
              <p className="text-sm font-medium text-gray-700">{emptyTitle}</p>
              <p className="mt-2 max-w-xs text-xs leading-5 text-gray-400">{emptyDescription}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
