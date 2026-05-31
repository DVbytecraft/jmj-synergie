import { apiClient } from "./client";
import type { Client, ClientCreate, ClientUpdate, ClientListResponse } from "@/types";

export type { Client };

export const clientsApi = {
  list: async (params?: { skip?: number; limit?: number; search?: string; status?: string; client_type?: string }) => {
    const res = await apiClient.get<ClientListResponse>("/clients", { params });
    return res.data;
  },

  get: async (id: string) => {
    const res = await apiClient.get<Client>(`/clients/${id}`);
    return res.data;
  },

  create: async (payload: ClientCreate) => {
    const res = await apiClient.post<Client>("/clients", payload);
    return res.data;
  },

  update: async (id: string, payload: ClientUpdate) => {
    const res = await apiClient.patch<Client>(`/clients/${id}`, payload);
    return res.data;
  },

  delete: async (id: string) => {
    await apiClient.delete(`/clients/${id}`);
  },
};
