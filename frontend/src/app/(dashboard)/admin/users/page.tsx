"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { useAuthStore } from "@/store/auth.store";
import {
  UserCog, Plus, Trash2, Loader2, Shield, CheckCircle, XCircle,
} from "lucide-react";

interface UserItem {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface CreateUserForm {
  email: string;
  full_name: string;
  password: string;
  role: string;
}

const ROLES = ["operator", "manager", "admin", "super_admin"] as const;

const roleColors: Record<string, string> = {
  super_admin: "bg-purple-100 text-purple-700",
  admin:       "bg-red-100 text-red-700",
  manager:     "bg-blue-100 text-blue-700",
  operator:    "bg-gray-100 text-gray-600",
};

export default function AdminUsersPage() {
  const { user: currentUser } = useAuthStore();
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CreateUserForm>({
    email: "", full_name: "", password: "", role: "operator",
  });
  const [formError, setFormError] = useState<string | null>(null);

  const { data: users, isLoading } = useQuery<UserItem[]>({
    queryKey: ["users"],
    queryFn: () => apiClient.get<UserItem[]>("/users/").then((r) => r.data),
  });

  const createMut = useMutation({
    mutationFn: (payload: CreateUserForm) =>
      apiClient.post<UserItem>("/users/", payload).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setShowForm(false);
      setForm({ email: "", full_name: "", password: "", role: "operator" });
      setFormError(null);
    },
    onError: (e: any) => setFormError(e.response?.data?.detail || "Erreur lors de la création"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/users/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!form.email || !form.full_name || !form.password) {
      setFormError("Tous les champs sont obligatoires");
      return;
    }
    createMut.mutate(form);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <UserCog className="w-6 h-6 text-blue-600" />
            Gestion des utilisateurs
          </h1>
          <p className="text-sm text-gray-500 mt-1">Créer et gérer les comptes d&apos;accès</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary">
          <Plus className="w-4 h-4" />
          Nouvel utilisateur
        </button>
      </div>

      {/* Formulaire création */}
      {showForm && (
        <div className="card p-6">
          <h2 className="font-semibold text-gray-900 mb-4">Créer un compte</h2>
          <form onSubmit={handleCreate} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nom complet</label>
              <input
                type="text"
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                placeholder="Jean Dupont"
                className="input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="jean@exemple.com"
                className="input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Mot de passe</label>
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="8 caractères minimum"
                className="input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Rôle</label>
              <select
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
                className="input"
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>{r.replace("_", " ")}</option>
                ))}
              </select>
            </div>

            {formError && (
              <div className="sm:col-span-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-2">
                {formError}
              </div>
            )}

            <div className="sm:col-span-2 flex gap-3">
              <button type="submit" disabled={createMut.isPending} className="btn-primary">
                {createMut.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                Créer le compte
              </button>
              <button
                type="button"
                onClick={() => { setShowForm(false); setFormError(null); }}
                className="btn-secondary"
              >
                Annuler
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Liste */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Utilisateurs ({users?.length ?? 0})</h2>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="table-header">Nom</th>
                <th className="table-header">Email</th>
                <th className="table-header">Rôle</th>
                <th className="table-header text-center">Actif</th>
                <th className="table-header">Créé le</th>
                <th className="table-header text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {!users?.length ? (
                <tr>
                  <td colSpan={6} className="table-cell text-center text-gray-400 py-8">
                    Aucun utilisateur
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr key={u.id} className="hover:bg-gray-50 transition-colors">
                    <td className="table-cell font-medium text-gray-900">{u.full_name}</td>
                    <td className="table-cell text-gray-500">{u.email}</td>
                    <td className="table-cell">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium capitalize ${roleColors[u.role] ?? "bg-gray-100 text-gray-600"}`}>
                        <Shield className="w-3 h-3" />
                        {u.role.replace("_", " ")}
                      </span>
                    </td>
                    <td className="table-cell text-center">
                      {u.is_active
                        ? <CheckCircle className="w-4 h-4 text-green-500 mx-auto" />
                        : <XCircle className="w-4 h-4 text-red-400 mx-auto" />}
                    </td>
                    <td className="table-cell text-gray-400">
                      {new Date(u.created_at).toLocaleDateString("fr-FR")}
                    </td>
                    <td className="table-cell text-center">
                      {u.id !== currentUser?.id && (
                        <button
                          onClick={() => {
                            if (confirm(`Supprimer ${u.full_name} ?`)) deleteMut.mutate(u.id);
                          }}
                          disabled={deleteMut.isPending}
                          className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors"
                          title="Supprimer"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
