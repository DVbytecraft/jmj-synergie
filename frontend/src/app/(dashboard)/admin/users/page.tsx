"use client";

import Link from "next/link";
import { Building2, Lock, ShieldAlert, UserCog } from "lucide-react";

export default function AdminUsersPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="bg-slate-950 px-8 py-10 text-white">
          <div className="mb-4 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10">
            <ShieldAlert className="h-7 w-7 text-amber-300" />
          </div>
          <h1 className="text-3xl font-bold">Mode entreprise unique activé</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
            La gestion multi-utilisateurs et multi-entreprises a été retirée pour cette installation.
            L&apos;application fonctionne avec un seul compte principal pour toute l&apos;entreprise.
          </p>
        </div>

        <div className="grid gap-4 px-8 py-8 md:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
            <UserCog className="mb-3 h-5 w-5 text-slate-700" />
            <h2 className="font-semibold text-slate-900">Compte unique</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Un seul utilisateur administrateur pilote les clients, produits, commandes et paiements.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
            <Lock className="mb-3 h-5 w-5 text-slate-700" />
            <h2 className="font-semibold text-slate-900">Connexion simplifiée</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Plus d&apos;inscription ni de création de comptes. L&apos;accès se fait avec le mot de passe principal.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
            <Building2 className="mb-3 h-5 w-5 text-slate-700" />
            <h2 className="font-semibold text-slate-900">Entreprise unique</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Toute la configuration de l&apos;entreprise se gère depuis le profil et les paramètres.
            </p>
          </div>
        </div>

        <div className="border-t border-slate-200 px-8 py-6">
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link href="/dashboard" className="btn-primary justify-center sm:w-auto">
              Retour au tableau de bord
            </Link>
            <Link href="/settings" className="btn-secondary justify-center sm:w-auto">
              Ouvrir les paramètres
            </Link>
            <Link href="/profil" className="btn-secondary justify-center sm:w-auto">
              Voir le profil
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
