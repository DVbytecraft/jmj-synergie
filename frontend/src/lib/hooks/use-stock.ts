import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { stockApi } from "@/lib/api/stock";
import type { StockAdjustPayload, StockConfigPayload } from "@/lib/api/stock";

export const STOCK_KEY = "stock";

export function useStockList(params?: { alerts_only?: boolean; skip?: number; limit?: number }) {
  return useQuery({
    queryKey: [STOCK_KEY, "list", params],
    queryFn: () => stockApi.list(params),
  });
}

export function useStockItem(productId: string) {
  return useQuery({
    queryKey: [STOCK_KEY, productId],
    queryFn: () => stockApi.get(productId),
    enabled: !!productId,
  });
}

export function useAdjustStock(productId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: StockAdjustPayload) => stockApi.adjust(productId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [STOCK_KEY] });
    },
  });
}

export function useConfigStock(productId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: StockConfigPayload) => stockApi.config(productId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [STOCK_KEY] });
    },
  });
}
