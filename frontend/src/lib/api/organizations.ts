import { apiClient } from "./client";
import type { Organization } from "@/types";

export type OrganizationUpdate = Omit<Organization, "id" | "code" | "is_active" | "logo_url">;

export const organizationsApi = {
  getMine: () =>
    apiClient.get<Organization>("/organizations/me").then((r) => r.data),

  saveMine: (payload: OrganizationUpdate) =>
    apiClient.put<Organization>("/organizations/me", payload).then((r) => r.data),

  uploadLogo: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient
      .post<Organization>("/organizations/me/logo", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
};
