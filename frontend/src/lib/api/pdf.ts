import { apiClient } from "./client";

async function generateAndDownload(endpoint: string, fileName: string): Promise<void> {
  const response = await apiClient.post<{ document_id: string; file_name: string }>(endpoint);
  const { document_id } = response.data;

  const fileResponse = await apiClient.get(`/documents/${document_id}/download`, {
    responseType: "blob",
  });

  const url = URL.createObjectURL(new Blob([fileResponse.data], { type: "application/pdf" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

export const pdfApi = {
  /** Pro forma — disponible dès la création (draft). */
  downloadProForma: (orderId: string): Promise<void> =>
    generateAndDownload(
      `/documents/pro-forma/${orderId}`,
      `proforma-${orderId.slice(0, 8)}.pdf`
    ),

  /** Facture définitive — seulement après confirmation de la commande. */
  downloadFacture: (orderId: string): Promise<void> =>
    generateAndDownload(
      `/documents/invoice/${orderId}`,
      `facture-${orderId.slice(0, 8)}.pdf`
    ),

  getDownloadUrl: (documentId: string): string =>
    `${apiClient.defaults.baseURL}/documents/${documentId}/download`,
};
