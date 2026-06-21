import { apiClient } from "./client";
import axios from "axios";

export interface PortalShareResponse {
  url: string;
  expires_at: string;
}

export interface PortalOrderInfo {
  order_number: string;
  status: string;
  client_name: string;
  currency: string;
  total_cents: number;
  paid_cents: number;
  document_types: string[];
}

export const portalApi = {
  /** Génère un lien partageable pour une commande (opérateur auth) */
  createShare: async (orderId: string): Promise<PortalShareResponse> => {
    const res = await apiClient.post<PortalShareResponse>(`/portal/orders/${orderId}/share`);
    return res.data;
  },

  /** Révoque le lien partageable d'une commande (opérateur auth) */
  revokeShare: async (orderId: string): Promise<void> => {
    await apiClient.delete(`/portal/orders/${orderId}/share`);
  },

  /** Récupère les infos publiques d'une commande via token (sans auth) */
  getOrderByToken: async (token: string): Promise<PortalOrderInfo> => {
    // Appel direct sans le middleware auth (apiClient utilise /api/v1 de Next.js)
    const res = await axios.get<PortalOrderInfo>(`/api/v1/portal/${token}`);
    return res.data;
  },
};
