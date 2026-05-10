import { apiClient } from "./client";
import type { Organization } from "@/types";

export type OrganizationUpdate = Omit<Organization, "id" | "code" | "is_active">;

export const organizationsApi = {
  getMine: () => apiClient.get<Organization>("/organizations/me").then((r) => r.data),
  saveMine: (payload: OrganizationUpdate) =>
    apiClient.put<Organization>("/organizations/me", payload).then((r) => r.data),
};
