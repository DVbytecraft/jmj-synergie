"use client";

import Link from "next/link";
import { MailCheck } from "lucide-react";

export default function VerifyEmailPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-4">
      <div className="w-full max-w-md text-center space-y-5">
        <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mx-auto">
          <MailCheck className="w-8 h-8 text-blue-600" />
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-slate-900">Vérification non requise</h1>
          <p className="text-sm text-slate-500">
            Le protocole OTP a été supprimé. Votre compte peut être utilisé directement après inscription.
          </p>
        </div>
        <div className="flex flex-col gap-3">
          <Link href="/login" className="btn-primary w-full justify-center">
            Aller à la connexion
          </Link>
          <Link href="/register" className="text-sm text-slate-500 hover:text-slate-700">
            Retour à l'inscription
          </Link>
        </div>
      </div>
    </div>
  );
}
