"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, Lock, ArrowLeft, CheckCircle, Eye, EyeOff } from "lucide-react";
import { apiClient } from "@/lib/api/client";

const schema = z.object({
  new_password: z.string().min(8, "Minimum 8 caractères"),
  confirm_password: z.string(),
}).refine((d) => d.new_password === d.confirm_password, {
  message: "Les mots de passe ne correspondent pas",
  path: ["confirm_password"],
});
type FormData = z.infer<typeof schema>;

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPwd, setShowPwd] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  if (!token) {
    return (
      <div className="text-center space-y-4">
        <p className="text-slate-500 text-sm">Lien invalide ou manquant.</p>
        <Link href="/forgot-password" className="btn-primary">
          Refaire une demande
        </Link>
      </div>
    );
  }

  const onSubmit = async (data: FormData) => {
    setError(null);
    try {
      await apiClient.post("/auth/reset-password", {
        token,
        new_password: data.new_password,
      });
      setDone(true);
      setTimeout(() => router.replace("/login"), 3000);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Lien invalide ou expiré. Faites une nouvelle demande.");
    }
  };

  return (
    <div className="w-full max-w-[400px] space-y-6">

      {/* Logo */}
      <div className="flex items-center justify-center gap-3">
        <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center">
          <span className="text-white font-bold text-sm">B</span>
        </div>
        <span className="text-slate-900 font-semibold text-lg">Biloz</span>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8 space-y-6">

        {done ? (
          /* ── Success ── */
          <div className="text-center space-y-4">
            <div className="w-14 h-14 bg-emerald-50 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle className="w-7 h-7 text-emerald-500" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900">Mot de passe mis à jour</h1>
              <p className="text-sm text-slate-500 mt-2">
                Votre mot de passe a été changé. Vous allez être redirigé vers la connexion…
              </p>
            </div>
            <Link href="/login" className="btn-primary w-full justify-center">
              Se connecter
            </Link>
          </div>
        ) : (
          /* ── Form ── */
          <>
            <div>
              <h1 className="text-xl font-bold text-slate-900">Nouveau mot de passe</h1>
              <p className="text-sm text-slate-500 mt-1.5">
                Choisissez un mot de passe sécurisé d'au moins 8 caractères.
              </p>
            </div>

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <label className="label">Nouveau mot de passe</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                  <input
                    {...register("new_password")}
                    type={showPwd ? "text" : "password"}
                    placeholder="••••••••"
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
                    placeholder="••••••••"
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

              {error && (
                <div className="alert-error">
                  {error}{" "}
                  <Link href="/forgot-password" className="underline font-medium">
                    Refaire une demande
                  </Link>
                </div>
              )}

              <button type="submit" disabled={isSubmitting} className="btn-primary w-full py-2.5">
                {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
                Mettre à jour le mot de passe
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
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <Suspense fallback={
        <div className="flex justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
        </div>
      }>
        <ResetPasswordForm />
      </Suspense>
    </div>
  );
}
