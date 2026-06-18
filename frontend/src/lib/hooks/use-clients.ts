import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { clientsApi } from "@/lib/api/clients";
import type { ClientCreate, ClientUpdate } from "@/types";

export const CLIENTS_KEY = "clients";

export function useClients(params?: {
  skip?: number;
  limit?: number;
  search?: string;
  status?: string;
  client_type?: string;
}) {
  return useQuery({
    queryKey: [CLIENTS_KEY, params],
    queryFn: () => clientsApi.list(params),
  });
}

export function useClient(id: string) {
  return useQuery({
    queryKey: [CLIENTS_KEY, id],
    queryFn: () => clientsApi.get(id),
    enabled: !!id,
  });
}

export function useCreateClient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ClientCreate) => clientsApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: [CLIENTS_KEY] }),
  });
}

export function useUpdateClient(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ClientUpdate) => clientsApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [CLIENTS_KEY] });
      qc.invalidateQueries({ queryKey: [CLIENTS_KEY, id] });
    },
  });
}

export function useDeleteClient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => clientsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [CLIENTS_KEY] }),
  });
}
