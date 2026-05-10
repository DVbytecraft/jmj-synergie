"use client";

import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { clientsApi } from "@/lib/api/clients";
import { Loader2, ArrowLeft, UserPlus } from "lucide-react";
import Link from "next/link";

const schema = z.object({
  client_type: z.enum(["individual", "company", "government", "ngo"]),
  full_name: z.string().min(2, "Minimum 2 caractères").max(255),
  phone: z.string().min(6, "Minimum 6 chiffres").max(30),
  email: z.string().email("Email invalide").optional().or(z.literal("")),
  company_name: z.string().max(255).optional().or(z.literal("")),
  address_line1: z.string().max(255).optional().or(z.literal("")),
  city: z.string().max(100).optional().or(z.literal("")),
  country: z.string().length(2).optional(),
  notes: z.string().max(2000).optional().or(z.literal("")),
});
type FormData = z.infer<typeof schema>;

export default function NewClientPage() {
  const router = useRouter();
  const qc = useQueryClient();

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { client_type: "individual", country: "CM" },
  });

  const { mutate, isPending, error } = useMutation({
    mutationFn: (data: FormData) =>
      clientsApi.create({
        ...data,
        email: data.email || undefined,
        company_name: data.company_name || undefined,
        address_line1: data.address_line1 || undefined,
        city: data.city || undefined,
        notes: data.notes || undefined,
      }),
    onSuccess: (client) => {
      qc.invalidateQueries({ queryKey: ["clients"] });
      router.push(`/clients/${client.id}`);
    },
  });

  return (
    <div className="max-w-2xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link href="/clients" className="btn-secondary py-1.5 px-3">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Nouveau client</h1>
          <p className="text-sm text-gray-500">Créer un nouveau compte client</p>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit((d) => mutate(d))} className="card p-6 space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div>
            <label className="label">Type de client *</label>
            <select {...register("client_type")} className="input">
              <option value="individual">Particulier</option>
              <option value="company">Entreprise</option>
              <option value="government">Administration</option>
              <option value="ngo">ONG</option>
            </select>
          </div>

          <div>
            <label className="label">Nom complet *</label>
            <input {...register("full_name")} placeholder="Jean Dupont" className="input" />
            {errors.full_name && <p className="text-red-500 text-xs mt-1">{errors.full_name.message}</p>}
          </div>

          <div>
            <label className="label">Téléphone *</label>
            <input {...register("phone")} placeholder="+237 6 12 34 56 78" className="input" />
            {errors.phone && <p className="text-red-500 text-xs mt-1">{errors.phone.message}</p>}
          </div>

          <div>
            <label className="label">Email</label>
            <input {...register("email")} type="email" placeholder="client@exemple.com" className="input" />
            {errors.email && <p className="text-red-500 text-xs mt-1">{errors.email.message}</p>}
          </div>

          <div>
            <label className="label">Entreprise / Raison sociale</label>
            <input {...register("company_name")} placeholder="ACME Sarl" className="input" />
          </div>

          <div>
            <label className="label">Ville</label>
            <input {...register("city")} placeholder="Douala" className="input" />
          </div>
        </div>

        <div>
          <label className="label">Adresse</label>
          <textarea
            {...register("address_line1")}
            rows={2}
            placeholder="123 rue de la Paix"
            className="input resize-none"
          />
        </div>

        <div>
          <label className="label">Notes</label>
          <textarea
            {...register("notes")}
            rows={2}
            placeholder="Informations complémentaires…"
            className="input resize-none"
          />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg">
            {(error as any)?.response?.data?.detail ?? "Erreur lors de la création"}
          </div>
        )}

        <div className="flex gap-3 justify-end pt-2 border-t border-gray-100">
          <Link href="/clients" className="btn-secondary">Annuler</Link>
          <button type="submit" disabled={isPending} className="btn-primary">
            {isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />}
            Créer le client
          </button>
        </div>
      </form>
    </div>
  );
}
