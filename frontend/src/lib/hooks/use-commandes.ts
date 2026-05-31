import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { commandesApi } from "@/lib/api/commandes";
import type { OrderCreate, OrderUpdate } from "@/types";

export const COMMANDES_KEY = "commandes";

export function useCommandes(params?: {
  skip?: number;
  limit?: number;
  status?: string;
  client_id?: string;
}) {
  return useQuery({
    queryKey: [COMMANDES_KEY, params],
    queryFn: () => commandesApi.list(params),
  });
}

export function useCommande(id: string) {
  return useQuery({
    queryKey: [COMMANDES_KEY, id],
    queryFn: () => commandesApi.get(id),
    enabled: !!id,
  });
}

export function useDashboardKPI() {
  return useQuery({
    queryKey: ["dashboard", "kpi"],
    staleTime: 60_000,
    queryFn: async () => {
      const { apiClient } = await import("@/lib/api/client");
      return apiClient.get("/orders/kpi").then((r) => r.data);
    },
  });
}

export function useCreateCommande() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: OrderCreate) => commandesApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [COMMANDES_KEY] });
      qc.invalidateQueries({ queryKey: ["dashboard", "kpi"] });
    },
  });
}

export function useUpdateCommande(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: OrderUpdate) => commandesApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [COMMANDES_KEY] });
      qc.invalidateQueries({ queryKey: [COMMANDES_KEY, id] });
      qc.invalidateQueries({ queryKey: ["dashboard", "kpi"] });
    },
  });
}

export function useConfirmerCommande() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => commandesApi.confirmer(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: [COMMANDES_KEY] });
      qc.invalidateQueries({ queryKey: [COMMANDES_KEY, id] });
      qc.invalidateQueries({ queryKey: ["dashboard", "kpi"] });
    },
  });
}

export function useAnnulerCommande() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => commandesApi.annuler(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: [COMMANDES_KEY] });
      qc.invalidateQueries({ queryKey: [COMMANDES_KEY, id] });
      qc.invalidateQueries({ queryKey: ["dashboard", "kpi"] });
    },
  });
}

export function useDeleteCommande() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => commandesApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [COMMANDES_KEY] });
      qc.invalidateQueries({ queryKey: ["dashboard", "kpi"] });
    },
  });
}
