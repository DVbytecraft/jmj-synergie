"use client";

import { useRouter, useParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useProduit, useUpdateProduit } from "@/lib/hooks/use-produits";
import { amountToCents, centsToAmount } from "@/lib/utils/money";
import { ArrowLeft, Loader2, Package } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

const schema = z.object({
  name: z.string().min(1, "Nom requis").max(255),
  description: z.string().optional().or(z.literal("")),
  unit_price: z.coerce.number().min(0, "Prix ≥ 0"),
  tax_rate: z.coerce.number().min(0).max(100),
  unit: z.string().min(1).max(20),
  category: z.string().max(100).optional().or(z.literal("")),
});

type FormValues = z.infer<typeof schema>;

export default function ProduitDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: produit, isLoading } = useProduit(id);
  const updateMut = useUpdateProduit(id);

  const { register, handleSubmit, reset, watch, setValue, formState: { errors, isDirty, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
  });
  const taxRate = watch("tax_rate") ?? 0;

  useEffect(() => {
    if (produit) {
      reset({
        name: produit.name,
        description: produit.description ?? "",
        unit_price: centsToAmount(produit.unit_price_cents),
        tax_rate: produit.tax_rate,
        unit: produit.unit ?? "unité",
        category: produit.category ?? "",
      });
    }
  }, [produit, reset]);

  const onSubmit = async (data: FormValues) => {
    await updateMut.mutateAsync({
      name: data.name,
      unit_price_cents: amountToCents(data.unit_price),
      description: data.description || undefined,
      tax_rate: data.tax_rate,
      unit: data.unit,
      category: data.category || undefined,
    });
    router.push("/produits");
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!produit) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-400 gap-3">
        <Package className="w-10 h-10" />
        <p>Produit introuvable</p>
        <Link href="/produits" className="btn-secondary">Retour</Link>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link href="/produits" className="p-2 rounded-lg hover:bg-gray-100 text-gray-500">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{produit.name}</h1>
          <p className="text-sm text-gray-500 font-mono">{produit.code}</p>
        </div>
        <span className={`sm:ml-auto text-xs font-medium px-2 py-0.5 rounded-full ${
          produit.status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
        }`}>
          {produit.status === "active" ? "Actif" : "Inactif"}
        </span>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="card p-4 sm:p-6 space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2 space-y-1">
            <label className="label">Nom *</label>
            <input {...register("name")} className="input" />
            {errors.name && <p className="text-red-500 text-xs">{errors.name.message}</p>}
          </div>

          <div className="space-y-1">
            <label className="label">Prix unitaire HT (XAF) *</label>
            <input {...register("unit_price")} type="number" min={0} step={1} className="input" />
            {errors.unit_price && <p className="text-red-500 text-xs">{errors.unit_price.message}</p>}
          </div>

          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
              <input type="checkbox" checked={taxRate > 0} onChange={(event) => setValue("tax_rate", event.target.checked ? 19.25 : 0, { shouldDirty: true })} />
              Appliquer la TVA
            </label>
            {taxRate > 0 && <input {...register("tax_rate")} aria-label="Taux TVA" type="number" min={0.01} max={100} step={0.01} className="input" />}
            {errors.tax_rate && <p className="text-red-500 text-xs">{errors.tax_rate.message}</p>}
          </div>

          <div className="space-y-1">
            <label className="label">Unité</label>
            <input {...register("unit")} className="input" />
          </div>

          <div className="space-y-1">
            <label className="label">Catégorie</label>
            <input {...register("category")} className="input" placeholder="Optionnel" />
          </div>
        </div>

        <div className="space-y-1">
          <label className="label">Description</label>
          <textarea {...register("description")} rows={3} className="input resize-none" />
        </div>

        {updateMut.error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg">
            {(updateMut.error as any)?.response?.data?.detail ?? "Erreur lors de la mise à jour"}
          </div>
        )}

        <div className="flex justify-end gap-3 pt-2 border-t border-gray-100">
          <Link href="/produits" className="btn-secondary">Annuler</Link>
          <button
            type="submit"
            disabled={!isDirty || isSubmitting || updateMut.isPending}
            className="btn-primary"
          >
            {(isSubmitting || updateMut.isPending) && <Loader2 className="w-4 h-4 animate-spin" />}
            Enregistrer
          </button>
        </div>
      </form>
    </div>
  );
}
