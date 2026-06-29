"use client";

import { use, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { quotesApi } from "@/lib/api/quotes";
import { clientsApi } from "@/lib/api/clients";
import { amountToCents, formatMoney } from "@/lib/utils/money";
import { Loader2, ArrowLeft, Plus, Trash2, Save } from "lucide-react";
import Link from "next/link";

// ─── Schema ───────────────────────────────────────────────────────────────────

const itemSchema = z.object({
  description: z.string().min(1, "Requis").max(255),
  quantity: z.coerce.number().int("Entier requis").positive("Quantité > 0"),
  unit_price: z.coerce.number().min(0, "Prix ≥ 0"),
});

const schema = z.object({
  client_id: z.string().uuid("Sélectionner un client"),
  items: z.array(itemSchema).min(1, "Ajouter au moins une ligne"),
  tax_rate: z.coerce.number().min(0).max(100).optional(),
  notes: z.string().max(1000).optional(),
  valid_until: z.string().optional(),
});
type FormData = z.infer<typeof schema>;

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function DevisEditPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const qc = useQueryClient();

  const { data: quote, isLoading: quoteLoading } = useQuery({
    queryKey: ["quotes", id],
    queryFn: () => quotesApi.get(id),
  });

  const { data: clientsData } = useQuery({
    queryKey: ["clients"],
    queryFn: () => clientsApi.list({ limit: 200 }),
  });
  const clients = clientsData?.items ?? [];

  const {
    register,
    control,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { items: [{ description: "", quantity: 1, unit_price: 0 }] },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "items" });

  // Pre-populate form once quote is loaded
  useEffect(() => {
    if (!quote) return;
    if (quote.status !== "draft") {
      router.replace(`/devis/${id}`);
      return;
    }
    reset({
      client_id: quote.client_id,
      tax_rate: Number(quote.tax_rate),
      notes: quote.notes ?? "",
      valid_until: quote.valid_until ? quote.valid_until.slice(0, 10) : "",
      items: quote.items.map((i) => ({
        description: i.description,
        quantity: i.quantity,
        unit_price: i.unit_price_cents / 100,
      })),
    });
  }, [quote, id, reset, router]);

  const updateMut = useMutation({
    mutationFn: (data: FormData) =>
      quotesApi.update(id, {
        client_id: data.client_id,
        items: data.items.map((i, idx) => ({
          description: i.description,
          quantity: i.quantity,
          unit_price_cents: amountToCents(i.unit_price),
          position: idx,
        })),
        tax_rate: data.tax_rate ?? 0,
        notes: data.notes || undefined,
        valid_until: data.valid_until || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["quotes", id] });
      qc.invalidateQueries({ queryKey: ["quotes"] });
      router.push(`/devis/${id}`);
    },
  });

  const watchItems = watch("items");
  const taxRate = watch("tax_rate") ?? 0;
  const subtotal = watchItems.reduce(
    (sum, item) => sum + (Number(item.quantity) || 0) * (Number(item.unit_price) || 0),
    0,
  );
  const taxAmount = subtotal * (Number(taxRate) / 100);
  const total = subtotal + taxAmount;

  if (quoteLoading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!quote) {
    return <div className="text-center py-16 text-gray-400">Devis introuvable</div>;
  }

  return (
    <div className="max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link href={`/devis/${id}`} className="btn-secondary py-1.5 px-3">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-gray-900">Modifier le devis</h1>
          <p className="text-sm text-gray-400 font-mono">{quote.quote_number}</p>
        </div>
      </div>

      {updateMut.error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg">
          {(updateMut.error as any)?.response?.data?.detail ?? "Une erreur est survenue"}
        </div>
      )}

      <form onSubmit={handleSubmit((data) => updateMut.mutate(data))} className="space-y-6">
        {/* Client + meta */}
        <div className="card p-5 space-y-4">
          <h2 className="font-semibold text-gray-900">Informations générales</h2>

          <div>
            <label className="label">Client *</label>
            <select className="input" {...register("client_id")}>
              <option value="">Sélectionner un client</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.full_name}{c.company_name ? ` — ${c.company_name}` : ""}
                </option>
              ))}
            </select>
            {errors.client_id && <p className="field-error">{errors.client_id.message}</p>}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">TVA (%)</label>
              <input type="number" step="0.01" min="0" max="100" className="input" {...register("tax_rate")} />
            </div>
            <div>
              <label className="label">Valide jusqu'au</label>
              <input type="date" className="input" {...register("valid_until")} />
            </div>
          </div>

          <div>
            <label className="label">Notes</label>
            <textarea className="input min-h-[80px]" {...register("notes")} placeholder="Conditions, remarques…" />
          </div>
        </div>

        {/* Lines */}
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">Lignes du devis</h2>
            <button
              type="button"
              onClick={() => append({ description: "", quantity: 1, unit_price: 0 })}
              className="btn-secondary btn-sm"
            >
              <Plus className="w-3.5 h-3.5" />
              Ajouter une ligne
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="table-header">Description</th>
                  <th className="table-header w-20">Qté</th>
                  <th className="table-header w-32">Prix unitaire</th>
                  <th className="table-header w-32 text-right">Total</th>
                  <th className="table-header w-10" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {fields.map((field, idx) => {
                  const qty = Number(watchItems[idx]?.quantity) || 0;
                  const price = Number(watchItems[idx]?.unit_price) || 0;
                  const lineTotal = qty * price;
                  return (
                    <tr key={field.id}>
                      <td className="table-cell">
                        <input
                          className="input text-sm py-1"
                          placeholder="Description"
                          {...register(`items.${idx}.description`)}
                        />
                        {errors.items?.[idx]?.description && (
                          <p className="field-error">{errors.items[idx]?.description?.message}</p>
                        )}
                      </td>
                      <td className="table-cell">
                        <input
                          type="number"
                          min="1"
                          className="input text-sm py-1 w-full text-center"
                          {...register(`items.${idx}.quantity`)}
                        />
                      </td>
                      <td className="table-cell">
                        <input
                          type="number"
                          step="0.01"
                          min="0"
                          className="input text-sm py-1 w-full"
                          placeholder="0"
                          {...register(`items.${idx}.unit_price`)}
                        />
                      </td>
                      <td className="table-cell text-right font-semibold tabular-nums">
                        {formatMoney(lineTotal)}
                      </td>
                      <td className="table-cell">
                        <button
                          type="button"
                          onClick={() => remove(idx)}
                          disabled={fields.length === 1}
                          className="btn-icon p-1 text-red-400 hover:text-red-600 disabled:opacity-30"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Totaux */}
          <div className="px-5 py-4 border-t border-gray-100 bg-gray-50 flex justify-end">
            <div className="w-56 space-y-1 text-sm">
              <div className="flex justify-between text-gray-600">
                <span>Sous-total HT</span>
                <span className="tabular-nums">{formatMoney(subtotal)}</span>
              </div>
              <div className="flex justify-between text-gray-600">
                <span>TVA ({Number(taxRate)}%)</span>
                <span className="tabular-nums">{formatMoney(taxAmount)}</span>
              </div>
              <div className="flex justify-between font-bold text-gray-900 pt-1 border-t border-gray-200">
                <span>Total TTC</span>
                <span className="tabular-nums text-blue-700">{formatMoney(total)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex justify-end gap-3">
          <Link href={`/devis/${id}`} className="btn-secondary">
            Annuler
          </Link>
          <button type="submit" disabled={updateMut.isPending} className="btn-primary">
            {updateMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Enregistrer les modifications
          </button>
        </div>
      </form>
    </div>
  );
}
