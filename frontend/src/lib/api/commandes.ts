import { apiClient } from "./client";
import type { Order, OrderCreate, OrderUpdate, OrderListResponse, OrderItem } from "@/types";

export type { Order, OrderItem };
export type { OrderStatus as StatutCommande } from "@/types";
export type Commande = Order;

export const commandesApi = {
  list: async (params?: { skip?: number; limit?: number; status?: string; client_id?: string; search?: string }) => {
    const res = await apiClient.get<OrderListResponse>("/orders", { params });
    return res.data;
  },

  get: async (id: string) => {
    const res = await apiClient.get<Order>(`/orders/${id}`);
    return res.data;
  },

  create: async (payload: OrderCreate) => {
    const res = await apiClient.post<Order>("/orders", payload);
    return res.data;
  },

  update: async (id: string, payload: OrderUpdate) => {
    const res = await apiClient.patch<Order>(`/orders/${id}`, payload);
    return res.data;
  },

  confirmer: async (id: string) => {
    const res = await apiClient.post<Order>(`/orders/${id}/confirm`);
    return res.data;
  },

  annuler: async (id: string) => {
    const res = await apiClient.post<Order>(`/orders/${id}/cancel`);
    return res.data;
  },

  delete: async (id: string) => {
    await apiClient.delete(`/orders/${id}`);
  },

  byClient: async (clientId: string, params?: { skip?: number; limit?: number }) => {
    const res = await apiClient.get<OrderListResponse>("/orders", {
      params: { client_id: clientId, ...params },
    });
    return res.data.items;
  },

  addItem: async (id: string, item: { description: string; quantity: number; unit_price_cents: number; unit?: string }) => {
    const res = await apiClient.post<Order>(`/orders/${id}/items`, item);
    return res.data;
  },

  removeItem: async (id: string, itemId: string) => {
    await apiClient.delete(`/orders/${id}/items/${itemId}`);
  },

  enregistrerLivraison: async (
    id: string,
    items: Array<{ item_id: string; quantity: number }>
  ) => {
    const res = await apiClient.post<Order>(`/orders/${id}/deliveries`, items);
    return res.data;
  },
};
