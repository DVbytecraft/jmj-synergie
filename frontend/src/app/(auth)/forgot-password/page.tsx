"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft, CheckCircle, Eye, EyeOff, Loader2, Lock, Mail } from "lucide-react";

import { apiClient } from "@/lib/api/client";

const resetSchema = z
  .object({
    email: z.string().email("Adresse email invalide"),
    new_password: z
      .string()
      .min(8, "Minimum 8 caractères")
      .regex(/[A-Z]/, "Au moins une majuscule")
      .regex(/[a-z]/, "Au moins une minuscule")
      .regex(/[0-9]/, "Au moins un chiffre"),
    confirm_password: z.string(),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Les mots de passe ne correspondent pas",
    path: ["confirm_password"],
  });

type ResetForm = z.infer<typeof resetSchema>;

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [showPwd, setShowPwd] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetForm>({ resolver: zodResolver(resetSchema) });

  const onSubmit = async (data: ResetForm) => {
    setError(null);
    try {
      await apiClient.post("/auth/forgot-password", { email: data.email });
      await apiClient.post("/auth/reset-password", {
        email: data.email,
        new_password: data.new_password,
      });
      setDone(true);
      setTimeout(() => router.replace("/login"), 2500);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Impossible de réinitialiser le mot de passe.");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-[420px] space-y-6">
        <div className="flex items-center justify-center gap-3">
          <img src="/logo.svg" alt="JMJ Synergie" className="w-9 h-9 rounded-xl" />
          <span className="text-slate-900 font-semibold text-lg">JMJ Synergie</span>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8 space-y-6">
          {done ? (
            <div className="text-center space-y-4">
              <div className="w-14 h-14 bg-emerald-50 rounded-full flex items-center justify-center mx-auto">
                <CheckCircle className="w-7 h-7 text-emerald-500" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">Mot de passe mis à jour</h1>
                <p className="text-sm text-slate-500 mt-2">
                  Votre mot de passe a été réinitialisé. Redirection vers la connexion…
                </p>
              </div>
            </div>
          ) : (
            <>
              <div>
                <h1 className="text-xl font-bold text-slate-900">Réinitialiser le mot de passe</h1>
                <p className="text-sm text-slate-500 mt-1.5">
                  Saisissez l'adresse email du compte puis définissez directement un nouveau mot de passe.
                </p>
              </div>

              <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
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
                  {errors.email && <p className="field-error">{errors.email.message}</p>}
                </div>

                <div>
                  <label className="label">Nouveau mot de passe</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                    <input
                      {...register("new_password")}
                      type={showPwd ? "text" : "password"}
                      autoComplete="new-password"
                      className="input pl-10 pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPwd((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    >
                      {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {errors.new_password && <p className="field-error">{errors.new_password.message}</p>}
                </div>

                <div>
                  <label className="label">Confirmer le mot de passe</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                    <input
                      {...register("confirm_password")}
                      type={showConfirm ? "text" : "password"}
                      autoComplete="new-password"
                      className="input pl-10 pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirm((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                    >
                      {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {errors.confirm_password && <p className="field-error">{errors.confirm_password.message}</p>}
                </div>

                {error && <div className="alert-error">{error}</div>}

                <button type="submit" disabled={isSubmitting} className="btn-primary w-full py-2.5">
                  {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
                  Réinitialiser
                </button>
              </form>

              <div className="text-center">
                <Link href="/login" className="text-sm text-slate-500 hover:text-slate-700 flex items-center justify-center gap-1.5">
                  <ArrowLeft className="w-3.5 h-3.5" />
                  Retour à la connexion
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
