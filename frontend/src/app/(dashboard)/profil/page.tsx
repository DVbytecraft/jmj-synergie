"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  CheckCircle,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  Lock,
  ShieldCheck,
  User,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { useAuthStore } from "@/store/auth.store";

// ─── Types ────────────────────────────────────────────────────────────────────

interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

// ─── Schemas ──────────────────────────────────────────────────────────────────

const nameSchema = z.object({
  full_name: z.string().min(2, "Minimum 2 caractères").max(100),
});
type NameForm = z.infer<typeof nameSchema>;

const emailSchema = z.object({
  email: z.string().email("Adresse email invalide"),
});
type EmailForm = z.infer<typeof emailSchema>;

const passwordSchema = z
  .object({
    current_password: z.string().min(1, "Requis"),
    new_password: z
      .string()
      .min(8, "Minimum 8 caractères")
      .regex(/[A-Z]/, "Au moins une majuscule")
      .regex(/[a-z]/, "Au moins une minuscule")
      .regex(/[0-9]/, "Au moins un chiffre"),
    confirm_password: z.string(),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: "Les mots de passe ne correspondent pas",
    path: ["confirm_password"],
  });
type PasswordForm = z.infer<typeof passwordSchema>;

// ─── Role badge ───────────────────────────────────────────────────────────────

const ROLE_CFG: Record<string, { label: string; className: string }> = {
  admin:       { label: "Administrateur",className: "bg-blue-100 text-blue-700"   },
  manager:     { label: "Manager",       className: "bg-indigo-100 text-indigo-700"},
  operator:    { label: "Opérateur",     className: "bg-slate-100 text-slate-700"  },
};

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ProfilPage() {
  const qc = useQueryClient();
  const user = useAuthStore((s) => s.user);

  const [nameSuccess, setNameSuccess] = useState(false);
  const [emailSuccess, setEmailSuccess] = useState(false);
  const [pwdSuccess, setPwdSuccess] = useState(false);
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  // ── Fetch current user ────────────────────────────────────────────────────
  const { data: profile, isLoading } = useQuery<UserProfile>({
    queryKey: ["users", "me"],
    queryFn: async () => (await apiClient.get<UserProfile>("/users/me")).data,
  });

  // ── Update name ───────────────────────────────────────────────────────────
  const nameForm = useForm<NameForm>({
    resolver: zodResolver(nameSchema),
    values: { full_name: profile?.full_name ?? "" },
  });

  const nameMut = useMutation({
    mutationFn: async (data: NameForm) => {
      const res = await apiClient.patch<UserProfile>("/users/me", data);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users", "me"] });
      setNameSuccess(true);
      setTimeout(() => setNameSuccess(false), 3000);
    },
  });

  const emailForm = useForm<EmailForm>({
    resolver: zodResolver(emailSchema),
    values: { email: profile?.email ?? "" },
  });

  const emailMut = useMutation({
    mutationFn: async (data: EmailForm) => {
      const res = await apiClient.patch<UserProfile>("/users/me/email", data);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users", "me"] });
      setEmailSuccess(true);
      setTimeout(() => setEmailSuccess(false), 4000);
    },
  });

  // ── Change password ───────────────────────────────────────────────────────
  const pwdForm = useForm<PasswordForm>({ resolver: zodResolver(passwordSchema) });

  const pwdMut = useMutation({
    mutationFn: async (data: PasswordForm) => {
      await apiClient.post("/users/me/change-password", {
        current_password: data.current_password,
        new_password: data.new_password,
      });
    },
    onSuccess: () => {
      pwdForm.reset();
      setPwdSuccess(true);
      setTimeout(() => setPwdSuccess(false), 4000);
    },
  });

  const roleCfg = ROLE_CFG[profile?.role ?? user?.role ?? "operator"] ?? ROLE_CFG.operator;

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Mon profil</h1>
        <p className="text-sm text-slate-500 mt-1">Gérez vos informations personnelles et votre mot de passe.</p>
      </div>

      {/* ── Identity card ─────────────────────────────────────────────── */}
      <div className="card p-6 flex items-center gap-5">
        <div className="w-14 h-14 bg-blue-100 rounded-full flex items-center justify-center shrink-0">
          <User className="w-7 h-7 text-blue-600" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-lg font-bold text-slate-900 truncate">{profile?.full_name}</p>
          <p className="text-sm text-slate-500 truncate">{profile?.email}</p>
        </div>
        <span className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${roleCfg.className}`}>
          {roleCfg.label}
        </span>
      </div>

      {/* ── Update name ──────────────────────────────────────────────── */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center gap-2">
          <User className="w-4 h-4 text-slate-500" />
          <h2 className="font-semibold text-slate-900">Nom complet</h2>
        </div>

        <form onSubmit={nameForm.handleSubmit((d) => nameMut.mutate(d))} className="space-y-4">
          <div>
            <label className="label">Nom affiché</label>
            <input
              {...nameForm.register("full_name")}
              type="text"
              className="input"
              placeholder="Prénom Nom"
            />
            {nameForm.formState.errors.full_name && (
              <p className="field-error">{nameForm.formState.errors.full_name.message}</p>
            )}
          </div>

          {nameMut.error && (
            <div className="alert-error">
              {(nameMut.error as any)?.response?.data?.detail ?? "Erreur lors de la mise à jour."}
            </div>
          )}

          {nameSuccess && (
            <div className="flex items-center gap-2 text-emerald-600 text-sm">
              <CheckCircle className="w-4 h-4" />
              Nom mis à jour avec succès.
            </div>
          )}

          <div className="flex justify-end">
            <button type="submit" disabled={nameMut.isPending} className="btn-primary">
              {nameMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <User className="w-4 h-4" />}
              Enregistrer
            </button>
          </div>
        </form>
      </div>

      {/* ── Change password ───────────────────────────────────────────── */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-slate-500" />
          <h2 className="font-semibold text-slate-900">Identifiant de connexion</h2>
        </div>

        <div className="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-lg px-4 py-3">
          <ShieldCheck className="w-4 h-4 text-blue-600 mt-0.5 shrink-0" />
          <p className="text-xs text-blue-700 leading-relaxed">
            Cette adresse email est l'identifiant unique de connexion de JMJ Synergie.
            La modifier invalidera les autres sessions actives.
          </p>
        </div>

        <form onSubmit={emailForm.handleSubmit((d) => emailMut.mutate(d))} className="space-y-4">
          <div>
            <label className="label">Email de connexion</label>
            <input
              {...emailForm.register("email")}
              type="email"
              className="input"
              placeholder="admin@jmjsynergie.com"
              autoComplete="email"
            />
            {emailForm.formState.errors.email && (
              <p className="field-error">{emailForm.formState.errors.email.message}</p>
            )}
          </div>

          {emailMut.error && (
            <div className="alert-error">
              {(emailMut.error as any)?.response?.data?.detail ?? "Erreur lors de la mise a jour de l'identifiant."}
            </div>
          )}

          {emailSuccess && (
            <div className="flex items-center gap-2 text-emerald-600 text-sm">
              <CheckCircle className="w-4 h-4" />
              Identifiant de connexion mis a jour avec succes.
            </div>
          )}

          <div className="flex justify-end">
            <button type="submit" disabled={emailMut.isPending} className="btn-primary">
              {emailMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
              Mettre a jour l'identifiant
            </button>
          </div>
        </form>
      </div>

      <div className="card p-6 space-y-4">
        <div className="flex items-center gap-2">
          <KeyRound className="w-4 h-4 text-slate-500" />
          <h2 className="font-semibold text-slate-900">Changer le mot de passe</h2>
        </div>

        <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
          <ShieldCheck className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
          <p className="text-xs text-amber-700 leading-relaxed">
            Changer votre mot de passe déconnectera toutes vos autres sessions actives.
          </p>
        </div>

        <form onSubmit={pwdForm.handleSubmit((d) => pwdMut.mutate(d))} className="space-y-4">
          {/* Current password */}
          <div>
            <label className="label">Mot de passe actuel</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
              <input
                {...pwdForm.register("current_password")}
                type={showCurrent ? "text" : "password"}
                autoComplete="current-password"
                placeholder="••••••••"
                className="input pl-10 pr-10"
              />
              <button type="button" onClick={() => setShowCurrent((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                {showCurrent ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {pwdForm.formState.errors.current_password && (
              <p className="field-error">{pwdForm.formState.errors.current_password.message}</p>
            )}
          </div>

          {/* New password */}
          <div>
            <label className="label">Nouveau mot de passe</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
              <input
                {...pwdForm.register("new_password")}
                type={showNew ? "text" : "password"}
                autoComplete="new-password"
                placeholder="••••••••"
                className="input pl-10 pr-10"
              />
              <button type="button" onClick={() => setShowNew((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                {showNew ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {pwdForm.formState.errors.new_password && (
              <p className="field-error">{pwdForm.formState.errors.new_password.message}</p>
            )}
          </div>

          {/* Confirm */}
          <div>
            <label className="label">Confirmer le nouveau mot de passe</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
              <input
                {...pwdForm.register("confirm_password")}
                type={showConfirm ? "text" : "password"}
                autoComplete="new-password"
                placeholder="••••••••"
                className="input pl-10 pr-10"
              />
              <button type="button" onClick={() => setShowConfirm((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {pwdForm.formState.errors.confirm_password && (
              <p className="field-error">{pwdForm.formState.errors.confirm_password.message}</p>
            )}
          </div>

          {pwdMut.error && (
            <div className="alert-error">
              {(pwdMut.error as any)?.response?.data?.detail ?? "Erreur lors du changement de mot de passe."}
            </div>
          )}

          {pwdSuccess && (
            <div className="flex items-center gap-2 text-emerald-600 text-sm">
              <CheckCircle className="w-4 h-4" />
              Mot de passe modifié. Toutes vos autres sessions ont été déconnectées.
            </div>
          )}

          <div className="flex justify-end">
            <button type="submit" disabled={pwdMut.isPending} className="btn-primary">
              {pwdMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
              Changer le mot de passe
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
