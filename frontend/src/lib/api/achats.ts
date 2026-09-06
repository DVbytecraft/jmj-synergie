import { apiClient } from "./client";

export interface Supplier {
  id: string;
  code: string;
  name: string;
  contact_name: string | null;
  email: string | null;
  phone: string;
  address_line1: string | null;
  tax_id: string | null;
  currency: string;
  notes: string | null;
}

export interface PurchaseItem {
  id: string;
  product_id: string | null;
  description: string;
  quantity: number;
  received_quantity: number;
  unit: string | null;
  purchase_unit_price_cents: number;
  line_total_cents: number;
}

export interface PurchaseOrder {
  id: string;
  purchase_number: string;
  supplier_id: string;
  supplier_name: string;
  sales_order_id: string | null;
  status: "draft" | "ordered" | "partially_received" | "received";
  currency: string;
  tax_rate: number;
  subtotal_cents: number;
  tax_cents: number;
  total_cents: number;
  expected_date: string | null;
  notes: string | null;
  items: PurchaseItem[];
  created_at: string;
}

export interface PurchaseInput {
  supplier_id: string;
  sales_order_id?: string;
  currency: string;
  apply_tax: boolean;
  tax_rate: number;
  expected_date?: string;
  notes?: string;
  items: Array<{
    product_id?: string;
    description: string;
    quantity: number;
    unit?: string;
    purchase_unit_price_cents: number;
  }>;
}

export const achatsApi = {
  suppliers: () => apiClient.get<{ items: Supplier[]; total: number }>("/purchases/suppliers").then((r) => r.data),
  createSupplier: (data: Omit<Supplier, "id" | "code" | "contact_name" | "address_line1" | "tax_id" | "notes"> & Partial<Supplier>) =>
    apiClient.post<Supplier>("/purchases/suppliers", data).then((r) => r.data),
  list: () => apiClient.get<{ items: PurchaseOrder[]; total: number }>("/purchases").then((r) => r.data),
  create: (data: PurchaseInput) => apiClient.post<PurchaseOrder>("/purchases", data).then((r) => r.data),
  update: (id: string, data: PurchaseInput) => apiClient.put<PurchaseOrder>(`/purchases/${id}`, data).then((r) => r.data),
  confirm: (id: string) => apiClient.post<PurchaseOrder>(`/purchases/${id}/confirm`).then((r) => r.data),
  receiveAll: (purchase: PurchaseOrder) => apiClient.post<PurchaseOrder>(`/purchases/${purchase.id}/receive`,
    purchase.items.filter((item) => item.quantity > item.received_quantity).map((item) => ({
      item_id: item.id,
      quantity: item.quantity - item.received_quantity,
    }))
  ).then((r) => r.data),
};
