"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { clientsApi } from "@/lib/api/clients";
import type { Client } from "@/types";
import { Plus, Search, Mail, Phone, MapPin, Trash2, Eye, Building2, Users } from "lucide-react";
import Link from "next/link";

/* ── Skeleton card ─────────────────────────────────── */
function SkeletonCard() {
  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-center gap-3">
        <div className="skeleton w-10 h-10 rounded-full" />
        <div className="space-y-1.5 flex-1">
          <div className="skeleton h-4 w-32 rounded" />
          <div className="skeleton h-3 w-20 rounded" />
        </div>
      </div>
      <div className="space-y-2">
        <div className="skeleton h-3 w-full rounded" />
        <div className="skeleton h-3 w-3/4 rounded" />
      </div>
      <div className="skeleton h-8 rounded-lg" />
    </div>
  );
}

/* ── Client card ───────────────────────────────────── */
function ClientCard({ client, onDelete }: { client: Client; onDelete: () => void }) {
  const isActive = client.status === "active";
  const initials = client.full_name
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className={`card flex flex-col ${!isActive ? "opacity-60" : ""}`}>
      {/* Header */}
      <div className="flex items-start justify-between p-5 pb-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-700 rounded-full flex items-center justify-center text-white font-semibold text-sm flex-shrink-0">
            {initials}
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-slate-900 truncate leading-tight">{client.full_name}</p>
            {client.company_name ? (
              <div className="flex items-center gap-1 mt-0.5">
                <Building2 className="w-3 h-3 text-slate-400 flex-shrink-0" />
                <p className="text-xs text-slate-500 truncate">{client.company_name}</p>
              </div>
            ) : (
              <p className="text-xs text-slate-400 mt-0.5">
                Client depuis {new Date(client.created_at).toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}
              </p>
            )}
          </div>
        </div>
        {!isActive && (
          <span className="badge bg-red-50 text-red-600 flex-shrink-0 ml-2">
            <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
            Inactif
          </span>
        )}
      </div>

      {/* Contact details */}
      <div className="px-5 pb-4 space-y-2 text-sm flex-1">
        {client.email && (
          <div className="flex items-center gap-2 text-slate-600">
            <Mail className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            <span className="truncate">{client.email}</span>
          </div>
        )}
        <div className="flex items-center gap-2 text-slate-600">
          <Phone className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
          <span>{client.phone}</span>
        </div>
        {client.address_line1 && (
          <div className="flex items-center gap-2 text-slate-600">
            <MapPin className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            <span className="truncate">
              {client.address_line1}
              {client.city ? `, ${client.city}` : ""}
            </span>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-2 px-5 py-3.5 border-t border-slate-100">
        <Link
          href={`/clients/${client.id}`}
          className="btn btn-secondary flex-1 btn-sm"
        >
          <Eye className="w-3.5 h-3.5" />
          Voir le profil
        </Link>
        <button
          onClick={onDelete}
          className="btn btn-sm border border-slate-200 text-slate-400 hover:text-red-600 hover:bg-red-50 hover:border-red-200 transition-colors rounded-lg p-2"
          title="Supprimer"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

/* ── Page ──────────────────────────────────────────── */
export default function ClientsPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const limit = 21;
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["clients", page],
    queryFn: () => clientsApi.list({ skip: page * limit, limit }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => clientsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["clients"] }),
  });

  const filtered = data?.items.filter(
    (c) =>
      c.full_name.toLowerCase().includes(search.toLowerCase()) ||
      (c.email ?? "").toLowerCase().includes(search.toLowerCase())
  ) ?? [];

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Clients</h1>
          <p className="page-subtitle">{data?.total ?? 0} clients enregistrés</p>
        </div>
        <Link href="/clients/new" className="btn-primary flex-shrink-0">
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">Nouveau client</span>
          <span className="sm:hidden">Nouveau</span>
        </Link>
      </div>

      {/* Search bar */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        <input
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(0); }}
          placeholder="Rechercher par nom ou email…"
          className="input pl-10"
        />
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <Users className="empty-state-icon" />
            <p className="empty-state-title">Aucun client trouvé</p>
            <p className="empty-state-desc">
              {search ? "Aucun résultat pour cette recherche" : "Commencez par créer votre premier client"}
            </p>
            {!search && (
              <Link href="/clients/new" className="btn-primary btn-sm">
                <Plus className="w-3.5 h-3.5" />
                Créer un client
              </Link>
            )}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((client) => (
            <ClientCard
              key={client.id}
              client={client}
              onDelete={() => deleteMut.mutate(client.id)}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {(data?.total ?? 0) > limit && (
        <div className="flex items-center justify-between pt-2">
          <p className="text-sm text-slate-500">
            {page * limit + 1}–{Math.min((page + 1) * limit, data?.total ?? 0)} sur {data?.total}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="pagination-btn"
            >
              Précédent
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={(page + 1) * limit >= (data?.total ?? 0)}
              className="pagination-btn"
            >
              Suivant
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
