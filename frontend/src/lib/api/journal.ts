/**
 * Journal — encapsule les listes de paiements et remboursements.
 * Le backend n'a pas d'endpoint /journal dédié ; on passe par /payments et /refunds.
 */
import { apiClient } from "./client";
import type { Payment, Refund } from "@/types";

export const journalApi = {
  paiements: (params?: { skip?: number; limit?: number; order_id?: string }) =>
    apiClient
      .get<Payment[]>("/payments", { params })
      .then((r) => r.data),

  remboursements: (params?: { skip?: number; limit?: number; status?: string }) =>
    apiClient
      .get<{ items: Refund[]; total: number }>("/refunds", { params })
      .then((r) => r.data),
};
