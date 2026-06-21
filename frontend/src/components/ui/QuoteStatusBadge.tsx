import type { QuoteStatus } from "@/types";

const STATUS_MAP: Record<QuoteStatus, { label: string; dot: string; bg: string; text: string }> = {
  draft:     { label: "Brouillon",  dot: "bg-slate-400",   bg: "bg-slate-100",   text: "text-slate-700"  },
  sent:      { label: "Envoyé",     dot: "bg-blue-500",    bg: "bg-blue-50",     text: "text-blue-700"   },
  accepted:  { label: "Accepté",    dot: "bg-emerald-500", bg: "bg-emerald-50",  text: "text-emerald-700"},
  rejected:  { label: "Refusé",     dot: "bg-red-400",     bg: "bg-red-50",      text: "text-red-700"    },
  expired:   { label: "Expiré",     dot: "bg-orange-400",  bg: "bg-orange-50",   text: "text-orange-700" },
  converted: { label: "Converti",   dot: "bg-purple-500",  bg: "bg-purple-50",   text: "text-purple-700" },
};

export function QuoteStatusBadge({ status }: { status: string }) {
  const cfg = STATUS_MAP[status as QuoteStatus] ?? {
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
