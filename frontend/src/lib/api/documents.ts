import { apiClient } from "./client";
import type { Document } from "@/types";

export type { Document };

export interface DocumentListResponse {
  total: number;
  skip: number;
  limit: number;
  items: Document[];
}

export const documentsApi = {
  /** Liste globale de tous les documents de l'organisation. */
  listAll: (params?: {
    skip?: number;
    limit?: number;
    document_type?: string;
    date_from?: string;
    date_to?: string;
    client_type?: string;
  }) =>
    apiClient
      .get<DocumentListResponse>("/documents", { params })
      .then((r) => r.data),

  /** Envoyer un document par email (destinataire optionnel). */
  sendEmail: (document_id: string, recipient_email?: string) =>
    apiClient
      .post<{ message: string }>(`/documents/${document_id}/send-email`, {
        recipient_email: recipient_email ?? null,
      })
      .then((r) => r.data),
  /** Générer un PDF pour un devis. */
  genererDevis: (quote_id: string) =>
    apiClient
      .post<{ document_id: string; file_name: string; message: string }>(
        `/documents/quote/${quote_id}`
      )
      .then((r) => r.data),
  /** Générer un pro forma pour une commande. */
  genererProForma: (order_id: string) =>
    apiClient
      .post<{ document_id: string; file_name: string; message: string }>(
        `/documents/pro-forma/${order_id}`
      )
      .then((r) => r.data),

  genererFacture: (order_id: string) =>
    apiClient
      .post<{ document_id: string; file_name: string; message: string }>(
        `/documents/invoice/${order_id}`
      )
      .then((r) => r.data),

  genererBonLivraison: (order_id: string, delivery_note_number?: string) =>
    apiClient
      .post<{ document_id: string; file_name: string; message: string }>(
        `/documents/delivery-note/${order_id}`,
        null,
        { params: delivery_note_number ? { delivery_note_number } : undefined }
      )
      .then((r) => r.data),

  /** Lister les documents d'une commande. */
  listByOrder: (order_id: string) =>
    apiClient
      .get<Document[]>(`/documents/orders/${order_id}`)
      .then((r) => r.data),

  /** Signer un document. */
  signer: (document_id: string, include_stamp = true) =>
    apiClient
      .post<{ message: string; signed_path: string }>(
        `/documents/${document_id}/sign`,
        null,
        { params: { include_stamp } }
      )
      .then((r) => r.data),

  /** URL de téléchargement d'un document. */
  telechargerUrl: (document_id: string) =>
    `${apiClient.defaults.baseURL}/documents/${document_id}/download`,

  /** Scanner une facture (OCR). */
  scanFacture: (file: File, order_id?: string) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient
      .post<{
        document_id: string;
        order_id: string | null;
        extracted_data: Record<string, unknown>;
        confidence: number;
        raw_text: string;
      }>("/documents/scan-invoice", form, {
        params: order_id ? { order_id } : undefined,
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },

  linkScanToOrder: (documentId: string, orderId: string) =>
    apiClient
      .post<{ document_id: string; order_id: string }>(`/documents/scans/${documentId}/link-order`, { order_id: orderId })
      .then((r) => r.data),
};
