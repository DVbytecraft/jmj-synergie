import { apiClient } from "./client";
import type { Payment, PaymentCreate, Refund, RefundCreate } from "@/types";

export type { Payment, PaymentMethod } from "@/types";
export type Paiement = Payment;
export type StatutPaiement = Payment["status"];
export type MethodePaiement = Payment["method"];

export const paiementsApi = {
  list: async (params?: { skip?: number; limit?: number; order_id?: string }) => {
    const res = await apiClient.get<{
      items: Payment[];
      total: number;
      total_completed_cents: number;
      total_refunded_cents: number;
    }>("/payments", { params });
    return res.data;
  },

  get: async (id: string) => {
    const res = await apiClient.get<Payment>(`/payments/${id}`);
    return res.data;
  },

  /** Enregistrer un paiement (virement, chèque, espèces, carte). */
  enregistrer: async (payload: PaymentCreate) => {
    const res = await apiClient.post<Payment>("/payments", payload);
    return res.data;
  },

  /** Alias pour rétrocompat avec l'ancienne interface. */
  paiementDirect: async (payload: PaymentCreate) => {
    return paiementsApi.enregistrer(payload);
  },

  /** Demander un remboursement. */
  demanderRemboursement: async (payload: RefundCreate) => {
    const res = await apiClient.post<Refund>("/refunds", payload);
    return res.data;
  },

  /** Lister les remboursements. */
  listRemboursements: async (params?: { skip?: number; limit?: number; status?: string }) => {
    const res = await apiClient.get<{ items: Refund[]; total: number }>("/refunds", { params });
    return res.data;
  },
};
