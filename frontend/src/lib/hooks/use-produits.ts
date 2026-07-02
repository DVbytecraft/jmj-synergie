import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { produitsApi } from "@/lib/api/produits";
import type { ProductCreate, ProductUpdate } from "@/types";

export const PRODUITS_KEY = "produits";

export function useProduits(params?: { skip?: number; limit?: number; status?: string; category?: string; search?: string }) {
  return useQuery({
    queryKey: [PRODUITS_KEY, params],
    queryFn: () => produitsApi.list(params),
  });
}

export function useProduit(id: string) {
  return useQuery({
    queryKey: [PRODUITS_KEY, id],
    queryFn: () => produitsApi.get(id),
    enabled: !!id,
  });
}

export function useCreateProduit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ProductCreate) => produitsApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: [PRODUITS_KEY] }),
  });
}

export function useUpdateProduit(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ProductUpdate) => produitsApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [PRODUITS_KEY] });
      qc.invalidateQueries({ queryKey: [PRODUITS_KEY, id] });
    },
  });
}

export function useDeleteProduit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => produitsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [PRODUITS_KEY] }),
  });
}
