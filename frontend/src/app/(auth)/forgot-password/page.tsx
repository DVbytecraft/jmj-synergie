"use client";

import Image from "next/image";
import Link from "next/link";
import { ArrowLeft, ShieldCheck } from "lucide-react";

export default function ForgotPasswordPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-[420px] space-y-6">
        <div className="flex items-center justify-center gap-3">
          <Image src="/logo.svg" alt="JMJ Synergie" width={36} height={36} className="w-9 h-9 rounded-xl" />
          <span className="text-slate-900 font-semibold text-lg">JMJ Synergie</span>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-card p-8 space-y-6 text-center">
          <div className="w-14 h-14 bg-blue-50 rounded-full flex items-center justify-center mx-auto">
            <ShieldCheck className="w-7 h-7 text-blue-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Récupération sécurisée</h1>
            <p className="text-sm text-slate-500 mt-2 leading-relaxed">
              Pour protéger le compte principal, sa réinitialisation est réservée à l’administrateur de l’hébergement.
              Si votre session est ouverte, modifiez votre mot de passe depuis la page Profil.
            </p>
          </div>
          <Link href="/login" className="btn-secondary w-full py-2.5 inline-flex items-center justify-center gap-2">
            <ArrowLeft className="w-4 h-4" />
            Retour à la connexion
          </Link>
        </div>
      </div>
    </div>
  );
}
