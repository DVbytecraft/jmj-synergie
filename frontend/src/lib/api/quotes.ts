import { apiClient } from "./client";
import type { Quote, QuoteCreate, QuoteUpdate, QuoteListResponse } from "@/types";

export const quotesApi = {
  list: async (params?: {
    skip?: number;
    limit?: number;
    status?: string;
    client_id?: string;
    search?: string;
  }) => {
    const res = await apiClient.get<QuoteListResponse>("/quotes", { params });
    return res.data;
  },

  get: async (id: string) => {
    const res = await apiClient.get<Quote>(`/quotes/${id}`);
    return res.data;
  },

  create: async (payload: QuoteCreate) => {
    const res = await apiClient.post<Quote>("/quotes", payload);
    return res.data;
  },

  update: async (id: string, payload: QuoteUpdate) => {
    const res = await apiClient.put<Quote>(`/quotes/${id}`, payload);
    return res.data;
  },

  send: async (id: string) => {
    const res = await apiClient.post<Quote>(`/quotes/${id}/send`);
    return res.data;
  },

  accept: async (id: string) => {
    const res = await apiClient.post<Quote>(`/quotes/${id}/accept`);
    return res.data;
  },

  reject: async (id: string) => {
    const res = await apiClient.post<Quote>(`/quotes/${id}/reject`);
    return res.data;
  },

  convert: async (id: string) => {
    const res = await apiClient.post<Quote>(`/quotes/${id}/convert`);
    return res.data;
  },

  delete: async (id: string) => {
    await apiClient.delete(`/quotes/${id}`);
  },
};
