const STATUS_MAP: Record<string, { label: string; dot: string; bg: string; text: string }> = {
  pending:   { label: "En attente", dot: "bg-orange-400", bg: "bg-orange-50",  text: "text-orange-700" },
  completed: { label: "Payé",       dot: "bg-emerald-500",bg: "bg-emerald-50", text: "text-emerald-700" },
  failed:    { label: "Échoué",     dot: "bg-red-400",    bg: "bg-red-50",     text: "text-red-700"    },
  refunded:  { label: "Remboursé",  dot: "bg-purple-400", bg: "bg-purple-50",  text: "text-purple-700" },
};

export function PaymentStatusBadge({ status }: { status: string }) {
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
