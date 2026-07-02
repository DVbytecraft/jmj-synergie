"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, Lock, Mail, ArrowRight, Users, ShoppingCart, TrendingUp, Eye, EyeOff } from "lucide-react";
import { useAuthStore } from "@/store/auth.store";
import { apiClient } from "@/lib/api/client";

const loginSchema = z.object({
  email: z.string().email("Email invalide"),
  password: z.string().min(6, "Mot de passe requis"),
});
type LoginForm = z.infer<typeof loginSchema>;

function LoginContent() {
  const [error, setError] = useState<string | null>(null);
  const [isWaking, setIsWaking] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionExpired = !!searchParams.get("from");
  const registeredEmail = searchParams.get("registered");
  const { setAuth } = useAuthStore();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });

  const onSubmit = async (data: LoginForm) => {
    setError(null);
    setIsWaking(false);
    try {
      const form = new URLSearchParams();
      form.append("username", data.email);
      form.append("password", data.password);
      const res = await apiClient.post("/auth/login", form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      setAuth(res.data.access_token);
      router.replace("/dashboard");
    } catch (e: unknown) {
      const err = e as { response?: { status?: number; data?: { detail?: unknown } } };
      const status = err.response?.status;
      if (status === 502 || status === 503 || status === 504) {
        setIsWaking(true);
        return;
      }
      if (status === 429) {
        setError("Trop de tentatives de connexion. Veuillez patienter quelques minutes avant de réessayer.");
        return;
      }
      const detail = err.response?.data?.detail;
      setError(
        typeof detail === "string" ? detail : "Email ou mot de passe incorrect"
      );
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* ── Left panel — branding ── */}
      <div className="hidden lg:flex lg:w-[52%] bg-slate-900 flex-col justify-between p-12 relative overflow-hidden">
        {/* Glow */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_60%_-10%,_rgb(59_130_246_/_0.25),_transparent)]" />

        {/* Logo */}
        <div className="relative flex items-center gap-3">
          <img src="/logo.svg" alt="JMJ Synergie" className="w-9 h-9 rounded-xl shadow-lg" />
          <span className="text-white font-semibold text-lg tracking-tight">JMJ Synergie</span>
        </div>

        {/* Hero */}
        <div className="relative space-y-7">
          <div className="space-y-4">
            <h2 className="text-4xl font-bold text-white leading-snug">
              Gérez votre activité<br />
              <span className="text-blue-400">en toute simplicité</span>
            </h2>
            <p className="text-slate-400 text-base leading-relaxed max-w-sm">
              Plateforme de gestion commerciale complète — clients, commandes, paiements et documents en un seul espace.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-3">
            {[
              { icon: Users,        label: "Clients",    desc: "Gestion centralisée" },
              { icon: ShoppingCart, label: "Commandes",  desc: "Suivi en temps réel" },
              { icon: TrendingUp,   label: "Analytique", desc: "Vue d'ensemble" },
            ].map(({ icon: Icon, label, desc }) => (
              <div
                key={label}
                className="bg-white/5 border border-white/8 rounded-xl p-4 backdrop-blur-sm"
              >
                <Icon className="w-5 h-5 text-blue-400 mb-3" />
                <p className="text-white text-sm font-medium leading-none">{label}</p>
                <p className="text-slate-500 text-xs mt-1">{desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <p className="relative text-slate-600 text-xs">
          © {new Date().getFullYear()} JMJ Synergie — Tous droits réservés
        </p>
      </div>

      {/* ── Right panel — form ── */}
      <div className="flex-1 flex items-center justify-center p-6 bg-white">
        <div className="w-full max-w-[360px]">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-3 mb-10 justify-center">
            <img src="/logo.svg" alt="JMJ Synergie" className="w-9 h-9 rounded-xl" />
            <span className="text-slate-900 font-semibold text-lg">JMJ Synergie</span>
          </div>

          <div className="mb-8">
            <h1 className="text-2xl font-bold text-slate-900">Connexion</h1>
            <p className="text-slate-500 text-sm mt-1.5">
              Utilisez le compte principal de l'entreprise pour accéder à l'application.
            </p>
          </div>

          {sessionExpired && !error && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 mb-6">
              Votre session a expiré. Veuillez vous reconnecter.
            </div>
          )}

          {registeredEmail && !sessionExpired && !error && (
            <div className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800 mb-6">
              L'inscription est désormais fermée. Connectez-vous avec le compte administrateur principal.
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} method="post" className="space-y-5">
            {/* Email */}
            <div>
              <label className="label">Adresse email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                <input
                  {...register("email")}
                  type="email"
                  autoComplete="email"
                  placeholder="vous@exemple.com"
                  className="input pl-10"
                />
              </div>
              {errors.email && (
                <p className="field-error">{errors.email.message}</p>
              )}
            </div>

            {/* Password */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-sm font-medium text-slate-700">Mot de passe</label>
                <Link
                  href="/forgot-password"
                  className="text-xs text-blue-600 hover:text-blue-700 hover:underline"
                >
                  Mot de passe oublié ?
                </Link>
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                <input
                  {...register("password")}
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  className="input pl-10 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                  tabIndex={-1}
                  aria-label={showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.password && (
                <p className="field-error">{errors.password.message}</p>
              )}
            </div>

            {/* Server waking up notice */}
            {isWaking && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                <p className="font-medium">Le serveur se réveille…</p>
                <p className="mt-0.5 text-amber-700">
                  Première connexion du jour — réessayez dans 30 secondes.
                </p>
              </div>
            )}

            {/* Server error */}
            {error && <div className="alert-error">{error}</div>}

            {/* Submit */}
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
              Se connecter
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-white">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    }>
      <LoginContent />
    </Suspense>
  );
}

