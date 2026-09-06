"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { commandesApi } from "@/lib/api/commandes";
import { clientsApi } from "@/lib/api/clients";
import { amountToCents, formatMoney } from "@/lib/utils/money";
import { Loader2, ArrowLeft, Plus, Trash2, ShoppingCart, UserPlus, X } from "lucide-react";
import Link from "next/link";
import { Suspense, useState } from "react";

// ─── Schemas ──────────────────────────────────────────────────────────────────

const itemSchema = z.object({
  description: z.string().min(1, "Requis").max(1000),
  quantity: z.coerce.number().int("Entier requis").positive("Quantité > 0"),
  unit_price: z.coerce.number().min(0, "Prix ≥ 0"),
  unit: z.string().max(20).optional().or(z.literal("")),
});

const schema = z.object({
  client_id: z.string().uuid("Sélectionner un client"),
  items: z.array(itemSchema).min(1, "Ajouter au moins une ligne"),
  notes: z.string().max(1000).optional(),
  tax_rate: z.coerce.number().min(0).max(100).optional(),
});
type FormData = z.infer<typeof schema>;

const newClientSchema = z.object({
  full_name: z.string().min(1, "Nom requis"),
  phone: z.string().min(1, "Téléphone requis"),
  client_type: z.enum(["individual", "company", "government", "ngo"]),
  company_name: z.string().optional(),
  email: z.string().email("Email invalide").optional().or(z.literal("")),
});
type NewClientData = z.infer<typeof newClientSchema>;

// ─── Mini-modal création client ───────────────────────────────────────────────

function CreateClientModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (id: string, label: string) => void;
}) {
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<NewClientData>({
    resolver: zodResolver(newClientSchema),
    defaultValues: { client_type: "individual" },
  });
  const clientType = watch("client_type");

  const { mutate, isPending, error } = useMutation({
    mutationFn: (data: NewClientData) =>
      clientsApi.create({
        full_name: data.full_name,
        phone: data.phone,
        client_type: data.client_type,
        company_name: data.company_name || undefined,
        email: data.email || undefined,
      }),
    onSuccess: (client) => {
      const label = client.full_name + (client.company_name ? ` — ${client.company_name}` : "");
      onCreated(client.id, label);
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-2 backdrop-blur-sm sm:items-center sm:p-4">
      <div className="max-h-[calc(100dvh-1rem)] w-full max-w-md space-y-4 overflow-y-auto rounded-2xl bg-white p-4 shadow-xl sm:p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900">Nouveau client</h2>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg">
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>

        <form onSubmit={handleSubmit((d) => mutate(d))} className="space-y-3">
          <div>
            <label className="label">Type *</label>
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

          {clientType === "company" && (
            <div>
              <label className="label">Société</label>
              <input {...register("company_name")} placeholder="ACME SARL" className="input" />
            </div>
          )}

          <div>
            <label className="label">Téléphone *</label>
            <input {...register("phone")} placeholder="+237 6XX XXX XXX" className="input" />
            {errors.phone && <p className="text-red-500 text-xs mt-1">{errors.phone.message}</p>}
          </div>

          <div>
            <label className="label">Email (optionnel)</label>
            <input {...register("email")} type="email" placeholder="jean@example.com" className="input" />
            {errors.email && <p className="text-red-500 text-xs mt-1">{errors.email.message}</p>}
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2 rounded-lg">
              {(error as any)?.response?.data?.detail ?? "Erreur lors de la création"}
            </div>
          )}

          <div className="flex flex-col-reverse justify-end gap-2 pt-1 sm:flex-row [&>*]:w-full sm:[&>*]:w-auto">
            <button type="button" onClick={onClose} className="btn-secondary text-sm py-1.5">
              Annuler
            </button>
            <button type="submit" disabled={isPending} className="btn-primary text-sm py-1.5">
              {isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <UserPlus className="w-3.5 h-3.5" />}
              Enregistrer
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Formulaire principal ─────────────────────────────────────────────────────

function NewCommandeForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedClientId = searchParams.get("client_id") ?? "";
  const qc = useQueryClient();

  const [showNewClient, setShowNewClient] = useState(false);
  const [extraClient, setExtraClient] = useState<{ id: string; label: string } | null>(null);

  const { data: clients } = useQuery({
    queryKey: ["clients", "all"],
    queryFn: () => clientsApi.list({ limit: 100 }),
  });

  const {
    register,
    handleSubmit,
    control,
    watch,
    setValue,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      client_id: preselectedClientId,
      items: [{ description: "", quantity: 1, unit_price: 0 }],
      notes: "",
      tax_rate: 0,
    },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "items" });

  const watchItems = watch("items");
  const watchTaxRate = watch("tax_rate") ?? 0;
  const subtotal = watchItems.reduce(
    (sum, l) => sum + (Number(l.quantity) || 0) * (Number(l.unit_price) || 0),
    0
  );
  const taxAmount = subtotal * (watchTaxRate / 100);
  const total = subtotal + taxAmount;

  const { mutate, isPending, error } = useMutation({
    mutationFn: (data: FormData) =>
      commandesApi.create({
        client_id: data.client_id,
        tax_rate: data.tax_rate,
        notes: data.notes || undefined,
        items: data.items.map((l) => ({
          description: l.description,
          quantity: l.quantity,
          unit_price_cents: amountToCents(l.unit_price),
          unit: l.unit || undefined,
        })),
      }),
    onSuccess: (commande) => {
      qc.invalidateQueries({ queryKey: ["commandes"] });
      qc.invalidateQueries({ queryKey: ["clients", "all"] });
      router.push(`/commandes/${commande.id}`);
    },
  });

  // Fusion : clients de l'API + éventuel client nouvellement créé
  const allClients = [
    ...(clients?.items ?? []),
    ...(extraClient && !clients?.items.find((c) => c.id === extraClient.id)
      ? [{ id: extraClient.id, full_name: extraClient.label, company_name: null }]
      : []),
  ];

  return (
    <div className="min-w-0 max-w-3xl space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/commandes" className="btn-secondary py-1.5 px-3">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Nouvelle commande</h1>
          <p className="text-sm text-gray-500">Créer un bon de commande</p>
        </div>
      </div>

      <form onSubmit={handleSubmit((d) => mutate(d))} className="space-y-5">
        {/* Client */}
        <div className="card p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="font-semibold text-gray-900">Client</h2>
            <button
              type="button"
              onClick={() => setShowNewClient(true)}
              className="btn-secondary w-full py-1.5 text-xs sm:w-auto"
            >
              <UserPlus className="w-3.5 h-3.5" />
              Nouveau client
            </button>
          </div>
          <div>
            <label className="label">Sélectionner un client *</label>
            <select {...register("client_id")} className="input">
              <option value="">— Choisir un client —</option>
              {allClients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.full_name}{c.company_name ? ` — ${c.company_name}` : ""}
                </option>
              ))}
            </select>
            {errors.client_id && (
              <p className="text-red-500 text-xs mt-1">{errors.client_id.message}</p>
            )}
          </div>
        </div>

        {/* Lignes */}
        <div className="card p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="font-semibold text-gray-900">Lignes de commande</h2>
            <button
              type="button"
              onClick={() => append({ description: "", quantity: 1, unit_price: 0 })}
              className="btn-secondary w-full py-1.5 text-xs sm:w-auto"
            >
              <Plus className="w-3.5 h-3.5" />
              Ajouter une ligne
            </button>
          </div>

          {errors.items && typeof errors.items.message === "string" && (
            <p className="text-red-500 text-xs mb-3">{errors.items.message}</p>
          )}

          <div className="space-y-3">
            {fields.map((field, i) => (
              <div key={field.id} className="grid grid-cols-1 sm:grid-cols-12 gap-2 items-start">
                <div className="sm:col-span-6">
                  <label className={`label ${i !== 0 ? "sm:hidden" : ""}`}>Description</label>
                  <input
                    {...register(`items.${i}.description`)}
                    placeholder="Description du produit/service"
                    className="input text-sm"
                  />
                  {errors.items?.[i]?.description && (
                    <p className="text-red-500 text-xs mt-1">
                      {errors.items[i]?.description?.message}
                    </p>
                  )}
                </div>
                <div className="sm:col-span-2">
                  <label className={`label ${i !== 0 ? "sm:hidden" : ""}`}>Qté</label>
                  <input
                    {...register(`items.${i}.quantity`)}
                    type="number"
                    min={1}
                    step={1}
                    className="input text-sm"
                  />
                  {errors.items?.[i]?.quantity && (
                    <p className="text-red-500 text-xs mt-1">
                      {errors.items[i]?.quantity?.message}
                    </p>
                  )}
                </div>
                <div className="sm:col-span-3">
                  <label className={`label ${i !== 0 ? "sm:hidden" : ""}`}>Prix unitaire</label>
                  <input
                    {...register(`items.${i}.unit_price`)}
                    type="number"
                    min={0}
                    step={1}
                    placeholder="0"
                    className="input text-sm"
                  />
                </div>
                <div className={`sm:col-span-1 ${i === 0 ? "sm:mt-6" : ""} flex items-center sm:block`}>
                  <button
                    type="button"
                    onClick={() => remove(i)}
                    disabled={fields.length === 1}
                    className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-30"
                    title="Supprimer"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* TVA */}
          <div className="mt-4 space-y-3">
            <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
              <input
                type="checkbox"
                checked={watchTaxRate > 0}
                onChange={(event) => setValue("tax_rate", event.target.checked ? 19.25 : 0)}
              />
              Appliquer la TVA à cette commande
            </label>
            {watchTaxRate > 0 && <div>
              <label className="label">Taux TVA (%)</label>
              <input {...register("tax_rate")} type="number" min={0.01} max={100} step={0.01} className="input w-32 text-sm" />
            </div>}
          </div>

          {/* Totaux */}
          <div className="mt-5 pt-4 border-t border-gray-100 space-y-1.5 text-sm">
            <div className="flex justify-between text-gray-600">
              <span>Sous-total HT</span>
              <span>{formatMoney(subtotal)}</span>
            </div>
            <div className="flex justify-between text-gray-600">
              <span>TVA ({watchTaxRate}%)</span>
              <span>{formatMoney(taxAmount)}</span>
            </div>
            <div className="flex justify-between font-semibold text-gray-900 text-base pt-1 border-t border-gray-100">
              <span>Total TTC</span>
              <span>{formatMoney(total)}</span>
            </div>
          </div>
        </div>

        {/* Notes */}
        <div className="card p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Notes (optionnel)</h2>
          <textarea
            {...register("notes")}
            rows={3}
            placeholder="Instructions de livraison, conditions particulières…"
            className="input resize-none"
          />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg">
            {(error as any)?.response?.data?.detail ?? "Erreur lors de la création"}
          </div>
        )}

        <div className="flex flex-col-reverse justify-end gap-3 sm:flex-row [&>*]:w-full sm:[&>*]:w-auto">
          <Link href="/commandes" className="btn-secondary">Annuler</Link>
          <button type="submit" disabled={isPending} className="btn-primary">
            {isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShoppingCart className="w-4 h-4" />}
            Créer la commande
          </button>
        </div>
      </form>

      {showNewClient && (
        <CreateClientModal
          onClose={() => setShowNewClient(false)}
          onCreated={(id, label) => {
            setExtraClient({ id, label });
            setValue("client_id", id, { shouldValidate: true });
            qc.invalidateQueries({ queryKey: ["clients", "all"] });
            setShowNewClient(false);
          }}
        />
      )}
    </div>
  );
}

export default function NewCommandePage() {
  return (
    <Suspense fallback={<div className="flex justify-center py-16"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>}>
      <NewCommandeForm />
    </Suspense>
  );
}
