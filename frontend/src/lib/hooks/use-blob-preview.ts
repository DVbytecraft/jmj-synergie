import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Shared state machine for "generate/fetch a PDF then preview it in an iframe"
 * flows (documents, commandes, devis, pdf pages all repeated this by hand —
 * factored out after a duplicated-render bug was found on the devis page).
 */
export function useBlobPreview() {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const previewUrlRef = useRef<string | null>(null);
  previewUrlRef.current = previewUrl;

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    };
  }, []);

  const close = useCallback(() => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    setPreviewUrl(null);
  }, []);

  /** Runs `producer`, which must resolve to a PDF Blob, and shows it as the preview. */
  const run = useCallback(async (producer: () => Promise<Blob>, title: string) => {
    setLoading(true);
    setError(null);
    try {
      const blob = await producer();
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      setPreviewUrl(URL.createObjectURL(blob));
      setPreviewTitle(title);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Erreur lors de la génération du document");
    } finally {
      setLoading(false);
    }
  }, []);

  const download = useCallback((fileName?: string) => {
    if (!previewUrlRef.current) return;
    const a = document.createElement("a");
    a.href = previewUrlRef.current;
    a.download = fileName ?? previewTitle;
    a.click();
  }, [previewTitle]);

  const clearError = useCallback(() => setError(null), []);

  return { previewUrl, previewTitle, loading, error, run, close, download, clearError };
}
