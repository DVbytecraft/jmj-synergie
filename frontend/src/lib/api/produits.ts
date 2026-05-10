import { apiClient } from "./client";
import type { Product, ProductCreate, ProductUpdate, PaginatedResponse } from "@/types";

export type { Product };
export type Produit = Product;
export type ProduitCreate = ProductCreate;
export type ProduitUpdate = ProductUpdate;

export const produitsApi = {
  list: (params?: { skip?: number; limit?: number; status?: string; category?: string }) =>
    apiClient
      .get<PaginatedResponse<Product>>("/products", { params })
      .then((r) => r.data),

  get: (id: string) =>
    apiClient.get<Product>(`/products/${id}`).then((r) => r.data),

  create: (data: ProductCreate) =>
    apiClient.post<Product>("/products", data).then((r) => r.data),

  update: (id: string, data: ProductUpdate) =>
    apiClient.patch<Product>(`/products/${id}`, data).then((r) => r.data),

  delete: (id: string) =>
    apiClient.delete(`/products/${id}`),

  activer: (id: string) =>
    apiClient.post<Product>(`/products/${id}/activate`).then((r) => r.data),

  desactiver: (id: string) =>
    apiClient.post<Product>(`/products/${id}/deactivate`).then((r) => r.data),
};
