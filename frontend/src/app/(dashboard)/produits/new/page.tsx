"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useCreateProduit } from "@/lib/hooks/use-produits";
import { amountToCents } from "@/lib/utils/money";
import { ArrowLeft, Loader2, Package } from "lucide-react";
import Link from "next/link";

const schema = z.object({
  name:        z.string().min(1, "Le nom est requis").max(255),
  unit_price:  z.coerce.number({ invalid_type_error: "Prix invalide" }).min(0, "Le prix doit être ≥ 0"),
  description: z.string().max(1000).optional().or(z.literal("")),
  tax_rate:    z.coerce.number().min(0).max(100).default(0),
  unit:        z.string().min(1, "Unité requise").max(20).default("unité"),
  category:    z.string().max(100).optional().or(z.literal("")),
});

type FormValues = z.infer<typeof schema>;

/** Extrait un message lisible depuis les erreurs FastAPI (string ou tableau 422) */
function extractApiError(error: unknown): string {
  const detail = (error as any)?.response?.data?.detail;
  if (!detail) return "Une erreur est survenue lors de la création";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e: any) => {
        const field = Array.isArray(e.loc) ? e.loc.slice(1).join(" → ") : "";
        return field ? `${field} : ${e.msg}` : e.msg;
      })
      .join(" • ");
  }
  return String(detail);
}

export default function NewProduitPage() {
  const router = useRouter();
  const createMut = useCreateProduit();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { tax_rate: 0, unit: "unité" },
  });
  const taxRate = watch("tax_rate") ?? 0;

  const onSubmit = async (data: FormValues) => {
    setServerError(null);
    try {
      await createMut.mutateAsync({
        name:             data.name,
        unit_price_cents: amountToCents(data.unit_price),
        description:      data.description || undefined,
        tax_rate:         data.tax_rate,
        unit:             data.unit,
        category:         data.category || undefined,
      });
      router.push("/produits");
    } catch (err) {
      setServerError(extractApiError(err));
    }
  };

  const isPending = isSubmitting || createMut.isPending;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* En-tête */}
      <div className="flex items-center gap-3">
        <Link href="/produits" className="btn-icon">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div>
          <h1 className="page-title">Nouveau produit</h1>
          <p className="page-subtitle">Ajouter un article au catalogue</p>
        </div>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <div className="card divide-y divide-slate-100">
          {/* Section — Informations générales */}
          <div className="p-6 space-y-5">
            <div className="flex items-center gap-2 mb-1">
              <Package className="w-4 h-4 text-slate-400" />
              <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
                Informations générales
              </h2>
            </div>

            {/* Nom */}
            <div>
              <label className="label">
                Nom du produit / service <span className="text-red-500">*</span>
              </label>
              <input
                {...register("name")}
                className="input"
                placeholder="Ex : Consultation juridique, Ciment Portland 50kg…"
                autoFocus
              />
              {errors.name && <p className="field-error">{errors.name.message}</p>}
            </div>

            {/* Description */}
            <div>
              <label className="label">
                Description <span className="text-slate-400 font-normal">(optionnel)</span>
              </label>
              <textarea
                {...register("description")}
                rows={3}
                className="input resize-none"
                placeholder="Détails du produit ou service…"
              />
            </div>

            {/* Catégorie */}
            <div>
              <label className="label">
                Catégorie <span className="text-slate-400 font-normal">(optionnel)</span>
              </label>
              <input
                {...register("category")}
                className="input"
                placeholder="Ex : Matériaux, Services, Électronique…"
              />
            </div>
          </div>

          {/* Section — Tarification */}
          <div className="p-6 space-y-5">
            <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide mb-1">
              Tarification
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Prix HT */}
              <div className="sm:col-span-1">
                <label className="label">
                  Prix unitaire HT (XAF) <span className="text-red-500">*</span>
                </label>
                <input
                  {...register("unit_price")}
                  type="number"
                  min={0}
                  step={1}
                  className="input"
                  placeholder="0"
                />
                {errors.unit_price && (
                  <p className="field-error">{errors.unit_price.message}</p>
                )}
              </div>

              {/* TVA */}
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  <input
                    type="checkbox"
                    checked={taxRate > 0}
                    onChange={(event) => setValue("tax_rate", event.target.checked ? 19.25 : 0, { shouldDirty: true })}
                  />
                  Appliquer la TVA
                </label>
                {taxRate > 0 && (
                  <input {...register("tax_rate")} aria-label="Taux TVA" type="number" min={0.01} max={100} step={0.01} className="input" />
                )}
                {errors.tax_rate && <p className="field-error">{errors.tax_rate.message}</p>}
              </div>

              {/* Unité */}
              <div>
                <label className="label">
                  Unité <span className="text-red-500">*</span>
                </label>
                <input
                  {...register("unit")}
                  className="input"
                  placeholder="pièce, kg, m², heure…"
                  list="unit-suggestions"
                />
                <datalist id="unit-suggestions">
                  <option value="unité" />
                  <option value="pièce" />
                  <option value="kg" />
                  <option value="litre" />
                  <option value="m²" />
                  <option value="m³" />
                  <option value="heure" />
                  <option value="jour" />
                  <option value="forfait" />
                </datalist>
                {errors.unit && (
                  <p className="field-error">{errors.unit.message}</p>
                )}
              </div>
            </div>
          </div>

          {/* Erreur serveur */}
          {serverError && (
            <div className="px-6 py-4">
              <div className="alert-error">{serverError}</div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 px-6 py-4 bg-slate-50/60">
            <Link href="/produits" className="btn-secondary">
              Annuler
            </Link>
            <button type="submit" disabled={isPending} className="btn-primary">
              {isPending && <Loader2 className="w-4 h-4 animate-spin" />}
              {isPending ? "Création en cours…" : "Créer le produit"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
