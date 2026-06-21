import { apiClient } from "./client";

export interface StockItem {
  id: string;
  code: string;
  name: string;
  category: string | null;
  unit: string | null;
  unit_price_cents: number;
  currency: string;
  track_stock: boolean;
  stock_quantity: number | null;
  low_stock_threshold: number | null;
  is_low_stock: boolean;
  status: string;
}

export interface StockList {
  items: StockItem[];
  total: number;
  alerts_count: number;
}

export type AdjustReason = "restock" | "loss" | "correction" | "sale" | "return";

export interface StockAdjustPayload {
  delta: number;
  reason: AdjustReason;
  note?: string;
}

export interface StockConfigPayload {
  track_stock: boolean;
  low_stock_threshold?: number | null;
  stock_quantity?: number | null;
}

export const stockApi = {
  list: (params?: { alerts_only?: boolean; skip?: number; limit?: number }) =>
    apiClient
      .get<StockList>("/stock", { params })
      .then((r) => r.data),

  get: (productId: string) =>
    apiClient
      .get<StockItem>(`/stock/${productId}`)
      .then((r) => r.data),

  adjust: (productId: string, payload: StockAdjustPayload) =>
    apiClient
      .post<StockItem>(`/stock/${productId}/adjust`, payload)
      .then((r) => r.data),

  config: (productId: string, payload: StockConfigPayload) =>
    apiClient
      .put<StockItem>(`/stock/${productId}/config`, payload)
      .then((r) => r.data),
};
