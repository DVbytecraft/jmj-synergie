"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowLeft,
  CheckCircle,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  Mail,
  ShieldCheck,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";

// ─── Schemas ────────────────────────────────────────────────────────────────

const emailSchema = z.object({
  email: z.string().email("Adresse email invalide"),
});
type EmailForm = z.infer<typeof emailSchema>;

const passwordSchema = z
  .object({
    new_password: z
      .string()
      .min(8, "Minimum 8 caractères")
      .regex(/[A-Z]/, "Au moins une majuscule")
      .regex(/[0-9]/, "Au moins un chiffre"),
    confirm_password: z.string(),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: "Les mots de passe ne correspondent pas",
    path: ["confirm_password"],
  });
type PasswordForm = z.infer<typeof passwordSchema>;

// ─── OTP digit input ─────────────────────────────────────────────────────────

function OtpInput({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  const inputs = useRef<Array<HTMLInputElement | null>>([]);
  const digits = Array.from({ length: 6 }, (_, i) => value[i] ?? "");

  const update = (idx: number, char: string) => {
    const next = digits.map((d, i) => (i === idx ? char : d)).join("");
    onChange(next);
    if (char && idx < 5) inputs.current[idx + 1]?.focus();
  };

  const handleKey = (idx: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace") {
      if (digits[idx]) {
        update(idx, "");
      } else if (idx > 0) {
        inputs.current[idx - 1]?.focus();
        update(idx - 1, "");
      }
      e.preventDefault();
    } else if (e.key === "ArrowLeft" && idx > 0) {
      inputs.current[idx - 1]?.focus();
    } else if (e.key === "ArrowRight" && idx < 5) {
      inputs.current[idx + 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (pasted.length === 6) {
      onChange(pasted);
      inputs.current[5]?.focus();
      e.preventDefault();
    }
  };

  return (
    <div className="flex gap-2 justify-center" onPaste={handlePaste}>
      {digits.map((d, idx) => (
        <input
          key={idx}
          ref={(el) => { inputs.current[idx] = el; }}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={d}
          disabled={disabled}
          onChange={(e) => {
            const char = e.target.value.replace(/\D/g, "").slice(-1);
            update(idx, char);
          }}
          onKeyDown={(e) => handleKey(idx, e)}
          onFocus={(e) => e.target.select()}
          className={[
            "w-11 h-12 text-center text-lg font-semibold rounded-lg border",
            "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500",
            "transition-colors",
            d
              ? "border-blue-400 bg-blue-50 text-slate-900"
              : "border-slate-300 bg-white text-slate-900",
            disabled ? "opacity-50 cursor-not-allowed" : "",
          ]
            .filter(Boolean)
            .join(" ")}
        />
      ))}
    </div>
  );
}

// ─── Step indicators ──────────────────────────────────────────────────────────

function StepBar({ current }: { current: 1 | 2 | 3 }) {
  const steps = [
    { n: 1, label: "Email" },
    { n: 2, label: "Vérification" },
    { n: 3, label: "Mot de passe" },
  ];
  return (
    <div className="flex items-center gap-2 justify-center mb-6">
      {steps.map(({ n, label }, i) => (
        <div key={n} className="flex items-center gap-2">
          <div className="flex flex-col items-center gap-1">
            <div
              className={[
                "w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors",
                current > n
                  ? "bg-emerald-500 text-white"
                  : current === n
                  ? "bg-blue-600 text-white"
                  : "bg-slate-200 text-slate-400",
              ].join(" ")}
            >
              {current > n ? <CheckCircle className="w-4 h-4" /> : n}
            </div>
            <span
              className={[
                "text-[10px] font-medium",
                current >= n ? "text-slate-700" : "text-slate-400",
              ].join(" ")}
            >
              {label}
            </span>
          </div>
          {i < steps.length - 1 && (
            <div
              className={[
                "w-8 h-0.5 mb-4 rounded transition-colors",
                current > n ? "bg-emerald-400" : "bg-slate-200",
              ].join(" ")}
            />
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ForgotPasswordPage() {
  const router = useRouter();

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  // session_token lives only in component state — never in URL or storage
  const [sessionToken, setSessionToken] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [showPwd, setShowPwd] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [done, setDone] = useState(false);

  const emailForm = useForm<EmailForm>({ resolver: zodResolver(emailSchema) });
  const passwordForm = useForm<PasswordForm>({ resolver: zodResolver(passwordSchema) });

  // ── Step 1 : send OTP ──────────────────────────────────────────────────────
  const handleEmailSubmit = async (data: EmailForm) => {
    setError(null);
    setSubmitting(true);
    try {
      await apiClient.post("/auth/forgot-password", { email: data.email });
      setEmail(data.email);
      setOtp("");
      setStep(2);
      startCooldown();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      if (typeof detail === "string" && detail.toLowerCase().includes("60")) {
        setError("Veuillez attendre 60 secondes avant de refaire une demande.");
      } else {
        setError("Une erreur est survenue. Veuillez réessayer.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  // ── Cooldown helper ────────────────────────────────────────────────────────
  const startCooldown = () => {
    setResendCooldown(60);
    const id = setInterval(() => {
      setResendCooldown((c) => {
        if (c <= 1) { clearInterval(id); return 0; }
        return c - 1;
      });
    }, 1000);
  };

  const handleResend = async () => {
    if (resendCooldown > 0) return;
    setError(null);
    setSubmitting(true);
    try {
      await apiClient.post("/auth/forgot-password", { email });
      setOtp("");
      startCooldown();
    } catch {
      setError("Impossible de renvoyer le code. Réessayez dans un moment.");
    } finally {
      setSubmitting(false);
    }
  };

  // ── Step 2 : verify OTP ────────────────────────────────────────────────────
  const handleOtpSubmit = async () => {
    if (otp.length !== 6) {
      setError("Entrez les 6 chiffres du code.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const resp = await apiClient.post<{ session_token: string }>(
        "/auth/verify-reset-otp",
        { email, code: otp },
      );
      setSessionToken(resp.data.session_token);
      setStep(3);
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? "";
      if (e?.response?.status === 429) {
        setError("Trop de tentatives. Recommencez depuis le début.");
        setTimeout(() => setStep(1), 3000);
      } else if (detail.toLowerCase().includes("expiré") || detail.toLowerCase().includes("expired")) {
        setError("Le code a expiré. Cliquez sur « Renvoyer le code ».");
      } else {
        setError("Code incorrect. Vérifiez votre email et réessayez.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  // ── Step 3 : set new password ──────────────────────────────────────────────
  const handlePasswordSubmit = async (data: PasswordForm) => {
    setError(null);
    setSubmitting(true);
    try {
      await apiClient.post("/auth/reset-password", {
        session_token: sessionToken,
        new_password: data.new_password,
      });
      setDone(true);
      setTimeout(() => router.replace("/login"), 3000);
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? "";
      if (detail.toLowerCase().includes("expiré") || detail.toLowerCase().includes("expired")) {
        setError("La session a expiré. Recommencez depuis le début.");
        setTimeout(() => { setStep(1); setOtp(""); setSessionToken(""); }, 3000);
      } else {
        setError(detail || "Une erreur est survenue. Réessayez.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-[420px] space-y-6">

        {/* Logo */}
        <div className="flex items-center justify-center gap-3">
          <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center">
            <span className="text-white font-bold text-sm">B</span>
          </div>
          <span className="text-slate-900 font-semibold text-lg">Biloz</span>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8 space-y-6">

          {done ? (
            /* ── Success ──────────────────────────────────────────────────── */
            <div className="text-center space-y-4">
              <div className="w-14 h-14 bg-emerald-50 rounded-full flex items-center justify-center mx-auto">
                <CheckCircle className="w-7 h-7 text-emerald-500" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">Mot de passe mis à jour</h1>
                <p className="text-sm text-slate-500 mt-2">
                  Votre mot de passe a été changé avec succès.
                  Vous allez être redirigé vers la connexion…
                </p>
              </div>
              <Link href="/login" className="btn-primary w-full justify-center">
                Se connecter maintenant
              </Link>
            </div>

          ) : step === 1 ? (
            /* ── Étape 1 : Email ──────────────────────────────────────────── */
            <>
              <StepBar current={1} />

              <div>
                <h1 className="text-xl font-bold text-slate-900">Mot de passe oublié</h1>
                <p className="text-sm text-slate-500 mt-1.5">
                  Entrez votre adresse email. Vous recevrez un code à 6 chiffres valable 15 minutes.
                </p>
              </div>

              <form onSubmit={emailForm.handleSubmit(handleEmailSubmit)} className="space-y-4">
                <div>
                  <label className="label">Adresse email</label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                    <input
                      {...emailForm.register("email")}
                      type="email"
                      autoComplete="email"
                      placeholder="vous@exemple.com"
                      className="input pl-10"
                    />
                  </div>
                  {emailForm.formState.errors.email && (
                    <p className="field-error">{emailForm.formState.errors.email.message}</p>
                  )}
                </div>

                {error && <div className="alert-error">{error}</div>}

                <button type="submit" disabled={submitting} className="btn-primary w-full py-2.5">
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
                  Envoyer le code
                </button>
              </form>

              <div className="text-center">
                <Link href="/login" className="text-sm text-slate-500 hover:text-slate-700 flex items-center justify-center gap-1.5">
                  <ArrowLeft className="w-3.5 h-3.5" />
                  Retour à la connexion
                </Link>
              </div>
            </>

          ) : step === 2 ? (
            /* ── Étape 2 : Code OTP ───────────────────────────────────────── */
            <>
              <StepBar current={2} />

              <div className="text-center">
                <div className="w-12 h-12 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-3">
                  <ShieldCheck className="w-6 h-6 text-blue-600" />
                </div>
                <h1 className="text-xl font-bold text-slate-900">Vérification de l&apos;identité</h1>
                <p className="text-sm text-slate-500 mt-1.5">
                  Un code à 6 chiffres a été envoyé à{" "}
                  <span className="font-semibold text-slate-700">{email}</span>
                </p>
              </div>

              <div className="space-y-4">
                <OtpInput value={otp} onChange={setOtp} disabled={submitting} />

                {error && <div className="alert-error text-center text-sm">{error}</div>}

                <button
                  onClick={handleOtpSubmit}
                  disabled={submitting || otp.length !== 6}
                  className="btn-primary w-full py-2.5"
                >
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                  Vérifier le code
                </button>

                <div className="flex items-center justify-between text-sm">
                  <button
                    type="button"
                    onClick={() => { setStep(1); setOtp(""); setError(null); }}
                    className="text-slate-500 hover:text-slate-700 flex items-center gap-1"
                  >
                    <ArrowLeft className="w-3.5 h-3.5" />
                    Changer d&apos;email
                  </button>

                  <button
                    type="button"
                    onClick={handleResend}
                    disabled={resendCooldown > 0 || submitting}
                    className="text-blue-600 hover:text-blue-700 disabled:text-slate-400 disabled:cursor-not-allowed font-medium"
                  >
                    {resendCooldown > 0 ? `Renvoyer dans ${resendCooldown}s` : "Renvoyer le code"}
                  </button>
                </div>
              </div>
            </>

          ) : (
            /* ── Étape 3 : Nouveau mot de passe ──────────────────────────── */
            <>
              <StepBar current={3} />

              <div>
                <h1 className="text-xl font-bold text-slate-900">Nouveau mot de passe</h1>
                <p className="text-sm text-slate-500 mt-1.5">
                  Choisissez un mot de passe sécurisé. Il doit contenir au moins 8 caractères,
                  une majuscule et un chiffre.
                </p>
              </div>

              <form onSubmit={passwordForm.handleSubmit(handlePasswordSubmit)} className="space-y-4">
                <div>
                  <label className="label">Nouveau mot de passe</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                    <input
                      {...passwordForm.register("new_password")}
                      type={showPwd ? "text" : "password"}
                      autoComplete="new-password"
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
                  {passwordForm.formState.errors.new_password && (
                    <p className="field-error">{passwordForm.formState.errors.new_password.message}</p>
                  )}
                </div>

                <div>
                  <label className="label">Confirmer le mot de passe</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                    <input
                      {...passwordForm.register("confirm_password")}
                      type={showConfirm ? "text" : "password"}
                      autoComplete="new-password"
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
                  {passwordForm.formState.errors.confirm_password && (
                    <p className="field-error">{passwordForm.formState.errors.confirm_password.message}</p>
                  )}
                </div>

                {error && <div className="alert-error">{error}</div>}

                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-primary w-full py-2.5"
                >
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
                  Définir le mot de passe
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
