"use client";

/**
 * OnboardingBanner — shown to new users who haven't configured their
 * issuer profile yet (no logo, no display_name, no company_name).
 *
 * Persists dismissal in localStorage so it won't reappear after the user
 * closes it, even if they haven't completed the setup.
 */
import { useState, useEffect } from "react";
import Link from "next/link";
import { X, Sparkles, Upload, Palette, Building2, PenLine } from "lucide-react";

const DISMISSED_KEY = "jmj_synergie_onboarding_dismissed";

interface OnboardingBannerProps {
  hasLogo:        boolean;
  hasDisplayName: boolean;
  hasCompanyName: boolean;
  hasSignature:   boolean;
}

export function OnboardingBanner({
  hasLogo,
  hasDisplayName,
  hasCompanyName,
  hasSignature,
}: OnboardingBannerProps) {
  const [dismissed, setDismissed] = useState(true); // default hidden until localStorage read

  useEffect(() => {
    // Only show if at least one step is incomplete and not already dismissed
    const wasDismissed = localStorage.getItem(DISMISSED_KEY) === "1";
    const isComplete = hasLogo && hasDisplayName && hasCompanyName && hasSignature;
    if (!wasDismissed && !isComplete) setDismissed(false);
  }, [hasLogo, hasDisplayName, hasCompanyName, hasSignature]);

  const handleDismiss = () => {
    localStorage.setItem(DISMISSED_KEY, "1");
    setDismissed(true);
  };

  if (dismissed) return null;

  const steps = [
    {
      icon: Building2,
      label: "Nom de votre société",
      done: hasCompanyName || hasDisplayName,
      href: "/settings",
    },
    {
      icon: Upload,
      label: "Logo de votre entreprise",
      done: hasLogo,
      href: "/settings#visuels",
    },
    {
      icon: PenLine,
      label: "Signature & cachet",
      done: hasSignature,
      href: "/settings#visuels",
    },
    {
      icon: Palette,
      label: "Couleurs de vos factures",
      done: false, // always suggest — users may want to customise
      href: "/settings#couleurs",
    },
  ];

  const done   = steps.filter((s) => s.done).length;
  const total  = steps.length;
  const pct    = Math.round((done / total) * 100);

  return (
    <div className="relative rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 to-indigo-50 p-5 mb-6">
      {/* Dismiss */}
      <button
        onClick={handleDismiss}
        className="absolute top-3 right-3 p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-white/60 transition-colors"
        aria-label="Fermer"
      >
        <X className="w-4 h-4" />
      </button>

      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center shrink-0 shadow">
          <Sparkles className="w-4 h-4 text-white" />
        </div>
        <div>
          <p className="font-semibold text-slate-900 text-sm">
            Personnalisez votre compte ({done}/{total})
          </p>
          <p className="text-xs text-slate-500 mt-0.5">
            Ces informations apparaissent sur toutes vos factures et documents.
          </p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 bg-blue-100 rounded-full mb-4 overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Steps */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {steps.map(({ icon: Icon, label, done: isDone, href }) => (
          <Link
            key={label}
            href={href}
            className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm transition-all ${
              isDone
                ? "bg-emerald-50 border border-emerald-100 text-emerald-700"
                : "bg-white border border-blue-100 text-slate-700 hover:border-blue-300 hover:shadow-sm"
            }`}
          >
            <Icon className={`w-4 h-4 shrink-0 ${isDone ? "text-emerald-500" : "text-blue-500"}`} />
            <span className="font-medium truncate">{label}</span>
            {isDone && (
              <span className="ml-auto shrink-0 text-xs font-semibold text-emerald-600">✓</span>
            )}
            {!isDone && (
              <span className="ml-auto shrink-0 text-xs text-blue-500">→</span>
            )}
          </Link>
        ))}
      </div>

      <p className="text-xs text-slate-400 mt-3 text-center">
        Accédez aux{" "}
        <Link href="/settings" className="text-blue-600 hover:underline font-medium">
          Paramètres
        </Link>{" "}
        à tout moment via le menu latéral.
      </p>
    </div>
  );
}
