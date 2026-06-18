"use client";
import { formatDateFr, formatDateTimeFr } from "@/lib/utils/format-dates";

import { useState, Fragment } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { useAuthStore } from "@/store/auth.store";
import {
  Users, Building2, Activity, TrendingUp, Plus, Trash2,
  Loader2, Shield, CheckCircle, XCircle, ChevronDown, ChevronUp,
  Eye, EyeOff, AlertTriangle, X, Globe, Phone, Mail,
  UserCheck, UserX, Sparkles,
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface Stats {
  total_users: number;
  total_organizations: number;
  users_online_today: number;
  orgs_online_today: number;
  new_users_this_week: number;
  new_orgs_this_month: number;
}

interface OrgItem {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  city: string | null;
  country: string | null;
  tax_id: string | null;
  rccm: string | null;
  is_active: boolean;
  created_at: string;
  user_count: number;
  active_user_count: number;
}

interface UserItem {
  id: string;
  email: string;
  full_name: string;
  role: string;
  status: string;
  is_deleted: boolean;
  organization_id: string | null;
  organization_name: string | null;
  last_login_at: string | null;
  created_at: string;
}

interface CreateOrgForm {
  org_name: string;
  org_email: string;
  org_phone: string;
  org_country: string;
  org_city: string;
  admin_full_name: string;
  admin_email: string;
  admin_password: string;
}

interface CreateOrgPayload {
  org_name: string;
  org_email?: string;
  org_phone?: string;
  org_country?: string;
  org_city?: string;
  admin_full_name: string;
  admin_email: string;
  admin_password: string;
}

// ─── Constantes UI ───────────────────────────────────────────────────────────

const ROLE_COLORS: Record<string, string> = {
  super_admin: "bg-purple-100 text-purple-700 border-purple-200",
  admin:       "bg-red-100    text-red-700    border-red-200",
  manager:     "bg-blue-100   text-blue-700   border-blue-200",
  operator:    "bg-slate-100  text-slate-600  border-slate-200",
};

const ROLE_LABELS: Record<string, string> = {
  super_admin: "Super Admin",
  admin:       "Admin",
  manager:     "Manager",
  operator:    "Opérateur",
};

function fmt(iso: string | null) {
  if (!iso) return "—";
  return formatDateFr(iso);
}

function fmtTime(iso: string | null) {
  if (!iso) return "Jamais";
  const d = new Date(iso);
  const now = new Date();
  const diff = (now.getTime() - d.getTime()) / 1000;
  if (diff < 60) return "À l'instant";
  if (diff < 3600) return `Il y a ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `Il y a ${Math.floor(diff / 3600)} h`;
  return fmt(iso);
}

// ─── Composants ──────────────────────────────────────────────────────────────

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color,
}: {
  icon: React.ElementType;
  label: string;
  value: number;
  sub?: string;
  color: string;
}) {
  return (
    <div className="card p-5 flex items-center gap-4">
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${color}`}>
        <Icon className="w-6 h-6" />
      </div>
      <div className="min-w-0">
        <p className="text-2xl font-bold text-slate-900 leading-none">{value}</p>
        <p className="text-sm font-medium text-slate-600 mt-0.5">{label}</p>
        {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function ConfirmDialog({
  message,
  onConfirm,
  onCancel,
  loading,
}: {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl p-6 max-w-sm w-full mx-4 animate-fade-in">
        <div className="flex items-start gap-3 mb-5">
          <div className="p-2 bg-red-100 rounded-xl flex-shrink-0">
            <AlertTriangle className="w-5 h-5 text-red-600" />
          </div>
          <p className="text-slate-800 text-sm leading-relaxed">{message}</p>
        </div>
        <div className="flex gap-3 justify-end">
          <button onClick={onCancel} className="btn-secondary btn-sm">Annuler</button>
          <button onClick={onConfirm} disabled={loading} className="btn-danger btn-sm">
            {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            Supprimer
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Page principale ─────────────────────────────────────────────────────────

export default function AdminPanel() {
  const { user: currentUser } = useAuthStore();
  const qc = useQueryClient();

  const [activeTab, setActiveTab] = useState<"orgs" | "users">("orgs");
  const [showCreateOrg, setShowCreateOrg] = useState(false);
  const [expandedOrg, setExpandedOrg] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<{ type: "org" | "user"; id: string; name: string } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [orgForm, setOrgForm] = useState<CreateOrgForm>({
    org_name: "", org_email: "", org_phone: "", org_country: "", org_city: "",
    admin_full_name: "", admin_email: "", admin_password: "",
  });

  // ── Queries ────────────────────────────────────────────────────────────────

  const { data: stats, isLoading: statsLoading } = useQuery<Stats>({
    queryKey: ["admin-stats"],
    queryFn: () => apiClient.get<Stats>("/admin/stats").then(r => r.data),
    refetchInterval: 30_000,
  });

  const { data: orgs, isLoading: orgsLoading } = useQuery<OrgItem[]>({
    queryKey: ["admin-orgs"],
    queryFn: () => apiClient.get<OrgItem[]>("/admin/organizations").then(r => r.data),
    enabled: activeTab === "orgs",
  });

  const { data: allUsers, isLoading: usersLoading } = useQuery<UserItem[]>({
    queryKey: ["admin-users"],
    queryFn: () => apiClient.get<UserItem[]>("/admin/users").then(r => r.data),
    enabled: activeTab === "users",
  });

  // ── Mutations ──────────────────────────────────────────────────────────────

  const createOrgMut = useMutation({
    mutationFn: (payload: CreateOrgPayload) =>
      apiClient.post<OrgItem>("/admin/organizations", payload).then(r => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-orgs"] });
      qc.invalidateQueries({ queryKey: ["admin-stats"] });
      setShowCreateOrg(false);
      setOrgForm({ org_name: "", org_email: "", org_phone: "", org_country: "", org_city: "", admin_full_name: "", admin_email: "", admin_password: "" });
      setFormError(null);
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      setFormError(err.response?.data?.detail || "Erreur lors de la création");
    },
  });

  const deleteOrgMut = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/admin/organizations/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-orgs"] });
      qc.invalidateQueries({ queryKey: ["admin-stats"] });
      setConfirmDelete(null);
    },
  });

  const deleteUserMut = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/admin/users/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      qc.invalidateQueries({ queryKey: ["admin-stats"] });
      setConfirmDelete(null);
    },
  });

  const toggleStatusMut = useMutation({
    mutationFn: ({ id, suspend }: { id: string; suspend: boolean }) =>
      apiClient.put(`/admin/users/${id}/status`, { suspend }).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  // ── Handlers ───────────────────────────────────────────────────────────────

  const handleCreateOrg = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!orgForm.org_name || !orgForm.admin_full_name || !orgForm.admin_email || !orgForm.admin_password) {
      setFormError("Les champs marqués * sont obligatoires");
      return;
    }
    createOrgMut.mutate({
      org_name:       orgForm.org_name,
      admin_full_name: orgForm.admin_full_name,
      admin_email:    orgForm.admin_email,
      admin_password: orgForm.admin_password,
      org_email:      orgForm.org_email   || undefined,
      org_phone:      orgForm.org_phone   || undefined,
      org_country:    orgForm.org_country || undefined,
      org_city:       orgForm.org_city    || undefined,
    });
  };

  const isSuperAdmin = currentUser?.role === "super_admin";

  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">

      {/* En-tête */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Panneau d&apos;administration</h1>
          <p className="text-sm text-slate-500 mt-1">Vue globale et contrôle de toutes les organisations</p>
        </div>
        {isSuperAdmin && (
          <button onClick={() => setShowCreateOrg(true)} className="btn-primary">
            <Plus className="w-4 h-4" />
            Nouvelle entreprise
          </button>
        )}
      </div>

      {/* KPI cards */}
      {statsLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card p-5 h-24 skeleton" />
          ))}
        </div>
      ) : stats ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            icon={Users}
            label="Utilisateurs total"
            value={stats.total_users}
            sub={`+${stats.new_users_this_week} cette semaine`}
            color="bg-blue-100 text-blue-600"
          />
          <StatCard
            icon={Building2}
            label="Entreprises"
            value={stats.total_organizations}
            sub={`+${stats.new_orgs_this_month} ce mois`}
            color="bg-violet-100 text-violet-600"
          />
          <StatCard
            icon={Activity}
            label="Connectés aujourd'hui"
            value={stats.users_online_today}
            sub="Sessions < 24 h"
            color="bg-emerald-100 text-emerald-600"
          />
          <StatCard
            icon={TrendingUp}
            label="Entreprises actives"
            value={stats.orgs_online_today}
            sub="Avec activité < 24 h"
            color="bg-amber-100 text-amber-600"
          />
        </div>
      ) : null}

      {/* Formulaire nouvelle entreprise */}
      {showCreateOrg && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="font-semibold text-slate-900 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-blue-600" />
              Créer une entreprise
            </h2>
            <button onClick={() => { setShowCreateOrg(false); setFormError(null); }} className="btn-icon">
              <X className="w-4 h-4" />
            </button>
          </div>

          <form onSubmit={handleCreateOrg} className="space-y-5">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Entreprise</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div>
                  <label className="label">Nom de l&apos;entreprise *</label>
                  <input value={orgForm.org_name} onChange={e => setOrgForm({ ...orgForm, org_name: e.target.value })} className="input" placeholder="Biloz" />
                </div>
                <div>
                  <label className="label">Email entreprise</label>
                  <input type="email" value={orgForm.org_email} onChange={e => setOrgForm({ ...orgForm, org_email: e.target.value })} className="input" placeholder="contact@entreprise.com" />
                </div>
                <div>
                  <label className="label">Téléphone</label>
                  <input value={orgForm.org_phone} onChange={e => setOrgForm({ ...orgForm, org_phone: e.target.value })} className="input" placeholder="+237 6XX XXX XXX" />
                </div>
                <div>
                  <label className="label">Ville</label>
                  <input value={orgForm.org_city} onChange={e => setOrgForm({ ...orgForm, org_city: e.target.value })} className="input" placeholder="Yaoundé" />
                </div>
                <div>
                  <label className="label">Pays</label>
                  <input value={orgForm.org_country} onChange={e => setOrgForm({ ...orgForm, org_country: e.target.value })} className="input" placeholder="Cameroun" />
                </div>
              </div>
            </div>

            <div className="border-t border-slate-100 pt-5">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Compte administrateur</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div>
                  <label className="label">Nom complet *</label>
                  <input value={orgForm.admin_full_name} onChange={e => setOrgForm({ ...orgForm, admin_full_name: e.target.value })} className="input" placeholder="Jean Dupont" />
                </div>
                <div>
                  <label className="label">Email *</label>
                  <input type="email" value={orgForm.admin_email} onChange={e => setOrgForm({ ...orgForm, admin_email: e.target.value })} className="input" placeholder="jean@entreprise.com" />
                </div>
                <div>
                  <label className="label">Mot de passe *</label>
                  <div className="relative">
                    <input
                      type={showPassword ? "text" : "password"}
                      value={orgForm.admin_password}
                      onChange={e => setOrgForm({ ...orgForm, admin_password: e.target.value })}
                      className="input pr-10"
                      placeholder="8 caractères minimum"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {formError && (
              <div className="alert-error flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                {formError}
              </div>
            )}

            <div className="flex gap-3 justify-end">
              <button type="button" onClick={() => { setShowCreateOrg(false); setFormError(null); }} className="btn-secondary">
                Annuler
              </button>
              <button type="submit" disabled={createOrgMut.isPending} className="btn-primary">
                {createOrgMut.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                Créer l&apos;entreprise
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-slate-100 rounded-xl w-fit">
        <button
          onClick={() => setActiveTab("orgs")}
          className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === "orgs" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
        >
          <span className="flex items-center gap-2">
            <Building2 className="w-4 h-4" />
            Entreprises {orgs ? `(${orgs.length})` : ""}
          </span>
        </button>
        <button
          onClick={() => setActiveTab("users")}
          className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === "users" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
        >
          <span className="flex items-center gap-2">
            <Users className="w-4 h-4" />
            Utilisateurs {allUsers ? `(${allUsers.length})` : ""}
          </span>
        </button>
      </div>

      {/* ── Tab : Entreprises ── */}
      {activeTab === "orgs" && (
        <div className="card overflow-hidden">
          {orgsLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
            </div>
          ) : !orgs?.length ? (
            <div className="empty-state">
              <Building2 className="empty-state-icon" />
              <p className="empty-state-title">Aucune entreprise</p>
              <p className="empty-state-desc">Créez la première organisation avec le bouton ci-dessus</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="table-header">Entreprise</th>
                  <th className="table-header">Contact</th>
                  <th className="table-header text-center">Utilisateurs</th>
                  <th className="table-header text-center">Actifs 24h</th>
                  <th className="table-header">Créée le</th>
                  <th className="table-header text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {orgs.map(org => (
                  <Fragment key={org.id}>
                    <tr className="hover:bg-slate-50 transition-colors">
                      <td className="table-cell">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-violet-700 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
                            {org.name.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <p className="font-semibold text-slate-900">{org.name}</p>
                            {org.city && (
                              <p className="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
                                <Globe className="w-3 h-3" />
                                {org.city}{org.country ? `, ${org.country}` : ""}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="table-cell">
                        <div className="space-y-0.5">
                          {org.email && (
                            <p className="text-xs text-slate-500 flex items-center gap-1">
                              <Mail className="w-3 h-3" /> {org.email}
                            </p>
                          )}
                          {org.phone && (
                            <p className="text-xs text-slate-500 flex items-center gap-1">
                              <Phone className="w-3 h-3" /> {org.phone}
                            </p>
                          )}
                          {!org.email && !org.phone && <span className="text-slate-300 text-xs">—</span>}
                        </div>
                      </td>
                      <td className="table-cell text-center">
                        <button
                          onClick={() => setExpandedOrg(expandedOrg === org.id ? null : org.id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 text-xs font-semibold hover:bg-blue-100 transition-colors"
                        >
                          {org.user_count}
                          {expandedOrg === org.id ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        </button>
                      </td>
                      <td className="table-cell text-center">
                        {org.active_user_count > 0 ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                            {org.active_user_count}
                          </span>
                        ) : (
                          <span className="text-slate-300 text-xs">—</span>
                        )}
                      </td>
                      <td className="table-cell text-slate-400 text-xs">{fmt(org.created_at)}</td>
                      <td className="table-cell text-center">
                        <button
                          onClick={() => setConfirmDelete({ type: "org", id: org.id, name: org.name })}
                          className="p-1.5 rounded-lg hover:bg-red-50 text-slate-300 hover:text-red-500 transition-colors"
                          title="Supprimer l'entreprise"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                    {/* Ligne expandée — utilisateurs de l'org */}
                    {expandedOrg === org.id && (
                      <tr>
                        <td colSpan={6} className="bg-slate-50 px-6 py-4">
                          <OrgUsersInline orgId={org.id} orgName={org.name} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Tab : Utilisateurs ── */}
      {activeTab === "users" && (
        <div className="card overflow-hidden">
          {usersLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
            </div>
          ) : !allUsers?.length ? (
            <div className="empty-state">
              <Users className="empty-state-icon" />
              <p className="empty-state-title">Aucun utilisateur</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="table-header">Utilisateur</th>
                  <th className="table-header">Entreprise</th>
                  <th className="table-header">Rôle</th>
                  <th className="table-header text-center">Statut</th>
                  <th className="table-header">Dernière connexion</th>
                  <th className="table-header text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {allUsers.map(u => (
                  <tr key={u.id} className={`hover:bg-slate-50 transition-colors ${u.status === "suspended" ? "opacity-60" : ""}`}>
                    <td className="table-cell">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                          {u.full_name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className="font-medium text-slate-900">{u.full_name}</p>
                          <p className="text-xs text-slate-400">{u.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="table-cell text-slate-500 text-xs">
                      {u.organization_name ?? <span className="text-slate-300">—</span>}
                    </td>
                    <td className="table-cell">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${ROLE_COLORS[u.role] ?? "bg-slate-100 text-slate-600 border-slate-200"}`}>
                        <Shield className="w-3 h-3" />
                        {ROLE_LABELS[u.role] ?? u.role}
                      </span>
                    </td>
                    <td className="table-cell text-center">
                      {u.status === "active"
                        ? <span className="inline-flex items-center gap-1 text-xs text-emerald-600 font-medium"><CheckCircle className="w-3.5 h-3.5" /> Actif</span>
                        : <span className="inline-flex items-center gap-1 text-xs text-amber-600 font-medium"><XCircle className="w-3.5 h-3.5" /> Suspendu</span>
                      }
                    </td>
                    <td className="table-cell text-xs text-slate-400">{fmtTime(u.last_login_at)}</td>
                    <td className="table-cell">
                      <div className="flex items-center justify-center gap-1">
                        {u.id !== currentUser?.id && (
                          <>
                            <button
                              onClick={() => toggleStatusMut.mutate({ id: u.id, suspend: u.status === "active" })}
                              disabled={toggleStatusMut.isPending}
                              className={`p-1.5 rounded-lg transition-colors ${u.status === "active" ? "hover:bg-amber-50 text-slate-300 hover:text-amber-500" : "hover:bg-emerald-50 text-slate-300 hover:text-emerald-500"}`}
                              title={u.status === "active" ? "Suspendre" : "Réactiver"}
                            >
                              {u.status === "active" ? <UserX className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}
                            </button>
                            <button
                              onClick={() => setConfirmDelete({ type: "user", id: u.id, name: u.full_name })}
                              className="p-1.5 rounded-lg hover:bg-red-50 text-slate-300 hover:text-red-500 transition-colors"
                              title="Supprimer"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Dialog confirmation suppression */}
      {confirmDelete && (
        <ConfirmDialog
          message={
            confirmDelete.type === "org"
              ? `Supprimer l'entreprise "${confirmDelete.name}" et tous ses utilisateurs ? Cette action est irréversible.`
              : `Supprimer le compte de "${confirmDelete.name}" ? Cette action est irréversible.`
          }
          loading={deleteOrgMut.isPending || deleteUserMut.isPending}
          onConfirm={() => {
            if (confirmDelete.type === "org") deleteOrgMut.mutate(confirmDelete.id);
            else deleteUserMut.mutate(confirmDelete.id);
          }}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </div>
  );
}

// ─── Composant inline — utilisateurs d'une org ───────────────────────────────

function OrgUsersInline({ orgId, orgName }: { orgId: string; orgName: string }) {
  const { data, isLoading } = useQuery<UserItem[]>({
    queryKey: ["admin-users"],
    queryFn: () => apiClient.get<UserItem[]>("/admin/users").then(r => r.data),
    select: (users) => users.filter(u => u.organization_id === orgId),
    staleTime: 30_000,
  });

  if (isLoading) return <div className="flex justify-center py-4"><Loader2 className="w-4 h-4 animate-spin text-blue-500" /></div>;
  if (!data?.length) return <p className="text-xs text-slate-400 text-center py-2">Aucun utilisateur dans {orgName}</p>;

  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden">
      <table className="w-full text-xs">
        <thead className="bg-slate-100">
          <tr>
            <th className="px-4 py-2 text-left font-semibold text-slate-500">Nom</th>
            <th className="px-4 py-2 text-left font-semibold text-slate-500">Email</th>
            <th className="px-4 py-2 text-left font-semibold text-slate-500">Rôle</th>
            <th className="px-4 py-2 text-left font-semibold text-slate-500">Dernière connexion</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {data.map(u => (
            <tr key={u.id}>
              <td className="px-4 py-2 font-medium text-slate-700">{u.full_name}</td>
              <td className="px-4 py-2 text-slate-400">{u.email}</td>
              <td className="px-4 py-2">
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${ROLE_COLORS[u.role] ?? ""}`}>
                  {ROLE_LABELS[u.role] ?? u.role}
                </span>
              </td>
              <td className="px-4 py-2 text-slate-400">
                {u.last_login_at ? formatDateTimeFr(u.last_login_at) : "Jamais"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
