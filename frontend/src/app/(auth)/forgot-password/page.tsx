"use client";

import { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, Mail, ArrowLeft, CheckCircle } from "lucide-react";
import { apiClient } from "@/lib/api/client";

const schema = z.object({
  email: z.string().email("Adresse email invalide"),
});
type FormData = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    setError(null);
    try {
      await apiClient.post("/auth/forgot-password", { email: data.email });
      setSent(true);
    } catch {
      setError("Une erreur est survenue. Veuillez réessayer.");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-[400px] space-y-6">

        {/* Logo */}
        <div className="flex items-center justify-center gap-3">
          <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center">
            <span className="text-white font-bold text-sm">B</span>
          </div>
          <span className="text-slate-900 font-semibold text-lg">Biloz</span>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8 space-y-6">

          {sent ? (
            /* ── Confirmation ── */
            <div className="text-center space-y-4">
              <div className="w-14 h-14 bg-emerald-50 rounded-full flex items-center justify-center mx-auto">
                <CheckCircle className="w-7 h-7 text-emerald-500" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">Email envoyé</h1>
                <p className="text-sm text-slate-500 mt-2">
                  Si cette adresse est associée à un compte, vous recevrez un code de vérification par email.
                  Utilisez ensuite ce code pour réinitialiser votre mot de passe.
                </p>
              </div>
              <Link href="/login" className="btn-secondary w-full justify-center">
                <ArrowLeft className="w-4 h-4" />
                Retour à la connexion
              </Link>
            </div>
          ) : (
            /* ── Form ── */
            <>
              <div>
                <h1 className="text-xl font-bold text-slate-900">Mot de passe oublié</h1>
                <p className="text-sm text-slate-500 mt-1.5">
                  Entrez votre email et nous vous enverrons un lien de réinitialisation.
                </p>
              </div>

              <form onSubmit={handleSubmit(onSubmit)} method="post" className="space-y-4">
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

                {error && <div className="alert-error">{error}</div>}

                <button type="submit" disabled={isSubmitting} className="btn-primary w-full py-2.5">
                  {isSubmitting ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Mail className="w-4 h-4" />
                  )}
                  Envoyer le lien
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
