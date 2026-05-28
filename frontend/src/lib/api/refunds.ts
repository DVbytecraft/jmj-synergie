import { apiClient } from "./client";

export interface RefundItem {
  id: string;
  refund_number: string;
  order_id: string | null;
  client_id: string;
  status: string;
  reason: string;
  reason_detail: string;
  requested_amount_cents: number;
  approved_amount_cents: number | null;
  currency: string;
  rejection_reason: string | null;
  notes: string | null;
  requested_at: string;
  approved_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface RequestRefundPayload {
  order_id: string;
  original_transaction_id: string;
  amount_cents: number;
  reason: string;
  reason_detail: string;
  notes?: string;
}

export interface ApproveRefundPayload {
  approved_amount_cents?: number;
  method: string;
}

export interface RejectRefundPayload {
  rejection_reason: string;
}

export const refundsApi = {
  request: async (payload: RequestRefundPayload): Promise<RefundItem> => {
    const res = await apiClient.post<RefundItem>("/refunds", payload);
    return res.data;
  },

  list: async (params?: { skip?: number; limit?: number; status?: string }): Promise<{ items: RefundItem[]; total: number }> => {
    const res = await apiClient.get<{ items: RefundItem[]; total: number }>("/refunds", { params });
    return res.data;
  },

  approve: async (id: string, payload: ApproveRefundPayload): Promise<RefundItem> => {
    const res = await apiClient.post<RefundItem>(`/refunds/${id}/approve`, payload);
    return res.data;
  },

  reject: async (id: string, payload: RejectRefundPayload): Promise<RefundItem> => {
    const res = await apiClient.post<RefundItem>(`/refunds/${id}/reject`, payload);
    return res.data;
  },
};
