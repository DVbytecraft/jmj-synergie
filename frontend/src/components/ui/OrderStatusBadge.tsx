const STATUS_MAP: Record<string, { label: string; dot: string; bg: string; text: string }> = {
  // English statuses
  draft:       { label: "Brouillon",  dot: "bg-slate-400",   bg: "bg-slate-100",   text: "text-slate-700" },
  confirmed:   { label: "Confirmée",  dot: "bg-blue-500",    bg: "bg-blue-50",     text: "text-blue-700"  },
  in_progress: { label: "En cours",   dot: "bg-amber-400",   bg: "bg-amber-50",    text: "text-amber-700" },
  partially_delivered: { label: "Partiellement livrée", dot: "bg-orange-500", bg: "bg-orange-50", text: "text-orange-700" },
  delivered:   { label: "Livrée",     dot: "bg-emerald-500", bg: "bg-emerald-50",  text: "text-emerald-700" },
  cancelled:   { label: "Annulée",    dot: "bg-red-400",     bg: "bg-red-50",      text: "text-red-700"   },
  refunded:    { label: "Remboursée", dot: "bg-purple-400",  bg: "bg-purple-50",   text: "text-purple-700" },
  // French statuses (backend)
  brouillon:   { label: "Brouillon",  dot: "bg-slate-400",   bg: "bg-slate-100",   text: "text-slate-700" },
  confirmee:   { label: "Confirmée",  dot: "bg-blue-500",    bg: "bg-blue-50",     text: "text-blue-700"  },
  en_cours:    { label: "En cours",   dot: "bg-amber-400",   bg: "bg-amber-50",    text: "text-amber-700" },
  livree:      { label: "Livrée",     dot: "bg-emerald-500", bg: "bg-emerald-50",  text: "text-emerald-700" },
  annulee:     { label: "Annulée",    dot: "bg-red-400",     bg: "bg-red-50",      text: "text-red-700"   },
  remboursee:  { label: "Remboursée", dot: "bg-purple-400",  bg: "bg-purple-50",   text: "text-purple-700" },
};

export function OrderStatusBadge({ status }: { status: string }) {
  const cfg = STATUS_MAP[status] ?? {
    label: status,
    dot: "bg-slate-400",
    bg: "bg-slate-100",
    text: "text-slate-700",
  };
  return (
    <span className={`badge ${cfg.bg} ${cfg.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}
