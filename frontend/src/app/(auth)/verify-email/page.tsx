"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, Mail, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";
import { useAuthStore } from "@/store/auth.store";
import { apiClient } from "@/lib/api/client";
import { organizationsApi } from "@/lib/api/organizations";

const RESEND_DELAY = 60;
const CODE_LENGTH = 6;

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const email = searchParams.get("email") ?? "";
  const router = useRouter();
  const { setAuth } = useAuthStore();

  const [digits, setDigits] = useState<string[]>(Array(CODE_LENGTH).fill(""));
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [success, setSuccess] = useState(false);
  const [countdown, setCountdown] = useState(RESEND_DELAY);
  const [resending, setResending] = useState(false);
  const [resendMessage, setResendMessage] = useState<string | null>(null);

  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (countdown <= 0) return;
    const id = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(id);
  }, [countdown]);

  const uploadPendingLogo = useCallback(async () => {
    try {
      const b64 = sessionStorage.getItem("biloz_pending_logo");
      if (!b64) return;
      const res = await fetch(b64);
      const blob = await res.blob();
      const ext = blob.type === "image/png" ? "png" : blob.type === "image/webp" ? "webp" : "jpg";
      const file = new File([blob], `logo.${ext}`, { type: blob.type });
      await organizationsApi.uploadLogo(file);
      sessionStorage.removeItem("biloz_pending_logo");
    } catch {
      // non-blocking — logo can be uploaded later in settings
    }
  }, []);

  const verify = useCallback(
    async (code: string) => {
      if (code.length !== CODE_LENGTH) return;
      setVerifying(true);
      setError(null);
      try {
        const res = await apiClient.post("/auth/verify-email", { email, code });
        setAuth(res.data.access_token);
        await uploadPendingLogo();
        setSuccess(true);
        setTimeout(() => router.replace("/dashboard"), 1200);
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: unknown } } };
        const status = (e as any)?.response?.status;
        const detail = err.response?.data?.detail;
        if (detail === "EMAIL_ALREADY_VERIFIED" || status === 409) {
          // Account already verified — go to normal login
          router.replace("/login");
          return;
        } else if (detail === "INVALID_OTP") {
          setError("Code incorrect. Vérifiez et réessayez.");
        } else if (detail === "OTP_EXPIRED") {
          setError("Ce code a expiré. Demandez-en un nouveau.");
        } else if (detail === "TOO_MANY_ATTEMPTS") {
          setError("Trop de tentatives. Demandez un nouveau code.");
        } else {
          setError(typeof detail === "string" ? detail : "Une erreur est survenue.");
        }
        setDigits(Array(CODE_LENGTH).fill(""));
        setTimeout(() => inputRefs.current[0]?.focus(), 50);
      } finally {
        setVerifying(false);
      }
    },
    [email, router, setAuth, uploadPendingLogo]
  );

  const handleChange = (index: number, value: string) => {
    const char = value.replace(/\D/g, "").slice(-1);
    const next = [...digits];
    next[index] = char;
    setDigits(next);
    setError(null);

    if (char && index < CODE_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus();
    }

    const code = next.join("");
    if (code.length === CODE_LENGTH && !next.includes("")) {
      verify(code);
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, CODE_LENGTH);
    if (!pasted) return;
    const next = Array(CODE_LENGTH).fill("");
    pasted.split("").forEach((c, i) => { next[i] = c; });
    setDigits(next);
    setError(null);
    const focusIdx = Math.min(pasted.length, CODE_LENGTH - 1);
    setTimeout(() => inputRefs.current[focusIdx]?.focus(), 0);
    if (pasted.length === CODE_LENGTH) {
      verify(pasted);
    }
  };

  const handleResend = async () => {
    if (countdown > 0 || resending) return;
    setResending(true);
    setResendMessage(null);
    setError(null);
    try {
      await apiClient.post("/auth/resend-verification", { email });
    } catch {
      // anti-enumeration: always show success
    } finally {
      setResendMessage("Un nouveau code vous a été envoyé.");
      setCountdown(RESEND_DELAY);
      setDigits(Array(CODE_LENGTH).fill(""));
      setTimeout(() => inputRefs.current[0]?.focus(), 50);
      setResending(false);
    }
  };

  if (!email) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-center space-y-3">
          <AlertCircle className="w-10 h-10 text-red-400 mx-auto" />
          <p className="text-slate-700 font-medium">Lien invalide — email manquant.</p>
          <a href="/register" className="text-blue-600 text-sm hover:underline">Retour à l'inscription</a>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-8 h-8 text-emerald-600" />
          </div>
          <h2 className="text-xl font-bold text-gray-900">Email vérifié !</h2>
          <p className="text-gray-500 text-sm">Redirection vers votre tableau de bord…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-4">
      <div className="w-full max-w-[400px]">
        <div className="flex items-center gap-3 mb-10 justify-center">
          <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center">
            <span className="text-white font-bold text-sm">B</span>
          </div>
          <span className="text-slate-900 font-semibold text-lg">Biloz</span>
        </div>

        <div className="text-center mb-8">
          <div className="w-14 h-14 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <Mail className="w-7 h-7 text-blue-600" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Vérifiez votre email</h1>
          <p className="text-slate-500 text-sm mt-2 leading-relaxed">
            Un code à 6 chiffres a été envoyé à<br />
            <span className="font-medium text-slate-700">{email}</span>
          </p>
        </div>

        <div className="flex gap-2.5 justify-center mb-6" onPaste={handlePaste}>
          {digits.map((d, i) => (
            <input
              key={i}
              ref={(el) => { inputRefs.current[i] = el; }}
              type="text"
              inputMode="numeric"
              pattern="\d*"
              maxLength={1}
              value={d}
              onChange={(e) => handleChange(i, e.target.value)}
              onKeyDown={(e) => handleKeyDown(i, e)}
              disabled={verifying}
              className={[
                "w-12 h-14 text-center text-xl font-bold rounded-xl border-2 outline-none transition-all",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                error
                  ? "border-red-300 bg-red-50 text-red-700"
                  : d
                    ? "border-blue-400 bg-blue-50 text-slate-900"
                    : "border-slate-200 bg-white text-slate-900 focus:border-blue-500 focus:bg-blue-50/40",
              ].join(" ")}
            />
          ))}
        </div>

        {verifying && (
          <div className="flex justify-center mb-4">
            <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 mb-4">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            {error}
          </div>
        )}

        {resendMessage && !error && (
          <div className="flex items-start gap-2 rounded-lg bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700 mb-4">
            <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0" />
            {resendMessage}
          </div>
        )}

        <div className="text-center">
          <p className="text-sm text-slate-500 mb-2">Vous n'avez pas reçu le code ?</p>
          <button
            type="button"
            onClick={handleResend}
            disabled={countdown > 0 || resending}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:underline disabled:text-slate-400 disabled:no-underline disabled:cursor-not-allowed transition-colors"
          >
            {resending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <RefreshCw className="w-3.5 h-3.5" />
            )}
            {countdown > 0 ? `Renvoyer dans ${countdown}s` : "Renvoyer le code"}
          </button>
        </div>

        <p className="text-center text-xs text-slate-400 mt-8">
          <a href="/register" className="hover:underline">Retour à l'inscription</a>
        </p>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-white">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    }>
      <VerifyEmailContent />
    </Suspense>
  );
}
