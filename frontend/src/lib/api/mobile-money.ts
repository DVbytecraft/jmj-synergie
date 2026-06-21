import { apiClient } from "./client";

export type MobileMoneyProvider = "orange_money" | "mtn_momo" | "moov_money";

export interface InitiatePaymentRequest {
  order_id: string;
  amount_cents: number;
  phone_number: string;
  provider: MobileMoneyProvider;
  currency?: string;
}

export interface InitiatePaymentResponse {
  transaction_id: string;
  payment_url: string;
  status: string;
}

export interface TransactionStatusResponse {
  transaction_id: string;
  status: string;
  amount_cents: number;
  currency: string;
  provider: string;
  created_at: string;
}

export const mobileMoneyApi = {
  initiate: async (payload: InitiatePaymentRequest): Promise<InitiatePaymentResponse> => {
    const res = await apiClient.post<InitiatePaymentResponse>("/mobile-money/initiate", payload);
    return res.data;
  },

  status: async (transactionId: string): Promise<TransactionStatusResponse> => {
    const res = await apiClient.get<TransactionStatusResponse>(`/mobile-money/status/${transactionId}`);
    return res.data;
  },
};

export const PROVIDER_LABELS: Record<MobileMoneyProvider, string> = {
  orange_money: "Orange Money",
  mtn_momo:     "MTN MoMo",
  moov_money:   "Moov Money",
};
