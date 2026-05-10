"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Loader2, Building2, User, Mail, Lock, Phone, ArrowRight,
  CheckCircle2, AlertCircle,
} from "lucide-react";
import { useAuthStore } from "@/store/auth.store";
import { apiClient } from "@/lib/api/client";

const registerSchema = z.object({
  organization_name: z.string().min(2, "Nom de société requis (min. 2 caractères)"),
  legal_name: z.string().optional(),
  tax_id: z.string().optional(),
  phone: z.string().optional(),
  email: z.string().email("Email invalide"),
  full_name: z.string().min(2, "Nom complet requis (min. 2 caractères)"),
  password: z.string().min(8, "Mot de passe requis (min. 8 caractères)"),
  confirm_password: z.string().min(8, "Confirmation requise"),
}).refine((d) => d.password === d.confirm_password, {
  message: "Les mots de passe ne correspondent pas",
  path: ["confirm_password"],
});

type RegisterForm = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const router = useRouter();
  const { setAuth } = useAuthStore();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>({ resolver: zodResolver(registerSchema) });

  const onSubmit = async (data: RegisterForm) => {
    setError(null);
    try {
      const { confirm_password, ...payload } = data;
      const res = await apiClient.post("/auth/register-organization", payload);
      setAuth(res.data.access_token, res.data.refresh_token);
      setSuccess(true);
      setTimeout(() => router.replace("/dashboard"), 1500);
    } catch (e: any) {
      const detail = e.response?.data?.detail;
      setError(
        typeof detail === "string"
          ? detail
          : "Une erreur est survenue. Vérifiez vos informations."
      );
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-8 h-8 text-emerald-600" />
          </div>
          <h2 className="text-xl font-bold text-gray-900">Compte créé avec succès !</h2>
          <p className="text-gray-500 text-sm">Redirection vers votre tableau de bord…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex">
      {/* ── Left panel ─────────────────────────────────────── */}
      <div className="hidden lg:flex lg:w-[48%] bg-slate-900 flex-col justify-between p-12 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_60%_-10%,_rgb(59_130_246_/_0.25),_transparent)]" />
        <div className="relative flex items-center gap-3">
          <div className="w-9 h-9 bg-blue-500 rounded-xl flex items-center justify-center shadow-lg">
            <span className="text-white font-bold text-sm">B</span>
          </div>
          <span className="text-white font-semibold text-lg tracking-tight">Biloz</span>
        </div>
        <div className="relative space-y-6">
          <h2 className="text-4xl font-bold text-white leading-snug">
            Votre société<br />
            <span className="text-blue-400">en quelques secondes</span>
          </h2>
          <p className="text-slate-400 text-base leading-relaxed max-w-sm">
            Créez votre espace de gestion commerciale. Clients, commandes, factures et documents centralisés.
          </p>
          <ul className="space-y-3">
            {[
              "Espace dédié et cloisonné pour votre société",
              "Factures, pro formas et bons de livraison PDF",
              "Envoi automatique des documents par email",
              "Multi-utilisateurs avec gestion des rôles",
            ].map((item) => (
              <li key={item} className="flex items-center gap-3 text-slate-300 text-sm">
                <CheckCircle2 className="w-4 h-4 text-blue-400 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-slate-600 text-xs">
          © {new Date().getFullYear()} Biloz — Tous droits réservés
        </p>
      </div>

      {/* ── Right panel — form ──────────────────────────────── */}
      <div className="flex-1 flex items-start justify-center p-6 bg-white overflow-y-auto">
        <div className="w-full max-w-[420px] py-10">
          <div className="lg:hidden flex items-center gap-3 mb-8 justify-center">
            <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center">
              <span className="text-white font-bold text-sm">B</span>
            </div>
            <span className="text-slate-900 font-semibold text-lg">Biloz</span>
          </div>

          <div className="mb-8">
            <h1 className="text-2xl font-bold text-slate-900">Créer un compte</h1>
            <p className="text-slate-500 text-sm mt-1.5">
              Déjà inscrit ?{" "}
              <Link href="/login" className="text-blue-600 hover:underline font-medium">
                Se connecter
              </Link>
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            {/* ── Société ── */}
            <div className="space-y-1">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5" /> Votre société
              </p>
            </div>

            <div>
              <label className="label">Nom commercial <span className="text-red-500">*</span></label>
              <input
                {...register("organization_name")}
                className="input"
                placeholder="Acme SARL"
              />
              {errors.organization_name && (
                <p className="field-error">{errors.organization_name.message}</p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Raison sociale</label>
                <input
                  {...register("legal_name")}
                  className="input"
                  placeholder="ACME Société à Responsabilité…"
                />
              </div>
              <div>
                <label className="label">NIF / Identifiant fiscal</label>
                <input
                  {...register("tax_id")}
                  className="input"
                  placeholder="0000000A"
                />
              </div>
            </div>

            <div>
              <label className="label">Téléphone société</label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                <input
                  {...register("phone")}
                  className="input pl-10"
                  placeholder="+229 00 00 00 00"
                />
              </div>
            </div>

            <hr className="border-slate-100" />

            {/* ── Compte admin ── */}
            <div className="space-y-1">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                <User className="w-3.5 h-3.5" /> Votre compte administrateur
              </p>
            </div>

            <div>
              <label className="label">Nom complet <span className="text-red-500">*</span></label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                <input
                  {...register("full_name")}
                  className="input pl-10"
                  placeholder="Jean-Marie Dupont"
                />
              </div>
              {errors.full_name && (
                <p className="field-error">{errors.full_name.message}</p>
              )}
            </div>

            <div>
              <label className="label">Adresse email <span className="text-red-500">*</span></label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                <input
                  {...register("email")}
                  type="email"
                  autoComplete="email"
                  className="input pl-10"
                  placeholder="vous@societe.com"
                />
              </div>
              {errors.email && (
                <p className="field-error">{errors.email.message}</p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Mot de passe <span className="text-red-500">*</span></label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                  <input
                    {...register("password")}
                    type="password"
                    autoComplete="new-password"
                    className="input pl-10"
                    placeholder="8 caractères min."
                  />
                </div>
                {errors.password && (
                  <p className="field-error">{errors.password.message}</p>
                )}
              </div>
              <div>
                <label className="label">Confirmation <span className="text-red-500">*</span></label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                  <input
                    {...register("confirm_password")}
                    type="password"
                    autoComplete="new-password"
                    className="input pl-10"
                    placeholder="Répétez"
                  />
                </div>
                {errors.confirm_password && (
                  <p className="field-error">{errors.confirm_password.message}</p>
                )}
              </div>
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary w-full py-2.5 mt-2"
            >
              {isSubmitting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ArrowRight className="w-4 h-4" />
              )}
              Créer mon espace
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
