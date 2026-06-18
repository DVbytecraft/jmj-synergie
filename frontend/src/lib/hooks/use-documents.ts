import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { documentsApi } from "@/lib/api/documents";

export const DOCUMENTS_KEY = "documents";

export function useDocumentsOrder(order_id: string) {
  return useQuery({
    queryKey: [DOCUMENTS_KEY, "order", order_id],
    queryFn: () => documentsApi.listByOrder(order_id),
    enabled: !!order_id,
  });
}

export function useGenererProForma() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (order_id: string) => documentsApi.genererProForma(order_id),
    onSuccess: (_, order_id) => {
      qc.invalidateQueries({ queryKey: [DOCUMENTS_KEY, "order", order_id] });
    },
  });
}

export function useGenererFacture() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (order_id: string) => documentsApi.genererFacture(order_id),
    onSuccess: (_, order_id) => {
      qc.invalidateQueries({ queryKey: [DOCUMENTS_KEY, "order", order_id] });
    },
  });
}

export function useGenererBonLivraison() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      order_id,
      delivery_note_number,
    }: {
      order_id: string;
      delivery_note_number?: string;
    }) => documentsApi.genererBonLivraison(order_id, delivery_note_number).then((r) => ({ ...r, order_id })),
    onSuccess: ({ order_id }) => {
      qc.invalidateQueries({ queryKey: [DOCUMENTS_KEY, "order", order_id] });
    },
  });
}

export function useSignerDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      document_id,
      order_id,
      include_stamp = true,
    }: {
      document_id: string;
      order_id: string;
      include_stamp?: boolean;
    }) => documentsApi.signer(document_id, include_stamp).then((r) => ({ ...r, order_id })),
    onSuccess: ({ order_id }) => {
      qc.invalidateQueries({ queryKey: [DOCUMENTS_KEY, "order", order_id] });
    },
  });
}
