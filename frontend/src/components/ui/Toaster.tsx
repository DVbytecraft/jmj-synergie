"use client";

/**
 * Minimal toast system backed by @radix-ui/react-toast.
 *
 * Usage from any component:
 *   import { toast } from "@/components/ui/Toaster";
 *   toast.success("Paiement enregistré");
 *   toast.error("Erreur réseau");
 *
 * Mount <Toaster /> once in Providers.tsx.
 */

import * as RadixToast from "@radix-ui/react-toast";
import { CheckCircle2, XCircle, Info, X } from "lucide-react";
import { useEffect, useState } from "react";

type ToastVariant = "success" | "error" | "info";

interface ToastItem {
  id: number;
  message: string;
  variant: ToastVariant;
}

// ── Simple pub/sub ────────────────────────────────────────────────────────────
let _nextId = 0;
type Listener = (item: ToastItem) => void;
const _listeners = new Set<Listener>();

function _emit(message: string, variant: ToastVariant) {
  const item: ToastItem = { id: ++_nextId, message, variant };
  _listeners.forEach((l) => l(item));
}

export const toast = {
  success: (msg: string) => _emit(msg, "success"),
  error: (msg: string) => _emit(msg, "error"),
  info: (msg: string) => _emit(msg, "info"),
};

// ── Toaster component (mount once) ───────────────────────────────────────────
const ICONS: Record<ToastVariant, React.ReactNode> = {
  success: <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />,
  error: <XCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />,
  info: <Info className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />,
};

const DURATION: Record<ToastVariant, number> = {
  success: 3500,
  error: 6000,
  info: 4500,
};

export function Toaster() {
  const [items, setItems] = useState<ToastItem[]>([]);

  useEffect(() => {
    const listener: Listener = (item) =>
      setItems((prev) => [...prev, item]);
    _listeners.add(listener);
    return () => { _listeners.delete(listener); };
  }, []);

  const dismiss = (id: number) =>
    setItems((prev) => prev.filter((i) => i.id !== id));

  return (
    <RadixToast.Provider swipeDirection="right">
      {items.map((item) => (
        <RadixToast.Root
          key={item.id}
          open
          duration={DURATION[item.variant]}
          onOpenChange={(open) => { if (!open) dismiss(item.id); }}
          className="
            flex items-start gap-2.5 rounded-xl border bg-white px-4 py-3 shadow-lg
            data-[state=open]:animate-in data-[state=open]:slide-in-from-bottom-4
            data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right-full
            data-[swipe=end]:animate-out data-[swipe=end]:translate-x-[var(--radix-toast-swipe-end-x)]
            max-w-[360px] w-full
          "
        >
          {ICONS[item.variant]}
          <RadixToast.Description className="flex-1 text-sm text-slate-700 leading-snug">
            {item.message}
          </RadixToast.Description>
          <RadixToast.Close
            onClick={() => dismiss(item.id)}
            className="text-slate-400 hover:text-slate-600 transition-colors flex-shrink-0"
            aria-label="Fermer"
          >
            <X className="w-3.5 h-3.5" />
          </RadixToast.Close>
        </RadixToast.Root>
      ))}
      <RadixToast.Viewport className="fixed bottom-4 left-4 right-4 z-[100] m-0 flex w-auto max-w-[360px] list-none flex-col gap-2 outline-none sm:left-auto sm:w-full" />
    </RadixToast.Provider>
  );
}
