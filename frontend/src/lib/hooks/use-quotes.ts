import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { quotesApi } from "@/lib/api/quotes";
import type { QuoteCreate, QuoteUpdate } from "@/types";

export const QUOTES_KEY = "quotes";

export function useQuotes(params?: {
  skip?: number;
  limit?: number;
  status?: string;
  client_id?: string;
  search?: string;
}) {
  return useQuery({
    queryKey: [QUOTES_KEY, params],
    queryFn: () => quotesApi.list(params),
  });
}

export function useQuote(id: string) {
  return useQuery({
    queryKey: [QUOTES_KEY, id],
    queryFn: () => quotesApi.get(id),
    enabled: !!id,
  });
}

export function useCreateQuote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: QuoteCreate) => quotesApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [QUOTES_KEY] });
    },
  });
}

export function useUpdateQuote(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: QuoteUpdate) => quotesApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [QUOTES_KEY] });
      qc.invalidateQueries({ queryKey: [QUOTES_KEY, id] });
    },
  });
}

export function useSendQuote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => quotesApi.send(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: [QUOTES_KEY] });
      qc.invalidateQueries({ queryKey: [QUOTES_KEY, id] });
    },
  });
}

export function useAcceptQuote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => quotesApi.accept(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: [QUOTES_KEY] });
      qc.invalidateQueries({ queryKey: [QUOTES_KEY, id] });
    },
  });
}

export function useRejectQuote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => quotesApi.reject(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: [QUOTES_KEY] });
      qc.invalidateQueries({ queryKey: [QUOTES_KEY, id] });
    },
  });
}

export function useConvertQuote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => quotesApi.convert(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: [QUOTES_KEY] });
      qc.invalidateQueries({ queryKey: [QUOTES_KEY, id] });
      qc.invalidateQueries({ queryKey: ["commandes"] });
    },
  });
}

export function useDeleteQuote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => quotesApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [QUOTES_KEY] });
    },
  });
}
