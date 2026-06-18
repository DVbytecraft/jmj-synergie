export default function DashboardLoading() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Titre de page */}
      <div className="space-y-2">
        <div className="h-7 w-48 bg-slate-200 rounded-lg" />
        <div className="h-4 w-72 bg-slate-100 rounded-lg" />
      </div>

      {/* Barre d'actions / filtres */}
      <div className="flex items-center gap-3">
        <div className="h-9 w-48 bg-slate-100 rounded-lg" />
        <div className="h-9 w-28 bg-slate-100 rounded-lg" />
        <div className="ml-auto h-9 w-32 bg-slate-200 rounded-lg" />
      </div>

      {/* Tableau / liste */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-4 px-4 py-3 border-b border-slate-100 bg-slate-50">
          {[32, 48, 24, 20, 16].map((w, i) => (
            <div key={i} className={`h-3.5 bg-slate-200 rounded w-${w}`} style={{ width: `${w * 4}px` }} />
          ))}
        </div>
        {/* Rows */}
        {Array.from({ length: 7 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 px-4 py-3.5 border-b border-slate-50">
            <div className="h-4 bg-slate-100 rounded" style={{ width: `${120 + (i % 3) * 40}px` }} />
            <div className="h-4 bg-slate-100 rounded" style={{ width: `${80 + (i % 4) * 20}px` }} />
            <div className="h-4 bg-slate-100 rounded" style={{ width: `${60 + (i % 2) * 30}px` }} />
            <div className="h-5 w-16 bg-slate-100 rounded-full ml-auto" />
          </div>
        ))}
      </div>
    </div>
  );
}
