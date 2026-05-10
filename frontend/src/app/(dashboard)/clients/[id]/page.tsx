"use client";

import { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { clientsApi } from "@/lib/api/clients";
import { commandesApi } from "@/lib/api/commandes";
import {
  ArrowLeft, Mail, Phone, MapPin, Calendar, Edit3,
  ShoppingCart, Loader2, Save, X, Building2
} from "lucide-react";
import Link from "next/link";
import { OrderStatusBadge } from "@/components/ui/OrderStatusBadge";
import { formatCents } from "@/lib/utils/money";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

const editSchema = z.object({
  full_name: z.string().min(2).max(255).optional(),
  email: z.string().email().optional().or(z.literal("")),
  phone: z.string().min(6).max(30).optional(),
  address_line1: z.string().max(255).optional().or(z.literal("")),
  city: z.string().max(100).optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
});
type EditForm = z.infer<typeof editSchema>;

export default function ClientDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [editing, setEditing] = useState(false);
  const qc = useQueryClient();

  const { data: client, isLoading } = useQuery({
    queryKey: ["clients", id],
    queryFn: () => clientsApi.get(id),
  });

  const { data: commandes, isLoading: loadingCmds } = useQuery({
    queryKey: ["commandes", "client", id],
    queryFn: () => commandesApi.byClient(id),
  });

  const { register, handleSubmit, reset, formState: { errors } } = useForm<EditForm>({
    resolver: zodResolver(editSchema),
    values: client
      ? {
          full_name: client.full_name,
          email: client.email ?? "",
          phone: client.phone,
          address_line1: client.address_line1 ?? "",
          city: client.city ?? "",
          notes: client.notes ?? "",
        }
      : undefined,
  });

  const updateMut = useMutation({
    mutationFn: (data: EditForm) =>
      clientsApi.update(id, {
        ...data,
        email: data.email || undefined,
        address_line1: data.address_line1 || undefined,
        city: data.city || undefined,
        notes: data.notes || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clients", id] });
      setEditing(false);
    },
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!client) {
    return <div className="text-center py-16 text-gray-400">Client introuvable</div>;
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <Link href="/clients" className="btn-secondary py-1.5 px-3">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-bold text-gray-900 truncate">{client.full_name}</h1>
          <p className="text-sm text-gray-500 font-mono">{client.code}</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {editing ? (
            <>
              <button onClick={() => { setEditing(false); reset(); }} className="btn-secondary">
                <X className="w-4 h-4" /> Annuler
              </button>
              <button
                onClick={handleSubmit((d) => updateMut.mutate(d))}
                disabled={updateMut.isPending}
                className="btn-primary"
              >
                {updateMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Enregistrer
              </button>
            </>
          ) : (
            <button onClick={() => setEditing(true)} className="btn-secondary">
              <Edit3 className="w-4 h-4" /> Modifier
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Client info */}
        <div className="lg:col-span-1 card p-6 space-y-5">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-blue-700 rounded-full flex items-center justify-center text-white font-bold text-xl">
              {client.full_name.charAt(0).toUpperCase()}
            </div>
            <div>
              {!editing && <p className="font-semibold text-gray-900">{client.full_name}</p>}
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${client.status === "active" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                {client.status === "active" ? "Actif" : "Inactif"}
              </span>
            </div>
          </div>

          {editing ? (
            <form className="space-y-4">
              <div>
                <label className="label">Nom complet</label>
                <input {...register("full_name")} className="input" />
                {errors.full_name && <p className="text-red-500 text-xs mt-1">{errors.full_name.message}</p>}
              </div>
              <div>
                <label className="label">Email</label>
                <input {...register("email")} type="email" className="input" />
              </div>
              <div>
                <label className="label">Téléphone</label>
                <input {...register("phone")} className="input" />
              </div>
              <div>
                <label className="label">Adresse</label>
                <input {...register("address_line1")} className="input" />
              </div>
              <div>
                <label className="label">Ville</label>
                <input {...register("city")} className="input" />
              </div>
              <div>
                <label className="label">Notes</label>
                <textarea {...register("notes")} rows={2} className="input resize-none" />
              </div>
            </form>
          ) : (
            <div className="space-y-3 text-sm">
              {client.company_name && (
                <div className="flex items-center gap-3 text-gray-600">
                  <Building2 className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  <span>{client.company_name}</span>
                </div>
              )}
              {client.email && (
                <div className="flex items-center gap-3 text-gray-600">
                  <Mail className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  <a href={`mailto:${client.email}`} className="hover:text-blue-600 truncate">{client.email}</a>
                </div>
              )}
              <div className="flex items-center gap-3 text-gray-600">
                <Phone className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <a href={`tel:${client.phone}`} className="hover:text-blue-600">{client.phone}</a>
              </div>
              {client.address_line1 && (
                <div className="flex items-start gap-3 text-gray-600">
                  <MapPin className="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" />
                  <span>{client.address_line1}{client.city ? `, ${client.city}` : ""}</span>
                </div>
              )}
              <div className="flex items-center gap-3 text-gray-400">
                <Calendar className="w-4 h-4 flex-shrink-0" />
                <span>Créé le {new Date(client.created_at).toLocaleDateString("fr-FR")}</span>
              </div>
            </div>
          )}

          <div className="pt-3 border-t border-gray-100">
            <Link
              href={`/commandes/new?client_id=${client.id}`}
              className="btn-primary w-full justify-center"
            >
              <ShoppingCart className="w-4 h-4" />
              Nouvelle commande
            </Link>
          </div>
        </div>

        {/* Commandes */}
        <div className="lg:col-span-2 card overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900">
              Commandes ({commandes?.length ?? 0})
            </h2>
          </div>

          {loadingCmds ? (
            <div className="flex justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
            </div>
          ) : !commandes?.length ? (
            <div className="py-10 text-center text-gray-400 text-sm">
              Aucune commande pour ce client
            </div>
          ) : (
            <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="table-header">N°</th>
                  <th className="table-header">Statut</th>
                  <th className="table-header text-right">HT</th>
                  <th className="table-header text-right">TTC</th>
                  <th className="table-header">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {commandes.map((c) => (
                  <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                    <td className="table-cell">
                      <Link href={`/commandes/${c.id}`} className="font-mono text-blue-600 hover:text-blue-700">
                        {c.order_number}
                      </Link>
                    </td>
                    <td className="table-cell"><OrderStatusBadge status={c.status} /></td>
                    <td className="table-cell text-right">{formatCents(c.subtotal_cents, c.currency)}</td>
                    <td className="table-cell text-right font-semibold">{formatCents(c.total_cents, c.currency)}</td>
                    <td className="table-cell text-gray-400">
                      {new Date(c.created_at).toLocaleDateString("fr-FR")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
