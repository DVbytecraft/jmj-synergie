/**
 * Export comptable — Journal de ventes OHADA.
 * Déclenche le téléchargement du fichier CSV ou XLSX directement depuis le navigateur.
 */
import { useAuthStore } from "@/store/auth.store";

export type ExportFormat = "csv" | "xlsx";

/**
 * Télécharge le journal de ventes pour la période donnée.
 * @param start  Date de début au format YYYY-MM-DD
 * @param end    Date de fin au format YYYY-MM-DD
 * @param format "csv" (défaut) ou "xlsx"
 */
export async function downloadJournal(
  start: string,
  end: string,
  format: ExportFormat = "csv"
): Promise<void> {
  const token = useAuthStore.getState().accessToken;
  const params = new URLSearchParams({ start, end, format });
  const url = `/api/v1/exports/journal-ventes?${params.toString()}`;

  const response = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    credentials: "include",
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => "Erreur inconnue");
    throw new Error(`Export échoué (${response.status}): ${detail}`);
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);

  const ext = format === "xlsx" ? "xlsx" : "csv";
  const filename = `journal-ventes-${start}-${end}.${ext}`;

  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(objectUrl);
}
