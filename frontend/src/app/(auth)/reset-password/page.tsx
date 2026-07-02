"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

/**
 * Legacy reset-password links are redirected to the simplified reset page.
 */
export default function ResetPasswordPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/forgot-password");
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="flex flex-col items-center gap-3 text-slate-500">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
        <p className="text-sm">Redirection…</p>
      </div>
    </div>
  );
}
