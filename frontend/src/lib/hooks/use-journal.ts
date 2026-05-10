import { useQuery } from "@tanstack/react-query";
import { journalApi } from "@/lib/api/journal";

export const JOURNAL_KEY = "journal";

export function useJournalPaiements(params?: {
  skip?: number;
  limit?: number;
  order_id?: string;
}) {
  return useQuery({
    queryKey: [JOURNAL_KEY, "paiements", params],
    queryFn: () => journalApi.paiements(params),
  });
}

export function useJournalRemboursements(params?: {
  skip?: number;
  limit?: number;
  status?: string;
}) {
  return useQuery({
    queryKey: [JOURNAL_KEY, "remboursements", params],
    queryFn: () => journalApi.remboursements(params),
  });
}
