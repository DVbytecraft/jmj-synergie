import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { paiementsApi } from "@/lib/api/paiements";
import type { PaymentCreate, RefundCreate } from "@/types";

export const PAIEMENTS_KEY = "paiements";

export function usePaiements(params?: { skip?: number; limit?: number; order_id?: string }) {
  return useQuery({
    queryKey: [PAIEMENTS_KEY, params],
    queryFn: () => paiementsApi.list(params),
  });
}

export function useEnregistrerPaiement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: PaymentCreate) => paiementsApi.enregistrer(data),
    onSuccess: (_, { order_id }) => {
      qc.invalidateQueries({ queryKey: [PAIEMENTS_KEY] });
      qc.invalidateQueries({ queryKey: ["commandes", order_id] });
    },
  });
}

export function useDemanderRemboursement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: RefundCreate) => paiementsApi.demanderRemboursement(data),
    onSuccess: (_, { order_id }) => {
      qc.invalidateQueries({ queryKey: [PAIEMENTS_KEY] });
      qc.invalidateQueries({ queryKey: ["commandes", order_id] });
    },
  });
}
