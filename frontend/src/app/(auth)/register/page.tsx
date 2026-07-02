"use client";

import Link from "next/link";
import { Lock, ShieldAlert } from "lucide-react";

export default function RegisterPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-6">
      <div className="w-full max-w-xl rounded-3xl border border-white/10 bg-white p-8 shadow-2xl">
        <div className="mb-6 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-100 text-amber-700">
          <ShieldAlert className="h-7 w-7" />
        </div>

        <h1 className="text-3xl font-bold text-slate-900">Inscriptions désactivées</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          Cette application fonctionne désormais pour une seule entreprise avec un compte principal.
          La création de nouveaux espaces et de nouveaux utilisateurs n&apos;est plus disponible.
        </p>

        <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
          Utilisez le mot de passe du compte administrateur principal pour accéder à la plateforme,
          gérer les clients, les commandes, les paiements et les documents.
        </div>

        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Link href="/login" className="btn-primary justify-center sm:flex-1">
            <Lock className="h-4 w-4" />
            Aller à la connexion
          </Link>
        </div>
      </div>
    </div>
  );
}
