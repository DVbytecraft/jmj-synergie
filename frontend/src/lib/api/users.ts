import { apiClient } from "./client";
import type { IssuerProfile } from "@/types";

export type IssuerProfileUpdate = Omit<IssuerProfile, "account_email" | "account_name">;

export const usersApi = {
  getMyIssuerProfile: () =>
    apiClient.get<IssuerProfile>("/users/me/profile").then((r) => r.data),

  saveMyIssuerProfile: (payload: IssuerProfileUpdate) =>
    apiClient.put<IssuerProfile>("/users/me/profile", payload).then((r) => r.data),

  uploadIssuerAsset: (assetType: "logo" | "stamp" | "signature", file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient
      .post<IssuerProfile>(`/users/me/profile/assets/${assetType}`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
};
